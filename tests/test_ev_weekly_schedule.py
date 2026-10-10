from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from energymanager.actuators import ActuatorRegistry
from energymanager.config import ConfigurationError, EvSettings, EvWeeklyScheduleEntry, Settings
from energymanager.house_state import HouseState
from energymanager.tasks import TaskRegistry

_LOCAL = ZoneInfo("Europe/Brussels")
_NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)  # Saturday 14:00 local.


def _set_value(state: HouseState, key: str, entity_id: str, value: float | bool, unit: str | None) -> None:
    reading = state.ensure_input(key, entity_id)
    reading.set_valid(value, unit=unit, observed_at_utc=_NOW, source_last_updated=_NOW.isoformat())


def _settings() -> EvSettings:
    return EvSettings(
        soc_entity="sensor.ev_soc",
        connected_entity="binary_sensor.ev_connected",
        charging_power_entity="sensor.ev_power",
        battery_capacity_kwh=46.8,
        charge_efficiency=0.90,
        target_soc_percent=80.0,
        weekly_schedule=(
            EvWeeklyScheduleEntry(
                weekdays=(0, 1, 2, 3, 4),
                departure_time_local="07:00",
                return_time_local="17:00",
                minimum_soc_percent=50.0,
                expected_trip_energy_kwh=10.0,
            ),
        ),
    )


def _tasks(settings: EvSettings, *, connected: bool = True, soc: float = 32.0):
    state = HouseState()
    _set_value(state, "ev.connected", "binary_sensor.ev_connected", connected, None)
    _set_value(state, "ev.soc", "sensor.ev_soc", soc, "%")
    _set_value(state, "ev.charging_power", "sensor.ev_power", 0.0, "W")
    actuators = ActuatorRegistry(Settings(ev=settings)).snapshots(state)
    return TaskRegistry(settings).snapshots(actuators, now_utc=_NOW, local_tz=_LOCAL)


def test_weekly_schedule_config_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "ev": {
                    "weekly_schedule": [
                        "days=mon,tue,wed,thu,fri|depart=07:00|return=17:00|min_soc=50|trip_kwh=10"
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    settings = Settings.load(path)
    entry = settings.ev.weekly_schedule[0]
    assert entry.weekdays == (0, 1, 2, 3, 4)
    assert entry.minimum_soc_percent == pytest.approx(50.0)
    assert entry.expected_trip_energy_kwh == pytest.approx(10.0)
    assert settings.as_options()["ev"]["weekly_schedule"][0] == (
        "days=mon,tue,wed,thu,fri|depart=07:00|return=17:00|min_soc=50|trip_kwh=10"
    )


def test_weekly_schedule_requires_quarter_hour_boundaries(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "ev": {
                    "weekly_schedule": [
                        "days=mon|depart=07:10|return=17:00|min_soc=50|trip_kwh=10"
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_weekly_schedule_generates_five_departures_plus_soft_terminal_target() -> None:
    tasks = _tasks(_settings())
    hard = [item for item in tasks if item.kind == "energy_by_deadline"]
    soft = [item for item in tasks if item.kind == "ev_terminal_soc_target"]

    assert len(hard) == 5
    assert len(soft) == 1
    assert hard[0].latest_end_local is not None
    assert hard[0].latest_end_local.isoformat() == "2026-10-12T07:00:00+02:00"
    assert hard[0].expected_return_local is not None
    assert hard[0].expected_return_local.isoformat() == "2026-10-12T17:00:00+02:00"
    assert hard[0].minimum_soc_percent == pytest.approx(50.0)
    assert hard[0].required_energy_kwh == pytest.approx(9.36)
    assert hard[1].required_energy_kwh == pytest.approx((8.424 + 10.0) / 0.90)
    assert soft[0].target_soc_percent == pytest.approx(80.0)
    assert len(soft[0].ev_unavailable_windows_local) == 5


def test_weekly_schedule_keeps_planning_while_car_is_in_a_known_away_window() -> None:
    settings = EvSettings(
        soc_entity="sensor.ev_soc",
        connected_entity="binary_sensor.ev_connected",
        charging_power_entity="sensor.ev_power",
        battery_capacity_kwh=46.8,
        target_soc_percent=80.0,
        weekly_schedule=(
            EvWeeklyScheduleEntry(
                weekdays=(5,),
                departure_time_local="13:00",
                return_time_local="18:00",
                minimum_soc_percent=50.0,
                expected_trip_energy_kwh=5.0,
            ),
        ),
    )
    tasks = _tasks(settings, connected=False, soc=55.0)
    assert any(item.planning_available for item in tasks)
    assert all(item.status != "waiting_for_connection" for item in tasks)
