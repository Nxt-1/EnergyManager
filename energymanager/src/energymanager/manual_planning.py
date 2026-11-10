"""Refine a manual quantity endpoint, preserving full joint calculation contexts."""

from dataclasses import replace
from datetime import timedelta
from typing import Any

from .domain import Snapshot
from .execution import delivery_fraction, wait_events
from .forecasts import apply_requirements
from .validation import TOL


def completion_context(original: Snapshot, seed: Snapshot, flows: dict[str, list[float]]) -> Snapshot:
    manual = dict((original.observation.ev_progress or {})["manual"])
    limit = max(original.observation.ev_kwh, manual["limit_kwh"])
    modes = [3 if b > .5 else 1 if a > .5 else 0 for a, b in zip(flows["one"], flows["three"])]
    waits = wait_events(seed, modes)
    completion = None
    for t, interval in enumerate(seed.intervals):
        if flows["ev_energy"][t] < limit - TOL <= flows["ev_energy"][t + 1]:
            power = (flows["amps_one"][t] + 3 * flows["amps_three"][t]) * seed.capabilities.voltage / 1000
            if power <= TOL:
                continue
            lost = (1 - delivery_fraction(seed, t, waits)) * interval.hours * 3600
            seconds = lost + (limit - flows["ev_energy"][t]) / power / seed.capabilities.ev_efficiency * 3600
            completion = min(interval.end, max(interval.start, interval.start + timedelta(seconds=seconds)))
            break
    intervals = []
    profile: list[dict[str, Any]] = []
    for t, interval in enumerate(seed.intervals):
        points = [interval.start]
        if completion is not None and interval.start < completion < interval.end:
            points.append(completion)
        points.append(interval.end)
        power = (round(flows["amps_one"][t]) + 3 * round(flows["amps_three"][t])) * seed.capabilities.voltage / 1000
        phase = modes[t] or seed.observation.ev_phases
        for left, right in zip(points, points[1:]):
            ended = completion is not None and left >= completion
            intervals.append(replace(interval, start=left, end=right,
                withdrawal_kwh=interval.withdrawal_kwh if left == interval.start else 0,
                available=interval.available and not ended))
            item = {"start": left.isoformat(), "end": right.isoformat(), "power_kw": 0.0 if ended else power,
                    "phases": phase}
            if profile and profile[-1]["end"] == item["start"] and all(profile[-1][k] == item[k] for k in ("power_kw", "phases")):
                profile[-1]["end"] = item["end"]
            else:
                profile.append(item)
    manual.update(schedule=profile, completion_at=completion.isoformat() if completion else None)
    progress = {**(original.observation.ev_progress or {}), "manual": manual}
    return replace(seed, observation=replace(seed.observation, ev_progress=progress), intervals=tuple(intervals),
                   provenance=seed.provenance + " · explicit manual quantity completion boundary")


def advisory_context(snapshot: Snapshot) -> Snapshot | None:
    manual = (snapshot.observation.ev_progress or {}).get("manual") or {}
    progress = snapshot.observation.ev_progress or {}
    if (not manual.get("enabled") or not snapshot.observation.connected
            or manual.get("status") not in ("active", "completed", "expired", "goal_changed")
            or progress.get("counter_issue") or progress.get("counter_stalled")):
        return None
    if not any(g.deadline > snapshot.observation.at and g.target(snapshot.capabilities, snapshot.policy)
               > max(snapshot.observation.ev_kwh, manual["limit_kwh"]) + .02 for g in snapshot.goals):
        return None
    # This explicitly hypothetical reference grants no execution authority. Rebuild
    # normal trip/unknown-return availability rather than removing individual flows.
    observation = replace(snapshot.observation, ev_state_known=True,
        ev_progress={**progress, "manual": {**manual, "enabled": False}})
    intervals = apply_requirements(snapshot.intervals, snapshot.goals, observation, snapshot.capabilities, snapshot.policy)
    return replace(snapshot, observation=observation, intervals=intervals,
                   provenance=snapshot.provenance + " · HYPOTHETICAL still-connected manual reference; NON-EXECUTABLE advisory")


def additional_instructions(snapshot: Snapshot, advisory: Snapshot, flows: dict[str, list[float]]) -> list[dict[str, Any]]:
    manual = (snapshot.observation.ev_progress or {})["manual"]
    modes = [3 if b > .5 else 1 if a > .5 else 0 for a, b in zip(flows["one"], flows["three"])]
    waits = wait_events(advisory, modes)
    instructions = []
    for t, interval in enumerate(advisory.intervals):
        if flows["ev_energy"][t + 1] <= manual["limit_kwh"] + TOL:
            continue
        power = (flows["amps_one"][t] + 3 * flows["amps_three"][t]) * advisory.capabilities.voltage / 1000
        if power <= TOL:
            continue
        lost = (1 - delivery_fraction(advisory, t, waits)) * interval.hours * 3600
        seconds = lost + max(0, manual["limit_kwh"] - flows["ev_energy"][t]) / power / advisory.capabilities.ev_efficiency * 3600
        at = interval.start + timedelta(seconds=seconds)
        if at >= interval.end:
            continue
        goals = [g for g in advisory.goals if g.deadline > at and g.target(advisory.capabilities, advisory.policy)
                 > max(snapshot.observation.ev_kwh, manual["limit_kwh"]) + .02]
        if not goals:
            continue
        goal = min(goals, key=lambda g: (g.deadline, g.id))
        instructions.append({"manual_id": manual["id"], "goal_id": goal.id, "revision": goal.revision,
                "would_start": at.isoformat(), "instruction_end": interval.end.isoformat(), "power_kw": power})
    return instructions
