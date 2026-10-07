from __future__ import annotations

from datetime import UTC, datetime

import pytest

from energymanager.actuators import ActuatorPowerRequest, ActuatorRegistry, EssActuatorSnapshot, EvActuatorSnapshot
from energymanager.config import EssSettings, EvSettings, Settings
from energymanager.house_state import HouseState

_NOW = datetime(2026, 10, 6, 20, 0, tzinfo=UTC)


def _set_value(state: HouseState, key: str, entity_id: str, value: float | bool, unit: str | None) -> None:
    reading = state.ensure_input(key, entity_id)
    reading.set_valid(
        value,
        unit=unit,
        observed_at_utc=_NOW,
        source_last_updated=_NOW.isoformat(),
    )


def test_registry_exposes_ready_ess_and_ev_capabilities() -> None:
    settings = Settings(
        ess=EssSettings(soc_entity="sensor.ess_soc", power_entity="sensor.ess_power"),
        ev=EvSettings(
            soc_entity="sensor.ev_soc",
            connected_entity="binary_sensor.ev_connected",
            charging_power_entity="sensor.ev_power",
        ),
    )
    state = HouseState()
    _set_value(state, "ess.soc", "sensor.ess_soc", 42.0, "%")
    _set_value(state, "ess.power", "sensor.ess_power", 500.0, "W")
    _set_value(state, "ev.soc", "sensor.ev_soc", 63.0, "%")
    _set_value(state, "ev.connected", "binary_sensor.ev_connected", True, None)
    _set_value(state, "ev.charging_power", "sensor.ev_power", 0.0, "W")

    ess, ev = ActuatorRegistry(settings).snapshots(state)

    assert isinstance(ess, EssActuatorSnapshot)
    assert ess.planning_available is True
    assert ess.soc_percent == pytest.approx(42.0)
    assert ess.capabilities.max_discharge_power_w == pytest.approx(2000.0)
    assert isinstance(ev, EvActuatorSnapshot)
    assert ev.planning_available is True
    assert ev.connected is True
    assert ev.capabilities.minimum_single_phase_power_w == pytest.approx(1380.0)
    assert ev.capabilities.maximum_three_phase_power_w == pytest.approx(11040.0)


def test_ev_actuator_is_unavailable_when_disconnected() -> None:
    settings = Settings(ev=EvSettings(connected_entity="binary_sensor.ev_connected"))
    state = HouseState()
    _set_value(state, "ev.connected", "binary_sensor.ev_connected", False, None)

    _, ev = ActuatorRegistry(settings).snapshots(state)

    assert isinstance(ev, EvActuatorSnapshot)
    assert ev.status == "disconnected"
    assert ev.planning_available is False


def test_ess_actuator_requires_valid_soc_for_planning() -> None:
    settings = Settings(ess=EssSettings(soc_entity="sensor.ess_soc"))

    ess, _ = ActuatorRegistry(settings).snapshots(HouseState())

    assert isinstance(ess, EssActuatorSnapshot)
    assert ess.status == "soc_unavailable"
    assert ess.planning_available is False


def test_ess_command_is_limited_to_configured_power() -> None:
    settings = Settings(ess=EssSettings(soc_entity="sensor.ess_soc", max_discharge_power_w=2000.0))
    state = HouseState()
    _set_value(state, "ess.soc", "sensor.ess_soc", 50.0, "%")

    result = ActuatorRegistry(settings).evaluate_commands(
        (ActuatorPowerRequest(actuator_id="ess", requested_power_w=2500.0),),
        state,
    )[0]

    assert result.status == "limited"
    assert result.accepted_power_w == pytest.approx(2000.0)
    assert result.reason == "power_limit"


def test_ess_command_respects_soc_boundary() -> None:
    settings = Settings(ess=EssSettings(soc_entity="sensor.ess_soc", min_soc_percent=10.0))
    state = HouseState()
    _set_value(state, "ess.soc", "sensor.ess_soc", 10.0, "%")

    result = ActuatorRegistry(settings).evaluate_commands(
        (ActuatorPowerRequest(actuator_id="ess", requested_power_w=500.0),),
        state,
    )[0]

    assert result.status == "rejected"
    assert result.accepted_power_w == pytest.approx(0.0)
    assert result.reason == "minimum_soc_reached"


def test_ev_command_translates_requested_power_to_discrete_1p_current() -> None:
    settings = Settings(
        ev=EvSettings(
            soc_entity="sensor.ev_soc",
            connected_entity="binary_sensor.ev_connected",
            charging_power_entity="sensor.ev_power",
        )
    )
    state = HouseState()
    _set_value(state, "ev.connected", "binary_sensor.ev_connected", True, None)
    _set_value(state, "ev.soc", "sensor.ev_soc", 40.0, "%")

    result = ActuatorRegistry(settings).evaluate_commands(
        (ActuatorPowerRequest(actuator_id="ev", requested_power_w=3000.0),),
        state,
    )[0]

    assert result.status == "limited"
    assert result.accepted_power_w == pytest.approx(2990.0)
    assert result.phase_count == 1
    assert result.current_a == pytest.approx(13.0)


def test_ev_command_can_select_three_phase_when_it_fits_better_below_request() -> None:
    settings = Settings(
        ev=EvSettings(
            soc_entity="sensor.ev_soc",
            connected_entity="binary_sensor.ev_connected",
        )
    )
    state = HouseState()
    _set_value(state, "ev.connected", "binary_sensor.ev_connected", True, None)
    _set_value(state, "ev.soc", "sensor.ev_soc", 40.0, "%")

    result = ActuatorRegistry(settings).evaluate_commands(
        (ActuatorPowerRequest(actuator_id="ev", requested_power_w=5000.0),),
        state,
    )[0]

    assert result.accepted_power_w == pytest.approx(4830.0)
    assert result.phase_count == 3
    assert result.current_a == pytest.approx(7.0)


def test_ev_command_below_minimum_resolves_to_idle() -> None:
    settings = Settings(
        ev=EvSettings(
            soc_entity="sensor.ev_soc",
            connected_entity="binary_sensor.ev_connected",
        )
    )
    state = HouseState()
    _set_value(state, "ev.connected", "binary_sensor.ev_connected", True, None)
    _set_value(state, "ev.soc", "sensor.ev_soc", 40.0, "%")

    result = ActuatorRegistry(settings).evaluate_commands(
        (ActuatorPowerRequest(actuator_id="ev", requested_power_w=1000.0),),
        state,
    )[0]

    assert result.status == "limited"
    assert result.accepted_power_w == pytest.approx(0.0)
    assert result.reason == "below_minimum_charge_power"
