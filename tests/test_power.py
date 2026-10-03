from __future__ import annotations

import pytest

from energymanager.power import (
    PowerStateError,
    grid_net_power_w,
    percentage_from_state,
    power_w_from_state,
    state_bool,
)


def test_power_in_watts_is_preserved() -> None:
    state = {"state": "-1234.5", "attributes": {"unit_of_measurement": "W"}}

    assert power_w_from_state(state) == pytest.approx(-1234.5)


def test_power_in_kw_is_converted() -> None:
    state = {"state": "2.75", "attributes": {"unit_of_measurement": "kW"}}

    assert power_w_from_state(state) == pytest.approx(2750.0)


@pytest.mark.parametrize("state_value", ["unknown", "unavailable", "", None, "nan", "inf", "-inf"])
def test_non_numeric_or_non_finite_states_are_rejected(state_value: str | None) -> None:
    state = {"state": state_value, "attributes": {"unit_of_measurement": "W"}}

    with pytest.raises(PowerStateError):
        power_w_from_state(state)


def test_unknown_power_unit_is_rejected() -> None:
    state = {"state": "12", "attributes": {"unit_of_measurement": "A"}}

    with pytest.raises(PowerStateError):
        power_w_from_state(state)


@pytest.mark.parametrize("value", [0, 42.5, 100])
def test_percentage_is_normalized(value: float) -> None:
    state = {"state": str(value), "attributes": {"unit_of_measurement": "%"}}

    assert percentage_from_state(state) == pytest.approx(value)


@pytest.mark.parametrize("value", [-0.1, 100.1])
def test_percentage_outside_range_is_rejected(value: float) -> None:
    state = {"state": str(value), "attributes": {"unit_of_measurement": "%"}}

    with pytest.raises(PowerStateError):
        percentage_from_state(state)


@pytest.mark.parametrize("value", ["on", "true", "1", "connected", "plugged"])
def test_common_true_states(value: str) -> None:
    assert state_bool({"state": value}) is True


@pytest.mark.parametrize("value", ["off", "false", "0", "disconnected", "unplugged"])
def test_common_false_states(value: str) -> None:
    assert state_bool({"state": value}) is False


def test_grid_net_power_is_import_minus_export() -> None:
    assert grid_net_power_w(1800.0, 0.0) == pytest.approx(1800.0)
    assert grid_net_power_w(0.0, 2400.0) == pytest.approx(-2400.0)
    assert grid_net_power_w(250.0, 250.0) == pytest.approx(0.0)


@pytest.mark.parametrize("import_power,export_power", [(-1.0, 0.0), (0.0, -1.0)])
def test_grid_net_power_rejects_negative_directional_inputs(import_power: float, export_power: float) -> None:
    with pytest.raises(PowerStateError):
        grid_net_power_w(import_power, export_power)
