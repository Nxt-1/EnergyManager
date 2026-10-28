"""Earlier required grid charging, after economic and continuity choices are fixed."""

from copy import deepcopy
from time import monotonic

from .optimization import JointModel
from .validation import TOL


class ChargingTiming:
    """Keep the selected sources and benefits while resolving indifferent EV timings."""

    def __init__(self, model: JointModel, flows: dict[str, list[float]]) -> None:
        self.model = deepcopy(model)
        self.model.add_continuity_limits()
        self.flows = flows
        m = self.model.linear
        values = self.model.warm_from(flows)
        adjustable = {"one", "three", "amps_one", "amps_three", "grid_ev", "ev_energy",
                      "grid_cumulative", "grid_direction", "start", "phase_setting", "phase_change",
                      "phase_restart", "variation", "causal_witness"}
        for name, indexes in m.variables.items():
            if name in adjustable or name == "rolling_cash_prefix" or name.startswith(("quarter_", "rolling_quarter_")):
                continue
            if name.startswith("margin_shortfall_"):
                m.upper[indexes[0]] = min(m.upper[indexes[0]], values[indexes[0]] + 1e-6)
                continue
            # Preserve PV/ESS dispatch, inventories, service and monthly peaks.
            for index in indexes:
                m.lower[index] = m.upper[index] = values[index]
        last_grid = m.variables["grid_cumulative"][-1]
        m.lower[last_grid] = m.upper[last_grid] = values[last_grid]
        for objective in (self.model.economic, self.model.cash, self.model.continuity_objective()):
            m.row(list(objective.items()), upper=self.model.value(objective, values) + 1e-6)
        start = model.snapshot.intervals[0].start
        self.objective = {m.variables["grid_ev"][t]: interval.hours * (interval.start - start).total_seconds() / 3600
                          for t, interval in enumerate(model.snapshot.intervals)}

    def earlier_seed(self, seconds: float) -> list[float]:
        """Move whole grid-only profiles first, so a solver timeout retains a useful start."""
        deadline = monotonic() + max(0, seconds)
        model, s = self.model, self.model.snapshot
        flows = deepcopy(self.flows)
        active = [a + b > .5 for a, b in zip(flows["one"], flows["three"])]
        sessions: list[tuple[int, int]] = []
        for t, on in enumerate(active):
            if on and (t == 0 or not active[t - 1]):
                sessions.append((t, t + 1))
            elif on:
                sessions[-1] = (sessions[-1][0], t + 1)
        best = model.warm_from(flows)
        previous_end = 0
        for left, right in sessions:
            if monotonic() >= deadline:
                break
            if any(flows[name][t] > TOL for name in ("pv_ev", "solar_dis_ev") for t in range(left, right)):
                previous_end = right
                continue
            length = right - left
            for first in range(previous_end, left):
                if monotonic() >= deadline:
                    break
                target = range(first, first + length)
                if any(not s.intervals[t].available
                       or (s.hold_until is not None and s.intervals[t].start < s.hold_until)
                       or abs(s.intervals[t].hours - s.intervals[left + j].hours) > 1e-9
                       or (active[t] and not left <= t < right)
                       for j, t in enumerate(target)):
                    continue
                candidate = deepcopy(flows)
                for name in ("one", "three", "amps_one", "amps_three", "grid_ev"):
                    for t in range(left, right):
                        candidate[name][t] = 0.0
                    for j, t in enumerate(target):
                        candidate[name][t] = flows[name][left + j]
                candidate["ev_energy"][0] = s.observation.ev_kwh
                candidate["grid_cumulative"][0] = 0.0
                for t, interval in enumerate(s.intervals):
                    candidate["ev_energy"][t + 1] = (candidate["ev_energy"][t]
                        + sum(candidate[name][t] for name in ("grid_ev", "pv_ev", "solar_dis_ev"))
                        * interval.hours * s.capabilities.ev_efficiency - interval.withdrawal_kwh)
                    candidate["grid_cumulative"][t + 1] = (candidate["grid_cumulative"][t]
                        + candidate["grid_ev"][t] * interval.hours * s.capabilities.ev_efficiency)
                    candidate["grid_direction"][t] = float(sum(candidate[name][t]
                        for name in ("grid_ev", "grid_house", "grid_store")) > 1e-8)
                values = model.warm_from(candidate)
                if model.linear.accepts(values):
                    flows, best = candidate, values
                    for t in range(left, right):
                        active[t] = False
                    for t in target:
                        active[t] = True
                    previous_end = first + length
                    break
            else:
                previous_end = right
        return best
