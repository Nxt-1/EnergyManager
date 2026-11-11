"""Validate a frozen calculation and check whether its instructions can be admitted."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from .domain import Observation, Snapshot, instant, json_data
from .deadline_audit import validate_certificate
from .validation import validate, rolling_comparison_errors
from .execution import execution_identity


def admit(
    snapshot: Snapshot, result: dict[str, Any], observation: Observation, at: datetime, *,
    previous_plan: dict[str, Any] | None = None, previous_authority: tuple[bool, bool, bool] = (False, False, False),
) -> tuple[dict[str, Any], list[str]]:
    """Preserve the calculated schedule; current readings gate authority, not its economics."""
    errors = validate(snapshot, result["flows"], result.get("service"))
    guard = result.get("deadline_guard", {})
    if guard.get("status") == "certified":
        errors.extend(validate_certificate(guard))
        scope = guard.get("scope", {})
        matching = next((g for g in snapshot.goals if g.id == scope.get("goal_id")
                         and g.revision == scope.get("revision") and g.deadline.isoformat() == scope.get("deadline")), None)
        if matching is None or matching.target(snapshot.capabilities, snapshot.policy) != scope.get("target_kwh"):
            errors.append("Cautious certificate authority does not match the current goal")
    reference = result.get("reference_flows")
    if reference:
        reference_errors = validate(snapshot, reference, result.get("service"))
        errors.extend("Reference: " + error for error in reference_errors)
        if not errors:
            errors.extend(rolling_comparison_errors(snapshot, reference, result["flows"]))

    if at < snapshot.intervals[0].start:
        errors.append("Publication clock precedes the input snapshot")
    first = next((t for t, interval in enumerate(snapshot.intervals) if interval.end > at), None)
    if first is None:
        errors.append("Candidate horizon has elapsed")
    age = (at - observation.at).total_seconds()
    if not 0 <= age <= snapshot.policy.measurement_max_age_seconds or observation.quality in (
        "unknown", "stale", "settling"
    ):
        errors.append("Current measurements are unavailable or stale")
    if (at - snapshot.forecast_at).total_seconds() > snapshot.policy.forecast_max_age_seconds:
        errors.append("Planning forecast is stale")
    if observation.connected != snapshot.observation.connected:
        errors.append("Connection state changed since calculation")
    if observation.ev_state_known != snapshot.observation.ev_state_known:
        errors.append("EV state availability changed since calculation")
    c = snapshot.capabilities
    if not (
        0 <= observation.ev_kwh <= c.ev_capacity_kwh
        and c.ess_min_kwh <= observation.ess_kwh <= c.ess_capacity_kwh
        and 0 <= observation.ess_grid_kwh <= observation.ess_kwh - c.ess_min_kwh + 1e-8
    ):
        errors.append("Current battery measurements violate physical bounds or provenance")

    admitted = deepcopy(result)
    admitted["publication_at"] = at.isoformat()
    admitted["admission"] = {
        "at": at.isoformat(), "passed": not errors, "errors": list(errors),
        "snapshot_id": snapshot.id, "input_digest": snapshot.digest,
        "observation": json_data(observation), "first_interval": first,
    }
    if not errors:
        admitted["adopted_at"] = at.isoformat()
        admitted["execution_id"] = execution_identity(admitted)
        if snapshot.execution is not None:
            until = instant(snapshot.execution["commitment_until"])
            admitted["execution_admission"] = {"acknowledged_phase": observation.ev_phases,
                "measured_ev_kw": observation.ev_power_kw, "at": at.isoformat(),
                "previous_plan_id": previous_plan.get("id") if previous_plan else None}
            if (previous_plan is not None and previous_plan["id"] == snapshot.hold_plan_id and at < until):
                admitted["execution_handover"] = {"until": until.isoformat(),
                    "plan": execution_source(previous_plan, at),
                    "ev_valid": previous_authority[0], "ess_valid": previous_authority[1],
                    "conditional_valid": previous_authority[2]}
    # Fast control selects the interval containing the current time. Keep every original
    # rate, stock, withdrawal, reservation and comparison on that same calculation grid.
    return admitted, errors


def execution_source(plan: dict[str, Any], at: datetime) -> dict[str, Any]:
    """Retain only dispatch evidence; do not nest obsolete calculations indefinitely."""
    keys = ("id", "execution_id", "intervals", "flows", "goals", "sessions", "reservations", "reasons",
            "conditional_tasks", "forecast_at", "deadline_guard", "execution", "peak_permissions",
            "running_allowance", "polish_reference_summary")
    source = {key: deepcopy(plan[key]) for key in keys if key in plan}
    handover = plan.get("execution_handover")
    if handover and at < instant(handover["until"]):
        source["execution_handover"] = {**handover, "plan": execution_source(handover["plan"], at)}
    return source
