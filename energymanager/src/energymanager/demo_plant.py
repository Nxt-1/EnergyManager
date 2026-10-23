"""Explicit synthetic device feed for offline closed-loop verification, never installation evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from .control import Command
from .domain import Observation, Snapshot


class DemoPlant:
    def __init__(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot
        self.observation = snapshot.observation
        self.completed_trips: set[str] = set()
        self.unknown_return = False
        self.phase_target: int | None = None
        self.phase_ready_at: datetime | None = None

    def step(self, at: datetime, command: Command | None) -> Observation:
        s, old = self.snapshot, self.observation
        c, p = s.capabilities, s.policy
        hours = max(0, (at - old.at).total_seconds() / 3600)
        interval = next((i for i in s.intervals if i.start <= at < i.end), s.intervals[-1])
        connected = old.connected
        ev, solar, grid = old.ev_kwh, old.ess_kwh - c.ess_min_kwh - old.ess_grid_kwh, old.ess_grid_kwh
        for trip in s.goals:
            if trip.kind != "trip":
                continue
            if old.at < trip.deadline <= at and trip.id not in self.completed_trips:
                self.completed_trips.add(trip.id)
                connected = False
                withdrawal = trip.withdrawal(p)
                if (
                    withdrawal <= ev
                    and withdrawal + p.arrival_reserve_km * p.consumption_kwh_per_100km / 100
                    <= c.ev_capacity_kwh
                ):
                    ev -= withdrawal
                else:
                    self.unknown_return = True
            if trip.return_at and old.at < trip.return_at <= at and not self.unknown_return:
                connected = True
        ev_kw = command.ev_kw if command and connected else 0.0
        actual_phase = old.ev_phases
        if command and command.phases != old.ev_phases:
            if self.phase_target != command.phases:
                self.phase_target = command.phases
                self.phase_ready_at = old.at + timedelta(seconds=10)
            assert self.phase_ready_at is not None
            active_hours = max(0, (at - max(old.at, self.phase_ready_at)).total_seconds()) / 3600
            ev_kw = ev_kw * min(1, active_hours / hours) if hours > 0 else 0.0
            if at >= self.phase_ready_at:
                actual_phase = command.phases
        else:
            self.phase_target = self.phase_ready_at = None
        ess_kw = command.ess_kw if command else 0.0
        if hours > 0:
            ev_kw = min(ev_kw, max(0, c.ev_capacity_kwh - ev) / hours / c.ev_efficiency)
            direct_dc = min(interval.pv_dc_kw, max(0, ess_kw) / c.ac_discharge_efficiency)
            discharge_dc = max(0, ess_kw / c.ac_discharge_efficiency - direct_dc)
            discharge_dc = min(discharge_dc, c.battery_discharge_kw, (solar + grid) / hours)
            if ess_kw > 0:
                ess_kw = min(
                    c.ac_discharge_kw,
                    (direct_dc + discharge_dc) * c.ac_discharge_efficiency,
                    max(0, interval.house_kw + ev_kw - interval.pv_ac_kw),
                )
                direct_dc = min(interval.pv_dc_kw, ess_kw / c.ac_discharge_efficiency)
                discharge_dc = max(0, ess_kw / c.ac_discharge_efficiency - direct_dc)
            grid_draw = min(grid, discharge_dc * hours)
            solar -= max(0, discharge_dc * hours - grid_draw)
            grid -= grid_draw
            remaining = max(0, c.ess_capacity_kwh - c.ess_min_kwh - solar - grid)
            dc_store = (
                min(
                    max(0, interval.pv_dc_kw - direct_dc),
                    c.dc_charge_kw,
                    c.battery_charge_kw / c.dc_efficiency,
                    remaining / hours / c.dc_efficiency,
                )
                if discharge_dc < 1e-8
                else 0
            )
            remaining -= dc_store * c.dc_efficiency * hours
            ac_store = min(
                max(0, -ess_kw),
                c.ac_charge_kw,
                max(0, c.battery_charge_kw - dc_store * c.dc_efficiency) / c.ac_charge_efficiency,
                max(0, remaining) / hours / c.ac_charge_efficiency,
            )
            if ess_kw < 0:
                ess_kw = -ac_store
            ac_solar = min(ac_store, max(0, interval.pv_ac_kw - interval.house_kw - ev_kw))
            solar += (dc_store * c.dc_efficiency + ac_solar * c.ac_charge_efficiency) * hours
            grid += (ac_store - ac_solar) * c.ac_charge_efficiency * hours
            ev += ev_kw * c.ev_efficiency * hours
        prefix = old.quarter_import_kwh
        peak = old.monthly_peak_kw
        quarter_end = old.at.replace(minute=old.at.minute // 15 * 15, second=0, microsecond=0) + timedelta(
            minutes=15
        )
        import_kw = max(0, interval.house_kw + ev_kw - interval.pv_ac_kw - ess_kw)
        if at >= quarter_end:
            prefix += import_kw * max(0, (quarter_end - old.at).total_seconds()) / 3600
            peak = max(peak, prefix * 4)
            prefix = import_kw * max(0, (at - quarter_end).total_seconds()) / 3600
        else:
            prefix += import_kw * hours
        if at.month != old.at.month:
            peak = 0.0
        self.observation = replace(
            old,
            at=at,
            ev_kwh=max(0, min(c.ev_capacity_kwh, ev)),
            ess_kwh=max(c.ess_min_kwh, min(c.ess_capacity_kwh, c.ess_min_kwh + solar + grid)),
            ess_grid_kwh=max(0, grid),
            connected=connected,
            house_kw=interval.house_kw,
            pv_ac_kw=interval.pv_ac_kw,
            pv_dc_kw=interval.pv_dc_kw,
            ev_power_kw=ev_kw,
            ess_power_kw=ess_kw,
            quarter_import_kwh=prefix,
            monthly_peak_kw=peak,
            quality="SYNTHETIC",
            ev_phases=actual_phase,
            ev_state_known=not self.unknown_return,
            ev_observed_at=at if not self.unknown_return else old.ev_observed_at or old.at,
        )
        return self.observation
