"""Runtime coordinator for the authoritative MILP shadow planner."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from .actuators import (
    ActuatorCommandResult,
    ActuatorRegistry,
    ActuatorSnapshot,
    EssActuatorSnapshot,
    EvActuatorSnapshot,
    find_ess_actuator,
)
from .control_health import ControlHealth, evaluate_control_health, publish_control_health
from .control_notifications import ControlNotificationManager
from .diagnostics import DiagnosticsPublisher
from .economics import EconomicsService, PlanCostEvaluation
from .ess_control import EssHardwareController
from .ev_control import EvHardwareController
from .fast_dispatch import evaluate_fast_dispatch, publish_fast_dispatch
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
_ESS_SOC_DEVIATION_TRIGGER_PERCENT = 3.0
_FAST_DISPATCH_INTERVAL_SECONDS = 1.0
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
        ess_controller: EssHardwareController | None = None,
        ev_controller: EvHardwareController | None = None,
        notification_manager: ControlNotificationManager | None = None,
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
        self._ess_controller = ess_controller
        self._ev_controller = ev_controller
        self._notification_manager = notification_manager
        self._plan: ShadowPlan | None = None
        self._last_plan_at_utc: datetime | None = None
        self._last_attempt_at_utc: datetime | None = None
        self._last_forecast_signature: tuple[str, str] | None = None
        self._last_task_signature: tuple[tuple[object, ...], ...] | None = None
        self._last_actuator_signature: tuple[tuple[object, ...], ...] | None = None
        self._latest_house_state: HouseState | None = None
        self._fast_dispatch_task: asyncio.Task[None] | None = None
        self._solve_task: asyncio.Task[None] | None = None
        self._fast_dispatch_sequence = 0
        self._last_control_health_signature: tuple[object, ...] | None = None

    @property
    def plan(self) -> ShadowPlan | None:
        return self._plan

    @property
    def solve_in_progress(self) -> bool:
        return self._solve_task is not None and not self._solve_task.done()

    async def update_from_house_state(
        self,
        house_state: HouseState,
        *,
        now_utc: datetime | None = None,
    ) -> None:
        """Observe live state and request replans without blocking input processing."""
        now = (now_utc or datetime.now(UTC)).astimezone(UTC)
        self._latest_house_state = house_state
        self._ensure_fast_dispatch_loop()

        context = await self._planning_context(house_state, now, publish_diagnostics=True)
        if context is None:
            return
        load_forecast, pv_forecast, economics, local_tz, actuators, tasks = context
        reason = self._replan_reason(
            load_forecast.generated_at_utc,
            pv_forecast.generated_at_utc,
            actuators,
            tasks,
            now,
        )
        if reason is None:
            return
        self._request_replan(
            reason,
            house_state,
            now,
            load_forecast,
            pv_forecast,
            economics,
            local_tz,
            actuators,
            tasks,
        )

    async def _planning_context(
        self,
        house_state: HouseState,
        now: datetime,
        *,
        publish_diagnostics: bool,
    ):
        load_forecast = self._load_service.forecast
        local_tz = None
        if load_forecast is not None and load_forecast.points:
            local_tz = load_forecast.points[0].period_start_local.tzinfo
        if local_tz is not None and self._economics_service is not None:
            await self._economics_service.observe_house_state(house_state, now_utc=now, local_tz=local_tz)

        health = self._evaluate_control_health(house_state, now)
        actuators = _apply_control_health_to_actuators(
            self._actuator_registry.snapshots(house_state),
            health,
            ess_control_enabled=self._ess_control_enabled,
            ev_control_enabled=self._ev_control_enabled,
        )
        if publish_diagnostics:
            await self._diagnostics.publish_actuator_status(actuators)
        if load_forecast is None:
            if publish_diagnostics:
                await self._diagnostics.publish_shadow_plan_status("waiting_for_load_forecast")
            return None
        if local_tz is None:
            local_tz = now.astimezone().tzinfo
        assert local_tz is not None
        tasks = self._task_registry.snapshots(actuators, now_utc=now, local_tz=local_tz)
        if publish_diagnostics:
            await publish_task_status(self._ha_client, tasks)
        pv_forecast = self._pv_service.forecast if self._pv_service is not None else None
        if pv_forecast is None:
            if publish_diagnostics:
                await self._diagnostics.publish_shadow_plan_status("waiting_for_pv_forecast")
            return None

        economics = self._economics_service
        if economics is None or not economics.optimizer_ready:
            if publish_diagnostics:
                await self._diagnostics.publish_shadow_plan_status("waiting_for_economics")
            return None
        if economics.current_profile is None or economics.capacity_state is None:
            if publish_diagnostics:
                await self._diagnostics.publish_shadow_plan_status("waiting_for_economics_state")
            return None
        return load_forecast, pv_forecast, economics, local_tz, actuators, tasks

    def _request_replan(
        self,
        reason: str,
        house_state: HouseState,
        now: datetime,
        load_forecast,
        pv_forecast,
        economics: EconomicsService,
        local_tz,
        actuators: tuple[ActuatorSnapshot, ...],
        tasks: tuple[PlanningTask, ...],
    ) -> None:
        if self.solve_in_progress:
            return
        if (
            reason != "control_health_change"
            and self._last_attempt_at_utc is not None
            and now - self._last_attempt_at_utc < _FAILED_RETRY_INTERVAL
        ):
            return
        self._last_attempt_at_utc = now
        self._solve_task = asyncio.create_task(
            self._run_replan(
                reason,
                house_state,
                now,
                load_forecast,
                pv_forecast,
                economics,
                local_tz,
                actuators,
                tasks,
            )
        )

    async def _run_replan(
        self,
        reason: str,
        house_state: HouseState,
        now: datetime,
        load_forecast,
        pv_forecast,
        economics: EconomicsService,
        local_tz,
        actuators: tuple[ActuatorSnapshot, ...],
        tasks: tuple[PlanningTask, ...],
    ) -> None:
        try:
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
                if self._can_retain_previous_plan(reason, datetime.now(UTC)):
                    _LOGGER.warning(
                        "MILP replan failed; retaining previous shadow plan temporarily: %s",
                        evaluation.reason,
                    )
                    return
                self._plan = None
                await self._diagnostics.publish_shadow_plan_status(
                    "milp_unavailable",
                    error=evaluation.reason or evaluation.status,
                )
                if self._ess_controller is not None:
                    await self._ess_controller.publish_command_status(
                        (),
                        ev_control_enabled=self._ev_control_enabled,
                    )
                    await self._ess_controller.safe_zero("milp_unavailable")
                else:
                    await self._diagnostics.publish_actuator_command_status(())
                if self._ev_controller is not None:
                    await self._ev_controller.safe_stop("milp_unavailable")
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

            await self._diagnostics.publish_shadow_plan(plan)
            cost_evaluation = await economics.publish_plan_cost(plan, local_tz=local_tz)
            latest_state = self._latest_house_state or house_state
            fast_result = evaluate_fast_dispatch(
                plan,
                latest_state,
                self._actuator_registry,
                now_utc=datetime.now(UTC),
                live_control=self._ess_control_enabled,
            )
            _log_plan(plan, actuators, tasks, cost_evaluation, fast_result.command_results)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - planning failure must not terminate the live controller.
            _LOGGER.exception("Unexpected asynchronous MILP planner failure")
        finally:
            if reason == "startup" and self._notification_manager is not None:
                self._notification_manager.complete_startup()

    def _replan_reason(
        self,
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
        if now_utc - self._last_plan_at_utc >= _PERIODIC_REPLAN_INTERVAL:
            return "periodic"
        return None

    @property
    def _ess_control_enabled(self) -> bool:
        return self._ess_controller is not None and self._ess_controller.enabled

    @property
    def _ev_control_enabled(self) -> bool:
        return self._ev_controller is not None and self._ev_controller.enabled

    async def shutdown(self) -> None:
        """Stop runtime tasks and leave the ESS setpoint neutral on a clean exit."""
        for task in (self._fast_dispatch_task, self._solve_task):
            if task is not None and not task.done():
                task.cancel()
        pending = tuple(
            task for task in (self._fast_dispatch_task, self._solve_task) if task is not None
        )
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        if self._notification_manager is not None:
            await self._notification_manager.shutdown()

    def _ensure_fast_dispatch_loop(self) -> None:
        if self._fast_dispatch_task is None or self._fast_dispatch_task.done():
            self._fast_dispatch_task = asyncio.create_task(self._fast_dispatch_loop())

    async def _fast_dispatch_loop(self) -> None:
        loop = asyncio.get_running_loop()
        next_run = loop.time()
        try:
            while True:
                delay = next_run - loop.time()
                if delay > 0.0:
                    await asyncio.sleep(delay)
                started = loop.time()
                await self._run_fast_dispatch_once()
                next_run = max(next_run + _FAST_DISPATCH_INTERVAL_SECONDS, started + _FAST_DISPATCH_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - fast dispatch must restart after an unexpected diagnostic failure.
            _LOGGER.exception("Fast dispatch loop stopped unexpectedly")

    async def _run_fast_dispatch_once(self) -> None:
        house_state = self._latest_house_state
        plan = self._plan
        if house_state is None:
            return
        now = datetime.now(UTC)
        if plan is None:
            if self._ess_controller is not None and self._ess_controller.enabled:
                await self._ess_controller.safe_zero("no_active_plan")
            if self._ev_controller is not None and self._ev_controller.enabled:
                await self._ev_controller.safe_stop("no_active_plan")
            health = self._evaluate_control_health(house_state, now)
            self._record_control_health(health)
            await self._publish_control_health(health)
            return

        health = self._evaluate_control_health(house_state, now)
        health_changed = self._record_control_health(health)
        if self._ess_control_enabled and not health.ess_available:
            if self._ess_controller is not None:
                await self._ess_controller.safe_zero("control_health_fallback")
            if self._ev_controller is not None and self._ev_controller.enabled:
                await self._ev_controller.safe_stop("control_health_fallback")
            await self._publish_control_health(health)
            if health_changed:
                await self._request_health_replan(house_state, now)
            return

        result = evaluate_fast_dispatch(
            plan,
            house_state,
            self._actuator_registry,
            now_utc=now,
            live_control=self._ess_control_enabled,
        )
        self._fast_dispatch_sequence += 1
        await publish_fast_dispatch(
            self._ha_client,
            result,
            control_interval_seconds=_FAST_DISPATCH_INTERVAL_SECONDS,
            dispatch_sequence=self._fast_dispatch_sequence,
            milp_solve_in_progress=self.solve_in_progress,
            control_enabled=self._ess_control_enabled,
            hardware_writes=self._ess_control_enabled,
        )
        if self._ess_controller is not None:
            await self._ess_controller.apply_dispatch(result)
        if self._ev_controller is not None:
            if health.ev_available:
                await self._ev_controller.apply_dispatch(result)
            else:
                await self._ev_controller.safe_stop("control_health_ev_unavailable")
        if self._ess_controller is not None:
            await self._ess_controller.publish_command_status(
                result.command_results,
                ev_control_enabled=self._ev_control_enabled,
            )
        else:
            await self._diagnostics.publish_actuator_command_status(result.command_results)

        post_health = self._evaluate_control_health(house_state, datetime.now(UTC))
        post_health_changed = self._record_control_health(post_health)
        await self._publish_control_health(post_health)
        if post_health_changed:
            await self._request_health_replan(house_state, now)
            if post_health.replan_required:
                return
        if not result.replan_required:
            return

        context = await self._planning_context(house_state, now, publish_diagnostics=False)
        if context is None:
            return
        load_forecast, pv_forecast, economics, local_tz, actuators, tasks = context
        self._request_replan(
            "fast_dispatch_residual",
            house_state,
            now,
            load_forecast,
            pv_forecast,
            economics,
            local_tz,
            actuators,
            tasks,
        )

    def _evaluate_control_health(self, house_state: HouseState, now: datetime) -> ControlHealth:
        ess_fault = None
        if self._ess_controller is not None and self._ess_controller.fault_active:
            ess_fault = self._ess_controller.last_error or "write_fault"
        ev_fault = None
        if self._ev_controller is not None and self._ev_controller.fault_active:
            ev_fault = self._ev_controller.last_error or "write_fault"
        return evaluate_control_health(
            house_state,
            now_utc=now,
            ess_control_enabled=self._ess_control_enabled,
            ev_control_enabled=self._ev_control_enabled,
            ess_fault=ess_fault,
            ev_fault=ev_fault,
        )

    async def _publish_control_health(self, health: ControlHealth) -> None:
        await publish_control_health(
            self._ha_client,
            health,
            ess_control_enabled=self._ess_control_enabled,
            ev_control_enabled=self._ev_control_enabled,
            ess_write_failures=(
                self._ess_controller.consecutive_failures if self._ess_controller is not None else 0
            ),
            ev_write_failures=(
                self._ev_controller.consecutive_failures if self._ev_controller is not None else 0
            ),
            ess_last_error=self._ess_controller.last_error if self._ess_controller is not None else None,
            ev_last_error=self._ev_controller.last_error if self._ev_controller is not None else None,
        )
        if self._notification_manager is not None:
            self._notification_manager.observe(health)

    def _record_control_health(self, health: ControlHealth) -> bool:
        signature: tuple[object, ...] = (
            health.state,
            health.ess_available,
            health.ev_available,
            health.stale_inputs,
            health.unavailable_inputs,
            health.reasons,
        )
        changed = signature != self._last_control_health_signature
        self._last_control_health_signature = signature
        return changed

    async def _request_health_replan(
        self,
        house_state: HouseState,
        now: datetime,
    ) -> None:
        context = await self._planning_context(house_state, now, publish_diagnostics=False)
        if context is None:
            return
        load_forecast, pv_forecast, economics, local_tz, actuators, tasks = context
        self._request_replan(
            "control_health_change",
            house_state,
            now,
            load_forecast,
            pv_forecast,
            economics,
            local_tz,
            actuators,
            tasks,
        )

    def _can_retain_previous_plan(self, trigger: str, now_utc: datetime) -> bool:
        if self._plan is None or self._last_plan_at_utc is None:
            return False
        if now_utc - self._last_plan_at_utc > _RETAIN_PLAN_MAX_AGE:
            return False
        return trigger in {"periodic", "forecast_update"}


def _apply_control_health_to_actuators(
    actuators: tuple[ActuatorSnapshot, ...],
    health: ControlHealth,
    *,
    ess_control_enabled: bool,
    ev_control_enabled: bool,
) -> tuple[ActuatorSnapshot, ...]:
    result: list[ActuatorSnapshot] = []
    for item in actuators:
        if (
            isinstance(item, EssActuatorSnapshot)
            and ess_control_enabled
            and not health.ess_available
            and item.planning_available
        ):
            item = replace(item, planning_available=False, status="control_health_unavailable")
        elif (
            isinstance(item, EvActuatorSnapshot)
            and ev_control_enabled
            and not health.ev_available
            and item.planning_available
        ):
            item = replace(item, planning_available=False, status="control_health_unavailable")
        result.append(item)
    return tuple(result)


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
        "curtailed DC PV %.2f kWh, economics %s, actuators [%s], tasks [%s], commands [%s]",
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
