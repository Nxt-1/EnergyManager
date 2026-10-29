"""Bounded solar-allocation alternatives on the original planning snapshot."""

from copy import deepcopy
from datetime import timedelta

from .optimization import JointModel


class SolarCapture:
    """Improve a useful near-term window without reopening every future decision."""

    def __init__(self, model: JointModel, flows: dict[str, list[float]]) -> None:
        self.original = model
        self.flows = flows

    def export_seed(self) -> list[float]:
        """Route otherwise unused DC through spare inverter capacity, keeping all stocks."""
        model, s = self.original, self.original.snapshot
        c = s.capabilities
        flows = deepcopy(self.flows)
        for t, interval in enumerate(s.intervals):
            imports = sum(flows[name][t] for name in ("grid_ev", "grid_house", "grid_store"))
            ac_charge = flows["pv_store"][t] + flows["grid_store"][t]
            if imports > 1e-8 or ac_charge > 1e-8:
                continue
            unused = max(0, interval.pv_dc_kw - flows["dc_store"][t] - flows["dc_invert"][t])
            output = sum(flows[name][t] for name in ("solar_dis_ev", "solar_dis_house", "grid_dis_house"))
            output += flows["dc_invert"][t] * c.ac_discharge_efficiency
            extra = min(unused, max(0, c.ac_discharge_kw - output) / c.ac_discharge_efficiency,
                        max(0, c.grid_connection_kw - flows["export"][t]) / c.ac_discharge_efficiency)
            flows["dc_invert"][t] += extra
            flows["export"][t] += extra * c.ac_discharge_efficiency
            if extra > 1e-8:
                # Idle direction flags are not physical commitments.
                flows["converter_charge"][t] = 0.0
                flows["grid_direction"][t] = 0.0
        return model.warm_from(flows)

    def windows(self) -> list[tuple[int, int]]:
        """Use bounded 24h windows across the full horizon, including the partial last day."""
        intervals = self.original.snapshot.intervals
        windows = []
        first = 0
        while first < len(intervals):
            end = intervals[first].start + timedelta(hours=24)
            last = next((t for t in range(first + 1, len(intervals)) if intervals[t].start >= end), len(intervals))
            if any(i.pv_ac_kw + i.pv_dc_kw > .05 for i in intervals[first:last]):
                windows.append((first, last))
            first = last
        return windows

    def neighborhood(self, first: int, boundary: int, *, economic_allowance: float = 1e-6,
                     preserve_ev_prefix: bool = True) -> JointModel:
        """Free one 24h window of solar/ESS routing and EV capture; preserve later supply.

        Later grid EV charging may shrink to avoid retaining a now-unnecessary purchase.
        No interval can import more, and future ESS stocks/dispatch remain unchanged.
        These are candidate restrictions, never new constraints on the joint search.
        """
        model = deepcopy(self.original)
        model.add_continuity_limits()
        s, m, flows = model.snapshot, model.linear, self.flows
        values = model.warm_from(flows)
        phase = min(s.capabilities.phases)
        other = "three" if phase == 1 else "one"
        # Keep achieved readiness, not just the minimum deadline target.
        if preserve_ev_prefix:
            for t, index in enumerate(m.variables["ev_energy"]):
                m.lower[index] = max(m.lower[index], flows["ev_energy"][t] - 1e-6)
        for name, indexes in m.variables.items():
            if name.startswith("margin_shortfall_"):
                m.upper[indexes[0]] = min(m.upper[indexes[0]], values[indexes[0]] + 1e-6)
            if name.startswith("peak_"):
                for index in indexes:
                    m.upper[index] = min(m.upper[index], values[index] + 1e-6)
        for name in ("ess_solar", "ess_grid"):
            for t in range(len(s.intervals) + 1):
                if t <= first or t >= boundary:
                    index = m.variables[name][t]
                    m.lower[index] = m.upper[index] = values[index]
        fixed_later = ("pv_ev", "pv_house", "pv_store", "export", "curtail", "grid_house", "grid_store",
                       "solar_dis_ev", "solar_dis_house", "grid_dis_house", "dc_store", "dc_invert",
                       "battery_charge", "converter_charge", "pv_store_mode")
        for name in fixed_later:
            for t in range(len(s.intervals)):
                if t < first or t >= boundary:
                    index = m.variables[name][t]
                    m.lower[index] = m.upper[index] = values[index]
        for t in range(len(s.intervals)):
            for name in ("grid_ev", "grid_house", "grid_store"):
                index = m.variables[name][t]
                m.upper[index] = min(m.upper[index], values[index])
                if t < first:
                    m.lower[index] = values[index]
            modes = (("one", "three", "amps_one", "amps_three") if t < first or t >= boundary
                     else (other, f"amps_{other}"))
            for name in modes:
                index = m.variables[name][t]
                m.upper[index] = min(m.upper[index], values[index])
                if t < first:
                    m.lower[index] = values[index]
        m.row(list(model.economic.items()), upper=model.value(model.economic, values) + economic_allowance)
        return model
