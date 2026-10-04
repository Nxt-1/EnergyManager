"""Diagnostic state publication into Home Assistant."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from . import __version__
from .ha_client import HomeAssistantClient
from .house_state import HouseState, InputReading
from .open_meteo import FORECAST_DAYS, FORECAST_MODEL
from .pv_forecast import CALIBRATION_VERSION, PvDailyEnergy, PvForecast

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
HOUSE_LOAD_POWER_ENTITY = "sensor.energy_manager_house_load_power"
KNOWN_CONTROLLABLE_LOAD_POWER_ENTITY = "sensor.energy_manager_known_controllable_load_power"
BACKGROUND_LOAD_POWER_ENTITY = "sensor.energy_manager_background_load_power"
PV_FORECAST_STATUS_ENTITY = "sensor.energy_manager_pv_forecast_status"
PV_FORECAST_TODAY_ENTITY = "sensor.energy_manager_pv_forecast_today_energy"
PV_FORECAST_TOMORROW_ENTITY = "sensor.energy_manager_pv_forecast_tomorrow_energy"
PV_FORECAST_NEXT_HOUR_ENTITY = "sensor.energy_manager_pv_forecast_next_hour_power"
PV_FORECAST_NEXT_7_DAYS_ENTITY = "sensor.energy_manager_pv_forecast_next_7_days_energy"

LEGACY_ENTITIES = (
    "sensor.energy_manager_observed_grid_power",
    "sensor.energy_manager_pv_day_ahead_today_energy",
    "sensor.energy_manager_pv_day_ahead_tomorrow_energy",
)

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
    """Publish read-only normalized house-state and forecast diagnostics."""

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
        """Publish derived power-balance values from the canonical house state."""
        await self._publish_grid_net(house_state)
        await self._publish_pv_total(house_state)
        await self._publish_house_load(house_state)
        await self._publish_known_controllable_load(house_state)
        await self._publish_background_load(house_state)

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

    async def publish_pv_forecast_status(
        self,
        status: str,
        *,
        generated_at_utc: datetime | None = None,
        error: str | None = None,
    ) -> None:
        """Publish independent health for the external PV predictor."""
        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager PV Forecast Status",
            "model": "Open-Meteo KNMI Seamless (HARMONIE AROME + ECMWF)",
            "model_id": FORECAST_MODEL,
            "forecast_days_requested": FORECAST_DAYS,
            "calibration_version": CALIBRATION_VERSION,
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if generated_at_utc is not None:
            attributes["forecast_generated_at_utc"] = generated_at_utc.isoformat()
        if error:
            attributes["error"] = error
        await self._client.set_state(PV_FORECAST_STATUS_ENTITY, status, attributes)

    async def publish_pv_forecast(
        self,
        forecast: PvForecast,
        *,
        now_local: datetime,
    ) -> None:
        """Publish compact forecast summaries while retaining full hourly data in Python."""
        today = forecast.daily_energy(now_local.date())
        tomorrow = forecast.daily_energy(now_local.date() + timedelta(days=1))
        await self._publish_pv_daily(PV_FORECAST_TODAY_ENTITY, "PV Forecast Today", today, forecast)
        await self._publish_pv_daily(
            PV_FORECAST_TOMORROW_ENTITY,
            "PV Forecast Tomorrow",
            tomorrow,
            forecast,
        )
        await self._publish_pv_next_7_days(forecast, now_local)
        await self._publish_pv_next_hour(forecast, now_local)

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

    async def _publish_house_load(self, house_state: HouseState) -> None:
        attributes = _power_attributes("Energy Manager House Load Power")
        attributes.update(
            {
                "positive_means": "consumption",
                "formula": "grid_net + solax_ac_pv + ess_ac_power",
                "shed_pv_handling": "excluded because shed MPPT is DC-coupled; AC effect is in ESS power",
            }
        )
        value = house_state.house_load_power_w
        if value is None:
            attributes["error"] = "Required configured power-balance inputs are not valid/fresh"
            await self._client.set_state(HOUSE_LOAD_POWER_ENTITY, "unavailable", attributes)
            return
        await self._client.set_state(HOUSE_LOAD_POWER_ENTITY, round(value, 3), attributes)

    async def _publish_known_controllable_load(self, house_state: HouseState) -> None:
        attributes = _power_attributes("Energy Manager Known Controllable Load Power")
        attributes.update(
            {
                "positive_means": "consumption",
                "included_loads": ["ev.charging_power"],
            }
        )
        value = house_state.known_controllable_load_power_w
        if value is None:
            attributes["error"] = "A configured controllable-load input is not valid/fresh"
            await self._client.set_state(KNOWN_CONTROLLABLE_LOAD_POWER_ENTITY, "unavailable", attributes)
            return
        await self._client.set_state(KNOWN_CONTROLLABLE_LOAD_POWER_ENTITY, round(value, 3), attributes)

    async def _publish_background_load(self, house_state: HouseState) -> None:
        attributes = _power_attributes("Energy Manager Background Load Power")
        attributes.update(
            {
                "positive_means": "consumption",
                "formula": "house_load - known_controllable_load",
            }
        )
        value = house_state.background_load_power_w
        if value is None:
            attributes["error"] = "House load or controllable-load power is not available"
            await self._client.set_state(BACKGROUND_LOAD_POWER_ENTITY, "unavailable", attributes)
            return
        await self._client.set_state(BACKGROUND_LOAD_POWER_ENTITY, round(value, 3), attributes)

    async def _publish_pv_daily(
        self,
        entity_id: str,
        friendly_name: str,
        daily: PvDailyEnergy | None,
        forecast: PvForecast,
    ) -> None:
        attributes = _energy_attributes(friendly_name)
        attributes.update(
            {
                "forecast_generated_at_utc": forecast.generated_at_utc.isoformat(),
                "calibration_version": CALIBRATION_VERSION,
            }
        )
        if daily is None:
            await self._client.set_state(entity_id, "unavailable", attributes)
            return
        attributes.update(_group_energy_attributes(daily))
        await self._client.set_state(entity_id, round(daily.total_kwh, 3), attributes)

    async def _publish_pv_next_7_days(self, forecast: PvForecast, now_local: datetime) -> None:
        attributes = _energy_attributes("Energy Manager PV Forecast Next 7 Days")
        attributes.update(
            {
                "forecast_generated_at_utc": forecast.generated_at_utc.isoformat(),
                "calibration_version": CALIBRATION_VERSION,
            }
        )
        daily = []
        for offset in range(1, 8):
            item = forecast.daily_energy(now_local.date() + timedelta(days=offset))
            if item is not None:
                daily.append(item)

        if not daily:
            await self._client.set_state(PV_FORECAST_NEXT_7_DAYS_ENTITY, "unavailable", attributes)
            return

        attributes.update(
            {
                "start_date": daily[0].target_date.isoformat(),
                "end_date": daily[-1].target_date.isoformat(),
                "days_available": len(daily),
                "complete": len(daily) == 7,
                "days": [
                    {
                        "date": item.target_date.isoformat(),
                        "front_kwh": round(item.front_kwh, 3),
                        "rear_kwh": round(item.rear_kwh, 3),
                        "shed_kwh": round(item.shed_kwh, 3),
                        "total_kwh": round(item.total_kwh, 3),
                    }
                    for item in daily
                ],
            }
        )
        total_kwh = sum(item.total_kwh for item in daily)
        await self._client.set_state(PV_FORECAST_NEXT_7_DAYS_ENTITY, round(total_kwh, 3), attributes)

    async def _publish_pv_next_hour(self, forecast: PvForecast, now_local: datetime) -> None:
        point = forecast.next_hour(now_local)
        attributes = _power_attributes("Energy Manager PV Forecast Next Hour Power")
        attributes["calibration_version"] = CALIBRATION_VERSION
        if point is None:
            await self._client.set_state(PV_FORECAST_NEXT_HOUR_ENTITY, "unavailable", attributes)
            return
        attributes.update(
            {
                "period_end_local": point.period_end_local.isoformat(),
                "front_power_w": round(point.front_power_w, 1),
                "rear_power_w": round(point.rear_power_w, 1),
                "shed_power_w": round(point.shed_power_w, 1),
                "raw_front_power_w": round(point.front_raw_power_w, 1),
                "raw_rear_power_w": round(point.rear_raw_power_w, 1),
                "raw_shed_power_w": round(point.shed_raw_power_w, 1),
                "cloud_cover_pct": point.cloud_cover_pct,
                "direct_radiation_wm2": point.direct_radiation_wm2,
                "diffuse_radiation_wm2": point.diffuse_radiation_wm2,
            }
        )
        await self._client.set_state(PV_FORECAST_NEXT_HOUR_ENTITY, round(point.total_power_w, 1), attributes)


def _power_attributes(friendly_name: str) -> dict[str, Any]:
    return {
        "friendly_name": friendly_name,
        "unit_of_measurement": "W",
        "device_class": "power",
        "state_class": "measurement",
        "last_update_utc": datetime.now(UTC).isoformat(),
    }


def _energy_attributes(friendly_name: str) -> dict[str, Any]:
    return {
        "friendly_name": friendly_name,
        "unit_of_measurement": "kWh",
        "last_update_utc": datetime.now(UTC).isoformat(),
    }


def _group_energy_attributes(daily: PvDailyEnergy) -> dict[str, Any]:
    return {
        "target_date": daily.target_date.isoformat(),
        "front_kwh": round(daily.front_kwh, 3),
        "rear_kwh": round(daily.rear_kwh, 3),
        "shed_kwh": round(daily.shed_kwh, 3),
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
