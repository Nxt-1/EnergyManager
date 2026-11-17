"""Frozen execution trajectory and explicit go-e transition delivery allowances."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256
import math
from typing import Any

from .domain import Capabilities, Interval, Snapshot, encode, instant


# Forecast allowances, not actuator dwell timers: stop acknowledgement, continuous
# stopped period, selector/start acknowledgement and expected delivery startup.
ACK_SECONDS = 30.0
RESTART_SECONDS = 30.0
CURRENT_STEP_SECONDS = 5.0
PHASE_SWITCH_SECONDS = ACK_SECONDS + 60.0 + ACK_SECONDS + ACK_SECONDS + 30.0
MINIMUM_PHASE_SWITCH_SECONDS = 60.0


def execution_protocol(snapshot: Snapshot) -> int:
    """Select immutable calculation arithmetic, never the active hardware protocol."""
    if snapshot.execution is None:
        return 0
    protocol = snapshot.execution.get("protocol", 2)
    if type(protocol) is not int or protocol not in (1, 2):
        raise ValueError(f"Unsupported frozen EV execution protocol: {protocol!r}")
    if protocol == 2 and snapshot.execution.get("phase_switch_seconds", PHASE_SWITCH_SECONDS) != PHASE_SWITCH_SECONDS:
        raise ValueError("Invalid protocol-2 phase forecast timing")
    return int(protocol)


def phase_switch_seconds(snapshot: Snapshot) -> float:
    """Historical protocol 1 retains its recorded forecast; current calculations use protocol 2."""
    if execution_protocol(snapshot) == 1:
        seconds = float((snapshot.execution or {}).get("phase_switch_seconds", 130.0))
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Invalid historical EV phase forecast timing")
        return seconds
    return PHASE_SWITCH_SECONDS


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


def running_context(snapshot: Snapshot, plan: dict[str, Any] | None, phase: int,
                    charger: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Freeze the running accepted profile as preference evidence, never new authority."""
    at = snapshot.intervals[0].start
    if not plan or not snapshot.observation.connected or not snapshot.observation.ev_state_known:
        return None
    source = dispatch_source(plan, at)
    target = task_target(source, at)
    if target is None or snapshot.observation.ev_kwh >= target - 1e-6:
        return None
    first = next(t for t, i in enumerate(source["intervals"]) if instant(i["start"]) <= at < instant(i["end"]))
    last = first
    f = source["flows"]
    while last + 1 < len(source["intervals"]) and f["one"][last + 1] + f["three"][last + 1] > .5:
        last += 1
    old_end = instant(source["intervals"][last]["end"])
    goals = [g for g in snapshot.goals if g.deadline >= old_end and g.target(snapshot.capabilities, snapshot.policy) >= target - .02]
    goal = min(goals, key=lambda g: g.deadline) if goals else None
    deadline = min(goal.deadline if goal else old_end, snapshot.intervals[-1].end)
    task_key = sha256(encode({"goal":goal.id if goal else None,"revision":goal.revision if goal else None,
        "deadline":deadline,"target":goal.target(snapshot.capabilities,snapshot.policy) if goal else target}).encode()).hexdigest()
    previous_allowance = plan.get("running_allowance") or source.get("running_allowance") or {}
    if previous_allowance.get("task_key") == task_key:
        spent = previous_allowance["spent_eur"]
    else:
        # Older releases already had this whole-plan envelope but no per-task
        # ledger. Never buy a second allowance when upgrading a running task.
        spent = snapshot.policy.polish_tolerance_eur if "polish_reference_summary" in source else 0.0
    profile: list[dict[str, Any]] = []
    ready = max(at, instant((charger or {}).get("ready_at", at.isoformat())))
    for t, item in enumerate(source["intervals"]):
        left, right = max(at, instant(item["start"])), min(deadline, instant(item["end"]))
        if left < right:
            points = [left] + ([ready] if left < ready < right else []) + [right]
            for begin, end in zip(points, points[1:]):
                profile.append({"start": begin.isoformat(), "end": end.isoformat(),
                                "one": round(f["amps_one"][t]) if begin >= ready else 0,
                                "three": round(f["amps_three"][t]) if begin >= ready else 0})
    # A finish-only endpoint must include the live ramp, even when the accepted
    # profile predates this protocol. Extend only this task's final setting.
    intervals = tuple(Interval(instant(item["start"]), instant(item["end"]), 0., 0., 0.) for item in profile)
    trajectory = replace(snapshot, intervals=intervals,
                         execution={"initial_phase": phase, "charger": charger or {}})
    last_one, last_three = round(f["amps_one"][last]), round(f["amps_three"][last])
    one = [0 if instant(item["start"]) < ready else item["one"]
           if instant(item["start"]) < old_end else last_one for item in profile]
    three = [0 if instant(item["start"]) < ready else item["three"]
             if instant(item["start"]) < old_end else last_three for item in profile]
    remaining = (target - snapshot.observation.ev_kwh) / snapshot.capabilities.ev_efficiency * 3600
    finish = None
    for segments in transition_trace(trajectory, one, three):
        for left, right, power in segments:
            area = power * (right - left).total_seconds()
            if power > 1e-8 and remaining <= area + 1e-8:
                finish = left + timedelta(seconds=max(0., remaining) / power)
                break
            remaining -= area
        if finish is not None:
            break
    return {"plan_id":source["id"], "phase":phase, "target_kwh":target,
            "goal_id":goal.id if goal else None, "goal_revision":goal.revision if goal else None,
            "deadline":deadline.isoformat(), "old_end":old_end.isoformat(), "profile":profile,
            "finish_at":finish.isoformat() if finish and at < finish <= deadline else None,
            "allowance":{"task_key":task_key,"spent_eur":spent}}


