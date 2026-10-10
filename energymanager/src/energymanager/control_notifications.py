"""Non-blocking notifications for live-control health transitions."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import NotificationSettings
from .control_health import ControlHealth

_LOGGER = logging.getLogger(__name__)
NOTIFICATION_STATUS_ENTITY = "sensor.energy_manager_notification_status"
NOTIFICATION_STATUS_VERSION = "2026-10-10-control-notifications-v1"


@dataclass(frozen=True, slots=True)
class _NotificationEvent:
    kind: str
    health_state: str
    title: str
    message: str
    send: bool
    created_at_utc: datetime


class ControlNotificationManager:
    """Turn material control-health transitions into asynchronous HA notifications."""

    def __init__(self, client, settings: NotificationSettings) -> None:
        self._client = client
        self._settings = settings
        self._last_health: ControlHealth | None = None
        self._active_alert = False
        self._last_queued_at: dict[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]], datetime] = {}
        self._queue: asyncio.Queue[_NotificationEvent | None] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._sent_count = 0
        self._suppressed_count = 0
        self._last_event: str | None = None
        self._last_notification_utc: datetime | None = None
        self._last_error: str | None = None

    @property
    def enabled(self) -> bool:
        return self._settings.enabled and self._settings.service is not None

    def observe(self, health: ControlHealth, *, now_utc: datetime | None = None) -> None:
        """Queue notifications for alert-worthy failures and their recovery."""
        now = (now_utc or datetime.now(UTC)).astimezone(UTC)
        previous = self._last_health
        self._last_health = health
        alertworthy = _is_alertworthy_failure(health)

        if previous is None:
            if alertworthy:
                self._active_alert = self._queue_failure(health, now)
            else:
                self._enqueue(_NotificationEvent("armed", health.state, "", "", False, now))
            return

        previous_alertworthy = _is_alertworthy_failure(previous)
        same_signature = (
            previous.state == health.state
            and previous.reasons == health.reasons
            and previous.stale_inputs == health.stale_inputs
            and previous.unavailable_inputs == health.unavailable_inputs
        )
        if same_signature:
            return

        if alertworthy:
            if not previous_alertworthy or health.state == "safe_fallback" and previous.state != "safe_fallback":
                self._active_alert = self._queue_failure(health, now)
            return

        if self._active_alert:
            title, message = _recovery_message(health)
            self._enqueue(_NotificationEvent("recovered", health.state, title, message, True, now))
            self._active_alert = False
            return

        self._enqueue(_NotificationEvent("health_changed", health.state, "", "", False, now))

    async def shutdown(self) -> None:
        """Drain queued notification work during a clean shutdown."""
        if self._worker_task is None:
            return
        await self._queue.put(None)
        await self._worker_task
        self._worker_task = None

    def _queue_failure(self, health: ControlHealth, now: datetime) -> bool:
        kind = health.state
        key = (kind, health.reasons, health.stale_inputs, health.unavailable_inputs)
        cooldown = timedelta(seconds=self._settings.cooldown_seconds)
        last = self._last_queued_at.get(key)
        if last is not None and now - last < cooldown:
            self._suppressed_count += 1
            self._enqueue(_NotificationEvent("suppressed", health.state, "", "", False, now))
            return False
        self._last_queued_at[key] = now
        title, message = _failure_message(health)
        self._enqueue(_NotificationEvent(kind, health.state, title, message, True, now))
        return True

    def _enqueue(self, event: _NotificationEvent) -> None:
        self._queue.put_nowait(event)
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        while True:
            event = await self._queue.get()
            try:
                if event is None:
                    return
                await self._handle_event(event)
            finally:
                self._queue.task_done()

    async def _handle_event(self, event: _NotificationEvent) -> None:
        self._last_event = event.kind
        if not self.enabled or not event.send:
            await self._publish_status("disabled" if not self.enabled else "armed", event.health_state)
            return

        assert self._settings.service is not None
        domain, service = self._settings.service.split(".", maxsplit=1)
        try:
            await self._client.call_service(
                domain,
                service,
                {"title": event.title, "message": event.message},
            )
        except Exception as exc:  # noqa: BLE001 - notification failure must never interrupt hardware control.
            self._last_error = str(exc)
            _LOGGER.warning("Control notification failed via %s: %s", self._settings.service, exc)
            await self._publish_status("error", event.health_state)
            return

        self._sent_count += 1
        self._last_notification_utc = datetime.now(UTC)
        self._last_error = None
        _LOGGER.info("Control notification sent: event=%s, health=%s", event.kind, event.health_state)
        await self._publish_status("sent", event.health_state)

    async def _publish_status(self, state: str, health_state: str) -> None:
        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager Notification Status",
            "notification_status_version": NOTIFICATION_STATUS_VERSION,
            "enabled": self.enabled,
            "service": self._settings.service,
            "cooldown_seconds": self._settings.cooldown_seconds,
            "last_health_state": health_state,
            "last_event": self._last_event,
            "sent_count": self._sent_count,
            "suppressed_count": self._suppressed_count,
            "last_notification_utc": (
                self._last_notification_utc.isoformat() if self._last_notification_utc is not None else None
            ),
            "last_error": self._last_error,
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        try:
            await self._client.set_state(NOTIFICATION_STATUS_ENTITY, state, attributes)
        except Exception as exc:  # noqa: BLE001 - diagnostics must not affect hardware control.
            _LOGGER.debug("Unable to publish notification diagnostics: %s", exc)


def _is_alertworthy_failure(health: ControlHealth) -> bool:
    if health.state == "healthy":
        return False
    if health.stale_inputs or health.unavailable_inputs:
        return True
    meaningful = tuple(reason for reason in health.reasons if reason != "ev:disconnected")
    return bool(meaningful) or health.state == "safe_fallback"


def _recovery_message(health: ControlHealth) -> tuple[str, str]:
    if health.state == "healthy":
        return "Energy Manager recovered", "Energy Manager live control returned to healthy operation."
    if health.reasons == ("ev:disconnected",):
        return (
            "Energy Manager failure cleared",
            "The control failure cleared. The EV remains disconnected; ESS control remains active.",
        )
    return "Energy Manager failure cleared", "The previously reported live-control failure cleared."


def _failure_message(health: ControlHealth) -> tuple[str, str]:
    reason = _reason_text(health)
    if health.state == "safe_fallback":
        return (
            "Energy Manager safe fallback",
            f"ESS control entered safe fallback. Reason: {reason}. ESS setpoint is forced to 0 W.",
        )

    if health.ess_available and not health.ev_available:
        return (
            "Energy Manager degraded",
            f"EV control is unavailable. Reason: {reason}. ESS control remains active.",
        )
    return "Energy Manager degraded", f"Energy Manager live control is degraded. Reason: {reason}."


def _reason_text(health: ControlHealth) -> str:
    details: list[str] = []
    for reason in health.reasons:
        if reason == "stale_inputs" or reason == "unavailable_inputs":
            continue
        if reason == "ev:disconnected":
            details.append("EV disconnected")
        elif reason.startswith("ev:"):
            details.append(f"EV {reason.removeprefix('ev:').replace('_', ' ')}")
        elif reason.startswith("ess:"):
            details.append(f"ESS {reason.removeprefix('ess:').replace('_', ' ')}")
        else:
            details.append(reason.replace("_", " "))
    if health.stale_inputs:
        details.append(f"stale inputs: {', '.join(health.stale_inputs)}")
    if health.unavailable_inputs:
        details.append(f"unavailable inputs: {', '.join(health.unavailable_inputs)}")
    return "; ".join(details) if details else "control health changed"
