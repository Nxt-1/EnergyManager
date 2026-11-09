"""Persistent charger-counter progress, distinct from reported vehicle stock."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any

from .domain import Capabilities, Goal, Observation, Policy, instant
from .live_inputs import Reading
from .store import Store


class EVProgress:
    """Credit measured increments once, independently of plan and requirement IDs."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self.state: dict[str, Any] = store.get("ev_progress", {})

    def update(self, observation: Observation, counter: Reading | None, source: str,
               capabilities: Capabilities, policy: Policy, goals: tuple[Goal, ...] = ()) -> Observation:
        o, c, s, at = observation, capabilities, self.state, observation.at
        valid = (counter is not None and counter.issue(at) is None
                 and isinstance(counter.value, float) and counter.value >= 0)
        reported = o.ev_kwh if o.ev_state_known else None
        fresh_soc = (reported is not None and o.ev_observed_at is not None
                     and -5 <= (at - o.ev_observed_at).total_seconds() <= policy.measurement_max_age_seconds)
        if not o.connected:
            s.setdefault("away_since", at.isoformat())
        elif s.get("away_since"):
            away = instant(s.pop("away_since"))
            departures = [g.deadline for g in goals if g.kind == "trip" and away <= g.deadline <= at]
            if departures:
                s["unknown_return"] = True
                s["reconcile_after"] = max(departures).isoformat()
        if s.get("unknown_return"):
            fresh_soc = fresh_soc and o.ev_observed_at is not None and o.ev_observed_at >= instant(s["reconcile_after"])
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
        # An unchanged HA value/report time never establishes a new vehicle sample.
        soc_changed = reported is not None and reported != s.get("soc_reference_kwh")
        if fresh_soc and o.ev_observed_at is not None and (soc_changed or s.get("unknown_return")) and (
                s.get("vehicle_at") is None or o.ev_observed_at > instant(s["vehicle_at"])):
            assert o.ev_observed_at is not None and reported is not None
            before = next((r for r in reversed(history) if instant(r["at"]) <= o.ev_observed_at), None)
            after = next((r for r in history if instant(r["at"]) >= o.ev_observed_at), None)
            aligned = before is not None and after is not None and before["kwh"] == after["kwh"]
            if aligned and valid:
                assert before is not None
                s["estimated_kwh"] = min(c.ev_capacity_kwh, reported
                    + (s["counter_kwh"] - before["kwh"]) * c.ev_efficiency)
                s.update(vehicle_at=o.ev_observed_at.isoformat(), uncertain=False,
                         reconciled_counter_kwh=before["kwh"], unknown_return=False, soc_reference_kwh=reported)
            elif history:
                s["uncertain"] = True
                # An unaligned SoC can establish a higher stock floor, never erase
                # measured progress. Anchor future increments at the next counter
                # read instead of adding an overlapping missing segment twice.
                if reported > s["estimated_kwh"]:
                    s["estimated_kwh"] = reported
                    if not valid:
                        s["counter_rebase_pending"] = True
            else:
                s.update(estimated_kwh=reported, vehicle_at=o.ev_observed_at.isoformat(),
                         unknown_return=False, soc_reference_kwh=reported)
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
        valid_at = usable_at if meter_usable else o.ev_observed_at if fresh_soc else None
        if meter_usable and moving_at is not None and valid_at is not None:
            valid_at = min(valid_at, moving_at)
        view = {"source": basis, "usable": usable, "issue": issue,
                "valid_until": (valid_at + timedelta(seconds=policy.measurement_max_age_seconds)).isoformat()
                               if valid_at else None,
                "entity_id": s.get("entity_id") or source or None, "counter_kwh": s.get("counter_kwh"),
                "counter_at": s.get("counter_at"), "reported_kwh": reported,
                "vehicle_observed_at": s.get("reported_vehicle_at"),
                "estimated_kwh": energy, "credited_kwh": s.get("credited_kwh", 0.0),
                "uncertain": s.get("uncertain", False), "segments": s.get("segments", 0)}
        self.store.put("ev_progress", s)
        known = usable and (("estimated_kwh" in s and not s.get("unknown_return")) or fresh_soc)
        return replace(o, ev_kwh=energy, ev_state_known=known,
                       ev_progress=view)