def freeze_execution(snapshot: Snapshot, plan: dict[str, Any] | None,
                     charger: dict[str, Any], *, conditional_valid: bool = True) -> Snapshot:
    """Commit the accepted trajectory, rather than extending the current command."""
    execution_protocol(snapshot)  # Unknown explicit formats cannot become current authority.
    start = snapshot.intervals[0].start
    ready = max(start, instant(charger.get("ready_at", start.isoformat())))
    initial_phase = int(charger.get("phase", snapshot.observation.ev_phases))
    running = running_context(snapshot, plan, initial_phase, charger)
    end = max(ready, start + timedelta(seconds=snapshot.policy.planning_budget_seconds + 15)) if plan else ready
    boundaries = {start, end, ready}
    if running and running["finish_at"]:
        boundaries.add(instant(running["finish_at"]))
    if running:
        for item in running["profile"]:
            boundaries.update((instant(item["start"]), instant(item["end"])))
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
    requested_one: list[float] = []
    requested_three: list[float] = []
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
        context = replace(snapshot, intervals=tuple(intervals),
                          execution={"initial_phase": initial_phase, "charger": charger})
        amps = round(power * 1000 / (phases * snapshot.capabilities.voltage)) if power else 0
        requested_one.append(amps if phases == 1 else 0)
        requested_three.append(amps if phases == 3 else 0)
        average, _ = transition_power(context, requested_one, requested_three)[-1]
        gain = average * interval.hours * snapshot.capabilities.ev_efficiency
        if power and target is not None and stock + gain > target + 1e-8:
            completion = delivery_endpoint(context, {"amps_one": requested_one, "amps_three": requested_three},
                                           index, target - stock)
            if interval.start < completion < interval.end:
                intervals[index:index + 1] = [replace(interval, end=completion),
                    replace(interval, start=completion, withdrawal_kwh=0.0)]
                modes.pop()
                requested_one.pop()
                requested_three.pop()
                continue
        commitments.append({"start": interval.start.isoformat(), "end": interval.end.isoformat(),
                            "power_kw": power, "phases": phases})
        stock += gain - interval.withdrawal_kwh
        if power:
            phase_before = phases
        index += 1
    return replace(snapshot, intervals=tuple(intervals), hold_until=end, hold_ev_kw=0.0,
                   hold_phases=initial_phase, hold_plan_id=plan["id"] if plan else None,
                   execution={"protocol": 2, "phase_switch_seconds": PHASE_SWITCH_SECONDS,
                              "initial_phase": initial_phase, "ready_at": ready.isoformat(),
                              "commitment_until": end.isoformat(), "commitments": commitments,
                              "charger": charger, "running_task":running})


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
                events.append((t, phase_switch_seconds(snapshot)))
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


