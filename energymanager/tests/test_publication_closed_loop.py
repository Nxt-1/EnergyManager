"""Frozen-plan admission and adaptive execution with deterministic synthetic measurements."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.control import FastControl
from energymanager.demo_plant import DemoPlant
from energymanager.domain import Goal, json_data
from energymanager.planner import Planner
from energymanager.publication import admit
from energymanager.reservations import reservations
from energymanager.service import Application
from energymanager.store import Store
from energymanager.validation import accounting, validate
from test_first_slice import tiny


def scheduled_flows(snapshot, grid_rates):
    names = (
        "pv_ev",
        "pv_house",
        "pv_store",
        "export",
        "curtail",
        "grid_ev",
        "grid_house",
        "grid_store",
        "solar_dis_ev",
        "solar_dis_house",
        "grid_dis_house",
        "dc_store",
        "dc_invert",
        "one",
        "three",
        "amps_one",
        "amps_three",
    )
    n = len(snapshot.intervals)
    flows = {name: [0.0] * n for name in names}
    flows["grid_ev"] = list(grid_rates)
    flows["grid_house"] = [i.house_kw for i in snapshot.intervals]
    flows["export"] = [i.pv_ac_kw for i in snapshot.intervals]
    flows["ev_energy"] = [snapshot.observation.ev_kwh]
    flows["ess_grid"] = [snapshot.observation.ess_grid_kwh] * (n + 1)
    flows["ess_solar"] = [
        snapshot.observation.ess_kwh - snapshot.capabilities.ess_min_kwh - snapshot.observation.ess_grid_kwh
    ] * (n + 1)
    for t, interval in enumerate(snapshot.intervals):
        if grid_rates[t]:
            flows["one"][t] = 1.0
            flows["amps_one"][t] = grid_rates[t] * 1000 / snapshot.capabilities.voltage
        flows["ev_energy"].append(
            flows["ev_energy"][-1]
            + grid_rates[t] * interval.hours * snapshot.capabilities.ev_efficiency
            - interval.withdrawal_kwh
        )
    return flows


def result_for(snapshot, flows):
    goals = [
        {
            **json_data(g),
            "target_kwh": g.target(snapshot.capabilities, snapshot.policy),
            "shortfall_kwh": 0.0,
            "planned_kwh": flows["ev_energy"][snapshot.checkpoint_index(g.deadline)],
            "status": "scheduled",
        }
        for g in snapshot.goals
    ]
    return {
        "id": "synthetic-plan",
        "snapshot_id": snapshot.id,
        "revision": snapshot.revision,
        "valid": True,
        "status": "SYNTHETIC",
        "service": {},
        "flows": flows,
        "intervals": json_data(snapshot.intervals),
        "summary": accounting(snapshot, flows),
        "goals": goals,
        "sessions": [],
        "reasons": [],
        "conditional_tasks": [],
        "reservations": reservations(snapshot, flows),
        "forecast_at": snapshot.forecast_at.isoformat(),
    }


def frozen_fixture():
    s = tiny(ev=24, ess=5, house=0.4)
    intervals = tuple(
        replace(
            s.intervals[-1],
            start=s.observation.at + timedelta(minutes=t),
            end=s.observation.at + timedelta(minutes=t + 5),
        )
        for t in range(0, 60, 5)
    )
    s = replace(
        s,
        intervals=intervals,
        observation=replace(s.observation, monthly_peak_kw=4.5),
        goals=(Goal("goal", "SYNTHETIC readiness", intervals[-1].end, 41),),
    )
    rates = [3.68] * 2 + [0.0] * (len(intervals) - 2)
    # One extra integer-amp slice supplies the remaining required energy.
    rates[2] = 1.38
    flows = scheduled_flows(s, rates)
    assert not validate(s, flows)
    result = result_for(s, flows)
    result["reference_flows"] = deepcopy(flows)
    return s, result


@pytest.mark.parametrize("ev_change,ess_change", [(0.0, 0.0), (0.234, 0.2), (-0.7, -1.0), (1.0, -0.1)])
def test_admission_keeps_frozen_plan_and_records_changed_measurements_separately(ev_change, ess_change):
    s, result = frozen_fixture()
    original = deepcopy(result)
    at = s.observation.at + timedelta(minutes=2)
    observation = replace(
        s.observation,
        at=at,
        ev_kwh=s.observation.ev_kwh + ev_change,
        ess_kwh=s.observation.ess_kwh + ess_change,
        quarter_import_kwh=1.1,
    )
    admitted, errors = admit(s, result, observation, at)
    assert not errors, errors
    assert result == original
    for key, value in original.items():
        assert admitted[key] == value
    assert admitted["admission"]["observation"] == json_data(observation)
    assert admitted["admission"]["input_digest"] == s.digest
    assert admitted["admission"]["passed"]
    assert "publication_repair" not in admitted and "adoption_snapshot" not in admitted
    assert not validate(s, admitted["flows"])


def test_admission_skips_elapsed_instructions_without_slicing_or_repeating_a_withdrawal():
    s, result = frozen_fixture()
    at = s.observation.at + timedelta(minutes=20)
    observation = replace(s.observation, at=at)
    admitted, errors = admit(s, result, observation, at)
    assert not errors
    assert admitted["admission"]["first_interval"] == 4
    assert admitted["intervals"] == result["intervals"]
    assert FastControl(s.capabilities, s.policy).tick(observation, at, admitted, 1).ev_kw == 0
    trip = Goal(
        "trip",
        "SYNTHETIC elapsed trip",
        s.intervals[2].start,
        kind="trip",
        distance_km=10,
        return_at=s.intervals[6].start,
    )
    intervals = list(s.intervals)
    intervals[2] = replace(intervals[2], withdrawal_kwh=trip.withdrawal(s.policy))
    s = replace(s, intervals=tuple(intervals), goals=(trip,))
    flows = scheduled_flows(s, [0.0] * len(intervals))
    result = result_for(s, flows)
    at = s.observation.at + timedelta(minutes=35)
    observation = replace(s.observation, at=at, ev_kwh=24 - trip.withdrawal(s.policy))
    admitted, errors = admit(s, result, observation, at)
    assert not errors
    assert admitted["intervals"] == result["intervals"]
    plant = DemoPlant(s)
    plant.observation = observation
    assert plant.step(at + timedelta(minutes=1), None).ev_kwh == observation.ev_kwh


@pytest.mark.parametrize("bad_reference", [False, True])
def test_frozen_physical_and_reference_validation_are_still_mandatory(bad_reference):
    s, result = frozen_fixture()
    flows = result["reference_flows"] if bad_reference else result["flows"]
    flows["grid_house"][3] += 1
    admitted, errors = admit(s, result, s.observation, s.observation.at)
    assert errors and any("House conservation" in e for e in errors)
    assert not admitted["admission"]["passed"]
    assert admitted["flows"] == result["flows"]


def test_frozen_optional_economics_are_still_audited():
    s = tiny(pv=2, house=0, ess=2.8, ev_value_eur_kwh=0)
    reference = scheduled_flows(s, [0.0] * len(s.intervals))
    flows = deepcopy(reference)
    for t, i in enumerate(s.intervals):
        flows["pv_ev"][t] = 1.38
        flows["export"][t] -= 1.38
        flows["one"][t] = 1
        flows["amps_one"][t] = 6
        flows["ev_energy"][t + 1] = flows["ev_energy"][t] + 1.38 * i.hours * s.capabilities.ev_efficiency
    assert not validate(s, flows) and not validate(s, reference)
    result = result_for(s, flows)
    result["reference_flows"] = reference
    _, errors = admit(s, result, s.observation, s.observation.at)
    assert any("24-hour combined comparison worsens" in e for e in errors)


@pytest.mark.parametrize(
    "problem",
    [
        "stale",
        "unknown",
        "settling",
        "future_read",
        "connection",
        "ev_availability",
        "capacity",
        "provenance",
        "elapsed",
        "early_clock",
        "forecast_age",
    ],
)
def test_real_admission_failures_remain_blocking(problem):
    s, result = frozen_fixture()
    at = s.observation.at + timedelta(minutes=2)
    observation = replace(s.observation, at=at)
    if problem == "stale":
        observation = replace(observation, at=at - timedelta(minutes=1))
    elif problem in ("unknown", "settling"):
        observation = replace(observation, quality=problem)
    elif problem == "future_read":
        observation = replace(observation, at=at + timedelta(seconds=1))
    elif problem == "connection":
        observation = replace(observation, connected=False)
    elif problem == "ev_availability":
        observation = replace(observation, ev_state_known=False)
    elif problem == "capacity":
        observation = replace(observation, ev_kwh=61)
    elif problem == "provenance":
        observation = replace(observation, ess_grid_kwh=4)
    elif problem == "elapsed":
        at = s.intervals[-1].end
    elif problem == "early_clock":
        at = s.intervals[0].start - timedelta(seconds=1)
    else:
        s = replace(s, forecast_at=s.forecast_at - timedelta(hours=3))
    admitted, errors = admit(s, result, observation, at)
    assert errors and not admitted["admission"]["passed"]


def test_unknown_ev_state_does_not_disable_a_valid_ess_schedule():
    s = tiny(ess=5, house=1)
    s = replace(
        s,
        observation=replace(s.observation, ev_state_known=False),
        intervals=tuple(replace(i, ev_state_known=False, available=False) for i in s.intervals),
    )
    result = result_for(s, scheduled_flows(s, [0.0] * len(s.intervals)))
    admitted, errors = admit(s, result, s.observation, s.observation.at)
    assert not errors
    command = FastControl(s.capabilities, s.policy).tick(s.observation, s.observation.at, admitted, 1)
    assert command.ev_kw == 0 and command.ess_kw > 0


def test_one_frozen_plan_keeps_live_ess_balancing_and_ev_peak_modulation():
    s, result = frozen_fixture()
    rates = [0.0] * len(s.intervals)
    rates[2] = 3.68
    target = 24 + 3.68 * s.intervals[2].hours * s.capabilities.ev_efficiency
    s = replace(
        s, goals=(replace(s.goals[0], target_soc_percent=target / s.capabilities.ev_capacity_kwh * 100),)
    )
    result = result_for(s, scheduled_flows(s, rates))
    assert not validate(s, result["flows"])
    at = s.observation.at + timedelta(minutes=15, seconds=-1)
    observation = replace(
        s.observation, at=at, ev_power_kw=3.68, ev_kwh=target - 0.01, quarter_import_kwh=1.1234
    )
    admitted, errors = admit(s, result, observation, at)
    assert not errors
    original = deepcopy(admitted)
    commands = []
    for house, pv in ((0.4, 0), (8, 0), (0.4, 8)):
        o = replace(observation, house_kw=house, pv_ac_kw=pv)
        commands.append(FastControl(s.capabilities, s.policy).tick(o, at, admitted, 1))
    baseline, loaded, sunny = commands
    assert baseline.ev_kw == pytest.approx(3.68)
    assert loaded.ev_kw < baseline.ev_kw and loaded.ess_kw > 0
    assert sunny.ess_kw < 0 and sunny.ev_kw > 0
    assert all(not c.replan for c in commands)
    assert admitted == original
    assert observation.quarter_import_kwh + (8 - loaded.ess_kw + loaded.ev_kw) / 3600 <= 4.5 * 0.25 + 1e-8


@pytest.mark.parametrize("ev_change", [0.0, 0.234, -0.7])
async def test_measurement_drift_during_a_solve_does_not_cancel_or_reject_it(
    tmp_path, monkeypatch, ev_change
):
    s, result = frozen_fixture()
    app = Application(Store(tmp_path / "synthetic.sqlite"), snapshot=s, policy=s.policy, demo=False)
    at = s.observation.at + timedelta(minutes=2)
    app.now = lambda: at
    monkeypatch.setattr(app, "build_snapshot", lambda: s)
    running, release = asyncio.Event(), asyncio.Event()

    async def calculate(snapshot, request_id):
        running.set()
        await release.wait()
        return deepcopy(result)

    async def accepted():
        app.shutdown = True

    monkeypatch.setattr(app, "calculate_plan", calculate)
    monkeypatch.setattr(app, "notify_permission_issues", accepted)
    app.requested.set()
    loop = asyncio.create_task(app.planning_loop())
    try:
        await asyncio.wait_for(running.wait(), 2)
        app.observe(replace(s.observation, at=at, ev_kwh=24 + ev_change, ess_kwh=4, house_kw=8))
        assert not app.requested.is_set() and app.revision == s.revision
        release.set()
        await asyncio.wait_for(loop, 3)
        assert app.status == "ready" and app.accepted["flows"] == result["flows"]
        assert app.ev_valid and app.ess_valid and app.conditional_valid
        assert {row["disposition"] for row in app.store.decisions()} == {"accepted"}
    finally:
        app.shutdown = True
        loop.cancel()
        await asyncio.gather(loop, return_exceptions=True)
        app.store.close()


def test_real_plan_and_fast_control_complete_required_goal_in_closed_loop():
    s = tiny(hours=1, ev=24, house=0.4, planning_budget_seconds=6)
    s = replace(s, goals=(Goal("goal", "SYNTHETIC readiness", s.intervals[-1].end, 42),))
    result = Planner().plan(s)
    assert result["valid"]
    plant, control, command = DemoPlant(s), FastControl(s.capabilities, s.policy), None
    for second in range(0, 3601, 5):
        at = s.observation.at + timedelta(seconds=second)
        observed = plant.step(at, command)
        command = control.tick(observed, at, result, 1)
    assert plant.observation.ev_kwh >= 25.19
    assert plant.observation.monthly_peak_kw <= 4.0001


async def test_periodic_calculation_still_uses_fresh_forecast_and_measurements(tmp_path, monkeypatch):
    s = tiny(hours=169, ev=50, ess=5)
    app = Application(Store(tmp_path / "synthetic-periodic.sqlite"), snapshot=s, policy=s.policy, demo=False)
    app.now = lambda: s.observation.at
    updated = tuple(replace(i, house_kw=1.4) for i in s.intervals)
    app.forecast_data = {
        "issued_at": s.forecast_at.isoformat(),
        "revision": "synthetic-new-forecast",
        "provenance": "SYNTHETIC",
        "intervals": json_data(updated),
    }
    app.observation = replace(s.observation, ev_kwh=50.234)
    real_wait_for = asyncio.wait_for
    periodic_waits = []

    async def wait_for(awaitable, timeout):
        if timeout == 300:
            periodic_waits.append(timeout)
            awaitable.close()
            raise TimeoutError
        return await real_wait_for(awaitable, timeout)

    snapshots = []

    async def calculate(snapshot, request_id):
        snapshots.append(snapshot)
        return result_for(snapshot, scheduled_flows(snapshot, [0.0] * len(snapshot.intervals)))

    async def accepted():
        app.shutdown = True

    monkeypatch.setattr(asyncio, "wait_for", wait_for)
    monkeypatch.setattr(app, "calculate_plan", calculate)
    monkeypatch.setattr(app, "notify_permission_issues", accepted)
    try:
        await real_wait_for(app.planning_loop(), 5)
        assert periodic_waits == [300]
        assert app.planning_activity["reason"] == "periodic" and app.status == "ready"
        assert snapshots[0].forecast_id == "synthetic-new-forecast"
        assert snapshots[0].observation.ev_kwh == 50.234
        assert snapshots[0].intervals[0].house_kw == 1.4
    finally:
        app.store.close()


def test_reported_0234_kwh_increase_does_not_reject_the_original_grid_purchase():
    s = tiny(hours=4, ev=14.976, ess=5)
    intervals = tuple(
        replace(
            s.intervals[-1],
            start=s.observation.at + timedelta(minutes=t),
            end=s.observation.at + timedelta(minutes=t + 5),
        )
        for t in range(0, 240, 5)
    )
    s = replace(
        s,
        capabilities=replace(s.capabilities, ev_capacity_kwh=46.8),
        intervals=intervals,
        observation=replace(s.observation, monthly_peak_kw=5.49),
        goals=(Goal("morning", "SYNTHETIC supplied-error reproduction", intervals[-1].end, 50),),
    )
    rates = [0.0] + [3.68] * 30 + [2.07] + [0.0] * 16
    result = result_for(s, scheduled_flows(s, rates))
    assert not validate(s, result["flows"])
    grid = sum(rate * i.hours * s.capabilities.ev_efficiency for rate, i in zip(rates, intervals))
    assert grid == pytest.approx(8.43525)
    at = s.observation.at + timedelta(minutes=2)
    observed = replace(s.observation, at=at, ev_kwh=15.21)
    assert 23.4 - observed.ev_kwh == pytest.approx(8.19)
    assert grid - (23.4 - observed.ev_kwh) - 0.1035 == pytest.approx(0.14175)
    admitted, errors = admit(s, result, observed, at)
    assert not errors
    assert admitted["flows"] == result["flows"] and admitted["summary"] == result["summary"]
    assert admitted["admission"]["observation"]["ev_kwh"] == 15.21


def test_lost_solar_keeps_the_plan_but_live_control_still_blocks_optional_grid_purchase():
    s = tiny(pv=2, house=0, ess=2.8)
    reference = scheduled_flows(s, [0.0] * len(s.intervals))
    flows = deepcopy(reference)
    for t, i in enumerate(s.intervals):
        flows["pv_ev"][t] = 1.38
        flows["export"][t] -= 1.38
        flows["one"][t] = 1
        flows["amps_one"][t] = 6
        flows["ev_energy"][t + 1] = flows["ev_energy"][t] + 1.38 * i.hours * s.capabilities.ev_efficiency
    result = result_for(s, flows)
    result["reference_flows"] = reference
    observed = replace(s.observation, ev_power_kw=1.38, pv_ac_kw=0)
    admitted, errors = admit(s, result, observed, s.observation.at)
    assert not errors
    with_pv = FastControl(s.capabilities, s.policy).tick(
        replace(observed, pv_ac_kw=2), observed.at, admitted, 1
    )
    without_pv = FastControl(s.capabilities, s.policy).tick(observed, observed.at, admitted, 1)
    assert with_pv.ev_kw == 1.38 and without_pv.ev_kw == 0
    assert not without_pv.replan
    assert admitted["flows"] == result["flows"]
