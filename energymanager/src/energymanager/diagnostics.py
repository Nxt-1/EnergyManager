"""Diagnostic state publication into Home Assistant."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from . import __version__
from .actuators import ACTUATOR_VERSION, ActuatorSnapshot, EssActuatorSnapshot, EvActuatorSnapshot
from .ha_client import HomeAssistantClient
from .house_state import HouseState, InputReading
from .load_backtest import BACKTEST_VERSION, BackgroundLoadBacktest
from .load_forecast import MODEL_VERSION, BackgroundLoadForecast
from .open_meteo import FORECAST_DAYS, FORECAST_MODEL
from .planner import PLANNER_HORIZON_HOURS, PLANNER_VERSION, ShadowPlan
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
BACKGROUND_LOAD_FORECAST_STATUS_ENTITY = "sensor.energy_manager_background_load_forecast_status"
BACKGROUND_LOAD_FORECAST_NEXT_HOUR_ENTITY = "sensor.energy_manager_background_load_forecast_next_hour_power"
BACKGROUND_LOAD_FORECAST_NEXT_24_HOURS_ENTITY = "sensor.energy_manager_background_load_forecast_next_24_hours_energy"
BACKGROUND_LOAD_FORECAST_NEXT_7_DAYS_ENTITY = "sensor.energy_manager_background_load_forecast_next_7_days_energy"
BACKGROUND_LOAD_BACKTEST_ENTITY = "sensor.energy_manager_background_load_backtest"
PV_FORECAST_STATUS_ENTITY = "sensor.energy_manager_pv_forecast_status"
PV_FORECAST_TODAY_ENTITY = "sensor.energy_manager_pv_forecast_today_energy"
PV_FORECAST_TOMORROW_ENTITY = "sensor.energy_manager_pv_forecast_tomorrow_energy"
PV_FORECAST_NEXT_HOUR_ENTITY = "sensor.energy_manager_pv_forecast_next_hour_power"
PV_FORECAST_NEXT_7_DAYS_ENTITY = "sensor.energy_manager_pv_forecast_next_7_days_energy"
DATABASE_STATUS_ENTITY = "sensor.energy_manager_database_status"
SHADOW_PLAN_STATUS_ENTITY = "sensor.energy_manager_shadow_plan_status"
SHADOW_PLAN_NET_DEFICIT_ENTITY = "sensor.energy_manager_shadow_plan_next_24_hours_net_deficit_energy"
SHADOW_PLAN_GRID_IMPORT_ENTITY = "sensor.energy_manager_shadow_plan_next_24_hours_grid_import_energy"
ACTUATOR_STATUS_ENTITY = "sensor.energy_manager_actuator_status"

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


    async def publish_database_status(
        self,
        status: str,
        *,
        database: str | None = None,
        url: str | None = None,
        error: str | None = None,
        migrated_pv_rows: int | None = None,
        migrated_load_rows: int | None = None,
        migrated_load_forecast_rows: int | None = None,
        legacy_backfill_status: str | None = None,
        legacy_backfill_source_rows: int | None = None,
        legacy_backfill_sources_updated: int | None = None,
        legacy_backfill_house_rows: int | None = None,
        legacy_backfill_background_rows: int | None = None,
        legacy_backfill_skipped_rows: int | None = None,
        legacy_backfill_start_utc: str | None = None,
        legacy_backfill_end_utc: str | None = None,
        legacy_backfill_error: str | None = None,
    ) -> None:
        """Publish health for optional InfluxDB 3 persistence without exposing credentials."""
        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager Database Status",
            "backend": "InfluxDB 3",
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if database is not None:
            attributes["database"] = database
        if url is not None:
            attributes["url"] = url
        if migrated_pv_rows is not None:
            attributes["migrated_pv_forecast_rows"] = migrated_pv_rows
        if migrated_load_rows is not None:
            attributes["migrated_background_load_rows"] = migrated_load_rows
        if migrated_load_forecast_rows is not None:
            attributes["migrated_background_forecast_rows"] = migrated_load_forecast_rows
        if legacy_backfill_status is not None:
            attributes["legacy_backfill_status"] = legacy_backfill_status
        if legacy_backfill_source_rows is not None:
            attributes["legacy_backfill_source_rows"] = legacy_backfill_source_rows
        if legacy_backfill_sources_updated is not None:
            attributes["legacy_backfill_sources_updated"] = legacy_backfill_sources_updated
        if legacy_backfill_house_rows is not None:
            attributes["legacy_backfill_house_rows"] = legacy_backfill_house_rows
        if legacy_backfill_background_rows is not None:
            attributes["legacy_backfill_background_rows"] = legacy_backfill_background_rows
        if legacy_backfill_skipped_rows is not None:
            attributes["legacy_backfill_skipped_rows"] = legacy_backfill_skipped_rows
        if legacy_backfill_start_utc is not None:
            attributes["legacy_backfill_start_utc"] = legacy_backfill_start_utc
        if legacy_backfill_end_utc is not None:
            attributes["legacy_backfill_end_utc"] = legacy_backfill_end_utc
        if legacy_backfill_error is not None:
            attributes["legacy_backfill_error"] = legacy_backfill_error
        if error:
            attributes["error"] = error
        await self._client.set_state(DATABASE_STATUS_ENTITY, status, attributes)


    async def publish_background_load_forecast_status(
        self,
        status: str,
        *,
        forecast: BackgroundLoadForecast | None = None,
        error: str | None = None,
    ) -> None:
        """Publish health and learning progress for the background-load predictor."""
        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager Background Load Forecast Status",
            "model": "Local 15-minute time-of-day baseline",
            "model_version": MODEL_VERSION,
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if forecast is not None:
            attributes.update(
                {
                    "forecast_generated_at_utc": forecast.generated_at_utc.isoformat(),
                    "history_sample_count": forecast.history_sample_count,
                    "history_days": round(forecast.history_days, 3),
                }
            )
        if error:
            attributes["error"] = error
        await self._client.set_state(BACKGROUND_LOAD_FORECAST_STATUS_ENTITY, status, attributes)

    async def publish_background_load_forecast(
        self,
        forecast: BackgroundLoadForecast,
        *,
        now_local: datetime,
    ) -> None:
        """Publish compact summaries while keeping the 15-minute forecast in Python."""
        common = {
            "forecast_generated_at_utc": forecast.generated_at_utc.isoformat(),
            "model_version": MODEL_VERSION,
            "model_stage": forecast.model_stage,
            "history_sample_count": forecast.history_sample_count,
            "history_days": round(forecast.history_days, 3),
        }

        next_hour = forecast.next_hour_average_power_w()
        attributes = _power_attributes("Energy Manager Background Load Forecast Next Hour Power")
        attributes.update(common)
        if forecast.points:
            attributes["window_start_local"] = forecast.points[0].period_start_local.isoformat()
            attributes["window_end_local"] = (
                forecast.points[min(3, len(forecast.points) - 1)].period_start_local + timedelta(minutes=15)
            ).isoformat()
            attributes["methods"] = sorted({point.method for point in forecast.points[:4]})
        await self._client.set_state(
            BACKGROUND_LOAD_FORECAST_NEXT_HOUR_ENTITY,
            "unavailable" if next_hour is None else round(next_hour, 1),
            attributes,
        )

        next_24 = forecast.next_24_hours_energy_kwh()
        attributes = _energy_attributes("Energy Manager Background Load Forecast Next 24 Hours")
        attributes.update(common)
        await self._client.set_state(
            BACKGROUND_LOAD_FORECAST_NEXT_24_HOURS_ENTITY,
            "unavailable" if next_24 is None else round(next_24, 3),
            attributes,
        )

        daily = []
        for offset in range(1, 8):
            item = forecast.daily_energy(now_local.date() + timedelta(days=offset))
            if item is not None:
                daily.append(item)
        attributes = _energy_attributes("Energy Manager Background Load Forecast Next 7 Days")
        attributes.update(common)
        if not daily:
            await self._client.set_state(BACKGROUND_LOAD_FORECAST_NEXT_7_DAYS_ENTITY, "unavailable", attributes)
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
                        "energy_kwh": round(item.energy_kwh, 3),
                    }
                    for item in daily
                ],
            }
        )
        total = sum(item.energy_kwh for item in daily)
        await self._client.set_state(BACKGROUND_LOAD_FORECAST_NEXT_7_DAYS_ENTITY, round(total, 3), attributes)

    async def publish_background_load_backtest(
        self,
        result: BackgroundLoadBacktest | None,
        *,
        error: str | None = None,
    ) -> None:
        """Publish rolling-origin load-forecast evaluation without changing the production model."""
        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager Background Load Backtest",
            "backtest_version": BACKTEST_VERSION,
            "model_version": MODEL_VERSION,
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if error is not None:
            attributes["error"] = error
            await self._client.set_state(BACKGROUND_LOAD_BACKTEST_ENTITY, "unavailable", attributes)
            return
        if result is None:
            attributes["reason"] = "insufficient_history"
            await self._client.set_state(BACKGROUND_LOAD_BACKTEST_ENTITY, "unavailable", attributes)
            return

        horizons: dict[str, Any] = {}
        for horizon in sorted({metric.horizon_hours for metric in result.metrics}):
            models = {}
            for metric in result.metrics:
                if metric.horizon_hours != horizon:
                    continue
                models[metric.model] = {
                    "total_energy_mae_kwh": (
                        None
                        if metric.total_energy_mae_kwh is None
                        else round(metric.total_energy_mae_kwh, 3)
                    ),
                    "energy_bias_kwh": (
                        None if metric.energy_bias_kwh is None else round(metric.energy_bias_kwh, 3)
                    ),
                    "timing_mismatch_kwh": (
                        None if metric.timing_mismatch_kwh is None else round(metric.timing_mismatch_kwh, 3)
                    ),
                    "peak_underprediction_w": (
                        None
                        if metric.peak_underprediction_w is None
                        else round(metric.peak_underprediction_w, 1)
                    ),
                    "p90_peak_underprediction_w": (
                        None
                        if metric.p90_peak_underprediction_w is None
                        else round(metric.p90_peak_underprediction_w, 1)
                    ),
                    "mae_w": round(metric.mae_w, 1),
                    "bias_w": round(metric.bias_w, 1),
                    "p90_abs_error_w": round(metric.p90_abs_error_w, 1),
                    "points": metric.points,
                    "issue_count": metric.issue_count,
                    "coverage": round(metric.coverage, 3),
                    "issue_coverage": round(metric.issue_coverage, 3),
                }
            horizons[f"{horizon}h"] = {
                "best_model": result.best_by_horizon.get(horizon),
                "best_model_basis": "total_energy_mae_kwh",
                "best_power_model": result.best_power_by_horizon.get(horizon),
                "models": models,
            }

        attributes.update(
            {
                "generated_at_utc": result.generated_at_utc.isoformat(),
                "evaluation_start_local": result.evaluation_start_local.isoformat(),
                "evaluation_end_local": result.evaluation_end_local.isoformat(),
                "issue_count": result.issue_count,
                "comparison_basis": "common_valid_intervals",
                "horizons": horizons,
                "current_model_dayparts": {
                    name: {
                        "mae_w": round(item.mae_w, 1),
                        "bias_w": round(item.bias_w, 1),
                        "p90_abs_error_w": round(item.p90_abs_error_w, 1),
                        "points": item.points,
                    }
                    for name, item in result.daypart_breakdown.items()
                },
                "current_model_daytypes": {
                    name: {
                        "mae_w": round(item.mae_w, 1),
                        "bias_w": round(item.bias_w, 1),
                        "p90_abs_error_w": round(item.p90_abs_error_w, 1),
                        "points": item.points,
                    }
                    for name, item in result.daytype_breakdown.items()
                },
            }
        )
        current_24h = result.metric("energy_manager", 24)
        state: str | float = "unavailable"
        if current_24h is not None and current_24h.total_energy_mae_kwh is not None:
            state = round(current_24h.total_energy_mae_kwh, 3)
        attributes["primary_metric"] = "24h total-energy MAE"
        attributes["unit_of_measurement"] = "kWh"
        await self._client.set_state(BACKGROUND_LOAD_BACKTEST_ENTITY, state, attributes)

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


    async def publish_actuator_status(self, actuators: tuple[ActuatorSnapshot, ...]) -> None:
        """Publish the read-only actuator catalog used by the planner."""
        configured = [item for item in actuators if item.configured]
        available = [item for item in configured if item.planning_available]
        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager Actuator Status",
            "actuator_version": ACTUATOR_VERSION,
            "shadow_mode": True,
            "control_enabled": False,
            "configured_count": len(configured),
            "planning_available_count": len(available),
            "actuators": [_actuator_attributes(item) for item in actuators],
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        state = "ready" if configured else "not_configured"
        await self._client.set_state(ACTUATOR_STATUS_ENTITY, state, attributes)

    async def publish_shadow_plan_status(self, status: str, *, error: str | None = None) -> None:
        """Publish planner readiness without implying that any control is active."""
        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager Shadow Plan Status",
            "planner_version": PLANNER_VERSION,
            "shadow_mode": True,
            "control_enabled": False,
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if error:
            attributes["error"] = error
        await self._client.set_state(SHADOW_PLAN_STATUS_ENTITY, status, attributes)

    async def publish_shadow_plan(self, plan: ShadowPlan) -> None:
        """Publish compact summaries for the current read-only shadow plan."""
        summary_24h = plan.summary(24)
        summary_48h = plan.summary(48)
        status_attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager Shadow Plan Status",
            "planner_version": PLANNER_VERSION,
            "shadow_mode": True,
            "control_enabled": False,
            "mode": "forecast_balance_with_actuator_projection",
            "horizon_hours": PLANNER_HORIZON_HOURS,
            "generated_at_utc": plan.generated_at_utc.isoformat(),
            "ess_projection_status": plan.ess_projection_status,
            "actuator_ids": [item.actuator_id for item in plan.actuator_snapshots],
            "next_24_hours": _rounded_summary(summary_24h),
            "next_48_hours": _rounded_summary(summary_48h),
            "next_intervals": [
                {
                    "start": item.period_start_local.isoformat(),
                    "background_w": round(item.background_load_w, 1),
                    "scheduled_w": round(item.scheduled_load_w, 1),
                    "pv_ac_w": round(item.pv_ac_power_w, 1),
                    "pv_dc_w": round(item.pv_dc_power_w, 1),
                    "pv_potential_w": round(item.pv_power_w, 1),
                    "net_before_control_w": round(item.net_power_before_control_w, 1),
                    "ess_ac_w": _round_optional(item.ess_ac_power_w, 1),
                    "projected_soc_percent": _round_optional(item.projected_soc_percent, 2),
                    "grid_after_ess_w": _round_optional(item.grid_power_after_ess_w, 1),
                    "curtailed_dc_pv_w": _round_optional(item.curtailed_dc_pv_w, 1),
                }
                for item in plan.intervals[:12]
            ],
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if plan.ess_resource is not None:
            status_attributes["ess_resource"] = {
                "initial_soc_percent": _round_optional(plan.ess_initial_soc_percent, 2),
                "capacity_kwh": round(plan.ess_resource.capacity_kwh, 3),
                "min_soc_percent": round(plan.ess_resource.min_soc_percent, 2),
                "max_soc_percent": round(plan.ess_resource.max_soc_percent, 2),
                "max_charge_power_w": round(plan.ess_resource.max_charge_power_w, 1),
                "max_discharge_power_w": round(plan.ess_resource.max_discharge_power_w, 1),
                "charge_efficiency": round(plan.ess_resource.charge_efficiency, 4),
                "discharge_efficiency": round(plan.ess_resource.discharge_efficiency, 4),
            }
        await self._client.set_state(SHADOW_PLAN_STATUS_ENTITY, "ready", status_attributes)

        energy_attributes = _energy_attributes("Energy Manager Shadow Plan Next 24 Hours Net Deficit")
        energy_attributes.update(
            {
                "planner_version": PLANNER_VERSION,
                "background_load_kwh": round(float(summary_24h["background_load_kwh"]), 3),
                "scheduled_load_kwh": round(float(summary_24h["scheduled_load_kwh"]), 3),
                "pv_potential_kwh": round(float(summary_24h["pv_potential_kwh"]), 3),
                "net_surplus_kwh": round(float(summary_24h["net_surplus_kwh"]), 3),
                "max_net_deficit_w": round(float(summary_24h["max_net_deficit_w"]), 1),
                "meaning": "raw forecast deficit before ESS, EV or other flexible-load scheduling",
            }
        )
        await self._client.set_state(
            SHADOW_PLAN_NET_DEFICIT_ENTITY,
            round(float(summary_24h["net_deficit_kwh"]), 3),
            energy_attributes,
        )

        grid_import_attributes = _energy_attributes("Energy Manager Shadow Plan Next 24 Hours Grid Import")
        grid_import_attributes.update(
            {
                "planner_version": PLANNER_VERSION,
                "ess_projection_status": plan.ess_projection_status,
                "meaning": "projected grid import after the read-only ESS self-consumption baseline",
            }
        )
        grid_import = summary_24h["grid_import_after_ess_kwh"]
        if isinstance(grid_import, (int, float)):
            grid_import_attributes.update(
                {
                    "grid_export_after_ess_kwh": _round_optional(
                        _optional_number(summary_24h["grid_export_after_ess_kwh"]), 3
                    ),
                    "curtailed_dc_pv_kwh": _round_optional(
                        _optional_number(summary_24h["curtailed_dc_pv_kwh"]), 3
                    ),
                    "end_soc_percent": _round_optional(_optional_number(summary_24h["end_soc_percent"]), 2),
                    "max_grid_import_after_ess_w": _round_optional(
                        _optional_number(summary_24h["max_grid_import_after_ess_w"]), 1
                    ),
                }
            )
            await self._client.set_state(
                SHADOW_PLAN_GRID_IMPORT_ENTITY,
                round(float(grid_import), 3),
                grid_import_attributes,
            )
        else:
            await self._client.set_state(SHADOW_PLAN_GRID_IMPORT_ENTITY, "unavailable", grid_import_attributes)

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



def _rounded_summary(
    summary: dict[str, float | int | str | None],
) -> dict[str, float | int | str | None]:
    rounded: dict[str, float | int | str | None] = {}
    for key, value in summary.items():
        if isinstance(value, float):
            rounded[key] = round(value, 3)
        else:
            rounded[key] = value
    return rounded


def _actuator_attributes(item: ActuatorSnapshot) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": item.actuator_id,
        "kind": item.kind,
        "configured": item.configured,
        "planning_available": item.planning_available,
        "status": item.status,
        "control_enabled": item.control_enabled,
    }
    if isinstance(item, EssActuatorSnapshot):
        base.update(
            {
                "soc_percent": _round_optional(item.soc_percent, 2),
                "current_power_w": _round_optional(item.current_power_w, 1),
                "capacity_kwh": round(item.capabilities.capacity_kwh, 3),
                "min_soc_percent": round(item.capabilities.min_soc_percent, 2),
                "max_soc_percent": round(item.capabilities.max_soc_percent, 2),
                "max_charge_power_w": round(item.capabilities.max_charge_power_w, 1),
                "max_discharge_power_w": round(item.capabilities.max_discharge_power_w, 1),
            }
        )
        return base
    if isinstance(item, EvActuatorSnapshot):
        base.update(
            {
                "connected": item.connected,
                "soc_percent": _round_optional(item.soc_percent, 2),
                "current_power_w": _round_optional(item.current_power_w, 1),
                "min_charge_current_a": round(item.capabilities.min_charge_current_a, 2),
                "max_charge_current_a": round(item.capabilities.max_charge_current_a, 2),
                "nominal_voltage_v": round(item.capabilities.nominal_voltage_v, 1),
                "supports_single_phase": item.capabilities.supports_single_phase,
                "supports_three_phase": item.capabilities.supports_three_phase,
                "minimum_single_phase_power_w": _round_optional(
                    item.capabilities.minimum_single_phase_power_w, 1
                ),
                "maximum_single_phase_power_w": _round_optional(
                    item.capabilities.maximum_single_phase_power_w, 1
                ),
                "minimum_three_phase_power_w": _round_optional(
                    item.capabilities.minimum_three_phase_power_w, 1
                ),
                "maximum_three_phase_power_w": _round_optional(
                    item.capabilities.maximum_three_phase_power_w, 1
                ),
            }
        )
    return base


def _round_optional(value: float | None, digits: int) -> float | None:
    return round(value, digits) if value is not None else None


def _optional_number(value: float | int | str | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
