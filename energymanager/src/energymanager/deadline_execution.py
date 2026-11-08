"""Select a pre-audited fallback using measured progress; never solve in fast control."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .domain import Observation, instant


def required_energy(guard: dict[str, Any], at: datetime) -> float:
    scope = guard["scope"]
    return scope["target_kwh"] + sum(i["withdrawal_kwh"] for i in guard.get("nominal_context", {}).get("intervals", [])
                                     if at <= instant(i["start"]) < instant(scope["deadline"]))


class DeadlineExecution:
    def __init__(self) -> None:
        self.plan_id: str | None = None
        self.active = False
        self.activation_key: str | None = None
        self.evidence: dict[str, Any] = {}

    def select(self, plan: dict[str, Any] | None, o: Observation, at: datetime, authorized: bool) -> dict[str, Any] | None:
        self.evidence = {"active": False}
        if plan is None:
            self.active = False
            return plan
        if plan["id"] != self.plan_id:
            self.plan_id, self.active = plan["id"], False
        guard = plan.get("deadline_guard", {})
        if guard.get("status") != "certified":
            return plan
        scope = guard["scope"]
        goal = next((g for g in plan["goals"] if g["id"] == scope["goal_id"]
                     and g["revision"] == scope["revision"] and g["deadline"] == scope["deadline"]), None)
        if (not authorized or goal is None or not o.ev_state_known or at >= instant(scope["deadline"])
                or o.ev_kwh >= required_energy(guard, at) - 1e-6):
            self.active = False
            return plan
        intervals = guard["context"]["intervals"]
        t = next((t for t, i in enumerate(intervals) if instant(i["start"]) <= at < instant(i["end"])), None)
        if t is None:
            return plan
        flows = guard["flows"]
        if guard["context"].get("appliance"):
            intervals = [{**i, "background_kw": i["house_kw"], "dishwasher_kw": power,
                          "house_kw": i["house_kw"] + power}
                         for i, power in zip(intervals, flows["dishwasher_power"])]
        power = sum(flows[name][t] for name in ("grid_ev", "pv_ev", "solar_dis_ev"))
        progress_needed = o.ev_kwh < guard["progress_kwh"][t + 1] - 1e-6
        permitted_now = at >= instant(guard["activation_at"]) or flows["grid_ev"][t] < 1e-6
        if not self.active and progress_needed and power > 1e-6 and permitted_now:
            self.active = True
            self.activation_key = f"{scope['goal_id']}:{scope['revision']}:{scope['deadline']}"
        self.evidence = {"active": self.active, "scope": scope,
                         "progress_kwh": guard["progress_kwh"][t + 1], "measured_kwh": o.ev_kwh}
        if not self.active:
            return plan
        reasons = list(plan.get("reasons", []))
        if any(value > 1e-6 for value in flows["grid_store"]):
            reasons.append({"kind": "peak_precharge", "text": "Cautious deadline household support"})
        return {**plan, "flows": flows, "intervals": intervals,
                "goals": [g for g in plan["goals"] if instant(g["deadline"]) <= instant(scope["deadline"])],
                "reservations": guard["reservations"], "conditional_tasks": [], "reasons": reasons}
