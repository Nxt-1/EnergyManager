from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from energymanager.house_state import HouseState, InputStatus


def test_derived_grid_and_pv_values_use_only_valid_inputs() -> None:
    state = HouseState()
    now = datetime(2026, 10, 3, 10, 0, tzinfo=UTC)

    for key, entity, value in (
        ("grid.import_power", "sensor.import", 1800.0),
        ("grid.export_power", "sensor.export", 250.0),
        ("pv.solax_power", "sensor.solax", 1200.0),
        ("pv.shed_power", "sensor.shed", 1800.0),
    ):
        reading = state.ensure_input(key, entity)
        reading.set_valid(value, unit="W", observed_at_utc=now, source_last_updated=None)

    assert state.grid_power_w == pytest.approx(1550.0)
    assert state.pv_total_power_w == pytest.approx(3000.0)


def test_configured_input_becomes_stale_after_threshold() -> None:
    state = HouseState()
    reading = state.ensure_input("ess.soc", "sensor.ess_soc")
    observed = datetime(2026, 10, 3, 10, 0, tzinfo=UTC)
    reading.set_valid(70.0, unit="%", observed_at_utc=observed, source_last_updated=None)

    state.update_staleness(timedelta(seconds=90), now_utc=observed + timedelta(seconds=91))

    assert reading.status is InputStatus.STALE
    assert state.value("ess.soc") is None


def test_unconfigured_pv_does_not_force_total_to_zero() -> None:
    state = HouseState()
    state.ensure_input("pv.solax_power", None)
    state.ensure_input("pv.shed_power", None)

    assert state.pv_total_power_w is None


def test_house_load_uses_ac_balance_and_excludes_dc_coupled_shed_pv() -> None:
    state = HouseState()
    now = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)

    for key, entity, value in (
        ("grid.import_power", "sensor.import", 1500.0),
        ("grid.export_power", "sensor.export", 0.0),
        ("pv.solax_power", "sensor.solax", 2000.0),
        ("pv.shed_power", "sensor.shed", 1800.0),
        ("ess.power", "sensor.ess", -500.0),
    ):
        reading = state.ensure_input(key, entity)
        reading.set_valid(value, unit="W", observed_at_utc=now, source_last_updated=None)

    assert state.house_load_power_w == pytest.approx(3000.0)


def test_background_load_subtracts_ev_charging_power() -> None:
    state = HouseState()
    now = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)

    for key, entity, value in (
        ("grid.import_power", "sensor.import", 2500.0),
        ("grid.export_power", "sensor.export", 0.0),
        ("pv.solax_power", "sensor.solax", 3000.0),
        ("ess.power", "sensor.ess", 500.0),
        ("ev.charging_power", "sensor.ev", 3500.0),
    ):
        reading = state.ensure_input(key, entity)
        reading.set_valid(value, unit="W", observed_at_utc=now, source_last_updated=None)

    assert state.house_load_power_w == pytest.approx(6000.0)
    assert state.known_controllable_load_power_w == pytest.approx(3500.0)
    assert state.background_load_power_w == pytest.approx(2500.0)


def test_unconfigured_ev_power_contributes_zero_to_controllable_load() -> None:
    state = HouseState()
    now = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)

    for key, entity, value in (
        ("grid.import_power", "sensor.import", 1000.0),
        ("grid.export_power", "sensor.export", 0.0),
        ("pv.solax_power", "sensor.solax", 500.0),
        ("ess.power", "sensor.ess", 0.0),
    ):
        reading = state.ensure_input(key, entity)
        reading.set_valid(value, unit="W", observed_at_utc=now, source_last_updated=None)
    state.ensure_input("ev.charging_power", None)

    assert state.known_controllable_load_power_w == pytest.approx(0.0)
    assert state.background_load_power_w == pytest.approx(1500.0)


def test_invalid_configured_ev_power_makes_background_load_unavailable() -> None:
    state = HouseState()
    now = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)

    for key, entity, value in (
        ("grid.import_power", "sensor.import", 1000.0),
        ("grid.export_power", "sensor.export", 0.0),
        ("pv.solax_power", "sensor.solax", 500.0),
        ("ess.power", "sensor.ess", 0.0),
    ):
        reading = state.ensure_input(key, entity)
        reading.set_valid(value, unit="W", observed_at_utc=now, source_last_updated=None)

    ev = state.ensure_input("ev.charging_power", "sensor.ev")
    ev.set_invalid("unavailable", observed_at_utc=now)

    assert state.known_controllable_load_power_w is None
    assert state.background_load_power_w is None
