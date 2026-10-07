from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from energymanager.actuators import ActuatorRegistry
from energymanager.config import EvSettings, Settings
from energymanager.house_state import HouseState
from energymanager.tasks import TaskRegistry

_LOCAL = ZoneInfo("Europe/Brussels")
_NOW = datetime(2026, 10, 7, 18, 0, tzinfo=UTC)


def _set_value(state: HouseState, key: str, entity_id: str, value: float | bool, unit: str | None) -> None:
    reading = state.ensure_input(key, entity_id)
    reading.set_valid(
        value,
        unit=unit,
        observed_at_utc=_NOW,
        source_last_updated=_NOW.isoformat(),
    )


def _ready_ev_settings(**overrides: object) -> EvSettings:
    values: dict[str, object] = {
        "soc_entity": "sensor.ev_soc",
        "connected_entity": "binary_sensor.ev_connected",
        "charging_power_entity": "sensor.ev_power",
        "battery_capacity_kwh": 70.0,
        "charge_efficiency": 0.90,
        "target_soc_percent": 80.0,
        "departure_time_local": "07:00",
    }
    values.update(overrides)
    return EvSettings(**values)  # type: ignore[arg-type]


def _task(settings: EvSettings, soc: float = 50.0, connected: bool = True):
    state = HouseState()
    _set_value(state, "ev.connected", "binary_sensor.ev_connected", connected, None)
    _set_value(state, "ev.soc", "sensor.ev_soc", soc, "%")
    _set_value(state, "ev.charging_power", "sensor.ev_power", 0.0, "W")
    actuators = ActuatorRegistry(Settings(ev=settings)).snapshots(state)
    return TaskRegistry(settings).snapshots(actuators, now_utc=_NOW, local_tz=_LOCAL)[0]


def test_ev_task_requires_battery_capacity_before_energy_can_be_derived() -> None:
    task = _task(_ready_ev_settings(battery_capacity_kwh=None))

    assert task.status == "configuration_required"
    assert task.planning_available is False
    assert task.required_energy_kwh is None


def test_ev_task_converts_soc_gap_to_ac_energy_requirement() -> None:
    task = _task(_ready_ev_settings(), soc=50.0)

    assert task.status == "ready"
    assert task.planning_available is True
    assert task.battery_energy_required_kwh == pytest.approx(21.0)
    assert task.required_energy_kwh == pytest.approx(21.0 / 0.90)
    assert task.latest_end_local is not None
    assert task.latest_end_local.hour == 7
    assert task.latest_end_local.date().isoformat() == "2026-10-08"


def test_ev_task_is_satisfied_when_target_soc_is_already_reached() -> None:
    task = _task(_ready_ev_settings(), soc=82.0)

    assert task.status == "satisfied"
    assert task.planning_available is False
    assert task.required_energy_kwh == pytest.approx(0.0)


def test_ev_task_waits_for_connection() -> None:
    task = _task(_ready_ev_settings(), connected=False)

    assert task.status == "waiting_for_connection"
    assert task.planning_available is False


def test_ev_task_marks_deadline_infeasible_if_required_energy_exceeds_available_window() -> None:
    settings = _ready_ev_settings(
        battery_capacity_kwh=100.0,
        target_soc_percent=100.0,
        departure_time_local="21:00",
        supports_single_phase=True,
        supports_three_phase=False,
        max_charge_current_a=6.0,
    )
    task = _task(settings, soc=0.0)

    assert task.status == "deadline_infeasible"
    assert task.planning_available is True
    assert task.feasible_at_max_power is False
