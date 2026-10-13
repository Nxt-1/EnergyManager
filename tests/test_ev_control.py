from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from energymanager.config import EvSettings
from energymanager.ev_control import EV_CONTROL_STATUS_ENTITY, EvHardwareController

_CURRENT_ENTITY = "number.goe_322561_amp"
_PHASE_ENTITY = "select.goe_322561_psm"
_FORCE_ENTITY = "select.goe_322561_frc"
_POWER_ENTITY = "sensor.goe_322561_nrg_11"


class FakeClient:
    def __init__(self, *, current: str = "6", phase: str = "1", force: str = "1") -> None:
        self.entity_states = {
            _CURRENT_ENTITY: current,
            _PHASE_ENTITY: phase,
            _FORCE_ENTITY: force,
            _POWER_ENTITY: "0",
        }
        self.published: dict[str, dict[str, object]] = {}
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def get_state(self, entity_id: str) -> dict[str, object]:
        return {"state": self.entity_states[entity_id]}

    async def call_service(self, domain: str, service: str, data: dict[str, object]) -> None:
        self.calls.append((domain, service, data))
        entity_id = str(data["entity_id"])
        if domain == "number":
            assert service == "set_value"
            self.entity_states[entity_id] = str(data["value"])
            return
        assert domain == "select"
        assert service == "select_option"
        self.entity_states[entity_id] = str(data["option"])

    async def set_state(self, entity_id: str, state: str, attributes: dict[str, object]) -> None:
        self.published[entity_id] = {"state": state, "attributes": attributes}


def _settings(*, enabled: bool = True) -> EvSettings:
    return EvSettings(
        current_entity=_CURRENT_ENTITY,
        phase_mode_entity=_PHASE_ENTITY,
        force_state_entity=_FORCE_ENTITY,
        charging_power_entity=_POWER_ENTITY,
        control_enabled=enabled,
        min_charge_current_a=6,
        max_charge_current_a=16,
    )


def _dispatch(*, power_w: float, phases: int, current_a: float, reason: str | None = None):
    command = SimpleNamespace(
        actuator_id="ev",
        requested_power_w=power_w,
        accepted_power_w=power_w,
        phase_count=phases,
        current_a=current_a,
        reason=reason,
    )
    return SimpleNamespace(command_results=(command,))


def test_ev_controller_applies_current_and_charge_force() -> None:
    client = FakeClient(current="6", phase="1", force="1")
    controller = EvHardwareController(client, _settings(), phase_switch_delay_seconds=0)

    asyncio.run(controller.apply_dispatch(_dispatch(power_w=2760, phases=1, current_a=12)))

    assert client.entity_states[_CURRENT_ENTITY] == "12"
    assert client.entity_states[_FORCE_ENTITY] == "2"
    status = client.published[EV_CONTROL_STATUS_ENTITY]
    assert status["state"] == "write_sent"
    assert status["attributes"]["hardware_writes"] is True


def test_ev_controller_stops_before_phase_switch_then_resumes() -> None:
    client = FakeClient(current="12", phase="1", force="2")
    controller = EvHardwareController(client, _settings(), phase_switch_delay_seconds=0)
    dispatch = _dispatch(power_w=4140, phases=3, current_a=6)

    async def scenario() -> None:
        await controller.apply_dispatch(dispatch)
        assert client.entity_states[_FORCE_ENTITY] == "1"
        assert client.entity_states[_PHASE_ENTITY] == "1"  # Physical switch must wait for zero power.
        controller._phase_switch_stopped_at_utc = datetime.now(UTC) - timedelta(seconds=4)
        await controller.apply_dispatch(dispatch)
        assert client.entity_states[_PHASE_ENTITY] == "2"
        assert client.entity_states[_FORCE_ENTITY] == "1"
        await controller.apply_dispatch(dispatch)

    asyncio.run(scenario())

    assert client.entity_states[_CURRENT_ENTITY] == "6"
    assert client.entity_states[_FORCE_ENTITY] == "2"
    force_off_index = next(
        index
        for index, call in enumerate(client.calls)
        if call[0] == "select" and call[2].get("entity_id") == _FORCE_ENTITY and call[2].get("option") == "1"
    )
    phase_index = next(
        index
        for index, call in enumerate(client.calls)
        if call[0] == "select" and call[2].get("entity_id") == _PHASE_ENTITY and call[2].get("option") == "2"
    )
    assert force_off_index < phase_index