def transition_trace(snapshot: Snapshot, one: list[float], three: list[float],
                     stocks: list[float] | None = None) -> list[list[tuple[datetime, datetime, float]]]:
    """Integrate a fixed candidate's coalesced live ramp over the original interval grid.

    Phase/start waits use the shared conservative forecast allowance. Current readback
    is assumed to acknowledge each five-second event; live control still requires it.
    Segments retain the requested task quantity endpoint and calculated power; neither
    is measured energy or a grant of additional command authority.
    """
    c, o = snapshot.capabilities, snapshot.observation
    historical = execution_protocol(snapshot) == 1
    modes = [3 if b > .5 else 1 if a > .5 else 0 for a, b in zip(one, three)]
    waits = wait_events(snapshot, modes)
    blocked = [(snapshot.intervals[k].start, snapshot.intervals[k].start + timedelta(seconds=seconds))
               for k, seconds in waits]
    phase = (snapshot.execution or {}).get("initial_phase", o.ev_phases)
    initial = ((snapshot.execution or {}).get("charger") or {}).get("current_a")
    current = int(initial if initial is not None else round(max(0., o.ev_power_kw) * 1000 / (c.voltage * phase)))
    on = o.ev_power_kw > .1
    charger = (snapshot.execution or {}).get("charger") or {}
    last_down = instant(charger["last_downward_at"]) if charger.get("last_downward_at") else None
    pending = (charger.get("pending") or {}).get("current")
    if pending and on:
        current = max(current, int(pending["value"]))
        last_down = snapshot.intervals[0].start
    result = []
    remaining_area: float | None = None
    for t, (interval, mode) in enumerate(zip(snapshot.intervals, modes)):
        segments = []
        if not historical and stocks is not None and mode and (t == 0 or not modes[t - 1]):
            end = t + 1
            while end < len(modes) and modes[end]:
                end += 1
            quantity = stocks[end] - stocks[t] + sum(i.withdrawal_kwh for i in snapshot.intervals[t:end])
            remaining_area = max(0., quantity) / c.ev_efficiency * 3600
        target = round(three[t] if mode == 3 else one[t]) if mode else 0
        at = interval.start
        while at < interval.end:
            active_wait = next((end for start, end in blocked if start <= at < end), None)
            if not mode or active_wait or remaining_area is not None and remaining_area <= 1e-8:
                on = False
                until = min(interval.end, active_wait) if active_wait else interval.end
                segments.append((at, until, 0.0))
                at = until
                continue
            phase = mode
            if historical or not on:
                current = target  # Startup at 6 A and delivery verification are included in the startup allowance.
            elif target >= current:
                current = target
            elif last_down is None or (at - last_down).total_seconds() >= CURRENT_STEP_SECONDS:
                current -= 1
                last_down = at
            on = True
            until = interval.end
            if current > target and last_down is not None:
                until = min(until, last_down + timedelta(seconds=CURRENT_STEP_SECONDS))
            future_wait = next((start for start, _ in blocked if at < start < until), None)
            if future_wait:
                until = future_wait
            power = current * phase * c.voltage / 1000
            if remaining_area is not None:
                until = min(until, at + timedelta(seconds=remaining_area / power))
                remaining_area = max(0., remaining_area - power * (until - at).total_seconds())
                if (until - at).total_seconds() <= 1e-6:
                    remaining_area = 0.
                    continue
            segments.append((at, until, power))
            at = until
        result.append(segments)
    return result


def transition_power(snapshot: Snapshot, one: list[float], three: list[float],
                     stocks: list[float] | None = None) -> list[tuple[float, float]]:
    """Average and peak of the fixed candidate's interval-integrated transition template."""
    return [(sum((end - start).total_seconds() * power for start, end, power in segments)
             / (interval.hours * 3600), max((power for _, _, power in segments), default=0.))
            for interval, segments in zip(snapshot.intervals, transition_trace(snapshot, one, three, stocks))]


def delivery_endpoint(snapshot: Snapshot, flows: dict[str, list[float]], index: int, battery_kwh: float) -> datetime:
    """Locate a quantity endpoint inside the actual transition template, including a live ramp."""
    segments = transition_trace(snapshot, flows["amps_one"], flows["amps_three"], flows.get("ev_energy"))[index]
    remaining = max(0., battery_kwh) / snapshot.capabilities.ev_efficiency * 3600
    for start, end, power in segments:
        area = (end - start).total_seconds() * power
        if power > 0 and area >= remaining:
            return start + timedelta(seconds=remaining / power)
        remaining -= area
    return snapshot.intervals[index].end
