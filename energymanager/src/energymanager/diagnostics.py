"""Diagnostic state publication into Home Assistant."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from . import __version__
from .ha_client import HomeAssistantClient

STATUS_ENTITY = "sensor.energy_manager_status"
GRID_POWER_ENTITY = "sensor.energy_manager_observed_grid_power"


class DiagnosticsPublisher:
    """Publish the minimum diagnostic states used by the first shadow-mode release."""

    def __init__(self, client: HomeAssistantClient, source_grid_entity: str | None) -> None:
        self._client = client
        self._source_grid_entity = source_grid_entity

    async def publish_status(self, status: str, *, error: str | None = None) -> None:
        """Publish Energy Manager connectivity/status information."""
        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager Status",
            "version": __version__,
            "shadow_mode": True,
            "grid_power_entity": self._source_grid_entity,
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if error:
            attributes["error"] = error

        await self._client.set_state(STATUS_ENTITY, status, attributes)

    async def publish_grid_power(self, power_w: float, source_state: dict[str, Any]) -> None:
        """Publish the observed grid power normalized to watts."""
        attributes = {
            "friendly_name": "Energy Manager Observed Grid Power",
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement",
            "source_entity": self._source_grid_entity,
            "source_last_updated": source_state.get("last_updated"),
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        await self._client.set_state(GRID_POWER_ENTITY, round(power_w, 3), attributes)
