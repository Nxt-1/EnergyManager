from __future__ import annotations

import json
from pathlib import Path

import pytest

from energymanager.config import (
    ConfigurationError,
    EssSettings,
    EvSettings,
    GridSettings,
    PvSettings,
    Settings,
)


def test_missing_options_file_uses_defaults(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "missing.json")

    assert settings.log_level == "info"
    assert settings.grid.import_power_entity is None
    assert settings.grid.export_power_entity is None
    assert settings.ess.power_positive_means == "discharge"
    assert settings.grid_power_configured is False


def test_grouped_options_are_loaded(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "log_level": "debug",
                "grid": {
                    "import_power_entity": "sensor.grid_import_power",
                    "export_power_entity": "sensor.grid_export_power",
                },
                "ess": {
                    "soc_entity": "sensor.ess_soc",
                    "power_entity": "sensor.ess_power",
                    "power_positive_means": "charge",
                },
                "pv": {
                    "solax_power_entity": "sensor.solax_power",
                    "shed_power_entity": "sensor.shed_power",
                },
                "ev": {
                    "soc_entity": "sensor.ev_soc",
                    "connected_entity": "binary_sensor.ev_connected",
                    "charging_power_entity": "sensor.ev_power",
                },
            }
        ),
        encoding="utf-8",
    )

    settings = Settings.load(path)

    assert settings.log_level == "debug"
    assert settings.grid.import_power_entity == "sensor.grid_import_power"
    assert settings.grid.export_power_entity == "sensor.grid_export_power"
    assert settings.ess.soc_entity == "sensor.ess_soc"
    assert settings.ess.power_positive_means == "charge"
    assert settings.pv.shed_power_entity == "sensor.shed_power"
    assert settings.ev.connected_entity == "binary_sensor.ev_connected"
    assert settings.grid_power_configured is True
    assert settings.legacy_options_detected is False


def test_v02_flat_grid_options_are_loaded_for_migration(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "grid_import_power_entity": "sensor.grid_import",
                "grid_export_power_entity": "sensor.grid_export",
            }
        ),
        encoding="utf-8",
    )

    settings = Settings.load(path)

    assert settings.grid.import_power_entity == "sensor.grid_import"
    assert settings.grid.export_power_entity == "sensor.grid_export"
    assert settings.legacy_options_detected is True
    assert "grid_import_power_entity" not in settings.as_options()
    assert settings.as_options()["grid"]["import_power_entity"] == "sensor.grid_import"


def test_configured_entities_are_deduplicated() -> None:
    settings = Settings(
        grid=GridSettings("sensor.import", "sensor.export"),
        ess=EssSettings(soc_entity="sensor.shared", power_entity="sensor.ess_power"),
        pv=PvSettings(solax_power_entity="sensor.shared"),
        ev=EvSettings(charging_power_entity="sensor.ev_power"),
    )

    assert settings.configured_entities().count("sensor.shared") == 1


@pytest.mark.parametrize(
    ("group", "key"),
    [
        ("grid", "import_power_entity"),
        ("grid", "export_power_entity"),
        ("ess", "soc_entity"),
        ("ess", "power_entity"),
        ("pv", "solax_power_entity"),
        ("pv", "shed_power_entity"),
        ("ev", "soc_entity"),
        ("ev", "connected_entity"),
        ("ev", "charging_power_entity"),
    ],
)
def test_invalid_entity_id_is_rejected(tmp_path: Path, group: str, key: str) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({group: {key: "Not an entity"}}), encoding="utf-8")

    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_same_grid_import_and_export_entity_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "grid": {
                    "import_power_entity": "sensor.grid_power",
                    "export_power_entity": "sensor.grid_power",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_invalid_ess_power_sign_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"ess": {"power_positive_means": "magic"}}), encoding="utf-8")

    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_pv_forecast_is_enabled_by_default(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "missing.json")

    assert settings.pv.forecast_enabled is True


