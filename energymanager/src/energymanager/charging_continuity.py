"""Full-horizon charging windows and constrained continuity alternatives."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from zoneinfo import ZoneInfo
from typing import Any

from .optimization import JointModel


@dataclass(frozen=True)
class ChargingWindow:
    first: int
    last: int
    available: bool


class ChargingContinuity:
    """Account for every interval, preserving selected benefits and earlier improvements."""

    def __init__(self, model: JointModel, flows: dict[str, list[float]],
                 windows: list[ChargingWindow] | None = None) -> None:
        self.model = model
        self.flows = flows
        self.windows = windows if windows is not None else self.partition()

    def partition(self) -> list[ChargingWindow]:
        intervals = self.model.snapshot.intervals
        zone = ZoneInfo(self.model.snapshot.policy.timezone)
        windows: list[ChargingWindow] = []
        first = 0
        for t in range(1, len(intervals)):
            availability_changed = intervals[t].available != intervals[t - 1].available
            day_changed = intervals[t].start.astimezone(zone).date() != intervals[t - 1].start.astimezone(zone).date()
            # Midnight must not split a session already running across that boundary.
            continuing = self.on(t - 1) and self.on(t)
            if availability_changed or day_changed and not continuing:
                windows.append(ChargingWindow(first, t, intervals[first].available))
                first = t
        windows.append(ChargingWindow(first, len(intervals), intervals[first].available))
        return windows

    def on(self, t: int) -> bool:
        return self.flows["one"][t] + self.flows["three"][t] > .5

    def sessions(self, window: ChargingWindow) -> int:
        return sum(self.on(t) and (t == window.first or not self.on(t - 1))
                   for t in range(window.first, window.last))

    def phases(self, window: ChargingWindow) -> set[int]:
        return {3 if self.flows["three"][t] > .5 else 1
                for t in range(window.first, window.last) if self.on(t)}

    @staticmethod
    def session_terms(model: JointModel, window: ChargingWindow) -> list[tuple[int, float]]:
        v = model.linear.variables
        return ([(v[name][window.first], 1.) for name in ("one", "three")]
                + [(v["start"][t], 1.) for t in range(window.first + 1, window.last)])

    @staticmethod
    def score_terms(model: JointModel, window: ChargingWindow) -> list[tuple[int, float]]:
        v = model.linear.variables
        return [(v[name][t], model.operations[v[name][t]])
                for name in ("start", "phase_change", "phase_restart", "variation")
                for t in range(window.first, window.last)]

    def protect(self, model: JointModel) -> None:
        """Prevent later work from trading a reviewed window's continuity for another's."""
        values = model.warm_from(self.flows)
        for window in self.windows:
            model.linear.row(self.session_terms(model, window), upper=self.sessions(window) + 1e-6)
            terms = self.score_terms(model, window)
            model.linear.row(terms, upper=sum(values[index] * weight for index, weight in terms) + 1e-6)

    def candidate(self, window: ChargingWindow, phase: int | None) -> JointModel:
        """Refine one EV window while sources and ESS remain joint horizon decisions."""
        model = deepcopy(self.model)
        model.add_continuity_limits()
        self.protect(model)
        s, m = model.snapshot, model.linear
        v, flows = m.variables, self.flows
        values = model.warm_from(flows)
        first, last = window.first, window.last
        # Other EV work and its energy commitments stay fixed. ESS stocks and
        # source routing are choices in the original model, including across midnight.
        for name in ("one", "three", "amps_one", "amps_three"):
            for t, index in enumerate(v[name]):
                if t < first or t >= last:
                    m.lower[index] = m.upper[index] = flows[name][t]
        # Fixed surrounding amperes and the original ledger determine the other
        # EV stocks. Only these boundary values are needed to retain quantity.
        for t in (first, last):
            index = v["ev_energy"][t]
            m.lower[index] = m.upper[index] = flows["ev_energy"][t]
        for name, indexes in v.items():
            if name.startswith("margin_shortfall_"):
                for index in indexes:
                    m.upper[index] = min(m.upper[index], values[index] + 1e-6)
        for goal in s.goals:
            if not s.intervals[0].start <= goal.deadline <= s.intervals[-1].end:
                continue
            for at in (goal.deadline, max(s.intervals[0].start, goal.deadline
                                         - timedelta(minutes=s.policy.completion_margin_minutes))):
                k = s.checkpoint_index(at)
                if first < k < last and s.ev_known_at(k):
                    required = min(goal.target(s.capabilities, s.policy), flows["ev_energy"][k])
                    m.lower[v["ev_energy"][k]] = max(m.lower[v["ev_energy"][k]], required - 1e-6)
        timing = self.timing_terms(model)
        m.row(list(timing.items()), upper=model.value(timing, values) + 1e-6)
        if phase is not None:
            m.row(self.session_terms(model, window), upper=1)
            other = "three" if phase == 1 else "one"
            for t in range(first, last):
                m.upper[v[other][t]] = m.upper[v[f"amps_{other}"][t]] = 0
                # Preserve partial-slot quantity in this quick one-session candidate.
                if abs(s.intervals[t].hours - 5 / 60) > 1e-9:
                    for name in ("one", "three", "amps_one", "amps_three"):
                        index = v[name][t]
                        m.lower[index] = m.upper[index] = flows[name][t]
        return model

    def packed_candidate(self, window: ChargingWindow, *, longest_run: bool = False) -> tuple[JointModel, int] | None:
        """Offer a compact integer-current profile; the model still chooses/checks sources.

        Keep irregular slots unchanged and group regular-slot ampere-hours. This gives
        bounded MIP searches a useful starting alternative, including a separate tail
        when exact selected energy cannot fit into one session. The alternative
        anchor consolidates early/late fragments into the existing longest run,
        avoiding a low-solar gap crossed by an earliest-start profile.
        """
        s, c, flows = self.model.snapshot, self.model.snapshot.capabilities, self.flows
        active = [t for t in range(window.first, window.last) if self.on(t)]
        regular = [t for t in range(window.first, window.last) if abs(s.intervals[t].hours - 5 / 60) < 1e-9]
        if not active or not regular:
            return None
        first = next((t for t in regular if t >= active[0]), None)
        if first is None:
            return None
        end = first
        while end < window.last and abs(s.intervals[end].hours - 5 / 60) < 1e-9:
            end += 1
        if longest_run:
            runs: list[tuple[int, int]] = []
            regular_set = set(regular)
            for t in range(window.first, window.last):
                if t in regular_set and self.on(t):
                    if not runs or runs[-1][1] != t:
                        runs.append((t, t + 1))
                    else:
                        runs[-1] = (runs[-1][0], t + 1)
            if not runs:
                return None
            first, end = max(runs, key=lambda span: span[1] - span[0])
        phases = sorted(c.phases)
        if s.hold_ev_kw > 0 and window.first == 0:
            phases = [s.hold_phases]
        for phase in phases:
            units = sum(flows["amps_one"][t] + 3 * flows["amps_three"][t] for t in regular) / phase
            total = round(units)
            if abs(total - units) > 1e-6 or total < c.minimum_current_a:
                continue
            length = min(end - first, total // c.minimum_current_a)
            if not length or length * c.maximum_current_a < total:
                continue
            current, extra = divmod(total, length)
            local = self.candidate(window, None)
            v, m = local.linear.variables, local.linear
            regular_set = set(regular)
            chosen = "one" if phase == 1 else "three"
            for t in range(window.first, window.last):
                amps = current + int(t - first < extra) if first <= t < first + length else 0
                for name in ("one", "three", "amps_one", "amps_three"):
                    value = flows[name][t]
                    if t in regular_set:
                        if name == chosen:
                            value = float(amps > 0)
                        elif name == f"amps_{chosen}":
                            value = float(amps)
                        else:
                            value = 0.
                    index = v[name][t]
                    m.lower[index] = m.upper[index] = value
            # These markers are determined by the fixed EV profile. Leaving them
            # as search variables adds symmetry without another physical choice.
            profile = local.warm_from(flows)
            for name in ("one", "three", "amps_one", "amps_three"):
                for index in v[name]:
                    profile[index] = m.lower[index]
            profile = local.canonical_values(profile)
            for name in ("start", "phase_setting", "phase_change", "phase_restart", "variation"):
                for index in v[name]:
                    m.lower[index] = m.upper[index] = profile[index]
            return local, phase
        return None

    @staticmethod
    def integer_dispatch(model: JointModel, flows: dict[str, list[float]]) -> dict[str, list[float]]:
        """Restore unpriced source indicators; callers must check the original integer model.

        Physical powers and energy stocks never change. A relaxed solution with
        incompatible simultaneous flows is rejected by the original rows, not repaired.
        """
        values = model.warm_from(flows)
        v = model.linear.variables
        modes = (("battery_charge", ("pv_store", "grid_store", "dc_store")),
                 ("converter_charge", ("pv_store", "grid_store")),
                 ("grid_direction", ("grid_ev", "grid_house", "grid_store")),
                 ("pv_store_mode", ("pv_store",)))
        for t in range(len(model.snapshot.intervals)):
            for name, sources in modes:
                values[v[name][t]] = float(sum(values[v[source][t]] for source in sources) > 1e-8)
        values = model.canonical_values(values)
        return {name: [values[index] for index in indexes] for name, indexes in v.items()}

    def summarize(self, window: ChargingWindow, record: dict[str, Any], revision: int) -> None:
        """Resolve a window from all attempts, keeping unresolved or stale searches visible."""
        attempts = record.get("attempts", [])
        record["sessions_after"] = self.sessions(window)
        record["had_timeouts"] = any(a["status"] == "Time limit reached" for a in attempts)
        unresolved = False
        if not window.available:
            outcome = "unavailable"
        elif not record["sessions_before"]:
            outcome = "no_charging"
        elif self.sessions(window) == 1 and len(self.phases(window)) == 1:
            outcome = "improved" if record.get("improvement_retained") else "already_continuous"
        else:
            completed = any(a["kind"] == "flexible" and a["status"] == "Optimal" and a.get("valid")
                            and not a.get("rejected") and a.get("result_revision") == revision for a in attempts)
            if completed:
                outcome = "no_improvement_found"
            else:
                unresolved = True
                if record["had_timeouts"]:
                    outcome = "unresolved_timeout"
                elif any(a.get("rejected") for a in attempts):
                    outcome = "candidate_rejected"
                elif attempts and all(a["status"] == "Infeasible" for a in attempts):
                    outcome = "candidate_infeasible"
                else:
                    outcome = "not_checked_budget"
        record["outcome"] = outcome
        record["unresolved"] = unresolved

    @staticmethod
    def timing_terms(model: JointModel) -> dict[int, float]:
        start = model.snapshot.intervals[0].start
        return {model.linear.variables["grid_ev"][t]: interval.hours * (interval.start - start).total_seconds() / 3600
                for t, interval in enumerate(model.snapshot.intervals)}
