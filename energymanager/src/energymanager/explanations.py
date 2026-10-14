"""Deterministic, bounded presentation of archived evidence; no hardware dependencies."""
from datetime import UTC, timedelta

from .decision_store import encode

LIMITATION = ("This view reports recorded constraints and stage comparisons. The unique reason for a particular "
             "time or power cannot be established from correlation; compare a frozen alternative to test a hypothesis.")


def plain(value):
    value = encode(value)
    if isinstance(value, dict):
        if "$datetime" in value:
            return value["$datetime"]
        if "$date" in value:
            return value["$date"]
        result = {k: plain(v) for k, v in value.items() if k != "$type"}
        if isinstance(result.get("parameters"), list):
            result["parameters"] = dict(result["parameters"])
        return result
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


def quality(evaluation):
    stages, previous = [], None
    for stage in evaluation.get("stages", []):
        current = {k: v for k, v in stage.items() if k not in {"plan", "$type"}}
        metrics = dict(stage.get("metrics", []))
        current["metrics"] = metrics
        current["metric_changes"] = ({k: v - previous[k] for k, v in metrics.items() if k in previous}
                                     if previous is not None else {})
        initial, final = stage.get("objective_before"), stage.get("objective")
        current["objective_improvement"] = initial - final if initial is not None and final is not None else None
        stages.append(current)
        previous = metrics
    return {"physical_validation": evaluation.get("validation_status", "not_run"),
            "status": evaluation.get("status"), "objective_eur": evaluation.get("milp_objective_eur"),
            "further_improvement_possible": any(s.get("status") not in {"Optimal", "constant"}
                                                 or not s.get("accepted") or (s.get("gap") or 0) > .001
                                                 for s in stages),
            "stages": stages}


def evaluation_view(evaluation):
    result = plain(evaluation)
    return {"quality": quality(result), "cost": result.get("milp_cost"),
            "intervals": (result.get("plan") or {}).get("intervals", []),
            "reason": result.get("reason"), "validation_errors": result.get("validation_errors", []),
            "adoption_ready": result.get("adoption_ready", False)}


def decision_view(snapshot, document):
    data = snapshot.inputs()
    frame = data["frame"]
    view = evaluation_view(document["evaluation"])
    intervals = view["intervals"] or plain(frame.intervals)
    selections = []
    # Group contiguous actions by device and direction. Every slot is also inspectable.
    for kind, key in (("EV session", "scheduled_load_w"), ("ESS action", "ess_ac_power_w")):
        active, direction = None, 0
        for index, slot in enumerate(intervals):
            power = slot.get(key) or 0
            sign = (1 if power > 1 else -1 if power < -1 else 0)
            if not sign:
                active, direction = None, 0
            else:
                if active is None or sign != direction:
                    active = {"kind": kind, "label": f"{kind} at {slot['period_start_local']}",
                              "start_index": index, "end_index": index + 1, "energy_kwh": 0}
                    selections.append(active)
                active["end_index"] = index + 1
                active["energy_kwh"] += power * .25 / 1000
                direction = sign
    for kind, items, identity in (("Requirement", frame.requirements, "requirement_id"),
                                  ("Job", frame.jobs, "job_id")):
        for item in items:
            start = item.earliest_start
            end = item.deadline if kind == "Requirement" else item.latest_finish
            indexes = [i for i, slot in enumerate(frame.intervals)
                       if (start is None or slot.period_start_local.astimezone(UTC) + timedelta(minutes=15)
                           > start.astimezone(UTC))
                       and (end is None or slot.period_start_local.astimezone(UTC) < end.astimezone(UTC))]
            selections.append({"kind": kind, "label": getattr(item, identity), "record": plain(item),
                               "start_index": min(indexes, default=0), "end_index": max(indexes, default=0) + 1})
    for index, slot in enumerate(intervals):
        selections.append({"kind": "Interval", "label": slot["period_start_local"],
                           "start_index": index, "end_index": index + 1})
    stage_intervals = [{"stage": stage["name"], "intervals": [
        {key: slot.get(key) for key in ("period_start_local", "scheduled_load_w", "ess_ac_power_w",
                                       "grid_power_after_ess_w", "projected_ev_soc_percent", "projected_soc_percent")}
        for slot in plain((stage.get("plan") or {}).get("intervals", []))
    ]} for stage in document["evaluation"].get("stages", [])]
    return {"stage_intervals": stage_intervals, "snapshot_id": snapshot.snapshot_id,
            "generated_at": frame.generated_at_utc.isoformat(),
            "disposition": document["disposition"], "evaluation": view, "intervals": intervals,
            "selections": selections, "requirements": plain(frame.requirements), "jobs": plain(frame.jobs),
            "resources": plain(frame.resources), "capabilities": plain(frame.actuator_snapshots),
            "policy": plain(data["policy"]), "tariff": plain(data["profile"]),
            "capacity_peak_baseline": plain(data["capacity_state"]),
            "observations": plain(data["observations"]), "changes": plain(document.get("changes", {})),
            "previous_intervals": plain(data["previous_plan"].intervals) if data["previous_plan"] else [],
            "limitation": LIMITATION}


def comparison_view(comparison):
    return {"snapshot_id": comparison["snapshot_id"], "request": plain(comparison["request"]),
            "baseline": evaluation_view(comparison["baseline"]),
            "alternative": evaluation_view(comparison["alternative"]),
            "delta": comparison["delta"], "economic_confidence": comparison["economic_confidence"],
            "infeasibility": comparison["infeasibility"], "limitation": LIMITATION}
