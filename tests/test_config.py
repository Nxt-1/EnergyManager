from __future__ import annotations

import json
from pathlib import Path

import pytest

from energymanager.config import ConfigurationError, Settings


def test_missing_options_file_uses_defaults(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "missing.json")

    assert settings.log_level == "info"
    assert settings.grid_import_power_entity is None
    assert settings.grid_export_power_entity is None
    assert settings.grid_power_configured is False


def test_options_are_loaded(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "log_level": "debug",
                "grid_import_power_entity": "sensor.grid_import_power",
                "grid_export_power_entity": "sensor.grid_export_power",
            }
        ),
        encoding="utf-8",
    )

    settings = Settings.load(path)

    assert settings.log_level == "debug"
    assert settings.grid_import_power_entity == "sensor.grid_import_power"
    assert settings.grid_export_power_entity == "sensor.grid_export_power"
    assert settings.grid_power_configured is True


@pytest.mark.parametrize("key", ["grid_import_power_entity", "grid_export_power_entity"])
def test_empty_grid_entity_becomes_none(tmp_path: Path, key: str) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({key: "   "}), encoding="utf-8")

    settings = Settings.load(path)

    assert getattr(settings, key) is None
    assert settings.grid_power_configured is False


@pytest.mark.parametrize("key", ["grid_import_power_entity", "grid_export_power_entity"])
def test_invalid_entity_id_is_rejected(tmp_path: Path, key: str) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({key: "Not an entity"}), encoding="utf-8")

    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_same_import_and_export_entity_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "grid_import_power_entity": "sensor.grid_power",
                "grid_export_power_entity": "sensor.grid_power",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        Settings.load(path)
