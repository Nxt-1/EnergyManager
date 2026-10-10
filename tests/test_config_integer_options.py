from __future__ import annotations

import json

from energymanager.config import Settings, effective_integer_option_diagnostics


def test_whole_number_options_load_without_value_changes(tmp_path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "ess": {
                    "min_soc_percent": 10,
                    "max_soc_percent": 100,
                    "max_charge_power_w": 2500,
                    "max_discharge_power_w": 2500,
                },
                "ev": {
                    "min_charge_current_a": 6,
                    "max_charge_current_a": 16,
                    "nominal_voltage_v": 230,
                    "target_soc_percent": 80,
                    "minimum_soc_percent": 50,
                },
            }
        ),
        encoding="utf-8",
    )

    settings = Settings.load(path)

    assert settings.ess.max_discharge_power_w == 2500.0
    assert settings.ev.nominal_voltage_v == 230.0
    assert settings.ev.minimum_soc_percent == 50.0
    assert effective_integer_option_diagnostics(settings) == {
        "ess": {
            "min_soc_percent": 10,
            "max_soc_percent": 100,
            "max_charge_power_w": 2500,
            "max_discharge_power_w": 2500,
        },
        "ev": {
            "min_charge_current_a": 6,
            "max_charge_current_a": 16,
            "nominal_voltage_v": 230,
            "target_soc_percent": 80,
            "minimum_soc_percent": 50,
        },
    }


def test_configuration_diagnostics_preserve_corrupted_effective_value(tmp_path) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"ess": {"max_discharge_power_w": 2493}}), encoding="utf-8")

    diagnostics = effective_integer_option_diagnostics(Settings.load(path))

    assert diagnostics["ess"]["max_discharge_power_w"] == 2493
