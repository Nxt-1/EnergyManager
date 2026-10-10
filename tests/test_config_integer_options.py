from __future__ import annotations

import json
from pathlib import Path

import pytest

from energymanager.config import ConfigurationError, Settings, effective_integer_option_diagnostics


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


def test_ev_hardware_control_requires_all_control_entities(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text('{"ev":{"control_enabled":true}}', encoding="utf-8")

    with pytest.raises(ConfigurationError, match="ev.current_entity"):
        Settings.load(path)


def test_ev_hardware_control_loads_goe_entities(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        '{"ev":{'
        '"control_enabled":true,'
        '"current_entity":"number.goe_322561_amp",'
        '"phase_mode_entity":"select.goe_322561_psm",'
        '"force_state_entity":"select.goe_322561_frc"'
        '}}',
        encoding="utf-8",
    )

    settings = Settings.load(path)

    assert settings.ev.control_enabled is True
    assert settings.ev.current_entity == "number.goe_322561_amp"
    assert settings.ev.phase_mode_entity == "select.goe_322561_psm"
    assert settings.ev.force_state_entity == "select.goe_322561_frc"
