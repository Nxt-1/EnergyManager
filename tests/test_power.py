from __future__ import annotations

import pytest
from energymanager.power import PowerStateError, power_w_from_state


def test_power_in_watts_is_preserved() -> None:
    state = {"state": "-1234.5", "attributes": {"unit_of_measurement": "W"}}

    assert power_w_from_state(state) == pytest.approx(-1234.5)


def test_power_in_kw_is_converted() -> None:
    state = {"state": "2.75", "attributes": {"unit_of_measurement": "kW"}}

    assert power_w_from_state(state) == pytest.approx(2750.0)


@pytest.mark.parametrize("state_value", ["unknown", "unavailable", "", None])
def test_non_numeric_states_are_rejected(state_value: str | None) -> None:
    state = {"state": state_value, "attributes": {"unit_of_measurement": "W"}}

    with pytest.raises(PowerStateError):
        power_w_from_state(state)


def test_unknown_unit_is_rejected() -> None:
    state = {"state": "12", "attributes": {"unit_of_measurement": "A"}}

    with pytest.raises(PowerStateError):
        power_w_from_state(state)
