from __future__ import annotations

import asyncio
from types import SimpleNamespace

from energymanager.config import EvSettings
from energymanager.ev_control import EV_CONTROL_STATUS_ENTITY, EvHardwareController

_CURRENT_ENTITY = "number.goe_322561_amp"
_PHASE_ENTITY = "select.goe_322561_psm"
_FORCE_ENTITY = "select.goe_322561_frc"


class FakeClient:
    def __init__(self, *, current: str = "6", phase: str = "1", force: str = "1") -> None:
        self.entity_states = {
            _CURRENT_ENTITY: current,
            _PHASE_ENTITY: phase,
            _FORCE_ENTITY: force,
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
        assert client.entity_states[_PHASE_ENTITY] == "2"
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
