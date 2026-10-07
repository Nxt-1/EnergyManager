from __future__ import annotations

import pytest

from energymanager.config import EssSettings, EvSettings, Settings
from energymanager.inputs import build_input_specs


def _power_state(value: str) -> dict[str, object]:
    return {"state": value, "attributes": {"unit_of_measurement": "W"}}


def test_ess_power_is_normalized_to_positive_discharge() -> None:
    settings = Settings(ess=EssSettings(power_entity="sensor.ess", power_positive_means="charge"))
    spec = next(spec for spec in build_input_specs(settings) if spec.key == "ess.power")

    assert spec.parser(_power_state("500")) == pytest.approx(-500.0)
    assert spec.parser(_power_state("-750")) == pytest.approx(750.0)


def test_ev_charging_power_clamps_small_negative_noise_to_zero() -> None:
    settings = Settings(ev=EvSettings(charging_power_entity="sensor.ev_power"))
    spec = next(spec for spec in build_input_specs(settings) if spec.key == "ev.charging_power")

    assert spec.parser(_power_state("-37.742")) == pytest.approx(0.0)
    assert spec.parser(_power_state("0")) == pytest.approx(0.0)
    assert spec.parser(_power_state("1380")) == pytest.approx(1380.0)


def test_ev_charging_power_rejects_large_negative_value() -> None:
    settings = Settings(ev=EvSettings(charging_power_entity="sensor.ev_power"))
    spec = next(spec for spec in build_input_specs(settings) if spec.key == "ev.charging_power")

    with pytest.raises(ValueError, match="negative beyond noise floor"):
        spec.parser(_power_state("-100.1"))
