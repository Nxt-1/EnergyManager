from __future__ import annotations

import pytest

from energymanager.power import PowerStateError, grid_net_power_w, power_w_from_state


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


def test_unknown_unit_is_rejected() -> None:
    state = {"state": "12", "attributes": {"unit_of_measurement": "A"}}

    with pytest.raises(PowerStateError):
        power_w_from_state(state)


def test_grid_net_power_is_import_minus_export() -> None:
    assert grid_net_power_w(1800.0, 0.0) == pytest.approx(1800.0)
    assert grid_net_power_w(0.0, 2400.0) == pytest.approx(-2400.0)
    assert grid_net_power_w(250.0, 250.0) == pytest.approx(0.0)


@pytest.mark.parametrize("import_power,export_power", [(-1.0, 0.0), (0.0, -1.0)])
def test_grid_net_power_rejects_negative_directional_inputs(import_power: float, export_power: float) -> None:
    with pytest.raises(PowerStateError):
        grid_net_power_w(import_power, export_power)
