"""Diagnostic state publication into Home Assistant."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from . import __version__
from .ha_client import HomeAssistantClient

STATUS_ENTITY = "sensor.energy_manager_status"
GRID_IMPORT_POWER_ENTITY = "sensor.energy_manager_grid_import_power"
GRID_EXPORT_POWER_ENTITY = "sensor.energy_manager_grid_export_power"
GRID_NET_POWER_ENTITY = "sensor.energy_manager_grid_power"


class DiagnosticsPublisher:
    """Publish read-only Energy Manager status and normalized grid measurements."""

    def __init__(
        self,
        client: HomeAssistantClient,
        source_import_entity: str | None,
        source_export_entity: str | None,
    ) -> None:
        self._client = client
        self._source_import_entity = source_import_entity
        self._source_export_entity = source_export_entity

    async def publish_status(self, status: str, *, error: str | None = None) -> None:
        """Publish Energy Manager connectivity/status information."""
        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager Status",
            "version": __version__,
            "shadow_mode": True,
            "grid_import_power_entity": self._source_import_entity,
            "grid_export_power_entity": self._source_export_entity,
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if error:
            attributes["error"] = error

        await self._client.set_state(STATUS_ENTITY, status, attributes)

    async def publish_grid_import_power(self, power_w: float, source_state: dict[str, Any]) -> None:
        """Publish normalized grid import power."""
        await self._publish_source_power(
            GRID_IMPORT_POWER_ENTITY,
            "Energy Manager Grid Import Power",
            power_w,
            self._source_import_entity,
            source_state,
        )

    async def publish_grid_export_power(self, power_w: float, source_state: dict[str, Any]) -> None:
        """Publish normalized grid export power."""
        await self._publish_source_power(
            GRID_EXPORT_POWER_ENTITY,
            "Energy Manager Grid Export Power",
            power_w,
            self._source_export_entity,
            source_state,
        )

    async def publish_grid_power(
        self,
        power_w: float,
        import_state: dict[str, Any],
        export_state: dict[str, Any],
    ) -> None:
        """Publish canonical net grid power: positive import, negative export."""
        attributes = self._power_attributes("Energy Manager Grid Power")
        attributes.update(
            {
                "positive_means": "import",
                "negative_means": "export",
                "source_import_entity": self._source_import_entity,
                "source_export_entity": self._source_export_entity,
                "source_import_last_updated": import_state.get("last_updated"),
                "source_export_last_updated": export_state.get("last_updated"),
            }
        )
        await self._client.set_state(GRID_NET_POWER_ENTITY, round(power_w, 3), attributes)

    async def publish_import_unavailable(self, reason: str, source_state: dict[str, Any] | None = None) -> None:
        """Mark the normalized grid-import diagnostic as unavailable."""
        await self._publish_unavailable(
            GRID_IMPORT_POWER_ENTITY,
            "Energy Manager Grid Import Power",
            self._source_import_entity,
            reason,
            source_state,
        )

    async def publish_export_unavailable(self, reason: str, source_state: dict[str, Any] | None = None) -> None:
        """Mark the normalized grid-export diagnostic as unavailable."""
        await self._publish_unavailable(
            GRID_EXPORT_POWER_ENTITY,
            "Energy Manager Grid Export Power",
            self._source_export_entity,
            reason,
            source_state,
        )

    async def publish_grid_power_unavailable(self, reason: str) -> None:
        """Mark canonical net grid power as unavailable."""
        attributes = self._power_attributes("Energy Manager Grid Power")
        attributes.update(
            {
                "positive_means": "import",
                "negative_means": "export",
                "source_import_entity": self._source_import_entity,
                "source_export_entity": self._source_export_entity,
                "error": reason,
            }
        )
        await self._client.set_state(GRID_NET_POWER_ENTITY, "unavailable", attributes)

    async def _publish_source_power(
        self,
        entity_id: str,
        friendly_name: str,
        power_w: float,
        source_entity: str | None,
        source_state: dict[str, Any],
    ) -> None:
        attributes = self._power_attributes(friendly_name)
        attributes.update(
            {
                "source_entity": source_entity,
                "source_last_updated": source_state.get("last_updated"),
            }
        )
        await self._client.set_state(entity_id, round(power_w, 3), attributes)

    async def _publish_unavailable(
        self,
        entity_id: str,
        friendly_name: str,
        source_entity: str | None,
        reason: str,
        source_state: dict[str, Any] | None,
    ) -> None:
        attributes = self._power_attributes(friendly_name)
        attributes.update(
            {
                "source_entity": source_entity,
                "source_last_updated": (source_state or {}).get("last_updated"),
                "error": reason,
            }
        )
        await self._client.set_state(entity_id, "unavailable", attributes)

    @staticmethod
    def _power_attributes(friendly_name: str) -> dict[str, Any]:
        return {
            "friendly_name": friendly_name,
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement",
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
