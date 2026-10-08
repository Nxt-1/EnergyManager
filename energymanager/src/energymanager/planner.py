"""Read-only shadow planning primitives for forecasted household energy flow."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from .actuators import (
    ActuatorSnapshot,
    EssActuatorSnapshot,
    EssCapabilities,
    EvActuatorSnapshot,
    find_ess_actuator,
    find_ev_actuator,
)
from .load_forecast import FORECAST_INTERVAL_MINUTES, BackgroundLoadForecast
from .pv_forecast import PvForecast
from .tasks import PlanningTask

PLANNER_VERSION = "2026-10-08-shadow-v7"
PLANNER_HORIZON_HOURS = 48
_INTERVAL_HOURS = FORECAST_INTERVAL_MINUTES / 60.0
_INTERVAL_DELTA = timedelta(minutes=FORECAST_INTERVAL_MINUTES)


@dataclass(frozen=True, slots=True)
class ShadowPlanInterval:
    """One 15-minute planner interval including an optional ESS feasibility projection."""

    period_start_local: datetime
    background_load_w: float
    scheduled_load_w: float
    pv_ac_power_w: float
    pv_dc_power_w: float
    pv_power_w: float
    net_power_before_control_w: float
    ess_ac_power_w: float | None = None
    battery_energy_delta_kwh: float | None = None
    projected_soc_percent: float | None = None
    grid_power_after_ess_w: float | None = None
    curtailed_dc_pv_w: float | None = None

    @property
    def total_load_w(self) -> float:
        return self.background_load_w + self.scheduled_load_w


@dataclass(frozen=True, slots=True)
class ShadowPlan:
    """Planner-ready read-only energy balance used as the base for later scheduling."""

    generated_at_utc: datetime
    intervals: tuple[ShadowPlanInterval, ...]
    ess_projection_status: str = "not_configured"
    actuator_snapshots: tuple[ActuatorSnapshot, ...] = ()
    tasks: tuple[PlanningTask, ...] = ()
    ess_resource: EssCapabilities | None = None
    ess_initial_soc_percent: float | None = None
    scheduling_strategy: str = "deadline_earliest"
    optimizer_status: str = "not_requested"
    optimizer_objective: str | None = None
    optimizer_score_eur: float | None = None
    optimizer_baseline_score_eur: float | None = None
    optimizer_candidate_evaluations: int = 0

    def summary(self, hours: int) -> dict[str, float | int | str | None]:
        """Return compact energy/peak statistics for the first requested hours."""
        count = min(len(self.intervals), max(0, hours * 60 // FORECAST_INTERVAL_MINUTES))
        intervals = self.intervals[:count]
        if not intervals:
            return {
                "hours": hours,
                "intervals": 0,
                "background_load_kwh": 0.0,
                "scheduled_load_kwh": 0.0,
                "pv_potential_kwh": 0.0,
                "pv_ac_potential_kwh": 0.0,
                "pv_dc_potential_kwh": 0.0,
                "net_deficit_kwh": 0.0,
                "net_surplus_kwh": 0.0,
                "max_net_deficit_w": 0.0,
                "ess_projection_status": self.ess_projection_status,
                "grid_import_after_ess_kwh": None,
                "grid_export_after_ess_kwh": None,
                "curtailed_dc_pv_kwh": None,
                "ess_ac_discharge_kwh": None,
                "ess_ac_charge_kwh": None,
                "battery_charge_stored_kwh": None,
                "battery_discharge_stored_kwh": None,
                "end_soc_percent": None,
                "min_soc_percent": None,
                "max_soc_percent": None,
                "max_grid_import_after_ess_w": None,
            }
        background = sum(item.background_load_w for item in intervals) * _INTERVAL_HOURS / 1000.0
        scheduled = sum(item.scheduled_load_w for item in intervals) * _INTERVAL_HOURS / 1000.0
        pv_ac = sum(item.pv_ac_power_w for item in intervals) * _INTERVAL_HOURS / 1000.0
        pv_dc = sum(item.pv_dc_power_w for item in intervals) * _INTERVAL_HOURS / 1000.0
        deficit = (
            sum(max(0.0, item.net_power_before_control_w) for item in intervals) * _INTERVAL_HOURS / 1000.0
        )
        surplus = (
            sum(max(0.0, -item.net_power_before_control_w) for item in intervals) * _INTERVAL_HOURS / 1000.0
        )
        result: dict[str, float | int | str | None] = {
            "hours": hours,
            "intervals": len(intervals),
            "background_load_kwh": background,
            "scheduled_load_kwh": scheduled,
            "pv_potential_kwh": pv_ac + pv_dc,
            "pv_ac_potential_kwh": pv_ac,
            "pv_dc_potential_kwh": pv_dc,
            "net_deficit_kwh": deficit,
            "net_surplus_kwh": surplus,
            "max_net_deficit_w": max(max(0.0, item.net_power_before_control_w) for item in intervals),
            "ess_projection_status": self.ess_projection_status,
            "grid_import_after_ess_kwh": None,
            "grid_export_after_ess_kwh": None,
            "curtailed_dc_pv_kwh": None,
            "ess_ac_discharge_kwh": None,
            "ess_ac_charge_kwh": None,
            "battery_charge_stored_kwh": None,
            "battery_discharge_stored_kwh": None,
            "end_soc_percent": None,
            "min_soc_percent": None,
            "max_soc_percent": None,
            "max_grid_import_after_ess_w": None,
        }
        if self.ess_projection_status != "projected":
            return result

        projected = [item for item in intervals if item.grid_power_after_ess_w is not None]
        if len(projected) != len(intervals):
            return result
        grid_values = [float(item.grid_power_after_ess_w) for item in projected]
        ess_ac_values = [float(item.ess_ac_power_w) for item in projected if item.ess_ac_power_w is not None]
        battery_deltas = [
            float(item.battery_energy_delta_kwh)
            for item in projected
            if item.battery_energy_delta_kwh is not None
        ]
        soc_values = [
            float(item.projected_soc_percent)
            for item in projected
            if item.projected_soc_percent is not None
        ]
        curtailed_values = [
            float(item.curtailed_dc_pv_w)
            for item in projected
            if item.curtailed_dc_pv_w is not None
        ]
        result.update(
            {
                "grid_import_after_ess_kwh": (
                    sum(max(0.0, power) for power in grid_values) * _INTERVAL_HOURS / 1000.0
                ),
                "grid_export_after_ess_kwh": (
                    sum(max(0.0, -power) for power in grid_values) * _INTERVAL_HOURS / 1000.0
                ),
                "curtailed_dc_pv_kwh": sum(curtailed_values) * _INTERVAL_HOURS / 1000.0,
                "ess_ac_discharge_kwh": (
                    sum(max(0.0, power) for power in ess_ac_values) * _INTERVAL_HOURS / 1000.0
                ),
                "ess_ac_charge_kwh": (
                    sum(max(0.0, -power) for power in ess_ac_values) * _INTERVAL_HOURS / 1000.0
                ),
                "battery_charge_stored_kwh": sum(max(0.0, delta) for delta in battery_deltas),
                "battery_discharge_stored_kwh": sum(max(0.0, -delta) for delta in battery_deltas),
                "end_soc_percent": soc_values[-1] if soc_values else None,
                "min_soc_percent": min(soc_values) if soc_values else None,
                "max_soc_percent": max(soc_values) if soc_values else None,
                "max_grid_import_after_ess_w": max(max(0.0, power) for power in grid_values),
            }
        )
        return result


class ShadowPlanner:
    """Merge independent forecasts, schedule deadline tasks and project the ESS baseline."""

    def build(
        self,
        load_forecast: BackgroundLoadForecast,
        pv_forecast: PvForecast,
        *,
        now_utc: datetime,
        actuators: tuple[ActuatorSnapshot, ...] = (),
        tasks: tuple[PlanningTask, ...] = (),
        objective_scorer: Callable[[ShadowPlan], float | None] | None = None,
        objective_name: str | None = None,
    ) -> ShadowPlan:
        if now_utc.tzinfo is None:
            raise ValueError("now_utc must be timezone-aware")
        horizon_end_utc = now_utc.astimezone(UTC) + timedelta(hours=PLANNER_HORIZON_HOURS)
        load_points = [
            point
            for point in load_forecast.points
            if now_utc.astimezone(UTC) <= point.period_start_local.astimezone(UTC) < horizon_end_utc
        ]
        if not load_points:
            raise ValueError("Background-load forecast has no future intervals in the planning horizon")
        base_intervals: list[ShadowPlanInterval] = []
        for load_point in load_points:
            pv_ac_w, pv_dc_w = _pv_powers_for_interval(pv_forecast, load_point.period_start_local)
            background_w = max(0.0, load_point.power_w)
            pv_total_w = pv_ac_w + pv_dc_w
            base_intervals.append(
                ShadowPlanInterval(
                    period_start_local=load_point.period_start_local,
                    background_load_w=background_w,
                    scheduled_load_w=0.0,
                    pv_ac_power_w=pv_ac_w,
                    pv_dc_power_w=pv_dc_w,
                    pv_power_w=pv_total_w,
                    net_power_before_control_w=background_w - pv_total_w,
                )
            )

        ess_actuator = find_ess_actuator(actuators)
        scheduling = _SchedulingResult(intervals=_schedule_tasks(base_intervals, actuators, tasks))
        if (
            objective_scorer is not None
            and objective_name is not None
            and ess_actuator is not None
            and ess_actuator.configured
            and ess_actuator.planning_available
            and ess_actuator.soc_percent is not None
        ):
            scheduling = _schedule_tasks_economically(
                base_intervals,
                actuators,
                tasks,
                ess_actuator,
                now_utc=now_utc,
                objective_scorer=objective_scorer,
                objective_name=objective_name,
            )

        if ess_actuator is None or not ess_actuator.configured:
            return _plan_from_scheduling(
                now_utc,
                scheduling,
                actuators,
                tasks,
                ess_projection_status="not_configured",
            )
        if not ess_actuator.planning_available or ess_actuator.soc_percent is None:
            return _plan_from_scheduling(
                now_utc,
                scheduling,
                actuators,
                tasks,
                ess_projection_status=ess_actuator.status,
                ess_resource=ess_actuator.capabilities,
            )

        projected_intervals = _project_ess(scheduling.intervals, ess_actuator)
        return _plan_from_scheduling(
            now_utc,
            scheduling,
            actuators,
            tasks,
            intervals=projected_intervals,
            ess_projection_status="projected",
            ess_resource=ess_actuator.capabilities,
            ess_initial_soc_percent=max(0.0, min(100.0, ess_actuator.soc_percent)),
        )


@dataclass(slots=True)
class _SchedulingResult:
    intervals: list[ShadowPlanInterval]
    strategy: str = "deadline_earliest"
    optimizer_status: str = "not_requested"
    objective_name: str | None = None
    score_eur: float | None = None
    baseline_score_eur: float | None = None
    candidate_evaluations: int = 0


def _plan_from_scheduling(
    now_utc: datetime,
    scheduling: _SchedulingResult,
    actuators: tuple[ActuatorSnapshot, ...],
    tasks: tuple[PlanningTask, ...],
    *,
    intervals: tuple[ShadowPlanInterval, ...] | None = None,
    ess_projection_status: str,
    ess_resource: EssCapabilities | None = None,
    ess_initial_soc_percent: float | None = None,
) -> ShadowPlan:
    return ShadowPlan(
        generated_at_utc=now_utc.astimezone(UTC),
        intervals=intervals if intervals is not None else tuple(scheduling.intervals),
        ess_projection_status=ess_projection_status,
        actuator_snapshots=actuators,
        tasks=tasks,
        ess_resource=ess_resource,
        ess_initial_soc_percent=ess_initial_soc_percent,
        scheduling_strategy=scheduling.strategy,
        optimizer_status=scheduling.optimizer_status,
        optimizer_objective=scheduling.objective_name,
        optimizer_score_eur=scheduling.score_eur,
        optimizer_baseline_score_eur=scheduling.baseline_score_eur,
        optimizer_candidate_evaluations=scheduling.candidate_evaluations,
    )


def _schedule_tasks_economically(
    intervals: list[ShadowPlanInterval],
    actuators: tuple[ActuatorSnapshot, ...],
    tasks: tuple[PlanningTask, ...],
    ess_actuator: EssActuatorSnapshot,
    *,
    now_utc: datetime,
    objective_scorer: Callable[[ShadowPlan], float | None],
    objective_name: str,
) -> _SchedulingResult:
    """Economically schedule the current EV deadline task with discrete charger states."""
    baseline_intervals = _schedule_tasks(intervals, actuators, tasks)
    baseline_plan = _candidate_plan(baseline_intervals, now_utc, actuators, tasks, ess_actuator)
    baseline_score = objective_scorer(baseline_plan)
    if baseline_score is None:
        return _SchedulingResult(
            intervals=baseline_intervals,
            optimizer_status="objective_unavailable",
            objective_name=objective_name,
        )

    ev_actuator = find_ev_actuator(actuators)
    active_tasks = [
        task
        for task in tasks
        if task.planning_available and task.required_energy_kwh is not None and task.required_energy_kwh > 0.0
    ]
    supported = [
        task
        for task in active_tasks
        if ev_actuator is not None
        and task.kind == "energy_by_deadline"
        and task.actuator_id == ev_actuator.actuator_id
    ]
    if ev_actuator is None or not ev_actuator.planning_available or len(active_tasks) != 1 or len(supported) != 1:
        return _SchedulingResult(
            intervals=baseline_intervals,
            optimizer_status="unsupported_task_set",
            objective_name=objective_name,
            score_eur=baseline_score,
            baseline_score_eur=baseline_score,
            candidate_evaluations=1,
        )

    task = supported[0]
    optimized = _optimize_ev_energy_task(
        intervals,
        task,
        ev_actuator,
        ess_actuator,
        now_utc=now_utc,
        actuators=actuators,
        tasks=tasks,
        objective_scorer=objective_scorer,
    )
    evaluations = optimized.candidate_evaluations + 1
    if optimized.score_eur is None:
        return _SchedulingResult(
            intervals=baseline_intervals,
            optimizer_status="objective_unavailable",
            objective_name=objective_name,
            score_eur=baseline_score,
            baseline_score_eur=baseline_score,
            candidate_evaluations=evaluations,
        )
    if optimized.score_eur >= baseline_score - 1e-9:
        return _SchedulingResult(
            intervals=baseline_intervals,
            optimizer_status="baseline_retained",
            objective_name=objective_name,
            score_eur=baseline_score,
            baseline_score_eur=baseline_score,
            candidate_evaluations=evaluations,
        )
    return _SchedulingResult(
        intervals=optimized.intervals,
        strategy="economic_ev_greedy",
        optimizer_status="optimized",
        objective_name=objective_name,
        score_eur=optimized.score_eur,
        baseline_score_eur=baseline_score,
        candidate_evaluations=evaluations,
    )


def _optimize_ev_energy_task(
    intervals: list[ShadowPlanInterval],
    task: PlanningTask,
    actuator: EvActuatorSnapshot,
    ess_actuator: EssActuatorSnapshot,
    *,
    now_utc: datetime,
    actuators: tuple[ActuatorSnapshot, ...],
    tasks: tuple[PlanningTask, ...],
    objective_scorer: Callable[[ShadowPlan], float | None],
) -> _SchedulingResult:
    """Greedily add the lowest marginal-cost charger increment until the task is fulfilled."""
    if task.earliest_start_local is None or task.latest_end_local is None or task.required_energy_kwh is None:
        return _SchedulingResult(intervals=list(intervals), optimizer_status="invalid_task")
    power_steps = _ev_charge_power_steps_w(actuator)
    if not power_steps:
        return _SchedulingResult(intervals=list(intervals), optimizer_status="no_charge_steps")

    earliest_utc = task.earliest_start_local.astimezone(UTC)
    latest_end_utc = task.latest_end_local.astimezone(UTC)
    eligible_indexes = [
        index
        for index, item in enumerate(intervals)
        if item.period_start_local.astimezone(UTC) >= earliest_utc
        and (item.period_start_local + _INTERVAL_DELTA).astimezone(UTC) <= latest_end_utc
    ]
    if not eligible_indexes:
        return _SchedulingResult(intervals=list(intervals), optimizer_status="no_eligible_intervals")

    scheduled = list(intervals)
    levels = {index: 0 for index in eligible_indexes}
    allocated_kwh = 0.0
    evaluations = 0
    current_plan = _candidate_plan(scheduled, now_utc, actuators, tasks, ess_actuator)
    current_score = objective_scorer(current_plan)
    evaluations += 1
    if current_score is None:
        return _SchedulingResult(
            intervals=scheduled,
            optimizer_status="objective_unavailable",
            candidate_evaluations=evaluations,
        )

    maximum_iterations = len(eligible_indexes) * len(power_steps)
    for _ in range(maximum_iterations):
        if allocated_kwh >= task.required_energy_kwh - 1e-9:
            break
        candidates: list[
            tuple[float, float, float, int, int, list[ShadowPlanInterval], float]
        ] = []
        remaining_kwh = task.required_energy_kwh - allocated_kwh
        for index in eligible_indexes:
            level = levels[index]
            if level >= len(power_steps):
                continue
            current_power_w = 0.0 if level == 0 else power_steps[level - 1]
            next_power_w = power_steps[level]
            added_power_w = next_power_w - current_power_w
            added_kwh = added_power_w * _INTERVAL_HOURS / 1000.0
            candidate_intervals = _add_scheduled_power(scheduled, index, added_power_w)
            candidate_plan = _candidate_plan(candidate_intervals, now_utc, actuators, tasks, ess_actuator)
            candidate_score = objective_scorer(candidate_plan)
            evaluations += 1
            if candidate_score is None:
                continue
            marginal_cost = (candidate_score - current_score) / added_kwh
            overshoot_kwh = max(0.0, added_kwh - remaining_kwh)
            candidates.append(
                (
                    overshoot_kwh,
                    marginal_cost,
                    candidate_score,
                    index,
                    level + 1,
                    candidate_intervals,
                    added_kwh,
                )
            )
        if not candidates:
            break
        non_overshooting = [candidate for candidate in candidates if candidate[0] <= 1e-9]
        if non_overshooting:
            chosen = min(non_overshooting, key=lambda item: (item[1], item[2], item[3]))
        else:
            chosen = min(candidates, key=lambda item: (item[0], item[1], item[2], item[3]))
        _, _, current_score, index, next_level, scheduled, added_kwh = chosen
        levels[index] = next_level
        allocated_kwh += added_kwh

    if allocated_kwh < task.required_energy_kwh - 1e-9:
        return _SchedulingResult(
            intervals=scheduled,
            optimizer_status="deadline_infeasible",
            score_eur=current_score,
            candidate_evaluations=evaluations,
        )
    return _SchedulingResult(
        intervals=scheduled,
        optimizer_status="candidate_ready",
        score_eur=current_score,
        candidate_evaluations=evaluations,
    )


def _candidate_plan(
    intervals: list[ShadowPlanInterval],
    now_utc: datetime,
    actuators: tuple[ActuatorSnapshot, ...],
    tasks: tuple[PlanningTask, ...],
    ess_actuator: EssActuatorSnapshot,
) -> ShadowPlan:
    projected = _project_ess(intervals, ess_actuator)
    return ShadowPlan(
        generated_at_utc=now_utc.astimezone(UTC),
        intervals=projected,
        ess_projection_status="projected",
        actuator_snapshots=actuators,
        tasks=tasks,
        ess_resource=ess_actuator.capabilities,
        ess_initial_soc_percent=max(0.0, min(100.0, float(ess_actuator.soc_percent))),
    )


def _add_scheduled_power(
    intervals: list[ShadowPlanInterval],
    index: int,
    added_power_w: float,
) -> list[ShadowPlanInterval]:
    candidate = list(intervals)
    item = candidate[index]
    scheduled_load_w = item.scheduled_load_w + added_power_w
    candidate[index] = replace(
        item,
        scheduled_load_w=scheduled_load_w,
        net_power_before_control_w=item.background_load_w + scheduled_load_w - item.pv_power_w,
    )
    return candidate


def _schedule_tasks(
    intervals: list[ShadowPlanInterval],
    actuators: tuple[ActuatorSnapshot, ...],
    tasks: tuple[PlanningTask, ...],
) -> list[ShadowPlanInterval]:
    """Apply the first deadline-only shadow task scheduler without an economic objective."""
    scheduled = list(intervals)
    ev_actuator = find_ev_actuator(actuators)
    if ev_actuator is None or not ev_actuator.planning_available:
        return scheduled
    for task in tasks:
        if task.kind != "energy_by_deadline" or task.actuator_id != ev_actuator.actuator_id:
            continue
        if not task.planning_available or task.required_energy_kwh is None or task.required_energy_kwh <= 0.0:
            continue
        scheduled = _schedule_ev_energy_task(scheduled, task, ev_actuator)
    return scheduled


def _schedule_ev_energy_task(
    intervals: list[ShadowPlanInterval],
    task: PlanningTask,
    actuator: EvActuatorSnapshot,
) -> list[ShadowPlanInterval]:
    """Place EV energy in the earliest eligible slots using feasible charger power steps."""
    if task.earliest_start_local is None or task.latest_end_local is None or task.required_energy_kwh is None:
        return intervals
    power_steps = _ev_charge_power_steps_w(actuator)
    if not power_steps:
        return intervals

    earliest_utc = task.earliest_start_local.astimezone(UTC)
    latest_end_utc = task.latest_end_local.astimezone(UTC)
    eligible_indexes = [
        index
        for index, item in enumerate(intervals)
        if item.period_start_local.astimezone(UTC) >= earliest_utc
        and (item.period_start_local + _INTERVAL_DELTA).astimezone(UTC) <= latest_end_utc
    ]
    remaining_kwh = task.required_energy_kwh
    scheduled = list(intervals)
    maximum_power_w = power_steps[-1]
    maximum_interval_kwh = maximum_power_w * _INTERVAL_HOURS / 1000.0

    for index in eligible_indexes:
        if remaining_kwh <= 1e-9:
            break
        if remaining_kwh >= maximum_interval_kwh - 1e-9:
            selected_power_w = maximum_power_w
        else:
            required_power_w = remaining_kwh * 1000.0 / _INTERVAL_HOURS
            selected_power_w = next(
                (power_w for power_w in power_steps if power_w >= required_power_w - 1e-9),
                maximum_power_w,
            )
        scheduled_load_w = scheduled[index].scheduled_load_w + selected_power_w
        scheduled[index] = replace(
            scheduled[index],
            scheduled_load_w=scheduled_load_w,
            net_power_before_control_w=(
                scheduled[index].background_load_w + scheduled_load_w - scheduled[index].pv_power_w
            ),
        )
        remaining_kwh -= selected_power_w * _INTERVAL_HOURS / 1000.0
    return scheduled


def _ev_charge_power_steps_w(actuator: EvActuatorSnapshot) -> tuple[float, ...]:
    """Return the EV actuator's feasible whole-ampere AC charging powers."""
    capabilities = actuator.capabilities
    minimum_current = math.ceil(capabilities.min_charge_current_a)
    maximum_current = math.floor(capabilities.max_charge_current_a)
    phase_counts: list[int] = []
    if capabilities.supports_single_phase:
        phase_counts.append(1)
    if capabilities.supports_three_phase:
        phase_counts.append(3)
    powers = {
        phase_count * capabilities.nominal_voltage_v * float(current_a)
        for phase_count in phase_counts
        for current_a in range(minimum_current, maximum_current + 1)
    }
    return tuple(sorted(powers))