def test_pv_forecast_can_be_disabled(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"pv": {"forecast_enabled": False}}), encoding="utf-8")

    settings = Settings.load(path)

    assert settings.pv.forecast_enabled is False
    assert settings.as_options()["pv"]["forecast_enabled"] is False


def test_invalid_pv_forecast_flag_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"pv": {"forecast_enabled": "yes"}}), encoding="utf-8")

    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_database_persistence_is_disabled_by_default(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "missing.json")

    assert settings.database.enabled is False
    assert settings.database.database == "energy_manager"


def test_database_settings_are_loaded(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "database": {
                    "enabled": True,
                    "url": "http://192.168.178.103:8181/",
                    "database": "energy_manager",
                    "token": "apiv3_secret",
                }
            }
        ),
        encoding="utf-8",
    )

    settings = Settings.load(path)

    assert settings.database.enabled is True
    assert settings.database.url == "http://192.168.178.103:8181"
    assert settings.database.database == "energy_manager"
    assert settings.database.token == "apiv3_secret"


def test_enabled_database_requires_url_and_token(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"database": {"enabled": True}}), encoding="utf-8")

    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_legacy_influx_backfill_settings_are_loaded(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "database": {
                    "enabled": True,
                    "url": "http://192.168.178.103:8181",
                    "database": "energy_manager",
                    "token": "apiv3_secret",
                },
                "legacy_influx": {
                    "backfill_enabled": True,
                    "url": "http://192.168.178.103:8086/",
                    "database": "home_assistant",
                    "retention_policy": "autogen",
                    "username": "energy_manager",
                    "password": "legacy-secret",
                },
            }
        ),
        encoding="utf-8",
    )

    settings = Settings.load(path)

    assert settings.legacy_influx.backfill_enabled is True
    assert settings.legacy_influx.url == "http://192.168.178.103:8086"
    assert settings.legacy_influx.database == "home_assistant"
    assert settings.legacy_influx.retention_policy == "autogen"
    assert settings.legacy_influx.username == "energy_manager"
    assert settings.legacy_influx.password == "legacy-secret"


def test_legacy_influx_credentials_must_be_configured_as_a_pair(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "legacy_influx": {
                    "backfill_enabled": False,
                    "username": "energy_manager",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_legacy_backfill_requires_target_database_and_source_url(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"legacy_influx": {"backfill_enabled": True}}), encoding="utf-8")

    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_ess_planning_defaults_are_available_without_new_options(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "missing.json")

    assert settings.ess.capacity_kwh == pytest.approx(15.0)
    assert settings.ess.min_soc_percent == pytest.approx(10.0)
    assert settings.ess.max_soc_percent == pytest.approx(100.0)
    assert settings.ess.max_charge_power_w == pytest.approx(2000.0)
    assert settings.ess.max_discharge_power_w == pytest.approx(2000.0)
    assert settings.ess.charge_efficiency == pytest.approx(0.95)
    assert settings.ess.discharge_efficiency == pytest.approx(0.95)


def test_ess_planning_envelope_is_loaded(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "ess": {
                    "capacity_kwh": 15.36,
                    "min_soc_percent": 15,
                    "max_soc_percent": 95,
                    "max_charge_power_w": 1800,
                    "max_discharge_power_w": 2100,
                    "charge_efficiency": 0.96,
                    "discharge_efficiency": 0.94,
                }
            }
        ),
        encoding="utf-8",
    )

    settings = Settings.load(path)

    assert settings.ess.capacity_kwh == pytest.approx(15.36)
    assert settings.ess.min_soc_percent == pytest.approx(15)
    assert settings.ess.max_soc_percent == pytest.approx(95)
    assert settings.ess.max_charge_power_w == pytest.approx(1800)
    assert settings.ess.max_discharge_power_w == pytest.approx(2100)
    assert settings.ess.charge_efficiency == pytest.approx(0.96)
    assert settings.ess.discharge_efficiency == pytest.approx(0.94)


def test_invalid_ess_planning_envelope_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps({"ess": {"min_soc_percent": 90, "max_soc_percent": 80}}),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        Settings.load(path)
