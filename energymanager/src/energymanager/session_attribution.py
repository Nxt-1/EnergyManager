"""Explain frozen EV-session energy using existing-stock-first planned allocations."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from .domain import Goal, Snapshot, instant

EPSILON = 1e-8


@dataclass
class EnergyLot:
    session_id: str | None
    remaining_kwh: float
    target_claimed_kwh: float = 0.0


class SessionEnergyLedger:
    """Keep energy use disjoint while recording first target support separately."""

    def __init__(self, snapshot: Snapshot, sessions: list[dict[str, Any]]) -> None:
        self.snapshot = snapshot
        self.sessions = {session["id"]: session for session in sessions if session["resource"] == "ev"}
        self.stock: deque[EnergyLot] = deque()
        self.known = False
        for session in self.sessions.values():
            session["energy_attribution"] = {
                "method": "existing_charge_first",
                "driving": [],
                "targets": [],
                "stored_kwh": 0.0,
                "unresolved_kwh": 0.0,
            }
            session["goal_ids"] = []

    def charge(self, session_id: str | None, energy: float) -> None:
        if energy <= EPSILON:
            return
        if self.stock and self.stock[-1].session_id == session_id:
            self.stock[-1].remaining_kwh += energy
        else:
            self.stock.append(EnergyLot(session_id, energy))

    def reconcile(self, energy: float) -> None:
        # A new known segment cannot inherit an allocation across an unknown return.
        self.known = True
        self.charge(None, energy)

    def credit(self, lot: EnergyLot, category: str, goal: Goal, energy: float) -> None:
        if lot.session_id is None or energy <= EPSILON:
            return
        rows = self.sessions[lot.session_id]["energy_attribution"][category]
        row = next((item for item in rows if item["goal_id"] == goal.id), None)
        if row is None:
            row = {
                "goal_id": goal.id,
                "title": goal.title,
                "deadline": goal.deadline.isoformat(),
                "kind": goal.kind,
                "energy_kwh": 0.0,
                "target_kwh": goal.target(self.snapshot.capabilities, self.snapshot.policy),
            }
            rows.append(row)
        row["energy_kwh"] += energy

    def support_target(self, goal: Goal) -> None:
        remaining = goal.target(self.snapshot.capabilities, self.snapshot.policy)
        for lot in self.stock:
            covered = min(remaining, lot.remaining_kwh)
            newly_claimed = max(0.0, covered - lot.target_claimed_kwh)
            self.credit(lot, "targets", goal, newly_claimed)
            lot.target_claimed_kwh += newly_claimed
            remaining -= covered
            if remaining <= EPSILON:
                break

    def withdraw(self, goal: Goal | None, energy: float) -> None:
        while self.stock and energy > EPSILON:
            lot = self.stock[0]
            used = min(energy, lot.remaining_kwh)
            if goal is not None:
                self.credit(lot, "driving", goal, used)
            elif lot.session_id is not None:
                self.sessions[lot.session_id]["energy_attribution"]["unresolved_kwh"] += used
            # Target support marks the front of each lot; consuming it does not make
            # the surviving, previously claimed energy eligible for another target.
            lot.target_claimed_kwh = max(0.0, lot.target_claimed_kwh - used)
            lot.remaining_kwh -= used
            energy -= used
            if lot.remaining_kwh <= EPSILON:
                self.stock.popleft()

    def unknown(self) -> None:
        for lot in self.stock:
            if lot.session_id is not None:
                self.sessions[lot.session_id]["energy_attribution"]["unresolved_kwh"] += lot.remaining_kwh
        self.stock.clear()
        self.known = False

    def finish(self) -> None:
        for lot in self.stock:
            if lot.session_id is not None:
                self.sessions[lot.session_id]["energy_attribution"]["stored_kwh"] += lot.remaining_kwh
        for session in self.sessions.values():
            allocation = session["energy_attribution"]
            driving = {row["goal_id"]: row["energy_kwh"] for row in allocation["driving"]}
            allocation["targets"] = [
                row
                for row in allocation["targets"]
                if row["kind"] != "trip" or row["energy_kwh"] > driving.get(row["goal_id"], 0) + EPSILON
            ]
            related: dict[str, Any] = {}
            for category in ("driving", "targets"):
                allocation[category].sort(key=lambda row: (instant(row["deadline"]), row["goal_id"]))
                related.update((row["goal_id"], row) for row in allocation[category])
            session["goal_ids"] = sorted(
                related, key=lambda identity: (instant(related[identity]["deadline"]), identity)
            )


def attribute_ev_sessions(
    snapshot: Snapshot, flows: dict[str, list[float]], sessions: list[dict[str, Any]]
) -> None:
    """Attach explanatory planned allocations without changing any trajectory or permission."""
    ledger = SessionEnergyLedger(snapshot, sessions)
    starts = [interval.start for interval in snapshot.intervals]
    owners: dict[int, str] = {}
    for session in ledger.sessions.values():
        left = bisect_left(starts, instant(session["start"]))
        right = bisect_left(starts, instant(session["end"]))
        owners.update((t, session["id"]) for t in range(left, right))
    checkpoints: dict[int, list[Goal]] = defaultdict(list)
    departures: dict[int, list[Goal]] = defaultdict(list)
    for goal in snapshot.goals:
        if not starts[0] <= goal.deadline <= snapshot.intervals[-1].end:
            continue
        index = snapshot.checkpoint_index(goal.deadline)
        checkpoints[index].append(goal)
        if goal.kind == "trip" and index < len(starts) and starts[index] == goal.deadline:
            departures[index].append(goal)

    for t in range(len(starts) + 1):
        if snapshot.ev_known_at(t):
            if not ledger.known:
                ledger.reconcile(flows["ev_energy"][t])
            if checkpoints[t]:
                # Simultaneous weaker thresholds add no extra energy requirement.
                goal = max(
                    checkpoints[t],
                    key=lambda item: (
                        item.target(snapshot.capabilities, snapshot.policy),
                        item.kind != "daily",
                        item.priority,
                        item.id,
                    ),
                )
                ledger.support_target(goal)
        else:
            ledger.unknown()
        if t == len(starts):
            break
        interval = snapshot.intervals[t]
        if not ledger.known or not interval.ev_state_known:
            ledger.unknown()
            continue
        incoming = sum(flows[name][t] for name in ("pv_ev", "grid_ev", "solar_dis_ev"))
        ledger.charge(owners.get(t), incoming * interval.hours * snapshot.capabilities.ev_efficiency)
        remaining = interval.withdrawal_kwh
        for trip in sorted(departures[t], key=lambda item: item.id):
            used = min(remaining, trip.withdrawal(snapshot.policy))
            ledger.withdraw(trip, used)
            remaining -= used
        ledger.withdraw(None, remaining)
    ledger.finish()
