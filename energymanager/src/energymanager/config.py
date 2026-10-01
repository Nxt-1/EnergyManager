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
    grid_power_entity: str | None = None

    @classmethod
    def load(cls, path: Path = _OPTIONS_PATH) -> "Settings":
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

        grid_power_entity = raw.get("grid_power_entity")
        if grid_power_entity is not None:
            grid_power_entity = str(grid_power_entity).strip()
            if not grid_power_entity:
                grid_power_entity = None
            elif not _ENTITY_ID_RE.fullmatch(grid_power_entity):
                raise ConfigurationError(f"Invalid Home Assistant entity ID: {grid_power_entity!r}")

        return cls(log_level=log_level, grid_power_entity=grid_power_entity)
