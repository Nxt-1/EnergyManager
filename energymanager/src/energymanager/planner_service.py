"""Runtime coordinator for the read-only shadow planner."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from .config import EssSettings
from .diagnostics import DiagnosticsPublisher
from .house_state import HouseState
from .load_service import BackgroundLoadService
from .planner import EssResource, ShadowPlan, ShadowPlanner
from .pv_service import PvForecastService

_LOGGER = logging.getLogger(__name__)
_REFRESH_INTERVAL = timedelta(minutes=1)


class ShadowPlannerService:
    """Build and publish a forecast plan without commanding any device."""

    def __init__(
        self,
        ha_client,
        load_service: BackgroundLoadService,
        pv_service: PvForecastService | None,
        *,
        ess_settings: EssSettings | None = None,
        planner: ShadowPlanner | None = None,
    ) -> None:
        self._diagnostics = DiagnosticsPublisher(ha_client)
        self._load_service = load_service
        self._pv_service = pv_service
        self._planner = planner or ShadowPlanner()
        self._ess_settings = ess_settings or EssSettings()
        self._ess_resource = (
            EssResource.from_settings(self._ess_settings)
            if self._ess_settings.soc_entity is not None
            else None
        )
        self._plan: ShadowPlan | None = None
        self._last_plan_at_utc: datetime | None = None

    @property
    def plan(self) -> ShadowPlan | None:
        return self._plan

    async def update_from_house_state(
        self,
        house_state: HouseState,
        *,
        now_utc: datetime | None = None,
    ) -> None:
        """Refresh the read-only plan from current forecasts and ESS SoC."""
        now = (now_utc or datetime.now(UTC)).astimezone(UTC)
        if self._last_plan_at_utc is not None and now - self._last_plan_at_utc < _REFRESH_INTERVAL:
            return

        load_forecast = self._load_service.forecast
        pv_forecast = self._pv_service.forecast if self._pv_service is not None else None
        if load_forecast is None:
            await self._diagnostics.publish_shadow_plan_status("waiting_for_load_forecast")
            return
        if pv_forecast is None:
            await self._diagnostics.publish_shadow_plan_status("waiting_for_pv_forecast")
            return

        ess_soc = house_state.value("ess.soc")
        ess_soc_percent = (
            float(ess_soc)
            if isinstance(ess_soc, (int, float)) and not isinstance(ess_soc, bool)
            else None
        )
        plan = self._planner.build(
            load_forecast,
            pv_forecast,
            now_utc=now,
            ess_resource=self._ess_resource,
            ess_soc_percent=ess_soc_percent,
        )
        self._plan = plan
        self._last_plan_at_utc = now
        await self._diagnostics.publish_shadow_plan(plan)

        summary = plan.summary(24)
        if plan.ess_projection_status == "projected":
            _LOGGER.info(
                "Shadow plan updated: next 24 h background %.2f kWh, PV potential %.2f kWh, "
                "raw deficit %.2f kWh, projected grid import %.2f kWh, ESS SoC %.1f -> %.1f%%, "
                "curtailed DC PV %.2f kWh",
                summary["background_load_kwh"],
                summary["pv_potential_kwh"],
                summary["net_deficit_kwh"],
                summary["grid_import_after_ess_kwh"],
                plan.ess_initial_soc_percent,
                summary["end_soc_percent"],
                summary["curtailed_dc_pv_kwh"],
            )
            return

        _LOGGER.info(
            "Shadow plan updated: next 24 h background %.2f kWh, PV potential %.2f kWh, "
            "net deficit %.2f kWh, net surplus %.2f kWh, ESS projection %s",
            summary["background_load_kwh"],
            summary["pv_potential_kwh"],
            summary["net_deficit_kwh"],
            summary["net_surplus_kwh"],
            plan.ess_projection_status,
        )
