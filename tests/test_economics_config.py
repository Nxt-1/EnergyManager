from __future__ import annotations

import json
from pathlib import Path

import pytest

from energymanager.config import ConfigurationError, Settings


def test_economics_is_disabled_by_default(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "missing.json")
    assert settings.economics.enabled is False
    assert settings.economics.configured is False
    assert settings.economics.capacity_tariff_floor_kw == pytest.approx(2.5)


def test_economics_settings_are_loaded_and_exported(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "economics": {
                    "enabled": True,
                    "import_energy_eur_per_kwh": 0.2528,
                    "export_energy_eur_per_kwh": 0.03,
                    "capacity_tariff_eur_per_kw_month": 4.5,
                    "capacity_tariff_floor_kw": 2.5,
                }
            }
        ),
        encoding="utf-8",
    )

    settings = Settings.load(path)

    assert settings.economics.configured is True
    assert settings.economics.import_energy_eur_per_kwh == pytest.approx(0.2528)
    assert settings.as_options()["economics"]["capacity_tariff_eur_per_kw_month"] == pytest.approx(4.5)


def test_enabled_economics_requires_all_marginal_prices(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"economics": {"enabled": True, "import_energy_eur_per_kwh": 0.25}}), encoding="utf-8")

    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_negative_economics_price_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps({"economics": {"export_energy_eur_per_kwh": -0.01}}),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        Settings.load(path)
