"""Configuration loading for the Home Assistant app."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_OPTIONS_PATH = Path("/data/options.json")
_ENTITY_ID_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
_VALID_LOG_LEVELS = {"debug", "info", "warning", "error"}
_VALID_ESS_POWER_SIGNS = {"discharge", "charge"}
_DATABASE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ConfigurationError(ValueError):
    """Raised when app configuration is invalid."""


@dataclass(frozen=True, slots=True)
class GridSettings:
    """Grid input mapping."""

    import_power_entity: str | None = None
    export_power_entity: str | None = None

    @property
    def configured(self) -> bool:
        """Return whether both directional grid power inputs are configured."""
        return self.import_power_entity is not None and self.export_power_entity is not None


@dataclass(frozen=True, slots=True)
class EssSettings:
    """ESS input mapping and source sign convention."""

    soc_entity: str | None = None
    power_entity: str | None = None
    power_positive_means: str = "discharge"


@dataclass(frozen=True, slots=True)
class PvSettings:
    """PV input mapping and predictor settings."""

    solax_power_entity: str | None = None
    shed_power_entity: str | None = None
    forecast_enabled: bool = True


@dataclass(frozen=True, slots=True)
class EvSettings:
    """EV input mapping."""

    soc_entity: str | None = None
    connected_entity: str | None = None
    charging_power_entity: str | None = None


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """InfluxDB 3 persistence settings."""

    enabled: bool = False
    url: str | None = None
    database: str = "energy_manager"
    token: str | None = None


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings exposed by the Home Assistant app configuration."""

    log_level: str = "info"
    grid: GridSettings = GridSettings()
    ess: EssSettings = EssSettings()
    pv: PvSettings = PvSettings()
    ev: EvSettings = EvSettings()
    database: DatabaseSettings = DatabaseSettings()
    legacy_options_detected: bool = False

    @property
    def grid_power_configured(self) -> bool:
        """Backward-compatible convenience property for the mandatory grid pair."""
        return self.grid.configured

    def configured_entities(self) -> tuple[str, ...]:
        """Return all configured Home Assistant source entity IDs without duplicates."""
        entities = (
            self.grid.import_power_entity,
            self.grid.export_power_entity,
            self.ess.soc_entity,
            self.ess.power_entity,
            self.pv.solax_power_entity,
            self.pv.shed_power_entity,
            self.ev.soc_entity,
            self.ev.connected_entity,
            self.ev.charging_power_entity,
        )
        return tuple(dict.fromkeys(entity for entity in entities if entity is not None))

    def as_options(self) -> dict[str, Any]:
        """Return normalized nested options suitable for writing back to Supervisor."""
        return {
            "log_level": self.log_level,
            "grid": _without_none(
                {
                    "import_power_entity": self.grid.import_power_entity,
                    "export_power_entity": self.grid.export_power_entity,
                }
            ),
            "ess": _without_none(
                {
                    "soc_entity": self.ess.soc_entity,
                    "power_entity": self.ess.power_entity,
                    "power_positive_means": self.ess.power_positive_means,
                }
            ),
            "pv": _without_none(
                {
                    "solax_power_entity": self.pv.solax_power_entity,
                    "shed_power_entity": self.pv.shed_power_entity,
                    "forecast_enabled": self.pv.forecast_enabled,
                }
            ),
            "ev": _without_none(
                {
                    "soc_entity": self.ev.soc_entity,
                    "connected_entity": self.ev.connected_entity,
                    "charging_power_entity": self.ev.charging_power_entity,
                }
            ),
            "database": _without_none(
                {
                    "enabled": self.database.enabled,
                    "url": self.database.url,
                    "database": self.database.database,
                    "token": self.database.token,
                }
            ),
        }

    @classmethod
    def load(cls, path: Path = _OPTIONS_PATH) -> Settings:
        """Load and validate settings from the Home Assistant app options file."""
        if not path.exists():
            return cls()

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Unable to read {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ConfigurationError(f"Expected a JSON object in {path}")

        log_level = str(raw.get("log_level", "info")).lower().strip()
        if log_level not in _VALID_LOG_LEVELS:
            allowed = ", ".join(sorted(_VALID_LOG_LEVELS))
            raise ConfigurationError(f"log_level must be one of: {allowed}")

        grid_raw = _mapping(raw.get("grid"), "grid")
        ess_raw = _mapping(raw.get("ess"), "ess")
        pv_raw = _mapping(raw.get("pv"), "pv")
        ev_raw = _mapping(raw.get("ev"), "ev")
        database_raw = _mapping(raw.get("database"), "database")

        legacy_options_detected = any(
            key in raw for key in ("grid_import_power_entity", "grid_export_power_entity")
        )

        grid_import = _optional_entity_id(
            grid_raw.get("import_power_entity", raw.get("grid_import_power_entity")),
            "grid.import_power_entity",
        )
        grid_export = _optional_entity_id(
            grid_raw.get("export_power_entity", raw.get("grid_export_power_entity")),
            "grid.export_power_entity",
        )
        if grid_import is not None and grid_import == grid_export:
            raise ConfigurationError("grid import and export power entities must be different")

        ess_power_sign = str(ess_raw.get("power_positive_means", "discharge")).lower().strip()
        if ess_power_sign not in _VALID_ESS_POWER_SIGNS:
            allowed = ", ".join(sorted(_VALID_ESS_POWER_SIGNS))
            raise ConfigurationError(f"ess.power_positive_means must be one of: {allowed}")

        database_enabled = _bool_option(database_raw.get("enabled", False), "database.enabled")
        database_url = _optional_string(database_raw.get("url"))
        database_name = str(database_raw.get("database", "energy_manager")).strip() or "energy_manager"
        database_token = _optional_string(database_raw.get("token"))
        if not _DATABASE_RE.fullmatch(database_name):
            raise ConfigurationError("database.database may only contain letters, numbers, underscores and hyphens")
        if database_enabled:
            if database_url is None or not database_url.startswith(("http://", "https://")):
                raise ConfigurationError("database.url must be an http:// or https:// URL when database is enabled")
            if database_token is None:
                raise ConfigurationError("database.token is required when database is enabled")

        return cls(
            log_level=log_level,
            grid=GridSettings(
                import_power_entity=grid_import,
                export_power_entity=grid_export,
            ),
            ess=EssSettings(
                soc_entity=_optional_entity_id(ess_raw.get("soc_entity"), "ess.soc_entity"),
                power_entity=_optional_entity_id(ess_raw.get("power_entity"), "ess.power_entity"),
                power_positive_means=ess_power_sign,
            ),
            pv=PvSettings(
                solax_power_entity=_optional_entity_id(
                    pv_raw.get("solax_power_entity"), "pv.solax_power_entity"
                ),
                shed_power_entity=_optional_entity_id(
                    pv_raw.get("shed_power_entity"), "pv.shed_power_entity"
                ),
                forecast_enabled=_bool_option(
                    pv_raw.get("forecast_enabled", True),
                    "pv.forecast_enabled",
                ),
            ),
            ev=EvSettings(
                soc_entity=_optional_entity_id(ev_raw.get("soc_entity"), "ev.soc_entity"),
                connected_entity=_optional_entity_id(
                    ev_raw.get("connected_entity"), "ev.connected_entity"
                ),
                charging_power_entity=_optional_entity_id(
                    ev_raw.get("charging_power_entity"), "ev.charging_power_entity"
                ),
            ),
            database=DatabaseSettings(
                enabled=database_enabled,
                url=database_url.rstrip("/") if database_url else None,
                database=database_name,
                token=database_token,
            ),
            legacy_options_detected=legacy_options_detected,
        )


def _mapping(value: object, option_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigurationError(f"{option_name} must be a configuration group")
    return value


def _optional_entity_id(value: object, option_name: str) -> str | None:
    """Normalize and validate an optional Home Assistant entity ID."""
    if value is None:
        return None

    entity_id = str(value).strip()
    if not entity_id:
        return None
    if not _ENTITY_ID_RE.fullmatch(entity_id):
        raise ConfigurationError(f"Invalid Home Assistant entity ID for {option_name}: {entity_id!r}")
    return entity_id


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _bool_option(value: object, option_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ConfigurationError(f"{option_name} must be true or false")


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
