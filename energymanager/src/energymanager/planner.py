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

PLANNER_VERSION = "2026-10-08-shadow-v8"
PLANNER_HORIZON_HOURS = 168
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
    """Compare a bounded portfolio of feasible EV schedules using the economic objective."""
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
    if ev_actuator is None or not ev_actuator.planning_available or len(supported) != len(active_tasks):
        return _SchedulingResult(
            intervals=baseline_intervals,
            optimizer_status="unsupported_task_set",
            objective_name=objective_name,
            score_eur=baseline_score,
            baseline_score_eur=baseline_score,
            candidate_evaluations=1,
        )
    if not supported:
        return _SchedulingResult(
            intervals=baseline_intervals,
            optimizer_status="no_active_tasks",
            objective_name=objective_name,
            score_eur=baseline_score,
            baseline_score_eur=baseline_score,
            candidate_evaluations=1,
        )

    power_steps = _ev_charge_power_steps_w(ev_actuator)
    if not power_steps:
        return _SchedulingResult(
            intervals=baseline_intervals,
            optimizer_status="no_charge_steps",
            objective_name=objective_name,
            score_eur=baseline_score,
            baseline_score_eur=baseline_score,
            candidate_evaluations=1,
        )

    base_projection = _project_ess(intervals, ess_actuator)
    base_grid_w = tuple(max(0.0, float(item.grid_power_after_ess_w or 0.0)) for item in base_projection)
    ceilings = _representative_power_ceilings(power_steps)
    strategies = ("base_grid_low", "net_low", "even", "latest")
    best_intervals = baseline_intervals
    best_score = baseline_score
    best_strategy = "deadline_earliest"
    evaluations = 1
    seen = {_schedule_signature(baseline_intervals)}

    ordered_tasks = tuple(sorted(supported, key=_task_deadline_key))
    for strategy in strategies:
        for ceiling_w in ceilings:
            candidate = _schedule_ev_task_set(
                intervals,
                ordered_tasks,
                ev_actuator,
                power_ceiling_w=ceiling_w,
                strategy=strategy,
                base_grid_w=base_grid_w,
            )
            if candidate is None:
                continue
            signature = _schedule_signature(candidate)
            if signature in seen:
                continue
            seen.add(signature)
            candidate_plan = _candidate_plan(candidate, now_utc, actuators, tasks, ess_actuator)
            candidate_score = objective_scorer(candidate_plan)
            evaluations += 1
            if candidate_score is None:
                continue
            if candidate_score < best_score - 1e-9:
                best_intervals = candidate
                best_score = candidate_score
                best_strategy = f"economic_ev_portfolio:{strategy}"

    if best_intervals is baseline_intervals:
        return _SchedulingResult(
            intervals=baseline_intervals,
            optimizer_status="baseline_retained",
            objective_name=objective_name,
            score_eur=baseline_score,
            baseline_score_eur=baseline_score,
            candidate_evaluations=evaluations,
        )
    return _SchedulingResult(
        intervals=best_intervals,
        strategy=best_strategy,
        optimizer_status="optimized",
        objective_name=objective_name,
        score_eur=best_score,
        baseline_score_eur=baseline_score,
        candidate_evaluations=evaluations,
    )


def _representative_power_ceilings(power_steps: tuple[float, ...]) -> tuple[float, ...]:
    """Return a small charger-power portfolio so search cost stays bounded as the horizon grows."""
    if len(power_steps) <= 5:
        return power_steps
    last = len(power_steps) - 1
    indexes = {0, round(last * 0.25), round(last * 0.50), round(last * 0.75), last}
    return tuple(power_steps[index] for index in sorted(indexes))


def _schedule_ev_task_set(
    intervals: list[ShadowPlanInterval],
    tasks: tuple[PlanningTask, ...],
    actuator: EvActuatorSnapshot,
    *,
    power_ceiling_w: float,
    strategy: str,
    base_grid_w: tuple[float, ...],
) -> list[ShadowPlanInterval] | None:
    """Schedule multiple additive EV energy requirements without exceeding one physical charger state."""
    scheduled = list(intervals)
    for task in tasks:
        scheduled = _schedule_ev_task_by_priority(
            scheduled,
            task,
            actuator,
            power_ceiling_w=power_ceiling_w,
            strategy=strategy,
            base_grid_w=base_grid_w,
        )
        if scheduled is None:
            return None
    return scheduled