def test_ev_controller_zero_command_forces_dont_charge() -> None:
    client = FakeClient(current="10", phase="1", force="2")
    controller = EvHardwareController(client, _settings())

    asyncio.run(controller.apply_dispatch(_dispatch(power_w=0, phases=0, current_a=0)))

    assert client.entity_states[_FORCE_ENTITY] == "1"
    assert client.published[EV_CONTROL_STATUS_ENTITY]["state"] == "stopped"


def test_ev_controller_disabled_never_writes_hardware() -> None:
    client = FakeClient(current="10", phase="1", force="2")
    controller = EvHardwareController(client, _settings(enabled=False))

    asyncio.run(controller.apply_dispatch(_dispatch(power_w=2300, phases=1, current_a=10)))

    assert client.calls == []
    assert client.published[EV_CONTROL_STATUS_ENTITY]["state"] == "disabled"


class StubbornCurrentClient(FakeClient):
    async def call_service(self, domain: str, service: str, data: dict[str, object]) -> None:
        self.calls.append((domain, service, data))
        entity_id = str(data["entity_id"])
        if domain == "number":
            assert service == "set_value"
            return
        assert domain == "select"
        assert service == "select_option"
        self.entity_states[entity_id] = str(data["option"])


def test_ev_controller_limits_unacknowledged_retries() -> None:
    client = StubbornCurrentClient(current="6", phase="1", force="1")
    controller = EvHardwareController(client, _settings(), phase_switch_delay_seconds=0)
    dispatch = _dispatch(power_w=2760, phases=1, current_a=12)

    async def scenario() -> None:
        for _ in range(6):
            await controller.apply_dispatch(dispatch)

    asyncio.run(scenario())

    assert controller.fault_active is True
    assert client.entity_states[_FORCE_ENTITY] == "1"
    status = client.published[EV_CONTROL_STATUS_ENTITY]
    assert status["attributes"]["fault_active"] is True


def test_connected_ev_not_charging_diagnostic_requires_sustained_zero_power() -> None:
    from datetime import UTC, datetime, timedelta

    class State:
        def __init__(self, connected: bool, power: float):
            self.connected = connected
            self.power = power

        def value(self, key: str):
            return self.connected if key == "ev.connected" else self.power

    controller = EvHardwareController(FakeClient(), _settings())
    start = datetime(2026, 10, 10, 20, tzinfo=UTC)
    controller._requested_charge_power_w = 1380.0
    controller._charge_enable_requested = True
    controller.observe_charging(State(True, 0.0), now_utc=start)
    controller.observe_charging(State(True, 0.0), now_utc=start + timedelta(seconds=89))
    assert controller.delivery_error is None
    controller.observe_charging(State(True, 0.0), now_utc=start + timedelta(seconds=91))
    assert controller.delivery_error == "charging_fault_latched"
    controller.observe_charging(State(True, 1380.0), now_utc=start + timedelta(seconds=92))
    assert controller.delivery_error == "charging_fault_latched"
    controller.observe_charging(State(False, 0.0), now_utc=start + timedelta(seconds=100))
    assert controller.delivery_error == "charging_fault_latched"


