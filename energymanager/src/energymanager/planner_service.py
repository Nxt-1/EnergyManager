"""Runtime coordinator for the read-only shadow planner."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from .diagnostics import DiagnosticsPublisher
from .house_state import HouseState
from .load_service import BackgroundLoadService
from .planner import ShadowPlan, ShadowPlanner
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
        planner: ShadowPlanner | None = None,
    ) -> None:
        self._diagnostics = DiagnosticsPublisher(ha_client)
        self._load_service = load_service
        self._pv_service = pv_service
        self._planner = planner or ShadowPlanner()
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
        """Refresh the plan when forecasts are available; house state is reserved for upcoming resources."""
        del house_state
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

        plan = self._planner.build(load_forecast, pv_forecast, now_utc=now)
        self._plan = plan
        self._last_plan_at_utc = now
        await self._diagnostics.publish_shadow_plan(plan)

        summary = plan.summary(24)
        _LOGGER.info(
            "Shadow plan updated: next 24 h background %.2f kWh, PV potential %.2f kWh, "
            "net deficit %.2f kWh, net surplus %.2f kWh",
            summary["background_load_kwh"],
            summary["pv_potential_kwh"],
            summary["net_deficit_kwh"],
            summary["net_surplus_kwh"],
        )
