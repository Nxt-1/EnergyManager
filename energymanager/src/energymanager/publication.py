"""Validate a frozen calculation and check whether its instructions can be admitted."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from .domain import Observation, Snapshot, json_data
from .validation import validate, rolling_comparison_errors


def admit(
    snapshot: Snapshot, result: dict[str, Any], observation: Observation, at: datetime
) -> tuple[dict[str, Any], list[str]]:
    """Preserve the calculated schedule; current readings gate authority, not its economics."""
    errors = validate(snapshot, result["flows"], result.get("service"))
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
    # Fast control selects the interval containing the current time. Keep every original
    # rate, stock, withdrawal, reservation and comparison on that same calculation grid.
    return admitted, errors
