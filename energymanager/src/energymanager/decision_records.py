"""Compact HA summaries and evidence-based comparisons of accepted plan revisions."""

from datetime import UTC


def observation_records(house_state):
    return tuple(
        {
            "key": r.key,
            "value": r.value,
            "unit": r.unit,
            "quality": str(r.status),
            "observed_at_utc": r.observed_at_utc,
            "last_valid_at_utc": r.last_valid_at_utc,
            "source_last_updated": r.source_last_updated,
            "held": r.held_reason is not None,
        }
        for r in house_state.readings.values()
    )


def plan_changes(previous, selected):
    if previous is None or selected is None:
        return ()
    old = {i.period_start_local.astimezone(UTC): i for i in previous.intervals}
    changes = []
    for item in selected.intervals:
        prior = old.get(item.period_start_local.astimezone(UTC))
        if prior is None:
            continue
        if (
            abs(item.scheduled_load_w - prior.scheduled_load_w) > 1
            or abs((item.grid_power_after_ess_w or 0) - (prior.grid_power_after_ess_w or 0)) > 1
        ):
            changes.append(
                {
                    "start": item.period_start_local,
                    "ev_delta_w": item.scheduled_load_w - prior.scheduled_load_w,
                    "grid_delta_w": (item.grid_power_after_ess_w or 0) - (prior.grid_power_after_ess_w or 0),
                }
            )
    return tuple(changes)


async def publish_decision(client, snapshot, result, disposition, persisted):
    from .decision_store import encode

    frame = snapshot.inputs()["frame"]
    await client.set_state(
        "sensor.energy_manager_v3_decision",
        disposition,
        {
            "friendly_name": "Energy Manager V3 Decision",
            "snapshot_id": snapshot.snapshot_id,
            "model_version": "3.0-preview.2",
            "persisted": persisted,
            "validation": result.validation_status,
            "solver_status": result.status,
            "objective_eur": result.milp_objective_eur,
            "stages": [
                {
                    "name": s.name,
                    "status": s.status,
                    "objective": s.objective,
                    "unit": s.unit,
                    "tolerance": s.tolerance,
                    "gap": s.gap,
                    "bound": s.bound,
                    "objective_before": s.objective_before,
                    "objective_improvement": (s.objective_before - s.objective
                                              if s.objective_before is not None and s.objective is not None else None),
                    "metrics": dict(s.metrics),
                    "runtime_seconds": s.runtime_seconds,
                    "accepted": s.accepted,
                }
                for s in result.stages
            ],
            # Only a bounded catalog is published; complete snapshots remain on disk.
            "requirements": [encode(r) for r in frame.requirements[:16]],
            "requirements_truncated": len(frame.requirements) > 16,
            "details_command": f"python -m energymanager.replay show {snapshot.snapshot_id}",
            "attribution": (
                "Stage changes are recorded facts. Individual causation is indeterminate without a counterfactual."
            ),
        },
    )


def input_changes(previous, frame):
    if previous is None:
        return {"initial_snapshot": True}
    old = {i.period_start_local.astimezone(UTC): i for i in previous.intervals}
    forecasts = []
    for interval in frame.intervals:
        prior = old.get(interval.period_start_local.astimezone(UTC))
        if prior is None:
            continue
        deltas = {name: getattr(interval, name) - getattr(prior, name)
                  for name in ("background_load_w", "pv_ac_power_w", "pv_dc_power_w")
                  if abs(getattr(interval, name) - getattr(prior, name)) > 1e-6}
        if deltas:
            forecasts.append({"start": interval.period_start_local, "deltas": deltas})
    return {"forecast_changes": tuple(forecasts),
            "previous_actuators": previous.actuator_snapshots,
            "current_actuators": frame.actuator_snapshots,
            "previous_requirements": previous.requirements,
            "current_requirements": frame.requirements}
