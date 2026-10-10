from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from energymanager.actuators import ActuatorRegistry
from energymanager.config import ConfigurationError, EssSettings, EvSettings, Settings
from energymanager.ess_control import ESS_CONTROL_STATUS_ENTITY, EssHardwareController
from energymanager.fast_dispatch import evaluate_fast_dispatch
from energymanager.house_state import HouseState
from energymanager.planner import ShadowPlan, ShadowPlanInterval

_NOW = datetime(2026, 10, 10, 15, 30, tzinfo=UTC)
_SETPOINT_ENTITY = "number.garage_gx_device_ac_power_setpoint"


class FakeClient:
    def __init__(self, setpoint_w: float = 0.0) -> None:
        self.setpoint_w = setpoint_w
        self.states: dict[str, dict[str, object]] = {}
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def get_state(self, entity_id: str) -> dict[str, object]:
        assert entity_id == _SETPOINT_ENTITY
        return {"state": str(self.setpoint_w)}

    async def call_service(self, domain: str, service: str, data: dict[str, object]) -> None:
        self.calls.append((domain, service, data))
        assert domain == "number"
        assert service == "set_value"
        self.setpoint_w = float(data["value"])

    async def set_state(self, entity_id: str, state: str, attributes: dict[str, object]) -> None:
        self.states[entity_id] = {"state": state, "attributes": attributes}


def _settings(*, control_enabled: bool = True) -> Settings:
    return Settings(
        ess=EssSettings(
            soc_entity="sensor.ess_soc",
            power_entity="sensor.ess_power",
            setpoint_entity=_SETPOINT_ENTITY,
            control_enabled=control_enabled,
            max_charge_power_w=2000.0,
            max_discharge_power_w=2000.0,
        ),
        ev=EvSettings(
            soc_entity="sensor.ev_soc",
            connected_entity="sensor.ev_connected",
            charging_power_entity="sensor.ev_power",
            battery_capacity_kwh=52.0,
        ),
    )


def _state(*, grid_w: float, ess_w: float, ev_w: float = 0.0) -> HouseState:
    state = HouseState()
    values = {
        "grid.import_power": max(0.0, grid_w),
        "grid.export_power": max(0.0, -grid_w),
        "ess.soc": 60.0,
        "ess.power": ess_w,
        "pv.solax_power": 0.0,
        "ev.connected": True,
        "ev.soc": 40.0,
        "ev.charging_power": ev_w,
    }
    for key, value in values.items():
        reading = state.ensure_input(key, f"sensor.{key.replace('.', '_')}")
        reading.set_valid(value, unit=None, observed_at_utc=_NOW, source_last_updated=None)
    return state


def _plan() -> ShadowPlan:
    interval = ShadowPlanInterval(
        period_start_local=_NOW,
        background_load_w=1000.0,
        scheduled_load_w=3000.0,
        pv_ac_power_w=0.0,
        pv_dc_power_w=0.0,
        pv_power_w=0.0,
        net_power_before_control_w=4000.0,
        ess_ac_power_w=500.0,
        projected_soc_percent=55.0,
        grid_power_after_ess_w=0.0,
        curtailed_dc_pv_w=0.0,
    )
    return ShadowPlan(generated_at_utc=_NOW, intervals=(interval,), ess_projection_status="projected")


def test_ess_controller_converts_discharge_to_negative_victron_setpoint() -> None:
    client = FakeClient()
    settings = _settings()
    result = evaluate_fast_dispatch(
        _plan(),
        _state(grid_w=500.0, ess_w=500.0),
        ActuatorRegistry(settings),
        now_utc=_NOW,
        live_control=True,
    )
    controller = EssHardwareController(client, settings.ess)

    async def scenario() -> None:
        await controller.apply_dispatch(result)
        await controller.apply_dispatch(result)

    asyncio.run(scenario())

    assert client.setpoint_w == -1000.0
    assert client.calls[-1][2]["value"] == -1000.0
    status = client.states[ESS_CONTROL_STATUS_ENTITY]
    assert status["state"] == "tracking"
    attributes = status["attributes"]
    assert isinstance(attributes, dict)
    assert attributes["hardware_writes"] is True
    assert attributes["acknowledged"] is True


def test_ess_controller_initializes_to_safe_zero() -> None:
    client = FakeClient(setpoint_w=-1500.0)
    controller = EssHardwareController(client, _settings().ess)

    asyncio.run(controller.initialize())

    assert client.setpoint_w == 0.0
    assert client.calls[-1][2]["value"] == 0.0


def test_ess_controller_disabled_never_calls_hardware() -> None:
    client = FakeClient(setpoint_w=-500.0)
    controller = EssHardwareController(client, _settings(control_enabled=False).ess)

    asyncio.run(controller.initialize())

    assert client.calls == []
    assert client.setpoint_w == -500.0


def test_settings_reject_enabled_control_without_setpoint(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text('{"ess":{"control_enabled":true}}', encoding="utf-8")

    with pytest.raises(ConfigurationError, match="setpoint_entity is required"):
        Settings.load(path)
