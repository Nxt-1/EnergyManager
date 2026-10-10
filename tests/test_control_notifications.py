from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from energymanager.config import NotificationSettings
from energymanager.control_health import ControlHealth
from energymanager.control_notifications import NOTIFICATION_STATUS_ENTITY, ControlNotificationManager

_NOW = datetime(2026, 10, 10, 15, 30, tzinfo=UTC)


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []
        self.states: dict[str, dict[str, object]] = {}

    async def call_service(self, domain: str, service: str, data: dict[str, object]) -> None:
        self.calls.append((domain, service, data))

    async def set_state(self, entity_id: str, state: str, attributes: dict[str, object]) -> None:
        self.states[entity_id] = {"state": state, "attributes": attributes}


def _health(state: str, *, ev_available: bool = True, reasons: tuple[str, ...] = ()) -> ControlHealth:
    return ControlHealth(
        state=state,
        ess_available=True,
        ev_available=ev_available,
        stale_inputs=(),
        unavailable_inputs=(),
        reasons=reasons,
        replan_required=state != "healthy",
    )


def test_notification_manager_sends_failure_once_and_recovery_once() -> None:
    client = FakeClient()
    manager = ControlNotificationManager(
        client,
        NotificationSettings(enabled=True, service="notify.mobile_app_phone", cooldown_seconds=300),
    )

    async def scenario() -> None:
        manager.observe(_health("healthy"), now_utc=_NOW)
        manager.complete_startup(now_utc=_NOW)
        manager.observe(
            _health("degraded", ev_available=False, reasons=("ev:write_fault",)),
            now_utc=_NOW + timedelta(seconds=1),
        )
        manager.observe(
            _health("degraded", ev_available=False, reasons=("ev:write_fault",)),
            now_utc=_NOW + timedelta(seconds=2),
        )
        manager.observe(_health("healthy"), now_utc=_NOW + timedelta(seconds=3))
        await manager.shutdown()

    asyncio.run(scenario())

    assert len(client.calls) == 2
    assert client.calls[0][0:2] == ("notify", "mobile_app_phone")
    assert "EV control is unavailable" in str(client.calls[0][2]["message"])
    assert "returned to healthy" in str(client.calls[1][2]["message"])
    status = client.states[NOTIFICATION_STATUS_ENTITY]
    assert status["state"] == "sent"
    assert status["attributes"]["sent_count"] == 2


def test_notification_manager_suppresses_repeated_failure_inside_cooldown() -> None:
    client = FakeClient()
    manager = ControlNotificationManager(
        client,
        NotificationSettings(enabled=True, service="notify.mobile_app_phone", cooldown_seconds=300),
    )

    async def scenario() -> None:
        manager.observe(_health("healthy"), now_utc=_NOW)
        manager.complete_startup(now_utc=_NOW)
        fault = _health("degraded", ev_available=False, reasons=("ev:write_fault",))
        manager.observe(fault, now_utc=_NOW + timedelta(seconds=1))
        manager.observe(_health("healthy"), now_utc=_NOW + timedelta(seconds=2))
        manager.observe(fault, now_utc=_NOW + timedelta(seconds=3))
        await manager.shutdown()

    asyncio.run(scenario())

    assert len(client.calls) == 2
    status = client.states[NOTIFICATION_STATUS_ENTITY]
    assert status["attributes"]["suppressed_count"] == 1


def test_normal_ev_disconnect_does_not_notify_phone() -> None:
    client = FakeClient()
    manager = ControlNotificationManager(
        client,
        NotificationSettings(enabled=True, service="notify.mobile_app_phone", cooldown_seconds=300),
    )

    async def scenario() -> None:
        manager.observe(_health("healthy"), now_utc=_NOW)
        manager.complete_startup(now_utc=_NOW)
        manager.observe(
            _health("degraded", ev_available=False, reasons=("ev:disconnected",)),
            now_utc=_NOW + timedelta(seconds=1),
        )
        manager.observe(_health("healthy"), now_utc=_NOW + timedelta(seconds=2))
        await manager.shutdown()

    asyncio.run(scenario())

    assert client.calls == []


def test_startup_transient_fault_is_not_sent_or_recovered() -> None:
    client = FakeClient()
    manager = ControlNotificationManager(
        client, NotificationSettings(enabled=True, service="notify.mobile_app_phone", cooldown_seconds=300)
    )

    async def scenario() -> None:
        manager.observe(_health("safe_fallback", reasons=("stale_inputs",)), now_utc=_NOW)
        manager.observe(_health("healthy"), now_utc=_NOW + timedelta(seconds=1))
        manager.complete_startup(now_utc=_NOW + timedelta(seconds=2))
        await manager.shutdown()

    asyncio.run(scenario())
    assert client.calls == []
    attrs = client.states[NOTIFICATION_STATUS_ENTITY]["attributes"]
    assert attrs["startup_complete"] is True
    assert attrs["startup_suppressed_count"] == 1


def test_persistent_startup_fault_is_reported_on_completion() -> None:
    client = FakeClient()
    manager = ControlNotificationManager(
        client, NotificationSettings(enabled=True, service="notify.mobile_app_phone", cooldown_seconds=300)
    )

    async def scenario() -> None:
        manager.observe(_health("safe_fallback", reasons=("stale_inputs",)), now_utc=_NOW)
        manager.complete_startup(now_utc=_NOW + timedelta(seconds=1))
        manager.observe(_health("healthy"), now_utc=_NOW + timedelta(seconds=2))
        await manager.shutdown()

    asyncio.run(scenario())
    assert len(client.calls) == 2
    assert "safe fallback" in str(client.calls[0][2]["title"])
    assert "recovered" in str(client.calls[1][2]["title"])
