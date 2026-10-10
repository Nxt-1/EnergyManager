"""Authoritative seven-day MILP shadow planner."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import UTC, timedelta
from time import perf_counter
from typing import Any

import numpy as np

from .actuators import EssActuatorSnapshot, EvActuatorSnapshot, find_ess_actuator, find_ev_actuator
from .economics import (
    ECONOMIC_OBJECTIVE_VERSION,
    CapacityPeakState,
    TariffProfile,
    evaluate_plan_cost,
    evaluate_plan_objective,
)
from .ha_client import HomeAssistantClient
from .planner import ShadowPlan, ShadowPlanInterval
from .tasks import PlanningTask

MILP_EVALUATION_VERSION = "2026-10-10-milp-v7"
MILP_STATUS_ENTITY = "sensor.energy_manager_milp_status"
MILP_TOTAL_TIME_BUDGET_SECONDS = 30.0
MILP_ECONOMIC_TIME_LIMIT_SECONDS = MILP_TOTAL_TIME_BUDGET_SECONDS
MILP_TIME_LIMIT_SECONDS = MILP_TOTAL_TIME_BUDGET_SECONDS
MILP_RELATIVE_GAP = 0.01
MILP_REFRESH_MINUTES = 10
MILP_ECONOMIC_TOLERANCE_EUR = 0.01
MILP_EARLY_VALUE_HALF_LIFE_DAYS = 3.0
_VALIDATION_POWER_TOLERANCE_W = 5.0
_INTERVAL_HOURS = 0.25
_INTERVAL_DELTA = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class MilpTaskValidation:
    """Independent post-solve check of one hard planner task."""

    task_id: str
    required_energy_kwh: float
    scheduled_energy_kwh: float
    scheduled_after_deadline_kwh: float
    charging_during_away_windows_kwh: float
    deadline_met: bool
    power_steps_valid: bool
    valid: bool


@dataclass(frozen=True, slots=True)
class MilpCostBreakdown:
    """Seven-day accounting used to compare the reference and MILP plans."""

    import_kwh: float
    export_kwh: float
    net_energy_cost_eur: float
    incremental_capacity_cost_eur: float | None
    total_marginal_cost_eur: float | None
    terminal_usable_ac_kwh: float
    terminal_ess_value_eur: float
    objective_eur: float
    max_grid_import_kw: float
    end_soc_percent: float


@dataclass(frozen=True, slots=True)
class MilpEvaluation:
    """Result of the authoritative HiGHS shadow planner solve."""

    status: str
    model_status: str | None
    solver_version: str | None
    solve_time_seconds: float | None
    mip_gap: float | None
    mip_node_count: int | None
    variable_count: int
    integer_variable_count: int
    constraint_count: int
    horizon_intervals: int
    active_task_count: int
    reference_strategy: str
    reference_objective_eur: float | None
    milp_objective_eur: float | None
    estimated_improvement_eur: float | None
    economic_solve_time_seconds: float | None = None
    economic_time_limit_seconds: float = MILP_ECONOMIC_TIME_LIMIT_SECONDS
    tie_break_solve_time_seconds: float | None = None
    tie_break_time_limit_seconds: float | None = None
    tie_break_status: str | None = None
    tie_break_warm_start_applied: bool = False
    tie_break_warm_start_status: str | None = None
    selected_solution_stage: str | None = None
    first_stage_objective_eur: float | None = None
    economic_tolerance_eur: float = MILP_ECONOMIC_TOLERANCE_EUR
    early_value_half_life_days: float = MILP_EARLY_VALUE_HALF_LIFE_DAYS
    time_weighted_grid_import_score: float | None = None
    preferred_ev_target_kwh: float = 0.0
    preferred_ev_scheduled_kwh: float = 0.0
    preferred_ev_shortfall_kwh: float = 0.0
    preferred_ev_shortfall_penalty_eur: float = 0.0
    validation_status: str = "not_run"
    validation_errors: tuple[str, ...] = ()
    task_validation: tuple[MilpTaskValidation, ...] = ()
    reference_cost: MilpCostBreakdown | None = None
    milp_cost: MilpCostBreakdown | None = None
    adoption_ready: bool = False
    fallback_to_reference: bool = True
    plan: ShadowPlan | None = None
    reason: str | None = None


@dataclass(slots=True)
class _MilpVariables:
    grid_import_kw: list[Any]
    grid_export_kw: list[Any]
    ac_charge_kw: list[Any]
    dc_charge_kw: list[Any]
    battery_discharge_kw: list[Any]
    dc_to_ac_kw: list[Any]
    curtailed_dc_kw: list[Any]
    stored_energy_kwh: list[Any]
    inverter_charge_mode: list[Any]
    battery_charge_mode: list[Any]
    ev_single_phase_a: dict[int, Any]
    ev_three_phase_a: dict[int, Any]
    ev_stored_energy_kwh: list[Any]
    ev_preferred_shortfall_kwh: Any | None
    capacity_peak_kw: dict[str, Any]


def evaluate_shadow_plan_milp(
    reference_plan: ShadowPlan,
    profile: TariffProfile,
    capacity_state: CapacityPeakState,
) -> MilpEvaluation:
    """Solve the authoritative EV+ESS MILP shadow plan."""
    ess = find_ess_actuator(reference_plan.actuator_snapshots)
    ev = find_ev_actuator(reference_plan.actuator_snapshots)
    active_tasks = tuple(
        task
        for task in reference_plan.tasks
        if task.planning_available
        and (
            task.kind == "ev_terminal_soc_target"
            or (task.required_energy_kwh is not None and task.required_energy_kwh > 0.0)
            or (task.preferred_energy_kwh is not None and task.preferred_energy_kwh > 0.0)
            or (task.expected_trip_energy_kwh is not None and task.expected_trip_energy_kwh > 0.0)
        )
    )
    reference_objective = _objective(reference_plan, profile, capacity_state)
    validation_error = _validate_inputs(reference_plan, ess, ev, active_tasks, profile, capacity_state)
    if validation_error is not None:
        return _empty_result(
            reference_plan,
            active_tasks,
            reference_objective,
            status="unsupported",
            reason=validation_error,
        )

    try:
        import highspy
    except ImportError as exc:
        return _empty_result(
            reference_plan,
            active_tasks,
            reference_objective,
            status="solver_unavailable",
            reason=str(exc),
        )

    assert ess is not None and ess.soc_percent is not None
    try:
        return _solve_model(highspy, reference_plan, profile, capacity_state, ess, ev, active_tasks)
    except Exception as exc:  # pragma: no cover - runtime safety around the optional diagnostic solver
        result = _empty_result(
            reference_plan,
            active_tasks,
            reference_objective,
            status="error",
            reason=f"{type(exc).__name__}: {exc}",
        )
        return _replace_solver_version(result, _solver_version(highspy))


def _empty_result(
    plan: ShadowPlan,
    tasks: tuple[PlanningTask, ...],
    reference_objective: float | None,
    *,
    status: str,
    reason: str,
) -> MilpEvaluation:
    return MilpEvaluation(
        status=status,
        model_status=None,
        solver_version=None,
        solve_time_seconds=None,
        mip_gap=None,
        mip_node_count=None,
        variable_count=0,
        integer_variable_count=0,
        constraint_count=0,
        horizon_intervals=len(plan.intervals),
        active_task_count=len(tasks),
        reference_strategy=plan.scheduling_strategy,
        reference_objective_eur=reference_objective,
        milp_objective_eur=None,
        estimated_improvement_eur=None,
        reason=reason,
    )


def _replace_solver_version(result: MilpEvaluation, version: str) -> MilpEvaluation:
    return MilpEvaluation(
        status=result.status,
        model_status=result.model_status,
        solver_version=version,
        solve_time_seconds=result.solve_time_seconds,
        mip_gap=result.mip_gap,
        mip_node_count=result.mip_node_count,
        variable_count=result.variable_count,
        integer_variable_count=result.integer_variable_count,
        constraint_count=result.constraint_count,
        horizon_intervals=result.horizon_intervals,
        active_task_count=result.active_task_count,
        reference_strategy=result.reference_strategy,
        reference_objective_eur=result.reference_objective_eur,
        milp_objective_eur=result.milp_objective_eur,
        estimated_improvement_eur=result.estimated_improvement_eur,
        economic_solve_time_seconds=result.economic_solve_time_seconds,
        economic_time_limit_seconds=result.economic_time_limit_seconds,
        tie_break_solve_time_seconds=result.tie_break_solve_time_seconds,
        tie_break_time_limit_seconds=result.tie_break_time_limit_seconds,
        tie_break_status=result.tie_break_status,
        tie_break_warm_start_applied=result.tie_break_warm_start_applied,
        tie_break_warm_start_status=result.tie_break_warm_start_status,
        selected_solution_stage=result.selected_solution_stage,
        first_stage_objective_eur=result.first_stage_objective_eur,
        economic_tolerance_eur=result.economic_tolerance_eur,
        early_value_half_life_days=result.early_value_half_life_days,
        time_weighted_grid_import_score=result.time_weighted_grid_import_score,
        preferred_ev_target_kwh=result.preferred_ev_target_kwh,
        preferred_ev_scheduled_kwh=result.preferred_ev_scheduled_kwh,
        preferred_ev_shortfall_kwh=result.preferred_ev_shortfall_kwh,
        preferred_ev_shortfall_penalty_eur=result.preferred_ev_shortfall_penalty_eur,
        validation_status=result.validation_status,
        validation_errors=result.validation_errors,
        task_validation=result.task_validation,
        reference_cost=result.reference_cost,
        milp_cost=result.milp_cost,
        adoption_ready=result.adoption_ready,
        fallback_to_reference=result.fallback_to_reference,
        plan=result.plan,
        reason=result.reason,
    )


def _validate_inputs(
    plan: ShadowPlan,
    ess: EssActuatorSnapshot | None,
    ev: EvActuatorSnapshot | None,
    tasks: tuple[PlanningTask, ...],
    profile: TariffProfile,
    capacity_state: CapacityPeakState,
) -> str | None:
    if not plan.intervals:
        return "empty_plan"
    if ess is None or not ess.planning_available or ess.soc_percent is None:
        return "ess_unavailable"
    if not capacity_state.history_complete or capacity_state.observed_peak_kw is None:
        return "capacity_history_incomplete"
    if profile.import_energy_eur_per_kwh <= profile.export_energy_eur_per_kwh:
        return "import_export_arbitrage_not_modelled"
    if not tasks:
        return None
    if ev is None or not ev.configured or ev.soc_percent is None:
        return "ev_unavailable"
    if ev.capabilities.battery_capacity_kwh is None:
        return "ev_battery_capacity_unavailable"
    last_interval_end_utc = (plan.intervals[-1].period_start_local + _INTERVAL_DELTA).astimezone(UTC)
    for task in tasks:
        if task.actuator_id != ev.actuator_id or task.kind not in {"energy_by_deadline", "ev_terminal_soc_target"}:
            return "unsupported_task_type"
        if task.earliest_start_local is None or task.latest_end_local is None:
            return "task_window_missing"
        if task.latest_end_local.astimezone(UTC) > last_interval_end_utc + timedelta(seconds=1):
            return "task_deadline_outside_horizon"
    return None

def _solve_model(
    highspy: Any,
    reference_plan: ShadowPlan,
    profile: TariffProfile,
    capacity_state: CapacityPeakState,
    ess: EssActuatorSnapshot,
    ev: EvActuatorSnapshot | None,
    active_tasks: tuple[PlanningTask, ...],
) -> MilpEvaluation:
    model = highspy.Highs()
    model.setOptionValue("output_flag", False)
    model.setOptionValue("threads", 1)
    model.setOptionValue("time_limit", MILP_ECONOMIC_TIME_LIMIT_SECONDS)
    model.setOptionValue("mip_rel_gap", MILP_RELATIVE_GAP)

    variables, integer_count = _build_variables(
        model,
        highspy,
        reference_plan,
        ess,
        ev,
        active_tasks,
        profile,
        capacity_state,
    )
    _add_constraints(model, reference_plan, ess, ev, active_tasks, variables)
    economic_expression = _economic_objective_expression(reference_plan, ess, ev, profile, variables)
    model.setObjective(economic_expression, sense=highspy.ObjSense.kMinimize)

    economic_started = perf_counter()
    model.run()
    economic_solve_time = perf_counter() - economic_started
    stage1_model_status = model.modelStatusToString(model.getModelStatus())
    stage1_info = model.getInfo()
    stage1_solution = model.getSolution()
    stage1_has_solution = _has_solution(highspy, stage1_info)
    reference_objective = _objective(reference_plan, profile, capacity_state)
    reference_cost = _cost_breakdown(reference_plan, profile, capacity_state)

    if not stage1_has_solution:
        return MilpEvaluation(
            status=_status_from_model(stage1_model_status, has_solution=False),
            model_status=stage1_model_status,
            solver_version=_solver_version(highspy),
            solve_time_seconds=economic_solve_time,
            mip_gap=_finite_optional(getattr(stage1_info, "mip_gap", None)),
            mip_node_count=_integer_optional(getattr(stage1_info, "mip_node_count", None)),
            variable_count=int(model.getNumCol()),
            integer_variable_count=integer_count,
            constraint_count=int(model.getNumRow()),
            horizon_intervals=len(reference_plan.intervals),
            active_task_count=len(active_tasks),
            reference_strategy=reference_plan.scheduling_strategy,
            reference_objective_eur=reference_objective,
            milp_objective_eur=None,
            estimated_improvement_eur=None,
            economic_solve_time_seconds=economic_solve_time,
            economic_time_limit_seconds=MILP_ECONOMIC_TIME_LIMIT_SECONDS,
            validation_status="not_run",
            reference_cost=reference_cost,
            adoption_ready=False,
            fallback_to_reference=False,
            reason="solver_returned_no_primal_solution",
        )

    stage1_values = list(stage1_solution.col_value)
    stage1_plan = _solution_plan(reference_plan, ess, ev, profile, variables, stage1_values)
    stage1_objective = _objective(stage1_plan, profile, capacity_state)
    stage1_internal_objective = _economic_objective_value(ess, ev, profile, variables, stage1_values)

    tie_break_time_limit = max(0.0, MILP_TOTAL_TIME_BUDGET_SECONDS - economic_solve_time)
    if tie_break_time_limit >= 0.5:
        model.addConstr(economic_expression <= stage1_internal_objective + MILP_ECONOMIC_TOLERANCE_EUR)
        tie_break_expression = _time_weighted_grid_import_expression(reference_plan, variables)
        model.setObjective(tie_break_expression, sense=highspy.ObjSense.kMinimize)
        warm_start_applied, warm_start_status = _set_primal_warm_start(model, highspy, stage1_values)
        model.setOptionValue("time_limit", tie_break_time_limit)

        tie_break_started = perf_counter()
        model.run()
        tie_break_solve_time = perf_counter() - tie_break_started
        stage2_model_status = model.modelStatusToString(model.getModelStatus())
        stage2_info = model.getInfo()
        stage2_solution = model.getSolution()
        stage2_has_solution = _has_solution(highspy, stage2_info)
        tie_break_status = _status_from_model(stage2_model_status, has_solution=stage2_has_solution)
    else:
        warm_start_applied = False
        warm_start_status = "skipped_no_budget"
        tie_break_solve_time = 0.0
        stage2_model_status = stage1_model_status
        stage2_info = stage1_info
        stage2_solution = stage1_solution
        stage2_has_solution = False
        tie_break_status = "skipped_no_budget"

    if stage2_has_solution:
        values = list(stage2_solution.col_value)
        selected_model_status = stage2_model_status
        selected_info = stage2_info
        selected_solution_stage = "tie_break"
    else:
        values = stage1_values
        selected_model_status = stage1_model_status
        selected_info = stage1_info
        selected_solution_stage = "economic"

    milp_plan = _solution_plan(reference_plan, ess, ev, profile, variables, values)
    milp_objective = _objective(milp_plan, profile, capacity_state)
    if milp_objective is not None:
        milp_plan = replace(milp_plan, optimizer_score_eur=milp_objective)
    improvement = None
    if reference_objective is not None and milp_objective is not None:
        improvement = reference_objective - milp_objective

    validation_errors, task_validation = _validate_solution_plan(
        reference_plan,
        milp_plan,
        ess,
        ev,
        active_tasks,
    )
    validation_status = "passed" if not validation_errors else "failed"
    selected_status = _status_from_model(selected_model_status, has_solution=True)
    adoption_ready = not validation_errors and selected_status in {"optimal", "feasible", "feasible_time_limit"}
    reason = None if not validation_errors else "; ".join(validation_errors[:4])
    total_solve_time = economic_solve_time + tie_break_solve_time

    return MilpEvaluation(
        status="invalid_solution" if validation_errors else selected_status,
        model_status=selected_model_status,
        solver_version=_solver_version(highspy),
        solve_time_seconds=total_solve_time,
        mip_gap=_finite_optional(getattr(selected_info, "mip_gap", None)),
        mip_node_count=_integer_optional(getattr(selected_info, "mip_node_count", None)),
        variable_count=int(model.getNumCol()),
        integer_variable_count=integer_count,
        constraint_count=int(model.getNumRow()),
        horizon_intervals=len(reference_plan.intervals),
        active_task_count=len(active_tasks),
        reference_strategy=reference_plan.scheduling_strategy,
        reference_objective_eur=reference_objective,
        milp_objective_eur=milp_objective,
        estimated_improvement_eur=improvement,
        economic_solve_time_seconds=economic_solve_time,
        economic_time_limit_seconds=MILP_ECONOMIC_TIME_LIMIT_SECONDS,
        tie_break_solve_time_seconds=tie_break_solve_time,
        tie_break_time_limit_seconds=tie_break_time_limit,
        tie_break_status=tie_break_status,
        tie_break_warm_start_applied=warm_start_applied,
        tie_break_warm_start_status=warm_start_status,
        selected_solution_stage=selected_solution_stage,
        first_stage_objective_eur=stage1_objective,
        time_weighted_grid_import_score=_time_weighted_grid_import_value(variables, values),
        preferred_ev_target_kwh=_preferred_target_kwh(active_tasks),
        preferred_ev_scheduled_kwh=(
            sum(item.scheduled_load_w for item in milp_plan.intervals) * _INTERVAL_HOURS / 1000.0
        ),
        preferred_ev_shortfall_kwh=milp_plan.preferred_ev_shortfall_kwh,
        preferred_ev_shortfall_penalty_eur=milp_plan.preferred_ev_shortfall_penalty_eur,
        validation_status=validation_status,
        validation_errors=validation_errors,
        task_validation=task_validation,
        reference_cost=reference_cost,
        milp_cost=_cost_breakdown(milp_plan, profile, capacity_state),
        adoption_ready=adoption_ready,
        fallback_to_reference=False,
        plan=milp_plan,
        reason=reason,
    )


def _set_primal_warm_start(model: Any, highspy: Any, values: list[float]) -> tuple[bool, str]:
    """Seed the second-stage MIP with the complete feasible first-stage primal solution."""
    try:
        indexes = np.arange(len(values), dtype=np.int32)
        primal_values = np.asarray(values, dtype=np.float64)
        status = model.setSolution(len(values), indexes, primal_values)
    except Exception as exc:  # pragma: no cover - defensive around the optional solver API
        return False, f"error:{type(exc).__name__}:{exc}"
    name = getattr(status, "name", str(status))
    return status == highspy.HighsStatus.kOk, str(name)


def _build_variables(
    model: Any,
    highspy: Any,
    plan: ShadowPlan,
    ess: EssActuatorSnapshot,
    ev: EvActuatorSnapshot | None,
    tasks: tuple[PlanningTask, ...],
    profile: TariffProfile,
    capacity_state: CapacityPeakState,
) -> tuple[_MilpVariables, int]:
    count = len(plan.intervals)
    resource = ess.capabilities
    max_charge_kw = resource.max_charge_power_w / 1000.0
    max_discharge_kw = resource.max_discharge_power_w / 1000.0
    min_energy = resource.capacity_kwh * resource.min_soc_percent / 100.0
    max_energy = resource.capacity_kwh * resource.max_soc_percent / 100.0
    initial_energy = resource.capacity_kwh * float(ess.soc_percent) / 100.0

    grid_import = [model.addVariable(lb=0.0, name=f"grid_import_{index}") for index in range(count)]
    grid_export = [model.addVariable(lb=0.0, name=f"grid_export_{index}") for index in range(count)]
    ac_charge = [model.addVariable(lb=0.0, ub=max_charge_kw, name=f"ac_charge_{index}") for index in range(count)]
    dc_charge = [model.addVariable(lb=0.0, ub=max_charge_kw, name=f"dc_charge_{index}") for index in range(count)]
    battery_discharge = [
        model.addVariable(lb=0.0, ub=max_discharge_kw, name=f"battery_discharge_{index}")
        for index in range(count)
    ]
    dc_to_ac = [model.addVariable(lb=0.0, ub=max_discharge_kw, name=f"dc_to_ac_{index}") for index in range(count)]
    curtailed_dc = [
        model.addVariable(lb=0.0, ub=max(0.0, item.pv_dc_power_w / 1000.0), name=f"dc_curtail_{index}")
        for index, item in enumerate(plan.intervals)
    ]
    stored_energy = [model.addVariable(lb=initial_energy, ub=initial_energy, name="stored_energy_0")]
    stored_energy.extend(
        model.addVariable(lb=min_energy, ub=max_energy, name=f"stored_energy_{index + 1}")
        for index in range(count)
    )

    integer_type = highspy.HighsVarType.kInteger
    inverter_charge_mode = [
        model.addVariable(lb=0.0, ub=1.0, type=integer_type, name=f"inverter_charge_mode_{index}")
        for index in range(count)
    ]
    battery_charge_mode = [
        model.addVariable(lb=0.0, ub=1.0, type=integer_type, name=f"battery_charge_mode_{index}")
        for index in range(count)
    ]
    integer_count = 2 * count

    ev_single: dict[int, Any] = {}
    ev_three: dict[int, Any] = {}
    ev_stored_energy: list[Any] = []
    preferred_shortfall = None
    if tasks and ev is not None and ev.capabilities.battery_capacity_kwh is not None and ev.soc_percent is not None:
        eligible = _ev_variable_indexes(plan, tasks)
        min_current = math.ceil(ev.capabilities.min_charge_current_a)
        max_current = math.floor(ev.capabilities.max_charge_current_a)
        for index in eligible:
            single_on = None
            three_on = None
            if ev.capabilities.supports_single_phase:
                single_on = model.addVariable(
                    lb=0.0,
                    ub=1.0,
                    type=integer_type,
                    name=f"ev_single_on_{index}",
                )
                ev_single[index] = model.addVariable(
                    lb=0.0,
                    ub=float(max_current),
                    type=integer_type,
                    name=f"ev_single_a_{index}",
                )
                model.addConstr(ev_single[index] >= min_current * single_on)
                model.addConstr(ev_single[index] <= max_current * single_on)
                integer_count += 2
            if ev.capabilities.supports_three_phase:
                three_on = model.addVariable(
                    lb=0.0,
                    ub=1.0,
                    type=integer_type,
                    name=f"ev_three_on_{index}",
                )
                ev_three[index] = model.addVariable(
                    lb=0.0,
                    ub=float(max_current),
                    type=integer_type,
                    name=f"ev_three_a_{index}",
                )
                model.addConstr(ev_three[index] >= min_current * three_on)
                model.addConstr(ev_three[index] <= max_current * three_on)
                integer_count += 2
            if single_on is not None and three_on is not None:
                model.addConstr(single_on + three_on <= 1.0)

        ev_capacity = ev.capabilities.battery_capacity_kwh
        initial_ev_energy = ev_capacity * float(ev.soc_percent) / 100.0
        ev_stored_energy = [model.addVariable(lb=initial_ev_energy, ub=initial_ev_energy, name="ev_energy_0")]
        ev_stored_energy.extend(
            model.addVariable(lb=0.0, ub=ev_capacity, name=f"ev_energy_{index + 1}")
            for index in range(count)
        )
        preferred_soc = _preferred_soc_percent(tasks)
        if preferred_soc is not None:
            preferred_target_battery_kwh = ev_capacity * preferred_soc / 100.0
            preferred_shortfall = model.addVariable(
                lb=0.0,
                ub=preferred_target_battery_kwh,
                name="ev_preferred_shortfall_battery_kwh",
            )

    month_peaks: dict[str, Any] = {}
    for item in plan.intervals:
        month = item.period_start_local.strftime("%Y-%m")
        if month in month_peaks:
            continue
        baseline = _capacity_baseline_kw(month, profile, capacity_state)
        month_peaks[month] = model.addVariable(lb=baseline, name=f"capacity_peak_{month.replace('-', '_')}")

    return (
        _MilpVariables(
            grid_import_kw=grid_import,
            grid_export_kw=grid_export,
            ac_charge_kw=ac_charge,
            dc_charge_kw=dc_charge,
            battery_discharge_kw=battery_discharge,
            dc_to_ac_kw=dc_to_ac,
            curtailed_dc_kw=curtailed_dc,
            stored_energy_kwh=stored_energy,
            inverter_charge_mode=inverter_charge_mode,
            battery_charge_mode=battery_charge_mode,
            ev_single_phase_a=ev_single,
            ev_three_phase_a=ev_three,
            ev_stored_energy_kwh=ev_stored_energy,
            ev_preferred_shortfall_kwh=preferred_shortfall,
            capacity_peak_kw=month_peaks,
        ),
        integer_count,
    )


def _add_constraints(
    model: Any,
    plan: ShadowPlan,
    ess: EssActuatorSnapshot,
    ev: EvActuatorSnapshot | None,
    tasks: tuple[PlanningTask, ...],
    variables: _MilpVariables,
) -> None:
    resource = ess.capabilities
    max_charge_kw = resource.max_charge_power_w / 1000.0
    max_discharge_kw = resource.max_discharge_power_w / 1000.0
    charge_efficiency = resource.charge_efficiency
    discharge_efficiency = resource.discharge_efficiency

    for index, item in enumerate(plan.intervals):
        ev_power = _ev_power_expression(ev, variables, index)
        ac_balance = (
            variables.grid_import_kw[index]
            - variables.grid_export_kw[index]
            + variables.battery_discharge_kw[index]
            + variables.dc_to_ac_kw[index]
            - variables.ac_charge_kw[index]
            - ev_power
        )
        model.addConstr(ac_balance == (item.background_load_w - item.pv_ac_power_w) / 1000.0)
        model.addConstr(
            variables.dc_to_ac_kw[index] / discharge_efficiency
            + variables.dc_charge_kw[index]
            + variables.curtailed_dc_kw[index]
            == item.pv_dc_power_w / 1000.0
        )
        model.addConstr(
            variables.ac_charge_kw[index] <= max_charge_kw * variables.inverter_charge_mode[index]
        )
        model.addConstr(
            variables.battery_discharge_kw[index] + variables.dc_to_ac_kw[index]
            <= max_discharge_kw * (1.0 - variables.inverter_charge_mode[index])
        )
        model.addConstr(
            variables.ac_charge_kw[index] + variables.dc_charge_kw[index]
            <= max_charge_kw * variables.battery_charge_mode[index]
        )
        model.addConstr(
            variables.battery_discharge_kw[index]
            <= max_discharge_kw * (1.0 - variables.battery_charge_mode[index])
        )
        model.addConstr(
            variables.stored_energy_kwh[index + 1]
            == variables.stored_energy_kwh[index]
            + _INTERVAL_HOURS
            * charge_efficiency
            * (variables.ac_charge_kw[index] + variables.dc_charge_kw[index])
            - _INTERVAL_HOURS / discharge_efficiency * variables.battery_discharge_kw[index]
        )
        month = item.period_start_local.strftime("%Y-%m")
        model.addConstr(variables.grid_import_kw[index] <= variables.capacity_peak_kw[month])
        if variables.ev_stored_energy_kwh and ev is not None:
            trip_energy = _ev_trip_energy_at_start(item.period_start_local, tasks)
            model.addConstr(
                variables.ev_stored_energy_kwh[index + 1]
                == variables.ev_stored_energy_kwh[index]
                - trip_energy
                + _INTERVAL_HOURS
                * ev.capabilities.charge_efficiency
                * _ev_power_expression(ev, variables, index)
            )

    if tasks and ev is not None and variables.ev_stored_energy_kwh:
        ev_capacity = ev.capabilities.battery_capacity_kwh
        assert ev_capacity is not None
        for task in tasks:
            if task.kind != "energy_by_deadline":
                continue
            if task.minimum_soc_percent is not None:
                state_index = _ev_state_index(plan, task.latest_end_local)
                if state_index is None:
                    raise ValueError(f"EV task deadline is not aligned to the planner grid: {task.task_id}")
                required_stored = ev_capacity * task.minimum_soc_percent / 100.0
                model.addConstr(variables.ev_stored_energy_kwh[state_index] >= required_stored)
                continue
            required_kwh = float(task.required_energy_kwh or 0.0)
            if required_kwh <= 0.0:
                continue
            task_energy: Any = 0.0
            for index in _eligible_indexes(plan, task, tasks):
                task_energy = task_energy + _INTERVAL_HOURS * _ev_power_expression(ev, variables, index)
            model.addConstr(task_energy >= required_kwh)

        preferred_soc = _preferred_soc_percent(tasks)
        if preferred_soc is not None and variables.ev_preferred_shortfall_kwh is not None:
            preferred_stored = ev_capacity * preferred_soc / 100.0
            model.addConstr(
                variables.ev_stored_energy_kwh[-1] + variables.ev_preferred_shortfall_kwh >= preferred_stored
            )


def _economic_objective_expression(
    plan: ShadowPlan,
    ess: EssActuatorSnapshot,
    ev: EvActuatorSnapshot | None,
    profile: TariffProfile,
    variables: _MilpVariables,
) -> Any:
    objective: Any = 0.0
    for index in range(len(plan.intervals)):
        objective = objective + _INTERVAL_HOURS * profile.import_energy_eur_per_kwh * variables.grid_import_kw[index]
        objective = objective - _INTERVAL_HOURS * profile.export_energy_eur_per_kwh * variables.grid_export_kw[index]
    for peak in variables.capacity_peak_kw.values():
        objective = objective + profile.capacity_tariff_eur_per_kw_month * peak
    if variables.ev_preferred_shortfall_kwh is not None and ev is not None:
        objective = (
            objective
            + profile.import_energy_eur_per_kwh
            / ev.capabilities.charge_efficiency
            * variables.ev_preferred_shortfall_kwh
        )
    return (
        objective
        - profile.import_energy_eur_per_kwh
        * ess.capabilities.discharge_efficiency
        * variables.stored_energy_kwh[-1]
    )


def _economic_objective_value(
    ess: EssActuatorSnapshot,
    ev: EvActuatorSnapshot | None,
    profile: TariffProfile,
    variables: _MilpVariables,
    values: list[float],
) -> float:
    objective = 0.0
    for grid_import, grid_export in zip(variables.grid_import_kw, variables.grid_export_kw, strict=True):
        objective += _INTERVAL_HOURS * profile.import_energy_eur_per_kwh * _value(grid_import, values)
        objective -= _INTERVAL_HOURS * profile.export_energy_eur_per_kwh * _value(grid_export, values)
    objective += profile.capacity_tariff_eur_per_kw_month * sum(
        _value(peak, values) for peak in variables.capacity_peak_kw.values()
    )
    if variables.ev_preferred_shortfall_kwh is not None and ev is not None:
        objective += (
            profile.import_energy_eur_per_kwh
            / ev.capabilities.charge_efficiency
            * _value(variables.ev_preferred_shortfall_kwh, values)
        )
    objective -= (
        profile.import_energy_eur_per_kwh
        * ess.capabilities.discharge_efficiency
        * _value(variables.stored_energy_kwh[-1], values)
    )
    return objective


def _time_weighted_grid_import_expression(
    plan: ShadowPlan,
    variables: _MilpVariables,
) -> Any:
    objective: Any = 0.0
    for index in range(len(plan.intervals)):
        objective += _early_value_weight(index) * _INTERVAL_HOURS * variables.grid_import_kw[index]
    return objective


def _time_weighted_grid_import_value(
    variables: _MilpVariables,
    values: list[float],
) -> float:
    return sum(
        _early_value_weight(index) * _INTERVAL_HOURS * _value(grid_import, values)
        for index, grid_import in enumerate(variables.grid_import_kw)
    )


def _early_value_weight(index: int) -> float:
    elapsed_days = index * _INTERVAL_HOURS / 24.0
    return 2.0 ** (-elapsed_days / MILP_EARLY_VALUE_HALF_LIFE_DAYS)


def _solution_plan(
    reference_plan: ShadowPlan,
    ess: EssActuatorSnapshot,
    ev: EvActuatorSnapshot | None,
    profile: TariffProfile,
    variables: _MilpVariables,
    values: list[float],
) -> ShadowPlan:
    resource = ess.capabilities
    intervals: list[ShadowPlanInterval] = []
    for index, item in enumerate(reference_plan.intervals):
        ev_kw = _ev_power_value(ev, variables, values, index)
        ac_charge_kw = _value(variables.ac_charge_kw[index], values)
        battery_discharge_kw = _value(variables.battery_discharge_kw[index], values)
        dc_to_ac_kw = _value(variables.dc_to_ac_kw[index], values)
        grid_kw = _value(variables.grid_import_kw[index], values) - _value(variables.grid_export_kw[index], values)
        stored_before = _value(variables.stored_energy_kwh[index], values)
        stored_after = _value(variables.stored_energy_kwh[index + 1], values)
        ev_soc = None
        if ev is not None and variables.ev_stored_energy_kwh and ev.capabilities.battery_capacity_kwh is not None:
            ev_energy_after = _value(variables.ev_stored_energy_kwh[index + 1], values)
            ev_soc = 100.0 * ev_energy_after / ev.capabilities.battery_capacity_kwh
        scheduled_w = max(0.0, ev_kw * 1000.0)
        intervals.append(
            ShadowPlanInterval(
                period_start_local=item.period_start_local,
                background_load_w=item.background_load_w,
                scheduled_load_w=scheduled_w,
                pv_ac_power_w=item.pv_ac_power_w,
                pv_dc_power_w=item.pv_dc_power_w,
                pv_power_w=item.pv_power_w,
                net_power_before_control_w=(
                    item.background_load_w + scheduled_w - item.pv_ac_power_w - item.pv_dc_power_w
                ),
                ess_ac_power_w=(battery_discharge_kw + dc_to_ac_kw - ac_charge_kw) * 1000.0,
                battery_energy_delta_kwh=stored_after - stored_before,
                projected_soc_percent=100.0 * stored_after / resource.capacity_kwh,
                grid_power_after_ess_w=grid_kw * 1000.0,
                curtailed_dc_pv_w=max(0.0, _value(variables.curtailed_dc_kw[index], values) * 1000.0),
                projected_ev_soc_percent=ev_soc,
            )
        )
    preferred_shortfall_battery_kwh = (
        _value(variables.ev_preferred_shortfall_kwh, values)
        if variables.ev_preferred_shortfall_kwh is not None
        else 0.0
    )
    preferred_shortfall_kwh = (
        preferred_shortfall_battery_kwh / ev.capabilities.charge_efficiency
        if ev is not None and preferred_shortfall_battery_kwh > 0.0
        else 0.0
    )
    preferred_penalty_eur = preferred_shortfall_kwh * profile.import_energy_eur_per_kwh
    return ShadowPlan(
        generated_at_utc=reference_plan.generated_at_utc,
        intervals=tuple(intervals),
        ess_projection_status="projected",
        actuator_snapshots=reference_plan.actuator_snapshots,
        tasks=reference_plan.tasks,
        ess_resource=resource,
        ess_initial_soc_percent=ess.soc_percent,
        scheduling_strategy="milp_joint_ev_ess",
        optimizer_status="optimized",
        optimizer_objective=ECONOMIC_OBJECTIVE_VERSION,
        preferred_ev_shortfall_kwh=preferred_shortfall_kwh,
        preferred_ev_shortfall_penalty_eur=preferred_penalty_eur,
    )


def _ev_power_expression(ev: EvActuatorSnapshot | None, variables: _MilpVariables, index: int) -> Any:
    if ev is None:
        return 0.0
    volts_kw = ev.capabilities.nominal_voltage_v / 1000.0
    expression: Any = 0.0
    if index in variables.ev_single_phase_a:
        expression = expression + volts_kw * variables.ev_single_phase_a[index]
    if index in variables.ev_three_phase_a:
        expression = expression + 3.0 * volts_kw * variables.ev_three_phase_a[index]
    return expression


def _ev_power_value(
    ev: EvActuatorSnapshot | None,
    variables: _MilpVariables,
    values: list[float],
    index: int,
) -> float:
    if ev is None:
        return 0.0
    volts_kw = ev.capabilities.nominal_voltage_v / 1000.0
    single_a = _value(variables.ev_single_phase_a[index], values) if index in variables.ev_single_phase_a else 0.0
    three_a = _value(variables.ev_three_phase_a[index], values) if index in variables.ev_three_phase_a else 0.0
    return volts_kw * single_a + 3.0 * volts_kw * three_a


def _preferred_target_kwh(tasks: tuple[PlanningTask, ...]) -> float:
    return max((float(task.preferred_energy_kwh or 0.0) for task in tasks), default=0.0)


def _preferred_soc_percent(tasks: tuple[PlanningTask, ...]) -> float | None:
    values = [
        float(task.target_soc_percent)
        for task in tasks
        if task.target_soc_percent is not None
        and (task.preferred_energy_kwh is not None or task.kind == "ev_terminal_soc_target")
    ]
    return max(values) if values else None


def _ev_variable_indexes(plan: ShadowPlan, tasks: tuple[PlanningTask, ...]) -> list[int]:
    starts = [task.earliest_start_local for task in tasks if task.earliest_start_local is not None]
    earliest_utc = min(value.astimezone(UTC) for value in starts) if starts else None
    unavailable = _ev_unavailable_windows_utc(tasks)
    return [
        index
        for index, item in enumerate(plan.intervals)
        if (earliest_utc is None or item.period_start_local.astimezone(UTC) >= earliest_utc)
        and not _interval_is_unavailable(item.period_start_local, unavailable)
    ]


def _eligible_indexes(
    plan: ShadowPlan,
    task: PlanningTask,
    tasks: tuple[PlanningTask, ...] = (),
) -> list[int]:
    assert task.earliest_start_local is not None and task.latest_end_local is not None
    earliest_utc = task.earliest_start_local.astimezone(UTC)
    latest_utc = task.latest_end_local.astimezone(UTC)
    unavailable = _ev_unavailable_windows_utc(tasks)
    return [
        index
        for index, item in enumerate(plan.intervals)
        if item.period_start_local.astimezone(UTC) >= earliest_utc
        and (item.period_start_local + _INTERVAL_DELTA).astimezone(UTC) <= latest_utc
        and not _interval_is_unavailable(item.period_start_local, unavailable)
    ]


def _ev_unavailable_windows_utc(
    tasks: tuple[PlanningTask, ...],
) -> tuple[tuple[Any, Any], ...]:
    windows: list[tuple[Any, Any]] = []
    for task in tasks:
        for start, end in task.ev_unavailable_windows_local:
            windows.append((start.astimezone(UTC), end.astimezone(UTC)))
        has_trip_window = task.latest_end_local is not None and task.expected_return_local is not None
        if task.kind == "energy_by_deadline" and has_trip_window:
            windows.append((task.latest_end_local.astimezone(UTC), task.expected_return_local.astimezone(UTC)))
    return tuple(dict.fromkeys(windows))


def _interval_is_unavailable(period_start_local: Any, windows: tuple[tuple[Any, Any], ...]) -> bool:
    start_utc = period_start_local.astimezone(UTC)
    return any(window_start <= start_utc < window_end for window_start, window_end in windows)


def _ev_state_index(plan: ShadowPlan, moment: Any) -> int | None:
    if moment is None:
        return None
    target_utc = moment.astimezone(UTC)
    for index, item in enumerate(plan.intervals):
        if abs((item.period_start_local.astimezone(UTC) - target_utc).total_seconds()) < 1.0:
            return index
    final_end = (plan.intervals[-1].period_start_local + _INTERVAL_DELTA).astimezone(UTC)
    if abs((final_end - target_utc).total_seconds()) < 1.0:
        return len(plan.intervals)
    return None


def _ev_trip_energy_at_start(period_start_local: Any, tasks: tuple[PlanningTask, ...]) -> float:
    start_utc = period_start_local.astimezone(UTC)
    total = 0.0
    for task in tasks:
        if task.kind != "energy_by_deadline" or task.latest_end_local is None:
            continue
        if abs((task.latest_end_local.astimezone(UTC) - start_utc).total_seconds()) < 1.0:
            total += float(task.expected_trip_energy_kwh or 0.0)
    return total


def _minimum_ev_interval_energy_kwh(ev: EvActuatorSnapshot) -> float:
    phase_count = 1 if ev.capabilities.supports_single_phase else 3
    minimum_current = math.ceil(ev.capabilities.min_charge_current_a)
    return phase_count * ev.capabilities.nominal_voltage_v * minimum_current * _INTERVAL_HOURS / 1000.0


def _capacity_baseline_kw(month: str, profile: TariffProfile, state: CapacityPeakState) -> float:
    if month == state.month_local:
        return max(profile.capacity_tariff_floor_kw, state.billing_peak_kw)
    return profile.capacity_tariff_floor_kw


def _objective(plan: ShadowPlan, profile: TariffProfile, state: CapacityPeakState) -> float | None:
    evaluation = evaluate_plan_objective(plan, profile, state, hours=168)
    return evaluation.objective_eur if evaluation is not None else None


def _has_solution(highspy: Any, info: Any) -> bool:
    return info.primal_solution_status == highspy.SolutionStatus.kSolutionStatusFeasible


def _validate_solution_plan(
    reference_plan: ShadowPlan,
    plan: ShadowPlan,
    ess: EssActuatorSnapshot,
    ev: EvActuatorSnapshot | None,
    tasks: tuple[PlanningTask, ...],
) -> tuple[tuple[str, ...], tuple[MilpTaskValidation, ...]]:
    errors: list[str] = []
    task_checks: list[MilpTaskValidation] = []
    if len(plan.intervals) != len(reference_plan.intervals):
        errors.append("interval_count_mismatch")
        return tuple(errors), ()

    resource = ess.capabilities
    stored_before = resource.capacity_kwh * float(ess.soc_percent or 0.0) / 100.0
    power_steps_valid = True
    unavailable = _ev_unavailable_windows_utc(tasks)
    ev_energy_before = None
    if tasks and ev is not None and ev.soc_percent is not None and ev.capabilities.battery_capacity_kwh is not None:
        ev_energy_before = ev.capabilities.battery_capacity_kwh * ev.soc_percent / 100.0
    for index, (reference, item) in enumerate(zip(reference_plan.intervals, plan.intervals, strict=True)):
        if item.period_start_local != reference.period_start_local:
            errors.append(f"interval_{index}_timestamp_mismatch")
        if item.projected_soc_percent is None or item.battery_energy_delta_kwh is None:
            errors.append(f"interval_{index}_ess_projection_missing")
        else:
            soc = float(item.projected_soc_percent)
            if soc < resource.min_soc_percent - 1e-4 or soc > resource.max_soc_percent + 1e-4:
                errors.append(f"interval_{index}_soc_out_of_bounds")
            stored_after = resource.capacity_kwh * soc / 100.0
            if abs((stored_after - stored_before) - float(item.battery_energy_delta_kwh)) > 0.002:
                errors.append(f"interval_{index}_stored_energy_mismatch")
            stored_before = stored_after

        ess_power = item.ess_ac_power_w
        grid_power = item.grid_power_after_ess_w
        if ess_power is None or grid_power is None:
            errors.append(f"interval_{index}_power_projection_missing")
            continue
        if ess_power > resource.max_discharge_power_w + _VALIDATION_POWER_TOLERANCE_W:
            errors.append(f"interval_{index}_ess_discharge_limit")
        if ess_power < -resource.max_charge_power_w - _VALIDATION_POWER_TOLERANCE_W:
            errors.append(f"interval_{index}_ess_charge_limit")
        expected_grid_w = item.background_load_w + item.scheduled_load_w - item.pv_ac_power_w - ess_power
        if abs(float(grid_power) - expected_grid_w) > _VALIDATION_POWER_TOLERANCE_W:
            errors.append(f"interval_{index}_ac_balance_mismatch")
        if item.curtailed_dc_pv_w is None or item.curtailed_dc_pv_w < -_VALIDATION_POWER_TOLERANCE_W:
            errors.append(f"interval_{index}_dc_curtailment_invalid")
        elif item.curtailed_dc_pv_w > item.pv_dc_power_w + _VALIDATION_POWER_TOLERANCE_W:
            errors.append(f"interval_{index}_dc_curtailment_exceeds_pv")
        if tasks and ev is not None:
            if item.projected_ev_soc_percent is None:
                errors.append(f"interval_{index}_ev_soc_projection_missing")
            elif not -1e-4 <= float(item.projected_ev_soc_percent) <= 100.0 + 1e-4:
                errors.append(f"interval_{index}_ev_soc_out_of_bounds")
            elif ev_energy_before is not None and ev.capabilities.battery_capacity_kwh is not None:
                ev_energy_after = (
                    ev.capabilities.battery_capacity_kwh * float(item.projected_ev_soc_percent) / 100.0
                )
                expected_ev_energy = (
                    ev_energy_before
                    - _ev_trip_energy_at_start(item.period_start_local, tasks)
                    + item.scheduled_load_w
                    * _INTERVAL_HOURS
                    / 1000.0
                    * ev.capabilities.charge_efficiency
                )
                if abs(ev_energy_after - expected_ev_energy) > 0.002:
                    errors.append(f"interval_{index}_ev_energy_mismatch")
                ev_energy_before = ev_energy_after
        if item.scheduled_load_w > _VALIDATION_POWER_TOLERANCE_W:
            if ev is None or not _ev_power_step_valid(item.scheduled_load_w, ev):
                power_steps_valid = False
                errors.append(f"interval_{index}_ev_power_step_invalid")
            if _interval_is_unavailable(item.period_start_local, unavailable):
                errors.append(f"interval_{index}_ev_charging_while_away")

    if not tasks:
        scheduled_kwh = sum(item.scheduled_load_w for item in plan.intervals) * _INTERVAL_HOURS / 1000.0
        if scheduled_kwh > 0.001:
            errors.append("scheduled_load_without_active_task")
        return tuple(dict.fromkeys(errors)), ()

    assert ev is not None
    for task in tasks:
        if task.kind != "energy_by_deadline":
            continue
        required_kwh = float(task.required_energy_kwh or 0.0)
        eligible = set(_eligible_indexes(plan, task, tasks))
        scheduled_kwh = sum(
            item.scheduled_load_w for index, item in enumerate(plan.intervals) if index in eligible
        ) * _INTERVAL_HOURS / 1000.0
        deadline_utc = task.latest_end_local.astimezone(UTC) if task.latest_end_local is not None else None
        scheduled_after_deadline_kwh = (
            sum(
                item.scheduled_load_w
                for item in plan.intervals
                if deadline_utc is not None
                and (item.period_start_local + _INTERVAL_DELTA).astimezone(UTC) > deadline_utc
            )
            * _INTERVAL_HOURS
            / 1000.0
        )
        charging_during_away_windows_kwh = (
            sum(
                item.scheduled_load_w
                for item in plan.intervals
                if _interval_is_unavailable(item.period_start_local, unavailable)
            )
            * _INTERVAL_HOURS
            / 1000.0
        )
        if task.minimum_soc_percent is not None:
            departure_soc = _ev_soc_at_deadline(plan, ev, task.latest_end_local)
            deadline_met = departure_soc is not None and departure_soc + 1e-4 >= task.minimum_soc_percent
        else:
            deadline_met = scheduled_kwh + 1e-6 >= required_kwh
        task_valid = deadline_met and power_steps_valid
        if not deadline_met:
            errors.append(f"task_{task.task_id}_departure_requirement_shortfall")
        task_checks.append(
            MilpTaskValidation(
                task_id=task.task_id,
                required_energy_kwh=required_kwh,
                scheduled_energy_kwh=scheduled_kwh,
                scheduled_after_deadline_kwh=scheduled_after_deadline_kwh,
                charging_during_away_windows_kwh=charging_during_away_windows_kwh,
                deadline_met=deadline_met,
                power_steps_valid=power_steps_valid,
                valid=task_valid,
            )
        )
    return tuple(dict.fromkeys(errors)), tuple(task_checks)


def _ev_soc_at_deadline(
    plan: ShadowPlan,
    ev: EvActuatorSnapshot,
    deadline: Any,
) -> float | None:
    if deadline is None or not plan.intervals:
        return None
    target_utc = deadline.astimezone(UTC)
    first_start = plan.intervals[0].period_start_local.astimezone(UTC)
    if abs((first_start - target_utc).total_seconds()) < 1.0:
        return ev.soc_percent
    for index, item in enumerate(plan.intervals[1:], start=1):
        if abs((item.period_start_local.astimezone(UTC) - target_utc).total_seconds()) < 1.0:
            return plan.intervals[index - 1].projected_ev_soc_percent
    final_end = (plan.intervals[-1].period_start_local + _INTERVAL_DELTA).astimezone(UTC)
    if abs((final_end - target_utc).total_seconds()) < 1.0:
        return plan.intervals[-1].projected_ev_soc_percent
    return None


def _ev_power_step_valid(power_w: float, ev: EvActuatorSnapshot) -> bool:
    if power_w <= _VALIDATION_POWER_TOLERANCE_W:
        return True
    minimum_current = math.ceil(ev.capabilities.min_charge_current_a)
    maximum_current = math.floor(ev.capabilities.max_charge_current_a)
    voltage = ev.capabilities.nominal_voltage_v
    phase_counts = []
    if ev.capabilities.supports_single_phase:
        phase_counts.append(1)
    if ev.capabilities.supports_three_phase:
        phase_counts.append(3)
    return any(
        abs(power_w - phases * voltage * current) <= _VALIDATION_POWER_TOLERANCE_W
        for phases in phase_counts
        for current in range(minimum_current, maximum_current + 1)
    )


def _cost_breakdown(
    plan: ShadowPlan,
    profile: TariffProfile,
    capacity_state: CapacityPeakState,
) -> MilpCostBreakdown | None:
    accounting = evaluate_plan_cost(plan, profile, capacity_state, hours=168)
    objective = evaluate_plan_objective(plan, profile, capacity_state, hours=168)
    if accounting is None or objective is None:
        return None
    summary = plan.summary(168)
    end_soc = summary.get("end_soc_percent")
    max_grid_w = summary.get("max_grid_import_after_ess_w")
    if not isinstance(end_soc, (int, float)) or not isinstance(max_grid_w, (int, float)):
        return None
    return MilpCostBreakdown(
        import_kwh=accounting.import_kwh,
        export_kwh=accounting.export_kwh,
        net_energy_cost_eur=accounting.net_energy_cost_eur,
        incremental_capacity_cost_eur=accounting.incremental_capacity_cost_eur,
        total_marginal_cost_eur=accounting.total_marginal_cost_eur,
        terminal_usable_ac_kwh=objective.terminal_usable_ac_kwh,
        terminal_ess_value_eur=objective.terminal_ess_value_eur,
        objective_eur=objective.objective_eur,
        max_grid_import_kw=float(max_grid_w) / 1000.0,
        end_soc_percent=float(end_soc),
    )


def _value(variable: Any, values: list[float]) -> float:
    return float(values[variable.index])


def _status_from_model(model_status: str, *, has_solution: bool) -> str:
    normalized = model_status.strip().lower().replace(" ", "_")
    if "optimal" in normalized:
        return "optimal"
    if has_solution and "time" in normalized and "limit" in normalized:
        return "feasible_time_limit"
    if has_solution:
        return "feasible"
    if "infeasible" in normalized:
        return "infeasible"
    if "time" in normalized and "limit" in normalized:
        return "time_limit_no_solution"
    return normalized or "unknown"


def _solver_version(highspy: Any) -> str:
    parts = [
        getattr(highspy, "HIGHS_VERSION_MAJOR", None),
        getattr(highspy, "HIGHS_VERSION_MINOR", None),
        getattr(highspy, "HIGHS_VERSION_PATCH", None),
    ]
    if all(part is not None for part in parts):
        return ".".join(str(part) for part in parts)
    return "unknown"


def _finite_optional(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _integer_optional(value: object) -> int | None:
    if not isinstance(value, int):
        return None
    return int(value)


async def publish_milp_evaluation(client: HomeAssistantClient, evaluation: MilpEvaluation) -> None:
    """Publish authoritative MILP solver status and validation diagnostics."""
    objective_delta = None
    if evaluation.first_stage_objective_eur is not None and evaluation.milp_objective_eur is not None:
        objective_delta = evaluation.milp_objective_eur - evaluation.first_stage_objective_eur
    attributes: dict[str, Any] = {
        "friendly_name": "Energy Manager MILP Planner",
        "milp_version": MILP_EVALUATION_VERSION,
        "authoritative": True,
        "shadow_mode": True,
        "hardware_writes": False,
        "solver": "HiGHS/highspy",
        "solver_version": evaluation.solver_version,
        "model_status": evaluation.model_status,
        "solve_time_seconds": _round_optional(evaluation.solve_time_seconds, 3),
        "economic_solve_time_seconds": _round_optional(evaluation.economic_solve_time_seconds, 3),
        "tie_break_solve_time_seconds": _round_optional(evaluation.tie_break_solve_time_seconds, 3),
        "total_time_budget_seconds": MILP_TOTAL_TIME_BUDGET_SECONDS,
        "economic_time_limit_seconds": evaluation.economic_time_limit_seconds,
        "tie_break_time_limit_seconds": _round_optional(evaluation.tie_break_time_limit_seconds, 3),
        "mip_relative_gap_target": MILP_RELATIVE_GAP,
        "mip_gap": _round_optional(evaluation.mip_gap, 5),
        "mip_node_count": evaluation.mip_node_count,
        "horizon_intervals": evaluation.horizon_intervals,
        "variable_count": evaluation.variable_count,
        "integer_variable_count": evaluation.integer_variable_count,
        "constraint_count": evaluation.constraint_count,
        "active_task_count": evaluation.active_task_count,
        "first_stage_objective_eur": _round_optional(evaluation.first_stage_objective_eur, 4),
        "milp_objective_eur": _round_optional(evaluation.milp_objective_eur, 4),
        "economic_objective_delta_eur": _round_optional(objective_delta, 4),
        "economic_tolerance_eur": evaluation.economic_tolerance_eur,
        "tie_break_status": evaluation.tie_break_status,
        "tie_break_warm_start_applied": evaluation.tie_break_warm_start_applied,
        "tie_break_warm_start_status": evaluation.tie_break_warm_start_status,
        "selected_solution_stage": evaluation.selected_solution_stage,
        "tie_break_objective": "exponential_time_weighted_grid_import",
        "early_value_half_life_days": evaluation.early_value_half_life_days,
        "time_weighted_grid_import_score": _round_optional(evaluation.time_weighted_grid_import_score, 5),
        "preferred_ev_target_kwh": round(evaluation.preferred_ev_target_kwh, 3),
        "preferred_ev_scheduled_kwh": round(evaluation.preferred_ev_scheduled_kwh, 3),
        "preferred_ev_shortfall_kwh": round(evaluation.preferred_ev_shortfall_kwh, 3),
        "preferred_ev_shortfall_penalty_eur": round(evaluation.preferred_ev_shortfall_penalty_eur, 3),
        "validation_status": evaluation.validation_status,
        "validation_errors": list(evaluation.validation_errors),
        "adoption_ready": evaluation.adoption_ready,
        "task_validation": [
            {
                "id": item.task_id,
                "required_energy_kwh": round(item.required_energy_kwh, 3),
                "scheduled_energy_kwh": round(item.scheduled_energy_kwh, 3),
                "scheduled_after_deadline_kwh": round(item.scheduled_after_deadline_kwh, 4),
                "charging_during_away_windows_kwh": round(item.charging_during_away_windows_kwh, 4),
                "deadline_met": item.deadline_met,
                "power_steps_valid": item.power_steps_valid,
                "valid": item.valid,
            }
            for item in evaluation.task_validation
        ],
        "milp_cost_7_days": _breakdown_attributes(evaluation.milp_cost),
        "reason": evaluation.reason,
    }
    if evaluation.plan is not None:
        summary = evaluation.plan.summary(168)
        attributes["milp_next_7_days"] = {
            "scheduled_load_kwh": _round_optional(summary["scheduled_load_kwh"], 3),
            "grid_import_kwh": _round_optional(summary["grid_import_after_ess_kwh"], 3),
            "grid_export_kwh": _round_optional(summary["grid_export_after_ess_kwh"], 3),
            "max_grid_import_w": _round_optional(summary["max_grid_import_after_ess_w"], 1),
            "end_soc_percent": _round_optional(summary["end_soc_percent"], 2),
            "ev_end_soc_percent": _round_optional(evaluation.plan.intervals[-1].projected_ev_soc_percent, 2),
            "curtailed_dc_pv_kwh": _round_optional(summary["curtailed_dc_pv_kwh"], 3),
        }
        attributes["milp_next_intervals"] = [
            {
                "start": item.period_start_local.isoformat(),
                "scheduled_w": round(item.scheduled_load_w, 1),
                "ess_ac_w": _round_optional(item.ess_ac_power_w, 1),
                "grid_w": _round_optional(item.grid_power_after_ess_w, 1),
                "soc_percent": _round_optional(item.projected_soc_percent, 2),
                "ev_soc_percent": _round_optional(item.projected_ev_soc_percent, 2),
            }
            for item in evaluation.plan.intervals[:12]
        ]
    await client.set_state(MILP_STATUS_ENTITY, evaluation.status, attributes)


def _breakdown_attributes(value: MilpCostBreakdown | None) -> dict[str, float | None] | None:
    if value is None:
        return None
    return {
        "import_kwh": round(value.import_kwh, 3),
        "export_kwh": round(value.export_kwh, 3),
        "net_energy_cost_eur": round(value.net_energy_cost_eur, 3),
        "incremental_capacity_cost_eur": _round_optional(value.incremental_capacity_cost_eur, 3),
        "total_marginal_cost_eur": _round_optional(value.total_marginal_cost_eur, 3),
        "terminal_usable_ac_kwh": round(value.terminal_usable_ac_kwh, 3),
        "terminal_ess_value_eur": round(value.terminal_ess_value_eur, 3),
        "objective_eur": round(value.objective_eur, 4),
        "max_grid_import_kw": round(value.max_grid_import_kw, 3),
        "end_soc_percent": round(value.end_soc_percent, 2),
    }


def _round_optional(value: object, digits: int) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value), digits)