def _schedule_ev_task_by_priority(
    intervals: list[ShadowPlanInterval],
    task: PlanningTask,
    actuator: EvActuatorSnapshot,
    *,
    power_ceiling_w: float,
    strategy: str,
    base_grid_w: tuple[float, ...],
) -> list[ShadowPlanInterval] | None:
    if task.earliest_start_local is None or task.latest_end_local is None or task.required_energy_kwh is None:
        return None
    steps = tuple(step for step in _ev_charge_power_steps_w(actuator) if step <= power_ceiling_w + 1e-9)
    if not steps:
        return None
    eligible = _eligible_task_indexes(intervals, task)
    if not eligible:
        return None
    order = _priority_indexes(intervals, eligible, strategy=strategy, base_grid_w=base_grid_w)
    scheduled = list(intervals)
    remaining_kwh = task.required_energy_kwh

    while remaining_kwh > 1e-9:
        progressed = False
        for index in order:
            current_w = scheduled[index].scheduled_load_w
            target_w = next((step for step in steps if step > current_w + 1e-9), None)
            if target_w is None:
                continue
            added_w = target_w - current_w
            scheduled = _add_scheduled_power(scheduled, index, added_w)
            remaining_kwh -= added_w * _INTERVAL_HOURS / 1000.0
            progressed = True
            if remaining_kwh <= 1e-9:
                break
        if not progressed:
            return None
    return scheduled


def _eligible_task_indexes(intervals: list[ShadowPlanInterval], task: PlanningTask) -> list[int]:
    if task.earliest_start_local is None or task.latest_end_local is None:
        return []
    earliest_utc = task.earliest_start_local.astimezone(UTC)
    latest_end_utc = task.latest_end_local.astimezone(UTC)
    return [
        index
        for index, item in enumerate(intervals)
        if item.period_start_local.astimezone(UTC) >= earliest_utc
        and (item.period_start_local + _INTERVAL_DELTA).astimezone(UTC) <= latest_end_utc
    ]


def _priority_indexes(
    intervals: list[ShadowPlanInterval],
    eligible: list[int],
    *,
    strategy: str,
    base_grid_w: tuple[float, ...],
) -> list[int]:
    if strategy == "base_grid_low":
        return sorted(eligible, key=lambda index: (base_grid_w[index], index))
    if strategy == "net_low":
        return sorted(eligible, key=lambda index: (intervals[index].net_power_before_control_w, index))
    if strategy == "latest":
        return list(reversed(eligible))
    if strategy == "even":
        return _spread_indexes(eligible)
    raise ValueError(f"Unknown EV scheduling strategy: {strategy}")


def _spread_indexes(indexes: list[int]) -> list[int]:
    """Return indexes in midpoint-first order so partial use is spread across the full task window."""
    result: list[int] = []
    ranges = [(0, len(indexes) - 1)]
    while ranges:
        left, right = ranges.pop(0)
        if left > right:
            continue
        middle = (left + right) // 2
        result.append(indexes[middle])
        ranges.append((left, middle - 1))
        ranges.append((middle + 1, right))
    return result


def _schedule_signature(intervals: list[ShadowPlanInterval]) -> tuple[int, ...]:
    return tuple(round(item.scheduled_load_w) for item in intervals)


def _task_deadline_key(task: PlanningTask) -> datetime:
    if task.latest_end_local is None:
        return datetime.max.replace(tzinfo=UTC)
    return task.latest_end_local.astimezone(UTC)


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
    """Place one additive EV requirement in earliest slots without exceeding charger capability."""
    if task.required_energy_kwh is None:
        return intervals
    power_steps = _ev_charge_power_steps_w(actuator)
    if not power_steps:
        return intervals
    eligible_indexes = _eligible_task_indexes(intervals, task)
    remaining_kwh = task.required_energy_kwh
    scheduled = list(intervals)
    maximum_power_w = power_steps[-1]

    for index in eligible_indexes:
        if remaining_kwh <= 1e-9:
            break
        current_power_w = scheduled[index].scheduled_load_w
        if current_power_w >= maximum_power_w - 1e-9:
            continue
        maximum_added_w = maximum_power_w - current_power_w
        maximum_added_kwh = maximum_added_w * _INTERVAL_HOURS / 1000.0
        if remaining_kwh >= maximum_added_kwh - 1e-9:
            target_power_w = maximum_power_w
        else:
            required_total_w = current_power_w + remaining_kwh * 1000.0 / _INTERVAL_HOURS
            target_power_w = next(
                (power_w for power_w in power_steps if power_w >= required_total_w - 1e-9),
                maximum_power_w,
            )
        added_power_w = max(0.0, target_power_w - current_power_w)
        scheduled = _add_scheduled_power(scheduled, index, added_power_w)
        remaining_kwh -= added_power_w * _INTERVAL_HOURS / 1000.0
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
