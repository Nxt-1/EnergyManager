"""Diagnostic state publication into Home Assistant."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from . import __version__
from .ha_client import HomeAssistantClient
from .house_state import HouseState, InputReading

STATUS_ENTITY = "sensor.energy_manager_status"
INPUT_HEALTH_ENTITY = "sensor.energy_manager_input_health"
GRID_IMPORT_POWER_ENTITY = "sensor.energy_manager_grid_import_power"
GRID_EXPORT_POWER_ENTITY = "sensor.energy_manager_grid_export_power"
GRID_NET_POWER_ENTITY = "sensor.energy_manager_grid_power"
ESS_SOC_ENTITY = "sensor.energy_manager_ess_soc"
ESS_POWER_ENTITY = "sensor.energy_manager_ess_power"
PV_SOLAX_POWER_ENTITY = "sensor.energy_manager_pv_solax_power"
PV_SHED_POWER_ENTITY = "sensor.energy_manager_pv_shed_power"
PV_TOTAL_POWER_ENTITY = "sensor.energy_manager_pv_total_power"
EV_SOC_ENTITY = "sensor.energy_manager_ev_soc"
EV_CONNECTED_ENTITY = "binary_sensor.energy_manager_ev_connected"
EV_CHARGING_POWER_ENTITY = "sensor.energy_manager_ev_charging_power"

LEGACY_ENTITIES = ("sensor.energy_manager_observed_grid_power",)

_DIAGNOSTIC_INPUTS: dict[str, tuple[str, str, str | None, str | None]] = {
    "grid.import_power": (GRID_IMPORT_POWER_ENTITY, "Energy Manager Grid Import Power", "W", "power"),
    "grid.export_power": (GRID_EXPORT_POWER_ENTITY, "Energy Manager Grid Export Power", "W", "power"),
    "ess.soc": (ESS_SOC_ENTITY, "Energy Manager ESS SoC", "%", "battery"),
    "ess.power": (ESS_POWER_ENTITY, "Energy Manager ESS Power", "W", "power"),
    "pv.solax_power": (PV_SOLAX_POWER_ENTITY, "Energy Manager Solax PV Power", "W", "power"),
    "pv.shed_power": (PV_SHED_POWER_ENTITY, "Energy Manager Shed PV Power", "W", "power"),
    "ev.soc": (EV_SOC_ENTITY, "Energy Manager EV SoC", "%", "battery"),
    "ev.connected": (EV_CONNECTED_ENTITY, "Energy Manager EV Connected", None, "connectivity"),
    "ev.charging_power": (EV_CHARGING_POWER_ENTITY, "Energy Manager EV Charging Power", "W", "power"),
}


class DiagnosticsPublisher:
    """Publish read-only normalized house-state diagnostics."""

    def __init__(self, client: HomeAssistantClient) -> None:
        self._client = client

    async def publish_status(
        self,
        status: str,
        *,
        house_state: HouseState | None = None,
        error: str | None = None,
    ) -> None:
        """Publish Energy Manager runtime status."""
        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager Status",
            "version": __version__,
            "shadow_mode": True,
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if house_state is not None:
            attributes["configured_inputs"] = house_state.configured_count
        if error:
            attributes["error"] = error
        await self._client.set_state(STATUS_ENTITY, status, attributes)

    async def publish_reading(self, reading: InputReading) -> None:
        """Publish one configured normalized source reading."""
        if reading.entity_id is None:
            return

        diagnostic = _DIAGNOSTIC_INPUTS.get(reading.key)
        if diagnostic is None:
            return
        entity_id, friendly_name, unit, device_class = diagnostic

        attributes: dict[str, Any] = {
            "friendly_name": friendly_name,
            "source_entity": reading.entity_id,
            "input_status": reading.status.value,
            "observed_at_utc": _iso(reading.observed_at_utc),
            "source_last_updated": reading.source_last_updated,
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if unit is not None:
            attributes["unit_of_measurement"] = unit
        if device_class is not None:
            attributes["device_class"] = device_class
        if entity_id.startswith("sensor."):
            attributes["state_class"] = "measurement"
        if reading.key == "ess.power":
            attributes["positive_means"] = "discharge"
            attributes["negative_means"] = "charge"
        if reading.error:
            attributes["error"] = reading.error

        if not reading.valid or reading.value is None:
            await self._client.set_state(entity_id, "unavailable", attributes)
            return

        if isinstance(reading.value, bool):
            state: str | float = "on" if reading.value else "off"
        else:
            state = round(float(reading.value), 3)
        await self._client.set_state(entity_id, state, attributes)

    async def publish_derived(self, house_state: HouseState) -> None:
        """Publish grid-net and total-PV values derived from the canonical house state."""
        await self._publish_grid_net(house_state)
        await self._publish_pv_total(house_state)

    async def publish_input_health(self, house_state: HouseState, health: str) -> None:
        """Publish aggregate input validity/freshness information."""
        problem_readings = house_state.invalid_or_stale
        attributes = {
            "friendly_name": "Energy Manager Input Health",
            "configured_inputs": house_state.configured_count,
            "problem_inputs": [reading.key for reading in problem_readings],
            "problem_count": len(problem_readings),
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        await self._client.set_state(INPUT_HEALTH_ENTITY, health, attributes)

    async def cleanup_legacy_entities(self) -> None:
        """Remove diagnostics created by older Energy Manager releases."""
        for entity_id in LEGACY_ENTITIES:
            await self._client.delete_state(entity_id)

    async def _publish_grid_net(self, house_state: HouseState) -> None:
        import_reading = house_state.readings.get("grid.import_power")
        export_reading = house_state.readings.get("grid.export_power")
        if import_reading is None or export_reading is None:
            return
        if import_reading.entity_id is None and export_reading.entity_id is None:
            return

        attributes = _power_attributes("Energy Manager Grid Power")
        attributes.update(
            {
                "positive_means": "import",
                "negative_means": "export",
                "source_import_entity": import_reading.entity_id,
                "source_export_entity": export_reading.entity_id,
            }
        )
        value = house_state.grid_power_w
        if value is None:
            attributes["error"] = "Grid import and export inputs are not both valid/fresh"
            await self._client.set_state(GRID_NET_POWER_ENTITY, "unavailable", attributes)
            return
        await self._client.set_state(GRID_NET_POWER_ENTITY, round(value, 3), attributes)

    async def _publish_pv_total(self, house_state: HouseState) -> None:
        solax = house_state.readings.get("pv.solax_power")
        shed = house_state.readings.get("pv.shed_power")
        if not any(reading is not None and reading.entity_id is not None for reading in (solax, shed)):
            return

        attributes = _power_attributes("Energy Manager Total PV Power")
        attributes.update(
            {
                "source_solax_entity": solax.entity_id if solax else None,
                "source_shed_entity": shed.entity_id if shed else None,
            }
        )
        value = house_state.pv_total_power_w
        if value is None:
            attributes["error"] = "One or more configured PV inputs are not valid/fresh"
            await self._client.set_state(PV_TOTAL_POWER_ENTITY, "unavailable", attributes)
            return
        await self._client.set_state(PV_TOTAL_POWER_ENTITY, round(value, 3), attributes)


def _power_attributes(friendly_name: str) -> dict[str, Any]:
    return {
        "friendly_name": friendly_name,
        "unit_of_measurement": "W",
        "device_class": "power",
        "state_class": "measurement",
        "last_update_utc": datetime.now(UTC).isoformat(),
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
