"""Persistent charger-counter progress, distinct from reported vehicle stock."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from .domain import Capabilities, Goal, Observation, Policy, instant
from .ev_feedback import EVFeedback
from .live_inputs import Reading
from .store import Store


class EVProgress:
    """Credit measured increments once, independently of plan and requirement IDs."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self.feedback = EVFeedback(store)
        self.automatic_observation: Observation | None = None
        self.state: dict[str, Any] = store.get("ev_progress", {})

    def update(self, observation: Observation, counter: Reading | None, source: str,
               capabilities: Capabilities, policy: Policy, goals: tuple[Goal, ...] = ()) -> Observation:
        o, c, s, at = observation, capabilities, self.state, observation.at
        valid = (counter is not None and counter.issue(at) is None
                 and isinstance(counter.value, float) and counter.value >= 0)
        reported = o.ev_kwh if o.ev_state_known else None
        new_report = self.feedback.changed_vehicle(o, policy)
        if new_report:
            s["report_changed_at"] = at.isoformat()
        fresh_soc = (reported is not None and o.ev_observed_at is not None
                     and -5 <= (at - o.ev_observed_at).total_seconds() <= policy.measurement_max_age_seconds)
        changed_at = instant(s["report_changed_at"]) if s.get("report_changed_at") else None
        fresh_soc = fresh_soc or (o.ev_observed_at is None and reported is not None and changed_at is not None
                                  and 0 <= (at - changed_at).total_seconds() <= policy.measurement_max_age_seconds)
        previous_reported = s.get("reported_kwh")
        if not o.connected:
            if "away_since" not in s:
                s["away_soc_reference_kwh"] = previous_reported if previous_reported is not None else reported
            s.setdefault("away_since", at.isoformat())
        elif s.get("away_since"):
            away = instant(s.pop("away_since"))
            # A charging counter cannot account for driving, registered or otherwise.
            # Keep its ledger, but require new stock evidence after every observed return.
            s["unknown_return"] = True
            s["reconcile_after"] = away.isoformat()
            s["uncertain"] = True
        if s.get("unknown_return"):
            fresh_soc = fresh_soc and (new_report or o.ev_observed_at is not None and o.ev_observed_at >= instant(s["reconcile_after"]))
        initializing = "estimated_kwh" not in s
        if initializing and reported is not None:
            s.update(estimated_kwh=reported, reported_kwh=reported, credited_kwh=0.0,
                     soc_reference_kwh=reported, baseline_at=at.isoformat(), vehicle_at=None,
                     segments=0, uncertain=not fresh_soc)
        if s.get("capacity_kwh", c.ev_capacity_kwh) != c.ev_capacity_kwh:
            # A capacity edit cannot rescale already measured delivery into new credit.
            s["estimated_kwh"] = min(c.ev_capacity_kwh, s.get("estimated_kwh", 0.0))
            s["uncertain"] = True
        s["capacity_kwh"] = c.ev_capacity_kwh
        s["reported_kwh"] = reported
        s["reported_vehicle_at"] = o.ev_observed_at.isoformat() if o.ev_observed_at else None
        history = s.setdefault("counter_history", [])
        if o.ev_power_kw > .1 and o.connected:
            s.setdefault("charging_since", at.isoformat())
        else:
            s.pop("charging_since", None)
        if valid:
            assert counter is not None and isinstance(counter.value, float)
            total = counter.value
            continuous = s.get("entity_id") == source and "counter_kwh" in s and total >= s["counter_kwh"]
            advanced = continuous and total > s["counter_kwh"]
            if advanced or not continuous:
                s.update(advanced_at=at.isoformat(), counter_stalled=False)
            rebasing = s.pop("counter_rebase_pending", False)
            if continuous and "estimated_kwh" in s and not rebasing and not initializing:
                gain = (total - s["counter_kwh"]) * c.ev_efficiency
                s["estimated_kwh"] = min(c.ev_capacity_kwh, s["estimated_kwh"] + gain)
                s["credited_kwh"] = s.get("credited_kwh", 0.0) + gain
            elif "counter_kwh" in s and not initializing:
                s["uncertain"] = True
                history.clear()
                s["segments"] = s.get("segments", 0) + 1
            s.update(entity_id=source, counter_kwh=total, counter_at=at.isoformat())
            history.append({"at": at.isoformat(), "kwh": total})
            history[:] = [r for r in history if (at - instant(r["at"])).total_seconds()
                          <= max(60, policy.measurement_max_age_seconds * 2)]
            if "estimated_kwh" in s:
                s["usable_at"] = at.isoformat()
            if s.get("charging_since"):
                delivery_at = max(instant(s["charging_since"]), instant(s.get("advanced_at", s["charging_since"])))
                if (at - delivery_at).total_seconds() > policy.measurement_max_age_seconds:
                    s["counter_stalled"] = True
        # Changed values are evidence distinct from HA read/report timestamps. Some
        # sources (including FordConnect Query SoC) expose no physical sample time.
        # Never repeatedly rebase on the old rounded SoC while the counter advances.
        reference = s.get("soc_reference_kwh")
        soc_changed = reported is not None and reference is not None and reported != reference
        lower_soc = (reported is not None and reference is not None and soc_changed
                     and (reported < reference or previous_reported is not None and reported < previous_reported))
        changed_return = (s.get("unknown_return") and soc_changed
                          and reported != s.get("away_soc_reference_kwh", reference))
        untimed_change = o.ev_observed_at is None and (lower_soc or changed_return or new_report)
        timed_change = (fresh_soc and o.ev_observed_at is not None and (soc_changed or s.get("unknown_return"))
                        and (s.get("vehicle_at") is None
                             or o.ev_observed_at > instant(s["vehicle_at"])))
        if o.connected and (timed_change or untimed_change or new_report):
            assert reported is not None
            before = next((r for r in reversed(history)
                           if o.ev_observed_at is not None and instant(r["at"]) <= o.ev_observed_at), None)
            after = next((r for r in history
                          if o.ev_observed_at is not None and instant(r["at"]) >= o.ev_observed_at), None)
            aligned = before is not None and after is not None and before["kwh"] == after["kwh"]
            rebase = valid and (aligned or new_report or lower_soc or s.get("unknown_return")
                               or reported > s["estimated_kwh"])
            vehicle_only = fresh_soc and not valid and (new_report or lower_soc or s.get("unknown_return")
                                                       or reported > s["estimated_kwh"])
            if rebase or vehicle_only:
                # With unknown/unaligned timing, omit any overlapping delivery up to
                # this read. Only later counter increments belong to the new baseline.
                counter_reference = s.get("counter_kwh")
                subsequent = 0.0
                if aligned and valid:
                    assert before is not None
                    counter_reference = before["kwh"]
                    subsequent = (s["counter_kwh"] - counter_reference) * c.ev_efficiency
                s.update(estimated_kwh=min(c.ev_capacity_kwh, reported + subsequent),
                         vehicle_at=o.ev_observed_at.isoformat() if o.ev_observed_at else None,
                         uncertain=not (aligned and valid), unknown_return=False,
                         soc_reference_kwh=reported, reconciled_counter_kwh=counter_reference,
                         baseline_revision=s.get("baseline_revision", 0) + 1,
                         reconciliation_basis="vehicle sample" if aligned and valid else
                                              "changed SoC; sample timing unknown" if untimed_change else
                                              "vehicle sample; counter overlap omitted")
                if vehicle_only:
                    s["counter_rebase_pending"] = True
                    s.pop("usable_at", None)
            else:
                s["uncertain"] = True
                if untimed_change:
                    # A lower reading contradicts retained stock, but cannot authorize
                    # either that stock or an untimed fallback during a counter outage.
                    s["unknown_return"] = True
                    s.setdefault("reconcile_after", at.isoformat())
        fresh_soc = fresh_soc and not s.get("unknown_return", False)
        usable_at = instant(s["usable_at"]) if s.get("usable_at") else None
        meter_usable = ("estimated_kwh" in s and usable_at is not None
                        and -5 <= (at - usable_at).total_seconds() <= policy.measurement_max_age_seconds)
        moving_at = None
        if s.get("charging_since"):
            moving_at = max(instant(s["charging_since"]), instant(s.get("advanced_at", s["charging_since"])))
            meter_usable = meter_usable and (at - moving_at).total_seconds() <= policy.measurement_max_age_seconds
        meter_usable = meter_usable and not s.get("unknown_return", False) and not s.get("counter_stalled", False)
        usable = meter_usable or fresh_soc
        energy = s.get("estimated_kwh", o.ev_kwh)
        basis = "go-e total energy" if meter_usable else "vehicle SoC" if fresh_soc else "retained progress"
        if fresh_soc and not meter_usable:
            assert reported is not None
            # Keep the counter ledger intact: a later total reading must not add its
            # whole missing segment to a SoC value that already includes that energy.
            energy = reported if s.get("unknown_return") else max(energy, reported)
        issue = None if usable else "EV paused: charging progress unavailable"
        if not usable and s.get("unknown_return"):
            issue = "EV paused: vehicle energy needs reconciliation"
        elif not usable and s.get("counter_stalled"):
            issue = "EV paused: charging energy counter is not advancing"
        cause = (None if usable else "post_trip" if s.get("unknown_return") else
                 "counter_stalled" if s.get("counter_stalled") else "counter_unmapped" if not source else
                 "vehicle_baseline" if "estimated_kwh" not in s else "counter_unavailable")
        valid_at = usable_at if meter_usable else (o.ev_observed_at or changed_at) if fresh_soc else None
        if meter_usable and moving_at is not None and valid_at is not None:
            valid_at = min(valid_at, moving_at)
        view = {"source": basis, "usable": usable, "issue": issue, "cause": cause,
                "reconciliation_required": bool(s.get("unknown_return")),
                "counter_stalled": bool(s.get("counter_stalled")),
                "configured_entity_id": source or None, "reconcile_after": s.get("reconcile_after"),
                "counter_issue": counter.issue(at) if counter else "Total-energy sensor not configured" if not source else "Counter read unavailable",
                "valid_until": (valid_at + timedelta(seconds=policy.measurement_max_age_seconds)).isoformat()
                               if valid_at else None,
                "entity_id": s.get("entity_id") or source or None, "counter_kwh": s.get("counter_kwh"),
                "counter_at": s.get("counter_at"), "reported_kwh": reported,
                "vehicle_observed_at": s.get("reported_vehicle_at"),
                "estimated_kwh": energy, "credited_kwh": s.get("credited_kwh", 0.0),
                "uncertain": s.get("uncertain", False), "segments": s.get("segments", 0),
                "baseline_revision": s.get("baseline_revision", 0),
                "reconciliation_basis": s.get("reconciliation_basis")}
        self.store.put("ev_progress", s)
        known = usable and (("estimated_kwh" in s and not s.get("unknown_return")) or fresh_soc)
        self.automatic_observation = replace(o, ev_kwh=energy, ev_state_known=known, ev_progress=view)
        return self.feedback.update(o, self.automatic_observation, counter, source, c, policy, goals)


