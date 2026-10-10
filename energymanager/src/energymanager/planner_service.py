"""Runtime coordinator for the authoritative MILP shadow planner."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from .actuators import (
    ActuatorCommandResult,
    ActuatorPowerRequest,
    ActuatorRegistry,
    ActuatorSnapshot,
    find_ess_actuator,
)
from .diagnostics import DiagnosticsPublisher
from .economics import EconomicsService, PlanCostEvaluation
from .house_state import HouseState
from .load_service import BackgroundLoadService
from .milp_planner import MilpEvaluation, evaluate_shadow_plan_milp, publish_milp_evaluation
from .planner import ShadowPlan, ShadowPlanner
from .pv_service import PvForecastService
from .task_diagnostics import publish_task_status
from .tasks import PlanningTask, TaskRegistry

_LOGGER = logging.getLogger(__name__)
_PERIODIC_REPLAN_INTERVAL = timedelta(minutes=10)
_FAILED_RETRY_INTERVAL = timedelta(minutes=1)
_RETAIN_PLAN_MAX_AGE = timedelta(minutes=30)
_LOAD_DEVIATION_TRIGGER_W = 750.0
_LOAD_DEVIATION_BUCKET_W = 500.0
_ESS_SOC_DEVIATION_TRIGGER_PERCENT = 3.0
_INTERVAL = timedelta(minutes=15)


class ShadowPlannerService:
    """Build, solve and publish the single authoritative MILP shadow plan."""

    def __init__(
        self,
        ha_client,
        load_service: BackgroundLoadService,
        pv_service: PvForecastService | None,
        *,
        actuator_registry: ActuatorRegistry,
        task_registry: TaskRegistry,
        economics_service: EconomicsService | None = None,
        planner: ShadowPlanner | None = None,
    ) -> None:
        self._ha_client = ha_client
        self._diagnostics = DiagnosticsPublisher(ha_client)
        self._load_service = load_service
        self._pv_service = pv_service
        self._planner = planner or ShadowPlanner()
        self._actuator_registry = actuator_registry
        self._task_registry = task_registry
        self._economics_service = economics_service
        self._plan: ShadowPlan | None = None
        self._last_plan_at_utc: datetime | None = None
        self._last_attempt_at_utc: datetime | None = None
        self._last_forecast_signature: tuple[str, str] | None = None
        self._last_task_signature: tuple[tuple[object, ...], ...] | None = None
        self._last_actuator_signature: tuple[tuple[object, ...], ...] | None = None
        self._last_load_deviation_bucket = 0

    @property
    def plan(self) -> ShadowPlan | None:
        return self._plan

    async def update_from_house_state(
        self,
        house_state: HouseState,
        *,
        now_utc: datetime | None = None,
    ) -> None:
        """Observe live state and replan periodically or immediately after a material change."""
        now = (now_utc or datetime.now(UTC)).astimezone(UTC)
        load_forecast = self._load_service.forecast
        local_tz = None
        if load_forecast is not None and load_forecast.points:
            local_tz = load_forecast.points[0].period_start_local.tzinfo
        if local_tz is not None and self._economics_service is not None:
            await self._economics_service.observe_house_state(house_state, now_utc=now, local_tz=local_tz)

        actuators = self._actuator_registry.snapshots(house_state)
        await self._diagnostics.publish_actuator_status(actuators)
        if load_forecast is None:
            await self._diagnostics.publish_shadow_plan_status("waiting_for_load_forecast")
            return
        if local_tz is None:
            local_tz = now.astimezone().tzinfo
        assert local_tz is not None
        tasks = self._task_registry.snapshots(actuators, now_utc=now, local_tz=local_tz)
        await publish_task_status(self._ha_client, tasks)
        pv_forecast = self._pv_service.forecast if self._pv_service is not None else None
        if pv_forecast is None:
            await self._diagnostics.publish_shadow_plan_status("waiting_for_pv_forecast")
            return

        economics = self._economics_service
        if economics is None or not economics.optimizer_ready:
            await self._diagnostics.publish_shadow_plan_status("waiting_for_economics")
            return
        if economics.current_profile is None or economics.capacity_state is None:
            await self._diagnostics.publish_shadow_plan_status("waiting_for_economics_state")
            return

        reason = self._replan_reason(
            house_state,
            load_forecast.generated_at_utc,
            pv_forecast.generated_at_utc,
            actuators,
            tasks,
            now,
        )
        if reason is None:
            return
        if self._last_attempt_at_utc is not None and now - self._last_attempt_at_utc < _FAILED_RETRY_INTERVAL:
            return
        self._last_attempt_at_utc = now

        frame = self._planner.build(
            load_forecast,
            pv_forecast,
            now_utc=now,
            actuators=actuators,
            tasks=tasks,
        )
        evaluation = await asyncio.to_thread(
            evaluate_shadow_plan_milp,
            frame,
            economics.current_profile,
            economics.capacity_state,
        )
        await publish_milp_evaluation(self._ha_client, evaluation)
        _LOGGER.info("MILP planner: trigger=%s, %s", reason, _milp_log(evaluation))

        if not evaluation.adoption_ready or evaluation.plan is None:
            if self._can_retain_previous_plan(reason, now):
                _LOGGER.warning("MILP replan failed; retaining previous shadow plan temporarily: %s", evaluation.reason)
                return
            self._plan = None
            await self._diagnostics.publish_shadow_plan_status(
                "milp_unavailable",
                error=evaluation.reason or evaluation.status,
            )
            await self._diagnostics.publish_actuator_command_status(())
            return

        plan = evaluation.plan
        self._plan = plan
        self._last_plan_at_utc = now
        self._last_forecast_signature = _forecast_signature(
            load_forecast.generated_at_utc,
            pv_forecast.generated_at_utc,
        )
        self._last_task_signature = _task_signature(tasks)
        self._last_actuator_signature = _actuator_signature(actuators)
        self._last_load_deviation_bucket = _background_deviation_bucket(house_state, plan, now)

        await self._diagnostics.publish_shadow_plan(plan)
        cost_evaluation = await economics.publish_plan_cost(plan, local_tz=local_tz)
        requests = _current_interval_requests(plan, now)
        command_results = self._actuator_registry.evaluate_commands(requests, house_state)
        await self._diagnostics.publish_actuator_command_status(command_results)
        _log_plan(plan, actuators, tasks, cost_evaluation, command_results)

    def _replan_reason(
        self,
        house_state: HouseState,
        load_generated_at_utc: datetime,
        pv_generated_at_utc: datetime,
        actuators: tuple[ActuatorSnapshot, ...],
        tasks: tuple[PlanningTask, ...],
        now_utc: datetime,
    ) -> str | None:
        if self._plan is None or self._last_plan_at_utc is None:
            return "startup"

        forecast_signature = _forecast_signature(load_generated_at_utc, pv_generated_at_utc)
        if forecast_signature != self._last_forecast_signature:
            return "forecast_update"
        if _task_signature(tasks) != self._last_task_signature:
            return "task_change"
        if _actuator_signature(actuators) != self._last_actuator_signature:
            return "actuator_change"
        if _ess_soc_deviates(self._plan, actuators, now_utc):
            return "ess_soc_deviation"

        deviation_bucket = _background_deviation_bucket(house_state, self._plan, now_utc)
        if deviation_bucket != self._last_load_deviation_bucket:
            return "background_load_deviation"
        if now_utc - self._last_plan_at_utc >= _PERIODIC_REPLAN_INTERVAL:
            return "periodic"
        return None

    def _can_retain_previous_plan(self, trigger: str, now_utc: datetime) -> bool:
        if self._plan is None or self._last_plan_at_utc is None:
            return False
        if now_utc - self._last_plan_at_utc > _RETAIN_PLAN_MAX_AGE:
            return False
        return trigger in {"periodic", "forecast_update"}


def _forecast_signature(load_generated_at_utc: datetime, pv_generated_at_utc: datetime) -> tuple[str, str]:
    return load_generated_at_utc.astimezone(UTC).isoformat(), pv_generated_at_utc.astimezone(UTC).isoformat()


def _task_signature(tasks: tuple[PlanningTask, ...]) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.task_id,
            item.kind,
            item.actuator_id,
            item.status,
            item.planning_available,
            _quarter_hour_bucket(item.earliest_start_local),
            _quarter_hour_bucket(item.latest_end_local),
            None if item.required_energy_kwh is None else round(item.required_energy_kwh * 4.0) / 4.0,
            None if item.preferred_energy_kwh is None else round(item.preferred_energy_kwh * 4.0) / 4.0,
            item.minimum_soc_percent,
            item.target_soc_percent,
            _quarter_hour_bucket(item.expected_return_local),
            item.expected_trip_energy_kwh,
        )
        for item in tasks
    )


def _actuator_signature(actuators: tuple[ActuatorSnapshot, ...]) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.actuator_id,
            item.kind,
            item.configured,
            item.planning_available,
            item.status,
            getattr(item, "connected", None),
        )
        for item in actuators
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _quarter_hour_bucket(value: datetime | None) -> str | None:
    if value is None:
        return None
    bucket_minute = value.minute - value.minute % 15
    return value.replace(minute=bucket_minute, second=0, microsecond=0).isoformat()


def _current_interval(plan: ShadowPlan, now_utc: datetime):
    for index, item in enumerate(plan.intervals):
        start_utc = item.period_start_local.astimezone(UTC)
        if start_utc <= now_utc < start_utc + _INTERVAL:
            return index, item
    for index, item in enumerate(plan.intervals):
        if item.period_start_local.astimezone(UTC) > now_utc:
            return index, item
    return None


def _background_deviation_bucket(house_state: HouseState, plan: ShadowPlan, now_utc: datetime) -> int:
    actual = house_state.background_load_power_w
    current = _current_interval(plan, now_utc)
    if actual is None or current is None:
        return 0
    _, interval = current
    deviation = actual - interval.background_load_w
    if abs(deviation) < _LOAD_DEVIATION_TRIGGER_W:
        return 0
    return round(deviation / _LOAD_DEVIATION_BUCKET_W)


def _ess_soc_deviates(
    plan: ShadowPlan,
    actuators: tuple[ActuatorSnapshot, ...],
    now_utc: datetime,
) -> bool:
    ess = find_ess_actuator(actuators)
    current = _current_interval(plan, now_utc)
    if ess is None or ess.soc_percent is None or current is None:
        return False
    index, _ = current
    if index == 0:
        expected = plan.ess_initial_soc_percent
    else:
        expected = plan.intervals[index - 1].projected_soc_percent
    if expected is None:
        return False
    return abs(float(ess.soc_percent) - float(expected)) >= _ESS_SOC_DEVIATION_TRIGGER_PERCENT


def _current_interval_requests(plan: ShadowPlan, now_utc: datetime) -> tuple[ActuatorPowerRequest, ...]:
    """Translate the current MILP interval into generic dry-run actuator requests."""
    current = _current_interval(plan, now_utc)
    if current is None:
        return ()
    _, interval = current
    requests: list[ActuatorPowerRequest] = []
    if interval.ess_ac_power_w is not None:
        requests.append(ActuatorPowerRequest(actuator_id="ess", requested_power_w=interval.ess_ac_power_w))
    if interval.scheduled_load_w > 0.0:
        requests.append(ActuatorPowerRequest(actuator_id="ev", requested_power_w=interval.scheduled_load_w))
    return tuple(requests)


def _cost_log(evaluation: PlanCostEvaluation | None) -> str:
    if evaluation is None:
        return "unavailable"
    if evaluation.total_marginal_cost_eur is None:
        return f"energy-only EUR {evaluation.net_energy_cost_eur:.2f}"
    return f"marginal EUR {evaluation.total_marginal_cost_eur:.2f}"


def _log_plan(
    plan: ShadowPlan,
    actuators: tuple[ActuatorSnapshot, ...],
    tasks: tuple[PlanningTask, ...],
    cost_evaluation: PlanCostEvaluation | None,
    command_results: tuple[ActuatorCommandResult, ...],
) -> None:
    summary = plan.summary(24)
    actuator_status = ", ".join(f"{item.actuator_id}:{item.status}" for item in actuators)
    task_status = ", ".join(f"{item.task_id}:{item.status}" for item in tasks)
    _LOGGER.info(
        "MILP shadow plan updated: next 24 h background %.2f kWh, scheduled %.2f kWh, PV potential %.2f kWh, "
        "pre-control deficit %.2f kWh, projected grid import %.2f kWh, ESS SoC %.1f -> %.1f%%, "
        "curtailed DC PV %.2f kWh, economics %s, actuators [%s], tasks [%s], dry-run commands [%s]",
        summary["background_load_kwh"],
        summary["scheduled_load_kwh"],
        summary["pv_potential_kwh"],
        summary["net_deficit_kwh"],
        summary["grid_import_after_ess_kwh"],
        plan.ess_initial_soc_percent,
        summary["end_soc_percent"],
        summary["curtailed_dc_pv_kwh"],
        _cost_log(cost_evaluation),
        actuator_status,
        task_status,
        _command_log(command_results),
    )


def _command_log(results: tuple[ActuatorCommandResult, ...]) -> str:
    if not results:
        return "none"
    return ", ".join(
        f"{item.actuator_id}:{item.requested_power_w:.0f}->{item.accepted_power_w:.0f}W/{item.status}"
        for item in results
    )


def _milp_log(evaluation: MilpEvaluation) -> str:
    details = [evaluation.status, f"validation={evaluation.validation_status}"]
    if evaluation.solve_time_seconds is not None:
        details.append(f"{evaluation.solve_time_seconds:.3f}s")
    if evaluation.tie_break_status is not None:
        details.append(f"tie-break={evaluation.tie_break_status}")
    if evaluation.milp_objective_eur is not None:
        details.append(f"EUR {evaluation.milp_objective_eur:.2f}")
    details.append(
        f"model {evaluation.variable_count} vars/{evaluation.integer_variable_count} integer/"
        f"{evaluation.constraint_count} constraints"
    )
    if evaluation.reason is not None:
        details.append(evaluation.reason)
    return ", ".join(details)
