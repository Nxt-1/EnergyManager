"""Configuration loading for the Home Assistant app."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_OPTIONS_PATH = Path("/data/options.json")
_ENTITY_ID_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
_VALID_LOG_LEVELS = {"debug", "info", "warning", "error"}


class ConfigurationError(ValueError):
    """Raised when app configuration is invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings exposed by the Home Assistant app configuration."""

    log_level: str = "info"
    grid_import_power_entity: str | None = None
    grid_export_power_entity: str | None = None

    @property
    def grid_power_configured(self) -> bool:
        """Return whether both grid power inputs have been configured."""
        return self.grid_import_power_entity is not None and self.grid_export_power_entity is not None

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

        grid_import_power_entity = _optional_entity_id(raw.get("grid_import_power_entity"), "grid_import_power_entity")
        grid_export_power_entity = _optional_entity_id(raw.get("grid_export_power_entity"), "grid_export_power_entity")

        if (
            grid_import_power_entity is not None
            and grid_export_power_entity is not None
            and grid_import_power_entity == grid_export_power_entity
        ):
            raise ConfigurationError("grid_import_power_entity and grid_export_power_entity must be different entities")

        return cls(
            log_level=log_level,
            grid_import_power_entity=grid_import_power_entity,
            grid_export_power_entity=grid_export_power_entity,
        )


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
