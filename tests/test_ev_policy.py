from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from energymanager.actuators import ActuatorRegistry
from energymanager.config import ConfigurationError, EvSettings, Settings
from energymanager.house_state import HouseState
from energymanager.tasks import TaskRegistry

_LOCAL = ZoneInfo("Europe/Brussels")
_NOW = datetime(2026, 10, 8, 18, 0, tzinfo=UTC)


def _set_value(state: HouseState, key: str, entity_id: str, value: float | bool, unit: str | None) -> None:
    reading = state.ensure_input(key, entity_id)
    reading.set_valid(
        value,
        unit=unit,
        observed_at_utc=_NOW,
        source_last_updated=_NOW.isoformat(),
    )


def _task(settings: EvSettings, *, soc: float) -> object:
    state = HouseState()
    _set_value(state, "ev.connected", "binary_sensor.ev_connected", True, None)
    _set_value(state, "ev.soc", "sensor.ev_soc", soc, "%")
    _set_value(state, "ev.charging_power", "sensor.ev_power", 0.0, "W")
    actuators = ActuatorRegistry(Settings(ev=settings)).snapshots(state)
    return TaskRegistry(settings).snapshots(actuators, now_utc=_NOW, local_tz=_LOCAL)[0]


def _settings(**overrides: object) -> EvSettings:
    values: dict[str, object] = {
        "soc_entity": "sensor.ev_soc",
        "connected_entity": "binary_sensor.ev_connected",
        "charging_power_entity": "sensor.ev_power",
        "battery_capacity_kwh": 46.8,
        "charge_efficiency": 0.90,
        "target_soc_percent": 80.0,
        "departure_time_local": "07:00",
    }
    values.update(overrides)
    return EvSettings(**values)  # type: ignore[arg-type]


def test_minimum_soc_defaults_to_existing_target_semantics() -> None:
    task = _task(_settings(), soc=60.0)
    assert task.minimum_soc_percent == pytest.approx(80.0)
    assert task.target_soc_percent == pytest.approx(80.0)
    assert task.required_energy_kwh == pytest.approx(task.preferred_energy_kwh)


def test_ev_task_separates_hard_minimum_from_soft_preferred_target() -> None:
    task = _task(_settings(minimum_soc_percent=50.0), soc=40.0)
    assert task.minimum_soc_percent == pytest.approx(50.0)
    assert task.target_soc_percent == pytest.approx(80.0)
    assert task.battery_energy_required_kwh == pytest.approx(4.68)
    assert task.required_energy_kwh == pytest.approx(5.2)
    assert task.preferred_battery_energy_kwh == pytest.approx(18.72)
    assert task.preferred_energy_kwh == pytest.approx(20.8)
    assert task.status == "ready"
    assert task.planning_available is True


def test_ev_task_remains_plannable_when_hard_minimum_is_met_but_preferred_target_is_not() -> None:
    task = _task(_settings(minimum_soc_percent=50.0), soc=60.0)
    assert task.required_energy_kwh == pytest.approx(0.0)
    assert task.preferred_energy_kwh is not None and task.preferred_energy_kwh > 0.0
    assert task.status == "ready"
    assert task.planning_available is True


def test_ev_minimum_soc_config_is_loaded_and_preserved(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps({"ev": {"minimum_soc_percent": 45, "target_soc_percent": 80}}),
        encoding="utf-8",
    )
    settings = Settings.load(path)
    assert settings.ev.minimum_soc_percent == pytest.approx(45.0)
    assert settings.ev.target_soc_percent == pytest.approx(80.0)
    assert settings.as_options()["ev"]["minimum_soc_percent"] == pytest.approx(45.0)


def test_ev_minimum_soc_cannot_exceed_preferred_target(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps({"ev": {"minimum_soc_percent": 85, "target_soc_percent": 80}}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError):
        Settings.load(path)
