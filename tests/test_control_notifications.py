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


def test_notification_manager_sends_failure_without_recovery_event() -> None:
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
            now_utc=_NOW + timedelta(seconds=17),
        )
        manager.observe(_health("healthy"), now_utc=_NOW + timedelta(seconds=18))
        await manager.shutdown()

    asyncio.run(scenario())

    assert len(client.calls) == 1
    assert client.calls[0][0:2] == ("notify", "mobile_app_phone")
    assert "EV control is unavailable" in str(client.calls[0][2]["message"])
    status = client.states[NOTIFICATION_STATUS_ENTITY]
    assert status["attributes"]["sent_count"] == 1
    assert not any(event["event"] == "recovered" for event in status["attributes"]["recent_events"])


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
        manager.observe(fault, now_utc=_NOW + timedelta(seconds=17))
        manager.observe(_health("healthy"), now_utc=_NOW + timedelta(seconds=18))
        manager.observe(fault, now_utc=_NOW + timedelta(seconds=19))
        manager.observe(fault, now_utc=_NOW + timedelta(seconds=35))
        await manager.shutdown()

    asyncio.run(scenario())

    assert len(client.calls) == 1
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
    assert len(client.calls) == 1
    assert "safe fallback" in str(client.calls[0][2]["title"])
    events = client.states[NOTIFICATION_STATUS_ENTITY]["attributes"]["recent_events"]
    assert not any(event["event"] == "recovered" for event in events)


def test_cooldown_suppression_is_once_per_episode_and_ess_escalation_is_reported() -> None:
    client = FakeClient()
    manager = ControlNotificationManager(
        client, NotificationSettings(enabled=True, service="notify.mobile_app_phone", cooldown_seconds=300)
    )
    ev_fault = _health("degraded", ev_available=False, reasons=("ev:write_fault",))
    ess_fault = ControlHealth(
        state="safe_fallback", ess_available=False, ev_available=False,
        stale_inputs=("ess.soc",), unavailable_inputs=(), reasons=("stale_inputs",), replan_required=True,
    )

    async def scenario() -> None:
        manager.observe(_health("healthy"), now_utc=_NOW)
        manager.complete_startup(now_utc=_NOW)
        manager.observe(ev_fault, now_utc=_NOW + timedelta(seconds=1))
        manager.observe(ev_fault, now_utc=_NOW + timedelta(seconds=17))
        manager.observe(_health("healthy"), now_utc=_NOW + timedelta(seconds=18))
        manager.observe(ev_fault, now_utc=_NOW + timedelta(seconds=20))
        for seconds in range(36, 95):
            manager.observe(ev_fault, now_utc=_NOW + timedelta(seconds=seconds))
        manager.observe(ess_fault, now_utc=_NOW + timedelta(seconds=100))
        manager.observe(ess_fault, now_utc=_NOW + timedelta(seconds=116))
        await manager.shutdown()

    asyncio.run(scenario())
    assert len(client.calls) == 2  # Original EV fault and genuinely new ESS fault.
    events = client.states[NOTIFICATION_STATUS_ENTITY]["attributes"]["recent_events"]
    assert len([event for event in events if event["event"] == "suppressed"]) == 1
    assert manager._suppressed_count == 1