def test_phase_switch_waits_for_zero_power_and_does_not_reverse_within_ten_minutes() -> None:
    client = FakeClient(current="9", phase="1", force="2")
    client.entity_states[_POWER_ENTITY] = "1600"
    controller = EvHardwareController(client, _settings(), phase_switch_delay_seconds=0)
    to_three = _dispatch(power_w=6210, phases=3, current_a=9)

    async def scenario() -> None:
        await controller.apply_dispatch(to_three)
        assert client.entity_states[_FORCE_ENTITY] == "1"
        assert client.entity_states[_PHASE_ENTITY] == "1"
        controller._phase_switch_stopped_at_utc = datetime.now(UTC) - timedelta(seconds=4)
        await controller.apply_dispatch(to_three)
        assert client.entity_states[_PHASE_ENTITY] == "1"  # Still measuring power.
        client.entity_states[_POWER_ENTITY] = "0"
        await controller.apply_dispatch(to_three)
        assert client.entity_states[_PHASE_ENTITY] == "2"
        await controller.apply_dispatch(to_three)
        assert client.entity_states[_FORCE_ENTITY] == "2"

        # Changing the plan back to single-phase cannot reverse the physical switch.
        to_one = _dispatch(power_w=1610, phases=1, current_a=7)
        await controller.apply_dispatch(to_one)
        assert client.entity_states[_PHASE_ENTITY] == "2"
        assert client.entity_states[_FORCE_ENTITY] == "1"  # 3-phase minimum would exceed 1610 W.
        status = client.published[EV_CONTROL_STATUS_ENTITY]
        assert status["attributes"]["phase_min_interval_seconds"] == 600
        assert status["attributes"]["last_phase_switch_utc"] is not None

    asyncio.run(scenario())


def test_phase_switch_retains_existing_phase_at_safe_current_during_dwell() -> None:
    client = FakeClient(current="6", phase="1", force="1")
    controller = EvHardwareController(client, _settings(), phase_switch_delay_seconds=0)
    controller._last_phase_switch_utc = datetime.now(UTC)

    asyncio.run(controller.apply_dispatch(_dispatch(power_w=6210, phases=3, current_a=9)))

    assert client.entity_states[_PHASE_ENTITY] == "1"
    assert client.entity_states[_CURRENT_ENTITY] == "16"
    assert client.entity_states[_FORCE_ENTITY] == "2"
    assert all(call[2].get("entity_id") != _PHASE_ENTITY for call in client.calls)


def test_phase_switch_stays_stopped_when_power_measurement_unavailable() -> None:
    client = FakeClient(current="12", phase="1", force="2")
    client.entity_states[_POWER_ENTITY] = "unavailable"
    controller = EvHardwareController(client, _settings(), phase_switch_delay_seconds=0)

    async def scenario() -> None:
        command = _dispatch(power_w=4140, phases=3, current_a=6)
        await controller.apply_dispatch(command)
        controller._phase_switch_stopped_at_utc = datetime.now(UTC) - timedelta(seconds=4)
        await controller.apply_dispatch(command)

    asyncio.run(scenario())
    assert client.entity_states[_PHASE_ENTITY] == "1"
    assert client.entity_states[_FORCE_ENTITY] == "1"
    assert client.published[EV_CONTROL_STATUS_ENTITY]["attributes"]["reason"] == "await_zero_charging_power"


def test_phase_replan_cannot_reverse_transition_already_started() -> None:
    client = FakeClient(current="10", phase="1", force="2")
    controller = EvHardwareController(client, _settings(), phase_switch_delay_seconds=0)

    async def scenario() -> None:
        to_three = _dispatch(power_w=6210, phases=3, current_a=9)
        await controller.apply_dispatch(to_three)
        controller._phase_switch_stopped_at_utc = datetime.now(UTC) - timedelta(seconds=4)
        await controller.apply_dispatch(to_three)
        assert client.entity_states[_PHASE_ENTITY] == "2"
        # A new contradictory plan arrives while the transition is still pending.
        await controller.apply_dispatch(_dispatch(power_w=1610, phases=1, current_a=7))
        assert client.entity_states[_PHASE_ENTITY] == "2"
        assert client.entity_states[_FORCE_ENTITY] == "1"
        assert controller._phase_switch_count == 1

    asyncio.run(scenario())