def _project_ess(
    intervals: list[ShadowPlanInterval],
    actuator: EssActuatorSnapshot,
) -> tuple[ShadowPlanInterval, ...]:
    """Project greedy self-consumption through the ESS actuator capability envelope."""
    if actuator.soc_percent is None:
        raise ValueError("ESS actuator SoC is required for projection")
    resource = actuator.capabilities
    soc = max(0.0, min(100.0, actuator.soc_percent))
    stored_kwh = resource.capacity_kwh * soc / 100.0
    minimum_kwh = resource.capacity_kwh * resource.min_soc_percent / 100.0
    maximum_kwh = resource.capacity_kwh * resource.max_soc_percent / 100.0
    projected: list[ShadowPlanInterval] = []
    for item in intervals:
        ac_balance_w = item.total_load_w - item.pv_ac_power_w
        ess_ac_power_w = 0.0
        battery_delta_kwh = 0.0
        curtailed_dc_w = 0.0
        if ac_balance_w >= 0.0:
            dc_to_ac_w = min(
                ac_balance_w,
                resource.max_discharge_power_w,
                item.pv_dc_power_w * resource.discharge_efficiency,
            )
            dc_used_w = dc_to_ac_w / resource.discharge_efficiency
            ess_ac_power_w += dc_to_ac_w
            remaining_deficit_w = ac_balance_w - dc_to_ac_w
            inverter_headroom_w = max(0.0, resource.max_discharge_power_w - dc_to_ac_w)
            available_stored_kwh = max(0.0, stored_kwh - minimum_kwh)
            battery_ac_limit_w = (
                available_stored_kwh * resource.discharge_efficiency / _INTERVAL_HOURS * 1000.0
            )
            battery_to_ac_w = min(remaining_deficit_w, inverter_headroom_w, battery_ac_limit_w)
            battery_used_kwh = battery_to_ac_w / resource.discharge_efficiency * _INTERVAL_HOURS / 1000.0
            stored_kwh -= battery_used_kwh
            battery_delta_kwh -= battery_used_kwh
            ess_ac_power_w += battery_to_ac_w
            remaining_deficit_w -= battery_to_ac_w
            unused_dc_w = max(0.0, item.pv_dc_power_w - dc_used_w)
            room_kwh = max(0.0, maximum_kwh - stored_kwh)
            charge_by_room_w = room_kwh / resource.charge_efficiency / _INTERVAL_HOURS * 1000.0
            dc_charge_w = min(unused_dc_w, resource.max_charge_power_w, charge_by_room_w)
            stored_added_kwh = dc_charge_w * resource.charge_efficiency * _INTERVAL_HOURS / 1000.0
            stored_kwh += stored_added_kwh
            battery_delta_kwh += stored_added_kwh
            curtailed_dc_w = max(0.0, unused_dc_w - dc_charge_w)
            grid_after_ess_w = max(0.0, remaining_deficit_w)
        else:
            ac_surplus_w = -ac_balance_w
            room_kwh = max(0.0, maximum_kwh - stored_kwh)
            charge_by_room_w = room_kwh / resource.charge_efficiency / _INTERVAL_HOURS * 1000.0
            dc_charge_w = min(item.pv_dc_power_w, resource.max_charge_power_w, charge_by_room_w)
            stored_added_dc_kwh = dc_charge_w * resource.charge_efficiency * _INTERVAL_HOURS / 1000.0
            stored_kwh += stored_added_dc_kwh
            battery_delta_kwh += stored_added_dc_kwh
            curtailed_dc_w = max(0.0, item.pv_dc_power_w - dc_charge_w)
            charge_headroom_w = max(0.0, resource.max_charge_power_w - dc_charge_w)
            room_kwh = max(0.0, maximum_kwh - stored_kwh)
            charge_by_room_w = room_kwh / resource.charge_efficiency / _INTERVAL_HOURS * 1000.0
            ac_charge_w = min(ac_surplus_w, charge_headroom_w, charge_by_room_w)
            stored_added_ac_kwh = ac_charge_w * resource.charge_efficiency * _INTERVAL_HOURS / 1000.0
            stored_kwh += stored_added_ac_kwh
            battery_delta_kwh += stored_added_ac_kwh
            ess_ac_power_w -= ac_charge_w
            grid_after_ess_w = -(ac_surplus_w - ac_charge_w)
        stored_kwh = max(0.0, min(resource.capacity_kwh, stored_kwh))
        projected_soc = 100.0 * stored_kwh / resource.capacity_kwh
        projected.append(
            ShadowPlanInterval(
                period_start_local=item.period_start_local,
                background_load_w=item.background_load_w,
                scheduled_load_w=item.scheduled_load_w,
                pv_ac_power_w=item.pv_ac_power_w,
                pv_dc_power_w=item.pv_dc_power_w,
                pv_power_w=item.pv_power_w,
                net_power_before_control_w=item.net_power_before_control_w,
                ess_ac_power_w=ess_ac_power_w,
                battery_energy_delta_kwh=battery_delta_kwh,
                projected_soc_percent=projected_soc,
                grid_power_after_ess_w=grid_after_ess_w,
                curtailed_dc_pv_w=curtailed_dc_w,
            )
        )
    return tuple(projected)


def _pv_powers_for_interval(forecast: PvForecast, interval_start_local: datetime) -> tuple[float, float]:
    """Return AC-coupled roof and DC-coupled shed PV potential for one planner interval."""
    start_utc = interval_start_local.astimezone(UTC)
    for point in forecast.points:
        end_utc = point.period_end_local.astimezone(UTC)
        if end_utc - timedelta(hours=1) <= start_utc < end_utc:
            ac_power_w = max(0.0, point.front_power_w + point.rear_power_w)
            dc_power_w = max(0.0, point.shed_power_w)
            return ac_power_w, dc_power_w
    return 0.0, 0.0
