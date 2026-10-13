"""Explicit lexicographic optimization: each accepted objective becomes a bound."""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class HierarchyPolicy:
    economic_tolerance_eur: float = 0.01
    robustness_tolerance_kwh: float = 0.05
    operations_tolerance_events: float = 0.0
    stability_tolerance_kwh: float = 0.01
    near_term_hours: int = 4
    total_seconds: float = 60.0
    economic_seconds: float = 30.0
    relative_gap: float = 0.001
    grid_import_limit_kw: float = 25.0
    grid_export_limit_kw: float = 25.0

    def __post_init__(self) -> None:
        limits = (
            (self.economic_tolerance_eur, 0, 1),
            (self.robustness_tolerance_kwh, 0, 5),
            (self.operations_tolerance_events, 0, 10),
            (self.stability_tolerance_kwh, 0, 5),
            (self.near_term_hours, 1, 24),
            (self.total_seconds, 1, 150),
            (self.economic_seconds, 0.1, self.total_seconds),
            (self.relative_gap, 0, 0.05),
            (self.grid_import_limit_kw, 0.1, 1000),
            (self.grid_export_limit_kw, 0.1, 1000),
        )
        if any(not math.isfinite(value) or not low <= value <= high for value, low, high in limits):
            raise ValueError("invalid V3 hierarchy policy")


@dataclass(frozen=True, slots=True)
class StageRecord:
    name: str
    unit: str
    status: str
    objective: float | None
    bound: float | None
    gap: float | None
    runtime_seconds: float
    tolerance: float
    accepted: bool
    plan: Any = None
    metrics: tuple[tuple[str, float], ...] = ()


def expression_value(highspy, expression, values) -> float:
    if isinstance(expression, (float, int)):
        return float(expression)
    return float(highspy.Highs.internal_get_value(values, expression))


def refine(model, highspy, stages, values, *, seconds, describe, normalize=lambda values: values):
    """Retain the last validated incumbent on timeout/error; never release a prior bound."""
    records = []
    bounds = []
    started = perf_counter()
    selected = list(values)
    last_info = model.getInfo()
    last_status = model.modelStatusToString(model.getModelStatus())
    for position, (name, unit, expr, tolerance) in enumerate(stages):
        remaining = seconds - (perf_counter() - started)
        if remaining < 0.01:
            records.append(StageRecord(name, unit, "skipped_budget", None, None, None, 0, tolerance, False))
            continue
        if isinstance(expr, (float, int)):
            plan, metrics = describe(selected)
            records.append(
                StageRecord(
                    name,
                    unit,
                    "constant",
                    float(expr),
                    float(expr),
                    0.0,
                    0.0,
                    tolerance,
                    True,
                    plan,
                    tuple(metrics.items()),
                )
            )
            continue
        model.setObjective(expr, sense=highspy.ObjSense.kMinimize)
        model.setSolution(len(selected), np.arange(len(selected), dtype=np.int32), np.asarray(selected))
        model.setOptionValue("time_limit", remaining / (len(stages) - position))
        before = perf_counter()
        model.run()
        elapsed = perf_counter() - before
        info = model.getInfo()
        status = model.modelStatusToString(model.getModelStatus())
        feasible = info.primal_solution_status == highspy.SolutionStatus.kSolutionStatusFeasible
        candidate = normalize(list(model.getSolution().col_value)) if feasible else selected
        value = expression_value(highspy, expr, candidate)
        # Do not accept a worse secondary incumbent, or a solver-tolerance violation.
        accepted = feasible and value <= expression_value(highspy, expr, selected) + 1e-6
        accepted = accepted and all(expression_value(highspy, e, candidate) <= b + 1e-6 for e, b in bounds)
        if accepted:
            selected = candidate
            last_info, last_status = info, status
        else:
            value = expression_value(highspy, expr, selected)
        plan, metrics = describe(selected)
        bound = getattr(info, "mip_dual_bound", None)
        gap = getattr(info, "mip_gap", None)
        records.append(
            StageRecord(
                name,
                unit,
                status if feasible else "no_incumbent:" + status,
                value,
                bound if bound is not None and math.isfinite(bound) else None,
                gap if gap is not None and math.isfinite(gap) else None,
                elapsed,
                tolerance,
                accepted,
                plan,
                tuple(metrics.items()),
            )
        )
        # Even a timeout incumbent has an inspectable bound for subsequent stages.
        if not isinstance(expr, (int, float)):
            model.addConstr(expr <= value + tolerance + 1e-8)
            bounds.append((expr, value + tolerance))
    return selected, last_info, last_status, tuple(records), perf_counter() - started


def validate_primal(model, values, tolerance=1e-5):
    """Independent row/column/integrality check, including all generic jobs and stage locks."""
    lp = model.getLp()
    errors = []
    if len(values) != lp.num_col_ or any(not math.isfinite(v) for v in values):
        return ("invalid_primal_vector",)
    lower, upper, integrality = lp.col_lower_, lp.col_upper_, lp.integrality_
    for i, value in enumerate(values):
        if value < lower[i] - tolerance or value > upper[i] + tolerance:
            errors.append(f"column_bound:{i}")
        if integrality and int(integrality[i]) == 1 and abs(value - round(value)) > tolerance:
            errors.append(f"integrality:{i}")
    matrix = lp.a_matrix_
    activity = [0.0] * lp.num_row_
    # Highs.getLp returns a column-wise sparse matrix.
    if int(matrix.format_) != 1:
        return ("unsupported_validation_matrix_format",)
    starts, indices, coefficients = matrix.start_, matrix.index_, matrix.value_
    for col, value in enumerate(values):
        for j in range(starts[col], starts[col + 1]):
            activity[indices[j]] += coefficients[j] * value
    lower, upper = lp.row_lower_, lp.row_upper_
    for row, value in enumerate(activity):
        if value < lower[row] - tolerance or value > upper[row] + tolerance:
            errors.append(f"constraint_bound:{row}")
    return tuple(errors)