def progress_warning(observation: Observation, at: datetime, goals: tuple[Goal, ...],
                     vehicle_source: str | None = None) -> dict[str, Any] | None:
    """Current operational presentation, independent of saved planning results/notifications."""
    progress = observation.ev_progress
    if progress is None:
        return None
    incident = progress.get("feedback_incident")
    if (not incident and progress.get("usable") and progress.get("valid_until")
            and at <= instant(progress["valid_until"])):
        return None
    counter_source = progress.get("configured_entity_id", progress.get("entity_id"))
    cause = progress.get("cause") or ("post_trip" if progress.get("reconciliation_required") else
        "counter_stalled" if progress.get("counter_stalled") else "counter_unmapped" if not counter_source
        else "counter_unavailable")
    if incident:
        cause = incident["cause"] if incident["cause"] in ("post_trip", "counter_stalled", "counter_unmapped", "counter_unavailable") else "vehicle_feedback"
    manual = progress.get("manual") or {}
    if manual.get("enabled") and not progress.get("usable"):
        cause = ("counter_stalled" if progress.get("counter_stalled") else
                 "counter_unavailable" if progress.get("counter_issue") else "manual_reference")
    vehicle_cause = cause in ("post_trip", "vehicle_baseline", "vehicle_feedback", "manual_reference")
    source = vehicle_source if vehicle_cause else counter_source
    title, action = {
        "counter_unmapped": ("EV progress sensor not selected", "Select go-e Total energy · eto in Measurements, save and restart."),
        "counter_unavailable": ("EV charging progress unavailable", "Restore the selected total-energy sensor with declared Wh/kWh units, or a genuinely fresh vehicle SoC."),
        "counter_stalled": ("EV energy counter is not advancing", "Check the selected total-energy sensor and its updates while charging; restore measured progress."),
        "post_trip": ("Vehicle energy needs reconciliation", "Restore a changed post-trip vehicle SoC with a usable total-energy counter, or a genuinely fresh vehicle sample; reconnect the vehicle if it is still away."),
        "vehicle_feedback": ("Vehicle feedback needs attention", "Restore a changed valid vehicle SoC, or confirm an actual current Manual SoC and the next goal in the EV tab."),
        "manual_reference": ("Manual SoC needs a new reference", "Check the counter and confirm the actual current SoC and next goal in the EV tab."),
        "vehicle_baseline": ("Vehicle energy baseline unavailable", "Restore a valid vehicle SoC to establish the total-energy reference."),
    }[cause]
    affected = {goal.id: {"id": goal.id, "revision": goal.revision, "title": goal.title,
                          "deadline": goal.deadline.isoformat()}
                for goal in goals if goal.deadline > at}
    return {"kind": "ev_progress", "id": "ev-feedback:" + incident["id"] if incident else "ev-progress:" + cause + ":" + (source or "vehicle"),
            "cause": cause, "title": title, "text": ("The confirmed manual goal may continue under normal guards; vehicle feedback remains unresolved."
                                       if (progress.get("manual") or {}).get("enabled") and progress.get("usable") else
                                       "EV charging is paused; task progress is retained and ESS remains independent."),
            "action": action, "entity_id": source,
            "source_issue": None if vehicle_cause else progress.get("counter_issue"),
            "vehicle_observed_at": progress.get("vehicle_observed_at"),
            "affected_goals": sorted(affected.values(), key=lambda goal: (goal["deadline"], goal["id"]))}
