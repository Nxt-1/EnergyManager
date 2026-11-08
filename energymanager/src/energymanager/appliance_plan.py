"""Energy-conserving discrete starts for one uninterrupted Bosch cycle."""

from __future__ import annotations

import bisect
import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from .domain import instant

if TYPE_CHECKING:
    from .domain import Snapshot


class CycleCurve:
    def __init__(self, points: list[dict[str, Any]]) -> None:
        if len(points) < 2:
            raise ValueError("A reviewed cycle needs a measured curve")
        self.times = [float(point["seconds"]) for point in points]
        self.powers = [float(point["power_w"]) for point in points]
        if self.times[0] != 0 or any(not math.isfinite(v) or v < 0 for v in self.times+self.powers):
            raise ValueError("Invalid cycle curve")
        if any(b <= a for a, b in zip(self.times,self.times[1:])):
            raise ValueError("Cycle times must increase")
        self.prefix = [0.0]
        for a,b,power in zip(self.times,self.times[1:],self.powers):
            self.prefix.append(self.prefix[-1]+(b-a)*power)

    def integral(self, seconds: float) -> float:
        value = max(0.0,min(seconds,self.times[-1]))
        index = min(len(self.times)-2,bisect.bisect_right(self.times,value)-1)
        return self.prefix[index]+(value-self.times[index])*self.powers[index]

    def mean_kw(self, start: datetime, left: datetime, right: datetime, idle_w: float = 0) -> float:
        a,b = (left-start).total_seconds(),(right-start).total_seconds()
        covered = max(0.0,min(b,self.times[-1])-max(a,0))
        energy = self.integral(b)-self.integral(a)+idle_w*((b-a)-covered)
        return energy/(b-a)/1000


def starts_for(snapshot: Snapshot) -> list[datetime]:
    task = snapshot.appliance
    if not task or not task.get("points"):
        return []
    if task.get("started_at"):
        return [instant(task["started_at"])]
    earliest = max(instant(task["ready_at"]),snapshot.hold_until or snapshot.intervals[0].start)
    choices = sorted({earliest, *[i.start for i in snapshot.intervals if i.start >= earliest]})
    choices = [at for at in choices if at+timedelta(seconds=task["curve_seconds"]) <= snapshot.intervals[-1].end]
    if task.get("asap"):
        return choices[:1]
    return [at for at in choices if at+timedelta(seconds=task["mean_duration_seconds"]) <= instant(task["deadline"])]


def selected_start(snapshot: Snapshot, flows: dict[str,list[float]]) -> datetime | None:
    choices = starts_for(snapshot)
    if not choices:
        if snapshot.appliance and snapshot.appliance.get("points"):
            raise ValueError("Required dishwasher cycle has no feasible start")
        return None
    weights = flows.get("dishwasher_start",[])
    if len(weights) != len(choices) or abs(sum(weights)-1)>2e-5 or any(min(abs(v),abs(1-v))>2e-5 for v in weights):
        raise ValueError("Invalid dishwasher start selection")
    return choices[max(range(len(weights)),key=weights.__getitem__)]


def resolved_power(snapshot: Snapshot, flows: dict[str,list[float]]) -> list[float]:
    if not snapshot.appliance:
        return [0.0]*len(snapshot.intervals)
    idle = snapshot.appliance["idle_w"]
    at = selected_start(snapshot,flows)
    if at is None:
        return [idle/1000]*len(snapshot.intervals)
    curve = CycleCurve(snapshot.appliance["points"])
    return [curve.mean_kw(at,i.start,i.end,idle) for i in snapshot.intervals]


def plan_evidence(snapshot: Snapshot, flows: dict[str,list[float]]) -> dict[str,Any] | None:
    task = snapshot.appliance
    if not task:
        return None
    at = selected_start(snapshot,flows)
    return {**task, "planned_start": at.isoformat() if at else None,
            "estimated_finish": (at+timedelta(seconds=task["mean_duration_seconds"])).isoformat() if at else None,
            "accounting_end": (at+timedelta(seconds=task["curve_seconds"])).isoformat() if at else None,
            "mapped_energy_kwh": sum(power*i.hours for power,i in zip(resolved_power(snapshot,flows),snapshot.intervals))}
