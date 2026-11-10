"""Vehicle-feedback incidents and explicitly confirmed, single-goal manual stock."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import math
from typing import Any
from uuid import uuid4

from .domain import Capabilities, Goal, Observation, Policy, instant, json_data
from .live_inputs import Reading
from .store import Store


class EVFeedback:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.state: dict[str, Any] = store.get("ev_feedback", {})

    def save(self) -> None:
        self.store.put("ev_feedback", self.state)

    @staticmethod
    def vehicle_value(raw: Observation, policy: Policy) -> float | None:
        if not raw.ev_state_known:
            return None
        if raw.ev_observed_at is not None and not -5 <= (raw.at - raw.ev_observed_at).total_seconds() <= policy.measurement_max_age_seconds:
            return None
        return raw.ev_kwh

    def changed_vehicle(self, raw: Observation, policy: Policy) -> bool:
        value = self.vehicle_value(raw, policy)
        previous = self.state.get("vehicle_kwh")
        return value is not None and (previous is not None and value != previous
                                     or previous is None and bool(self.state.get("manual", {}).get("enabled")))

    def notice(self, key: str, message: str) -> None:
        self.state.setdefault("notices", {}).setdefault(key, {"kind": "ev_feedback", "message": message})

    def clear_refresh(self) -> None:
        pending = self.state.pop("refresh", None)
        if pending:
            self.state.get("notices", {}).pop("ev-manual-refresh:" + pending["id"], None)

    def incident(self, cause: str, at: datetime) -> None:
        if self.state.get("incident"):
            priority = {"stuck_soc": 3, "vehicle_unavailable": 2, "post_trip": 2}
            if priority.get(cause, 1) >= priority.get(self.state["incident"]["cause"], 1):
                self.state["incident"]["cause"] = cause
            return
        issue = {"id": uuid4().hex, "cause": cause, "at": at.isoformat()}
        self.state["incident"] = issue
        self.store.event("ev_feedback_problem", issue)
        self.notice("ev-feedback:" + issue["id"],
                    "EV battery feedback needs attention. Automatic charging is paused without a trustworthy reference. "
                    "Open the EV tab to restore feedback or confirm an actual current Manual SoC for the next goal. ESS continues.")

    def update(self, raw: Observation, automatic: Observation, counter: Reading | None, source: str,
               capabilities: Capabilities, policy: Policy, goals: tuple[Goal, ...]) -> Observation:
        s, at, c = self.state, raw.at, capabilities
        value = self.vehicle_value(raw, policy)
        changed = self.changed_vehicle(raw, policy)
        valid = counter is not None and counter.issue(at) is None and isinstance(counter.value, float) and counter.value >= 0
        previous = s.get("counter")
        gain = 0.0
        if valid:
            assert counter is not None and isinstance(counter.value, float)
            continuous = previous and previous["source"] == source and counter.value >= previous["kwh"]
            if continuous:
                assert previous is not None
                gain = (counter.value - previous["kwh"]) * c.ev_efficiency
            elif previous:
                s.update(delivery_kwh=0.0, threshold_at=None)
            s["counter"] = {"source": source, "kwh": counter.value, "at": counter.received_at.isoformat()}
        if s.get("capacity_kwh", c.ev_capacity_kwh) != c.ev_capacity_kwh or s.get("efficiency", c.ev_efficiency) != c.ev_efficiency:
            s.update(delivery_kwh=0.0, threshold_at=None)
        s.update(capacity_kwh=c.ev_capacity_kwh, efficiency=c.ev_efficiency)
        manual = s.get("manual", {})
        if changed:
            s["automatic_reference_suspended"] = False
            issue = s.pop("incident", None)
            recovery_id = issue["id"] if issue else manual.get("id") if manual.get("enabled") else None
            if manual.get("enabled"):
                manual.update(enabled=False, status="recovered")
            s.update(delivery_kwh=0.0, threshold_at=None)
            self.clear_refresh()
            if recovery_id:
                self.notice("ev-feedback-recovered:" + recovery_id,
                            "New vehicle SoC received. Battery stock is corrected and normal EV planning can resume under its usual guards.")
                self.store.event("ev_feedback_recovered", {"id": recovery_id, "reported_kwh": value, "at": at})
        if value is not None:
            if "vehicle_kwh" not in s or changed:
                s["report_reference_kwh"] = value
                s.update(delivery_kwh=0.0, threshold_at=None)
            s["vehicle_kwh"] = value
        if not changed and "report_reference_kwh" in s:
            # Saturation cannot manufacture an expected three-point rise near full.
            room = max(0.0, c.ev_capacity_kwh - s["report_reference_kwh"])
            s["delivery_kwh"] = min(room, s.get("delivery_kwh", 0.0) + gain)
            if s["delivery_kwh"] + 1e-9 >= .03 * c.ev_capacity_kwh:
                if s.get("threshold_at") is None:
                    s["threshold_at"] = at.isoformat()
                if (at - instant(s["threshold_at"])).total_seconds() >= 900:
                    self.incident("stuck_soc", at)
        if raw.connected:
            if not raw.ev_state_known:
                self.incident("vehicle_unavailable", at)
            elif automatic.ev_progress and automatic.ev_progress.get("reconciliation_required") and not changed:
                self.incident("post_trip", at)
            elif automatic.ev_progress and not automatic.ev_progress.get("usable"):
                self.incident(automatic.ev_progress.get("cause") or "counter_unavailable", at)
        issue = s.get("incident")
        if (issue and issue["cause"] not in ("stuck_soc", "vehicle_unavailable")
                and not manual.get("enabled") and automatic.ev_state_known
                and automatic.ev_progress and automatic.ev_progress.get("usable")):
            s.pop("incident", None)
            self.notice("ev-feedback-recovered:" + issue["id"], "EV progress source restored. Normal charging can resume under the existing guards.")
        if manual.get("enabled"):
            if not raw.connected:
                manual["status"] = "unplugged"
            elif manual["capacity_kwh"] != c.ev_capacity_kwh or manual["efficiency"] != c.ev_efficiency:
                manual["status"] = "reference_required"
            elif at >= instant(manual["goal"]["deadline"]):
                manual["status"] = "expired"
            else:
                matching = next((g for g in goals if g.id == manual["goal"]["id"]), None)
                if (matching is None or matching.revision != manual["goal"]["revision"]
                        or matching.deadline != instant(manual["goal"]["deadline"])
                        or abs(matching.target(c, policy) - manual["target_kwh"]) > 1e-8):
                    manual["status"] = "goal_changed"
            if valid and manual["status"] in ("active", "completed", "expired", "goal_changed"):
                assert counter is not None and isinstance(counter.value, float)
                if source != manual["counter_source"] or counter.value < manual["counter_kwh"]:
                    manual["status"] = "reference_required"
                else:
                    manual["delivered_kwh"] += (counter.value - manual["counter_kwh"]) * c.ev_efficiency
                    manual["counter_kwh"] = counter.value
                    quantum = c.minimum_current_a * c.voltage * min(c.phases) / 1000 * c.ev_efficiency * policy.control_period_seconds / 3600
                    if manual["status"] in ("active", "completed") and manual["delivered_kwh"] >= manual["quantity_kwh"] - max(1e-6, quantum):
                        manual["status"] = "completed"
        result = self.apply(automatic, at, policy)
        self.save()
        return result

    def apply(self, automatic: Observation, at: datetime, policy: Policy) -> Observation:
        s = self.state
        progress = dict(automatic.ev_progress or {})
        manual = s.get("manual", {})
        energy, known = automatic.ev_kwh, automatic.ev_state_known
        if manual.get("enabled"):
            energy = min(s.get("capacity_kwh", manual["capacity_kwh"]), manual["reference_kwh"] + manual["delivered_kwh"])
            anchor = s.get("counter")
            usable = (manual["status"] in ("active", "completed") and automatic.connected
                      and anchor is not None and anchor["source"] == manual["counter_source"]
                      and -5 <= (at - instant(anchor["at"])).total_seconds() <= policy.measurement_max_age_seconds
                      and not progress.get("counter_stalled"))
            known = bool(usable)
            valid_until = None
            if usable:
                assert anchor is not None
                valid_until = (instant(anchor["at"]) + timedelta(seconds=policy.measurement_max_age_seconds)).isoformat()
            progress.update(usable=bool(usable), estimated_kwh=energy, uncertain=True,
                            source="manual SoC + go-e total energy", cause=None if usable else "manual_reference",
                            issue=None if usable else "Manual reference or charging counter unavailable",
                            valid_until=valid_until)
        elif s.get("automatic_reference_suspended") or s.get("incident", {}).get("cause") in ("stuck_soc", "vehicle_unavailable", "post_trip"):
            known = False
            progress.update(usable=False, cause="vehicle_feedback", issue="Vehicle feedback needs attention", valid_until=None)
        progress.update(feedback_incident=s.get("incident"), feedback_delivery_kwh=s.get("delivery_kwh", 0),
                        feedback_threshold_at=s.get("threshold_at"), manual=dict(manual) if manual else None)
        return replace(automatic, ev_kwh=energy, ev_state_known=known, ev_progress=progress)

    def confirm(self, soc_percent: Any, goal: Goal, observation: Observation, counter: Reading | None,
                source: str, capabilities: Capabilities, policy: Policy, at: datetime) -> None:
        if (type(soc_percent) not in (int, float) or not math.isfinite(soc_percent)
                or not 0 <= soc_percent <= 100):
            raise ValueError("Enter the actual current SoC between 0 and 100%")
        if not observation.connected or observation.quality == "unknown" or (at - observation.at).total_seconds() > policy.measurement_max_age_seconds:
            raise ValueError("A current connected vehicle observation is required")
        if (counter is None or counter.issue(at) is not None or not isinstance(counter.value, float)
                or counter.value < 0 or (observation.ev_progress or {}).get("counter_stalled")):
            raise ValueError("Restore a usable charging counter before confirming Manual SoC")
        if goal.deadline <= at:
            raise ValueError("Confirm a current future charging goal")
        reference = soc_percent / 100 * capabilities.ev_capacity_kwh
        target = goal.target(capabilities, policy)
        self.state["counter"] = {"source": source, "kwh": counter.value, "at": counter.received_at.isoformat()}
        # Manual authority cannot silently become an unlimited automatic reference
        # when switched off. A changed vehicle report grounds automatic stock again.
        self.state["automatic_reference_suspended"] = True
        self.state["manual"] = {"id": uuid4().hex, "enabled": True, "status": "active",
            "reference_kwh": reference, "soc_percent": soc_percent, "entered_at": at.isoformat(),
            "goal": json_data(goal), "target_kwh": target, "quantity_kwh": max(0.0, target - reference),
            "limit_kwh": max(reference, target), "delivered_kwh": 0.0,
            "capacity_kwh": capabilities.ev_capacity_kwh, "efficiency": capabilities.ev_efficiency,
            "counter_source": source, "counter_kwh": counter.value}
        self.clear_refresh()
        self.store.event("ev_manual_confirmed", self.state["manual"])
        self.save()

    def disable(self) -> None:
        if self.state.get("manual"):
            self.state["manual"].update(enabled=False, status="off")
            self.store.event("ev_manual_disabled", {"id": self.state["manual"]["id"]})
        self.save()

    def request_refresh(self, at: datetime, demand: dict[str, Any]) -> None:
        manual = self.state.get("manual", {})
        if not manual.get("enabled") or self.state.get("refresh"):
            return
        if instant(demand["would_start"]) > at or demand["manual_id"] != manual["id"]:
            return
        self.state["refresh"] = {"id": uuid4().hex, "at": at.isoformat(), "demand": demand}
        self.notice("ev-manual-refresh:" + self.state["refresh"]["id"],
                    "Another EV charge now needs a new battery reference. Open the EV tab and confirm the actual current Manual SoC and next goal. Extra charging remains paused; ESS continues.")
        self.save()
