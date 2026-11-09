"""Frozen execution trajectory and explicit go-e transition delivery allowances."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any

from .domain import Capabilities, Snapshot, encode, instant


# Existing sequencer: stop acknowledgement, 10 s preparation, phase acknowledgement,
# 30 s restart hold, and start acknowledgement. Current confirmation overlaps the hold.
ACK_SECONDS = 30.0
RESTART_SECONDS = 30.0
PHASE_SWITCH_SECONDS = 10.0 + ACK_SECONDS + ACK_SECONDS + RESTART_SECONDS + ACK_SECONDS
MINIMUM_PHASE_SWITCH_SECONDS = 10.0 + RESTART_SECONDS


def execution_identity(plan: dict[str, Any]) -> str:
    """An ID change alone neither purchases energy nor discards unfinished work."""
    flows = plan["flows"]
    return sha256(encode({"input_digest": plan.get("input_digest"),
        "intervals": plan["intervals"], "goals": plan["goals"],
        "flows": {name: flows[name] for name in
                  ("one", "three", "amps_one", "amps_three", "grid_ev", "pv_ev", "solar_dis_ev", "ev_energy")},
        "peak_permissions": plan.get("peak_permissions", [])}).encode()).hexdigest()


def dispatch_source(plan: dict[str, Any], at: datetime) -> dict[str, Any]:
    while plan.get("execution_handover") and at < instant(plan["execution_handover"]["until"]):
        plan = plan["execution_handover"]["plan"]
    return plan


def requested_mode(plan: dict[str, Any], t: int, at: datetime, current_phase: int,
                   capabilities: Capabilities) -> tuple[float, int]:
    """Do not enter a phase that must be abandoned before its mandatory waits finish."""
    source = dispatch_source(plan, at)
    if source is not plan:
        position = next((k for k, item in enumerate(source["intervals"])
                         if instant(item["start"]) <= at < instant(item["end"])), None)
        return requested_mode(source, position, at, current_phase, capabilities) if position is not None else (0, current_phase)
    f = plan["flows"]
    phase = 3 if f["three"][t] > .5 else 1 if f["one"][t] > .5 else current_phase
    power = (f["amps_one"][t] + 3 * f["amps_three"][t]) * capabilities.voltage / 1000
    if power and phase != current_phase:
        following = t + 1
        while following < len(plan["intervals"]) and f["three" if phase == 3 else "one"][following] > .5:
            following += 1
        if (following < len(plan["intervals"])
                and f["three" if current_phase == 3 else "one"][following] > .5
                and (instant(plan["intervals"][following]["start"]) - at).total_seconds()
                    < MINIMUM_PHASE_SWITCH_SECONDS):
            phase = current_phase
            power = min(power, capabilities.maximum_current_a * phase * capabilities.voltage / 1000)
    return power, phase


def task_target(plan: dict[str, Any], at: datetime) -> float | None:
    source = dispatch_source(plan, at)
    f = source["flows"]
    t = next((t for t, item in enumerate(source["intervals"])
              if instant(item["start"]) <= at < instant(item["end"])), None)
    if t is None or "ev_energy" not in f or f["one"][t] + f["three"][t] < .5:
        return None
    while t + 1 < len(source["intervals"]) and (
            f["one"][t + 1] + f["three"][t + 1] > .5 if source.get("execution") else
            sum(f[name][t + 1] for name in ("pv_ev", "grid_ev", "solar_dis_ev")) > 1e-5):
        t += 1
    return float(f["ev_energy"][t + 1])


def freeze_execution(snapshot: Snapshot, plan: dict[str, Any] | None,
                     charger: dict[str, Any], *, conditional_valid: bool = True) -> Snapshot:
    """Commit the accepted trajectory, rather than extending the current command."""
    start = snapshot.intervals[0].start
    ready = max(start, instant(charger.get("ready_at", start.isoformat())))
    initial_phase = int(charger.get("phase", snapshot.observation.ev_phases))
    end = max(ready, start + timedelta(seconds=snapshot.policy.planning_budget_seconds + 15)) if plan else ready
    boundaries = {start, end, ready}
    if plan:
        source_plan = plan
        while source_plan:
            for item in source_plan["intervals"]:
                for key in ("start", "end"):
                    at = instant(item[key])
                    if start < at < end:
                        boundaries.add(at)
            handover = source_plan.get("execution_handover")
            if not handover:
                break
            if start < instant(handover["until"]) < end:
                boundaries.add(instant(handover["until"]))
            source_plan = handover["plan"]
    boundaries = {at for at in boundaries if start <= at <= snapshot.intervals[-1].end}
    points = sorted({*(i.start for i in snapshot.intervals), snapshot.intervals[-1].end, *boundaries})
    intervals = []
    source = 0
    for left, right in zip(points, points[1:]):
        while snapshot.intervals[source].end <= left:
            source += 1
        original = snapshot.intervals[source]
        intervals.append(replace(original, start=left, end=right,
                                 withdrawal_kwh=original.withdrawal_kwh if left == original.start else 0.0))
    commitments = []
    modes: list[int] = []
    stock = snapshot.observation.ev_kwh
    phase_before = initial_phase
    index = 0
    while index < len(intervals):
        interval = intervals[index]
        if interval.start >= end:
            break
        phases, power = phase_before, 0.0
        target = None
        if plan and interval.start >= ready:
            source_plan = plan
            authorized, conditional = True, conditional_valid
            while source_plan.get("execution_handover") and interval.start < instant(source_plan["execution_handover"]["until"]):
                handover = source_plan["execution_handover"]
                authorized = authorized and handover["ev_valid"]
                conditional = conditional and handover["conditional_valid"]
                source_plan = handover["plan"]
            forecast_fresh = (interval.start - instant(source_plan.get("forecast_at", start.isoformat()))
                              ).total_seconds() <= snapshot.policy.forecast_max_age_seconds
            required = any(interval.start < instant(g["deadline"]) and stock < g["target_kwh"]
                + sum(i["withdrawal_kwh"] for i in source_plan["intervals"]
                      if interval.start <= instant(i["start"]) < instant(g["deadline"])) - .02
                for g in source_plan.get("goals", []))
            t = next((t for t, item in enumerate(plan["intervals"])
                      if instant(item["start"]) <= interval.start < instant(item["end"])), None)
            if t is not None and interval.available and authorized and (conditional and forecast_fresh or required):
                power, phases = requested_mode(plan, t, interval.start, phase_before, snapshot.capabilities)
                target = task_target(plan, interval.start)
                if target is not None and stock >= target - 1e-6:
                    power = 0.0
        modes.append(phases if power else 0)
        context = replace(snapshot, intervals=tuple(intervals), execution={"initial_phase": initial_phase})
        fraction = delivery_fraction(context, index, wait_events(context, modes))
        gain = power * interval.hours * snapshot.capabilities.ev_efficiency * fraction
        if power and target is not None and stock + gain > target + 1e-8:
            lost_seconds = interval.hours * 3600 * (1 - fraction)
            completion = interval.start + timedelta(seconds=lost_seconds
                + (target - stock) / power / snapshot.capabilities.ev_efficiency * 3600)
            if interval.start < completion < interval.end:
                intervals[index:index + 1] = [replace(interval, end=completion),
                    replace(interval, start=completion, withdrawal_kwh=0.0)]
                modes.pop()
                continue
        commitments.append({"start": interval.start.isoformat(), "end": interval.end.isoformat(),
                            "power_kw": power, "phases": phases})
        stock += gain - interval.withdrawal_kwh
        if power:
            phase_before = phases
        index += 1
    return replace(snapshot, intervals=tuple(intervals), hold_until=end, hold_ev_kw=0.0,
                   hold_phases=initial_phase, hold_plan_id=plan["id"] if plan else None,
                   execution={"protocol": 1, "phase_switch_seconds": PHASE_SWITCH_SECONDS,
                              "initial_phase": initial_phase, "ready_at": ready.isoformat(),
                              "commitment_until": end.isoformat(), "commitments": commitments,
                              "charger": charger})


def wait_events(snapshot: Snapshot, modes: list[int]) -> list[tuple[int, float]]:
    """Derive physical interruptions from requested modes, including partial slots."""
    if snapshot.execution is None:
        return []
    phase = snapshot.execution["initial_phase"]
    previous_on = snapshot.observation.ev_power_kw > .1
    events = []
    for t, mode in enumerate(modes):
        if mode:
            if mode != phase:
                events.append((t, PHASE_SWITCH_SECONDS))
            elif not previous_on:
                prior_off = snapshot.intervals[t - 1].hours * 3600 if t else RESTART_SECONDS
                remaining = max(0, RESTART_SECONDS - prior_off)
                if remaining:
                    events.append((t, remaining))
            phase = mode
        previous_on = mode > 0
    return events


def delivery_fraction(snapshot: Snapshot, t: int, events: list[tuple[int, float]]) -> float:
    interval = snapshot.intervals[t]
    lost = sum(max(0.0, (min(interval.end, snapshot.intervals[k].start + timedelta(seconds=seconds))
                        - max(interval.start, snapshot.intervals[k].start)).total_seconds())
               for k, seconds in events if k <= t)
    return max(0.0, 1 - lost / (interval.hours * 3600))
