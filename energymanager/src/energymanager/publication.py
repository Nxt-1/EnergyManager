"""Reconcile elapsed execution against current measurements before publication."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from .domain import Observation, Snapshot, instant, json_data
from .validation import TOL, accounting, validate, rolling_comparison_errors
from .reservations import reservations


def split_interval(
    snapshot: Snapshot, flows: dict[str, list[float]], boundary: datetime
) -> Snapshot:
    """Split rates and interpolate inventories without repeating a departure withdrawal."""
    index = next((t for t, i in enumerate(snapshot.intervals) if i.start < boundary < i.end), None)
    if index is None:
        return snapshot
    interval = snapshot.intervals[index]
    fraction = (boundary - interval.start).total_seconds() / (interval.end - interval.start).total_seconds()
    for name, values in flows.items():
        if name in ("ev_energy", "ess_solar", "ess_grid"):
            withdrawal = interval.withdrawal_kwh if name == "ev_energy" else 0.0
            value = values[index] + fraction * (values[index + 1] + withdrawal - values[index])
            values.insert(index + 1, value)
        else:
            values.insert(index + 1, values[index])
    intervals = list(snapshot.intervals)
    intervals[index:index + 1] = [
        replace(interval, end=boundary, withdrawal_kwh=0.0),
        replace(interval, start=boundary),
    ]
    return replace(snapshot, intervals=tuple(intervals))


def extend_required_session(
    snapshot: Snapshot, flows: dict[str, list[float]], service: dict[str, float] | None,
    lost_delivery_kwh: float,
) -> tuple[Snapshot, dict[str, list[float]], dict[str, Any] | None]:
    """Try one bounded same-phase extension; the caller must audit the entire result."""
    shortages = []
    for goal in snapshot.goals:
        if not snapshot.intervals[0].start <= goal.deadline <= snapshot.intervals[-1].end:
            continue
        k = snapshot.checkpoint_index(goal.deadline)
        if not snapshot.ev_known_at(k):
            continue
        target = (service or {}).get(goal.id, goal.target(snapshot.capabilities, snapshot.policy))
        deficit = target - flows["ev_energy"][k]
        if deficit > TOL:
            shortages.append((goal.deadline, deficit))
    if not shortages:
        return snapshot, flows, None
    required = max(deficit for _, deficit in shortages)
    if required > lost_delivery_kwh + TOL:
        return snapshot, flows, None
    deadline = min(at for at, _ in shortages)
    c = snapshot.capabilities
    # Only extend an existing future session. Never introduce a restart or phase switch.
    start = next((
        t for t in range(1, len(snapshot.intervals))
        if snapshot.intervals[t].start < deadline
        and (snapshot.hold_until is None or snapshot.intervals[t].start >= snapshot.hold_until)
        and flows["one"][t - 1] + flows["three"][t - 1] > 0.5
        and flows["one"][t] + flows["three"][t] < 0.5
        and snapshot.intervals[t].available and snapshot.intervals[t].ev_state_known
    ), None)
    if start is None:
        return snapshot, flows, None
    phase = 3 if flows["three"][start - 1] > 0.5 else 1
    power = phase * c.voltage / 1000 * c.minimum_current_a
    duration = timedelta(seconds=required / (power * c.ev_efficiency) * 3600)
    end = snapshot.intervals[start].start + duration
    if end > deadline:
        return snapshot, flows, None
    slots = [t for t, i in enumerate(snapshot.intervals) if i.start < end and t >= start]
    if any(
        not snapshot.intervals[t].available or not snapshot.intervals[t].ev_state_known
        or flows["one"][t] + flows["three"][t] > 0.5
        for t in slots
    ):
        return snapshot, flows, None
    repaired = deepcopy(flows)
    current = split_interval(snapshot, repaired, end)
    delivered = 0.0
    for t, interval in enumerate(current.intervals):
        if t >= start and interval.start < end:
            repaired["grid_ev"][t] += power
            repaired["three" if phase == 3 else "one"][t] = 1.0
            repaired["amps_three" if phase == 3 else "amps_one"][t] = float(c.minimum_current_a)
            delivered += power * interval.hours * c.ev_efficiency
        repaired["ev_energy"][t + 1] += delivered
    return current, repaired, {
        "kind": "elapsed_delivery_session_extension",
        "energy_kwh": delivered,
        "start": current.intervals[start].start.isoformat(), "end": end.isoformat(), "phases": phase,
    }


def rebase(
    snapshot: Snapshot, result: dict[str, Any], observation: Observation, at: datetime
) -> tuple[Snapshot, dict[str, Any], list[str]]:
    """Keep only future power, rebuilding every storage state from actual current energy."""
    if at < snapshot.intervals[0].start:
        return snapshot, result, ["Publication clock precedes the input snapshot"]
    first = next((t for t, i in enumerate(snapshot.intervals) if i.end > at), None)
    if first is None:
        return snapshot, result, ["Candidate horizon has elapsed"]
    intervals = list(snapshot.intervals[first:])
    if at > intervals[0].start:
        # Departure withdrawal at this boundary has already happened; never repeat it.
        intervals[0] = replace(intervals[0], start=at, withdrawal_kwh=0.0)
    goals = tuple(g for g in snapshot.goals if g.deadline > at)
    current = replace(
        snapshot, id=uuid4().hex, observation=observation, intervals=tuple(intervals), goals=goals
    )
    adopted = deepcopy(result)
    adopted["adoption_snapshot"] = json_data(current)
    adopted["adoption_digest"] = current.digest
    adopted["publication_at"] = at.isoformat()
    adopted["candidate_at_calculation"] = {
        key: result[key] for key in ("flows", "intervals", "summary", "goals", "sessions")
    }
    original_flows = result["flows"]
    names = (
        "pv_ev",
        "pv_house",
        "pv_store",
        "export",
        "curtail",
        "grid_ev",
        "grid_house",
        "grid_store",
        "solar_dis_ev",
        "solar_dis_house",
        "grid_dis_house",
        "dc_store",
        "dc_invert",
        "one",
        "three",
        "amps_one",
        "amps_three",
    )
    flows = {name: original_flows[name][first:] for name in names}
    c = current.capabilities
    flows["ev_energy"] = [observation.ev_kwh]
    flows["ess_grid"] = [observation.ess_grid_kwh]
    flows["ess_solar"] = [observation.ess_kwh - c.ess_min_kwh - observation.ess_grid_kwh]
    for t, i in enumerate(intervals):
        room_kw = (
            max(0, c.ess_capacity_kwh - c.ess_min_kwh - flows["ess_solar"][-1] - flows["ess_grid"][-1])
            / i.hours
        )
        charging_kw = (
            flows["dc_store"][t] * c.dc_efficiency
            + (flows["pv_store"][t] + flows["grid_store"][t]) * c.ac_charge_efficiency
        )
        excess = max(0, charging_kw - room_kw)
        for name, efficiency in (
            ("dc_store", c.dc_efficiency),
            ("pv_store", c.ac_charge_efficiency),
            ("grid_store", c.ac_charge_efficiency),
        ):
            reduction = min(flows[name][t], excess / efficiency)
            flows[name][t] -= reduction
            excess -= reduction * efficiency
            if name == "pv_store" and reduction > 0:
                imp = sum(flows[key][t] for key in ("grid_ev", "grid_house", "grid_store"))
                flows["export" if imp < 1e-7 else "curtail"][t] += reduction
        # Balancing continues during the solve. Release household preferences when its
        # measured inventory is lower; never publish a negative future source ledger.
        solar_available = max(0, flows["ess_solar"][-1]) * c.ac_discharge_efficiency / i.hours
        solar_discharge = flows["solar_dis_house"][t] + flows["solar_dis_ev"][t]
        shortage = max(0, solar_discharge - solar_available)
        reduction = min(shortage, flows["solar_dis_house"][t])
        flows["solar_dis_house"][t] -= reduction
        flows["grid_house"][t] += reduction
        shortage -= reduction
        if shortage > 1e-9:
            replacement = min(shortage, flows["pv_house"][t])
            flows["solar_dis_ev"][t] -= replacement
            flows["pv_ev"][t] += replacement
            flows["pv_house"][t] -= replacement
            flows["grid_house"][t] += replacement
        grid_available = max(0, flows["ess_grid"][-1]) * c.ac_discharge_efficiency / i.hours
        reduction = max(0, flows["grid_dis_house"][t] - grid_available)
        flows["grid_dis_house"][t] -= reduction
        flows["grid_house"][t] += reduction
        ev = sum(flows[name][t] for name in ("pv_ev", "grid_ev", "solar_dis_ev"))
        solar_in = flows["pv_store"][t] * c.ac_charge_efficiency + flows["dc_store"][t] * c.dc_efficiency
        solar_out = (flows["solar_dis_ev"][t] + flows["solar_dis_house"][t]) / c.ac_discharge_efficiency
        grid_in = flows["grid_store"][t] * c.ac_charge_efficiency
        grid_out = flows["grid_dis_house"][t] / c.ac_discharge_efficiency
        flows["ev_energy"].append(flows["ev_energy"][-1] + ev * i.hours * c.ev_efficiency - i.withdrawal_kwh)
        flows["ess_solar"].append(flows["ess_solar"][-1] + (solar_in - solar_out) * i.hours)
        flows["ess_grid"].append(flows["ess_grid"][-1] + (grid_in - grid_out) * i.hours)
    errors = validate(current, flows, result.get("service"))
    if errors and all(error.startswith("Required outcome ") for error in errors):
        # Held power is a forecast, not measured delivery. Recover only that elapsed
        # amount, and never compensate for a measured inventory loss or an away period.
        elapsed_delivery = sum(
            sum(original_flows[name][t] for name in ("pv_ev", "grid_ev", "solar_dis_ev"))
            * max(0.0, (min(i.end, at) - i.start).total_seconds()) / 3600 * c.ev_efficiency
            for t, i in enumerate(snapshot.intervals) if i.start < at
        )
        if (observation.connected and observation.ev_state_known
                and observation.ev_kwh >= snapshot.observation.ev_kwh - TOL
                and not any(i.withdrawal_kwh for i in snapshot.intervals if i.start < at)
                and not validate(snapshot, original_flows, result.get("service"))):
            trial, repaired, repair = extend_required_session(current, flows, result.get("service"), elapsed_delivery)
            repair_errors = validate(trial, repaired, result.get("service")) if repair else errors
            if not repair_errors:
                current, flows = trial, repaired
                intervals = list(current.intervals)
                adopted["publication_repair"] = repair
                adopted["adoption_snapshot"] = json_data(current)
                adopted["adoption_digest"] = current.digest
                errors = []
    if errors:
        # Keep the failed reconciliation as labelled evidence, not executable flows.
        adopted["publication_candidate"] = {"flows": flows, "intervals": json_data(intervals)}
        return current, adopted, errors
    if result.get("reference_flows"):
        reference_result = {
            **result,
            "flows": result["reference_flows"],
            "goals": [],
            "sessions": [],
            "conditional_tasks": [],
        }
        del reference_result["reference_flows"]
        reference_snapshot, reference, reference_errors = rebase(snapshot, reference_result, observation, at)
        if reference_errors:
            adopted["publication_candidate"] = {"flows": flows, "intervals": json_data(intervals)}
            return (
                current,
                adopted,
                ["Reference cannot be reconciled with measured state: " + reference_errors[0]],
            )
        # Each trajectory can need a different extension. Compare them on the union
        # of their boundaries, preserving the exact energy of every original interval.
        current_boundaries = {i.end for i in current.intervals}
        reference_boundaries = {i.end for i in reference_snapshot.intervals}
        for boundary in sorted(reference_boundaries - current_boundaries):
            current = split_interval(current, flows, boundary)
        for boundary in sorted(current_boundaries - reference_boundaries):
            reference_snapshot = split_interval(reference_snapshot, reference["flows"], boundary)
        intervals = list(current.intervals)
        errors = validate(current, flows, result.get("service"))
        errors += validate(current, reference["flows"], result.get("service"))
        errors += rolling_comparison_errors(current, reference["flows"], flows)
        if errors:
            adopted["publication_candidate"] = {"flows": flows, "intervals": json_data(intervals)}
            adopted["adoption_snapshot"] = json_data(current)
            adopted["adoption_digest"] = current.digest
            return current, adopted, errors
        adopted["reference_flows"] = reference["flows"]
        adopted["reference_summary"] = accounting(current, reference["flows"])
        if reference.get("publication_repair"):
            adopted["reference_publication_repair"] = reference["publication_repair"]
    adopted["flows"] = flows
    adopted["intervals"] = json_data(intervals)
    adopted["reservations"] = reservations(current, flows)
    adopted["adoption_snapshot"] = json_data(current)
    adopted["adoption_digest"] = current.digest
    adopted["adopted_at"] = at.isoformat()
    adopted["remaining_summary"] = accounting(current, flows)
    adopted["summary"] = {**result["summary"], **adopted["remaining_summary"], "intervals": len(intervals)}
    for goal in adopted["goals"]:
        if instant(goal["deadline"]) > at:
            k = current.checkpoint_index(instant(goal["deadline"]))
            if current.ev_known_at(k):
                goal["planned_kwh"] = flows["ev_energy"][k]
                goal["shortfall_kwh"] = max(0, goal["target_kwh"] - goal["planned_kwh"])
                ready = k
                if goal["shortfall_kwh"] <= TOL:
                    while ready > 0 and flows["ev_energy"][ready - 1] >= goal["target_kwh"] - TOL:
                        ready -= 1
                    completed = intervals[0].start if ready == 0 else intervals[ready - 1].end
                    margin = (instant(goal["deadline"]) - completed).total_seconds() / 60
                    goal.update(completion_at=completed.isoformat(), completion_margin_minutes=margin,
                                desired_margin_met=margin >= current.policy.completion_margin_minutes)
        else:
            goal["elapsed_prediction"] = True
    for session in adopted["sessions"]:
        repair = adopted.get("publication_repair")
        if repair and session["resource"] == "ev" and session["end"] == repair["start"]:
            session["end"] = repair["end"]
        session["elapsed_prediction"] = instant(session["start"]) < at
        if instant(session["end"]) > at:
            session["start"] = max(instant(session["start"]), at).isoformat()
            energy = 0.0
            for t, i in enumerate(intervals):
                hours = (
                    max(
                        0,
                        (
                            min(i.end, instant(session["end"])) - max(i.start, instant(session["start"]))
                        ).total_seconds(),
                    )
                    / 3600
                )
                if session["resource"] == "ev":
                    rate = (
                        sum(flows[name][t] for name in ("pv_ev", "grid_ev", "solar_dis_ev")) * c.ev_efficiency
                    )
                else:
                    rate = abs(
                        (flows["pv_store"][t] + flows["grid_store"][t]) * c.ac_charge_efficiency
                        + flows["dc_store"][t] * c.dc_efficiency
                        - sum(
                            flows[name][t] for name in ("solar_dis_ev", "solar_dis_house", "grid_dis_house")
                        )
                        / c.ac_discharge_efficiency
                    )
                energy += rate * hours
            session["energy_kwh"] = energy
    adopted["sessions"] = [session for session in adopted["sessions"] if instant(session["end"]) > at]
    for task in adopted.get("conditional_tasks", []):
        task["quantity_kwh"] = min(task["quantity_kwh"], max(0, task["target_ev_kwh"] - observation.ev_kwh))
    adopted["conditional_tasks"] = [
        task
        for task in adopted.get("conditional_tasks", [])
        if instant(task["deadline"]) > at and task["quantity_kwh"] > 2e-5
    ]
    return current, adopted, []
