"""Runtime coordinator for the read-only shadow planner."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from .actuators import ActuatorCommandResult, ActuatorPowerRequest, ActuatorRegistry
from .diagnostics import DiagnosticsPublisher
from .house_state import HouseState
from .load_service import BackgroundLoadService
from .planner import ShadowPlan, ShadowPlanner
from .pv_service import PvForecastService
from .tasks import TaskRegistry

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
        actuator_registry: ActuatorRegistry,
        task_registry: TaskRegistry,
        planner: ShadowPlanner | None = None,
    ) -> None:
        self._diagnostics = DiagnosticsPublisher(ha_client)
        self._load_service = load_service
        self._pv_service = pv_service
        self._planner = planner or ShadowPlanner()
        self._actuator_registry = actuator_registry
        self._task_registry = task_registry
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
        """Refresh the read-only plan from current forecasts and actuator snapshots."""
        now = (now_utc or datetime.now(UTC)).astimezone(UTC)
        if self._last_plan_at_utc is not None and now - self._last_plan_at_utc < _REFRESH_INTERVAL:
            return

        actuators = self._actuator_registry.snapshots(house_state)
        await self._diagnostics.publish_actuator_status(actuators)

        load_forecast = self._load_service.forecast
        pv_forecast = self._pv_service.forecast if self._pv_service is not None else None
        if load_forecast is None:
            await self._diagnostics.publish_shadow_plan_status("waiting_for_load_forecast")
            return

        local_tz = load_forecast.points[0].period_start_local.tzinfo if load_forecast.points else None
        if local_tz is None:
            local_tz = now.astimezone().tzinfo
        assert local_tz is not None
        tasks = self._task_registry.snapshots(actuators, now_utc=now, local_tz=local_tz)
        await self._diagnostics.publish_task_status(tasks)

        if pv_forecast is None:
            await self._diagnostics.publish_shadow_plan_status("waiting_for_pv_forecast")
            return

        plan = self._planner.build(
            load_forecast,
            pv_forecast,
            now_utc=now,
            actuators=actuators,
            tasks=tasks,
        )
        self._plan = plan
        self._last_plan_at_utc = now
        await self._diagnostics.publish_shadow_plan(plan)

        requests = _next_interval_requests(plan)
        command_results = self._actuator_registry.evaluate_commands(requests, house_state)
        await self._diagnostics.publish_actuator_command_status(command_results)

        summary = plan.summary(24)
        actuator_status = ", ".join(f"{item.actuator_id}:{item.status}" for item in actuators)
        task_status = ", ".join(f"{item.task_id}:{item.status}" for item in tasks)
        if plan.ess_projection_status == "projected":
            _LOGGER.info(
                "Shadow plan updated: next 24 h background %.2f kWh, PV potential %.2f kWh, "
                "raw deficit %.2f kWh, projected grid import %.2f kWh, ESS SoC %.1f -> %.1f%%, "
                "curtailed DC PV %.2f kWh, actuators [%s], tasks [%s], dry-run commands [%s]",
                summary["background_load_kwh"],
                summary["pv_potential_kwh"],
                summary["net_deficit_kwh"],
                summary["grid_import_after_ess_kwh"],
                plan.ess_initial_soc_percent,
                summary["end_soc_percent"],
                summary["curtailed_dc_pv_kwh"],
                actuator_status,
                task_status,
                _command_log(command_results),
            )
            return

        _LOGGER.info(
            "Shadow plan updated: next 24 h background %.2f kWh, PV potential %.2f kWh, "
            "net deficit %.2f kWh, net surplus %.2f kWh, ESS projection %s, actuators [%s], "
            "tasks [%s], dry-run commands [%s]",
            summary["background_load_kwh"],
            summary["pv_potential_kwh"],
            summary["net_deficit_kwh"],
            summary["net_surplus_kwh"],
            plan.ess_projection_status,
            actuator_status,
            task_status,
            _command_log(command_results),
        )


def _next_interval_requests(plan: ShadowPlan) -> tuple[ActuatorPowerRequest, ...]:
    """Convert the next planner interval into generic actuator requests for dry-run translation."""
    if not plan.intervals:
        return ()
    next_interval = plan.intervals[0]
    if next_interval.ess_ac_power_w is None:
        return ()
    return (ActuatorPowerRequest(actuator_id="ess", requested_power_w=next_interval.ess_ac_power_w),)


def _command_log(results: tuple[ActuatorCommandResult, ...]) -> str:
    if not results:
        return "none"
    return ", ".join(
        f"{item.actuator_id}:{item.requested_power_w:.0f}->{item.accepted_power_w:.0f}W/{item.status}"
        for item in results
    )
