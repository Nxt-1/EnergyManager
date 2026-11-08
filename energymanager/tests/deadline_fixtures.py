"""Labelled synthetic deadline cases; no installation data or network access."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from energymanager.domain import Capabilities, Goal, Interval, Observation, Policy, Snapshot, time_grid


def example(name: str) -> Snapshot:
    start = datetime(2026, 11, 7, 7, tzinfo=UTC)
    if name == "held_partial":
        start += timedelta(minutes=2, seconds=47)
    hours = 10 if name == "room_after_pv" else 7
    required = 8.0
    if name == "no_pv":
        hours = 4
    if name == "insufficient":
        hours, required = 4, 16.0
    if name == "held_partial":
        hours, required = 2, 1.17
    if name == "margin_only_shortfall":
        hours, required = 3, 14.5
    c = Capabilities(
        ev_capacity_kwh=46.8, phases=(1,), ac_charge_kw=0, ac_discharge_kw=0,
        dc_charge_kw=0, battery_charge_kw=0, battery_discharge_kw=0,
    )
    grid = time_grid(start, hours)
    if name == "margin_only_shortfall":
        c = replace(c, phases=(3,))
    intervals: list[Interval] = []
    for left, right in zip(grid, grid[1:]):
        hour = (left - start).total_seconds() / 3600
        solar = 0.5 + 5 / (3 * c.ev_efficiency) if 3 <= hour < 6 else 0.0
        if name in ("no_pv", "insufficient", "held_partial", "stored_solar"):
            solar = 0.0
        if name == "margin_only_shortfall":
            solar = 2.65
        away = name == "trip" and 4 <= hour < 5
        withdrawal = 2.0 if name == "trip" and abs(hour - 4) < 1e-8 else 0.0
        intervals.append(Interval(left, right, 0.5, solar, 0, available=not away, withdrawal_kwh=withdrawal))
    if name == "stored_solar":
        c = replace(c, ac_discharge_kw=2.5, battery_discharge_kw=4.0)
    initial = 20.0
    target = initial + required - sum(i.withdrawal_kwh for i in intervals)
    goals = [Goal("finish", "SYNTHETIC deadline", grid[-1], target / c.ev_capacity_kwh * 100)]
    if name == "trip":
        goals.append(Goal("before-trip", "SYNTHETIC pre-trip checkpoint", start + timedelta(hours=4),
                          24 / c.ev_capacity_kwh * 100))
    held = name == "held_partial"
    policy = Policy(planning_budget_seconds=120, automatic_peak_kw=3.5, completion_margin_minutes=0)
    observation = Observation(start, initial, c.ess_min_kwh + (2.0 if name == "stored_solar" else 0), True, 0.5, 0, 0,
                              monthly_peak_kw=3.5, ev_power_kw=2.07 if held else 0, ev_phases=min(c.phases))
    return Snapshot(
        "SYNTHETIC-deadline-" + name, 1, observation, start, "SYNTHETIC", tuple(intervals), tuple(goals),
        c, policy, hold_until=start + timedelta(seconds=135) if held else None,
        hold_ev_kw=2.07 if held else 0, hold_phases=1,
    )
