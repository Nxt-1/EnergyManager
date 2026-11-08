"""Deterministic local EV/ESS response and P1 fixtures, never installation evidence."""

from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.control import FastControl
from energymanager.domain import Goal
from test_first_slice import tiny
from test_publication_closed_loop import result_for, scheduled_flows


def example(power=2.3, house=.5):
    s = tiny(hours=1, house=house, automatic_peak_kw=3.5)
    s = replace(s, observation=replace(s.observation, monthly_peak_kw=3.5),
                goals=(Goal("goal", "SYNTHETIC target", s.intervals[-1].end, 48),))
    return s, result_for(s, scheduled_flows(s, [power] * len(s.intervals)))


def test_soc_lead_does_not_stop_active_task_and_later_goal_does_not_extend_it():
    s, plan = example()
    control = FastControl(s.capabilities, s.policy)
    # A one-point SoC jump puts the meter ahead of this slot, below this task's endpoint.
    o = replace(s.observation, ev_kwh=24.6, ev_power_kw=2.3)
    assert o.ev_kwh > plan["flows"]["ev_energy"][1]
    command = control.tick(o, o.at, plan, 1)
    assert command.current_a == 10
    task_target = plan["flows"]["ev_energy"][-1]
    plan["goals"][0]["target_kwh"] = 60  # Later/unrelated demand cannot extend the accepted session.
    done = control.tick(replace(o, at=o.at + timedelta(seconds=1), ev_kwh=task_target),
                        o.at + timedelta(seconds=1), plan, 1)
    assert done.current_a == 0 and "target reached" in done.reason
    revoked = control.tick(o, o.at + timedelta(seconds=2), plan, 1, ev_valid=False)
    assert revoked.current_a == 0


def test_live_source_loss_and_unknown_state_remain_authoritative():
    s, plan = example()
    plan["flows"]["pv_ev"] = plan["flows"]["grid_ev"]
    plan["flows"]["grid_ev"] = [0.0] * len(s.intervals)
    control = FastControl(s.capabilities, s.policy)
    o = replace(s.observation, pv_ac_kw=4)
    assert control.tick(o, o.at, plan, 1).current_a > 0
    assert control.tick(replace(o, pv_ac_kw=0), o.at, plan, 1).current_a == 0
    assert control.tick(replace(o, ev_state_known=False), o.at, plan, 1).current_a == 0


@pytest.mark.parametrize("latency,meter_delay", [(0, 0), (3, 5), (12, 10)])
def test_exact_quarter_with_sustained_load_and_delayed_fake_reduction(latency, meter_delay):
    s, plan = example(house=.4)
    control = FastControl(s.capabilities, s.policy)
    energy = [0.0]
    actual_ev = 0.0
    requested_ev = None
    pending = []
    for second in range(900):
        at = s.observation.at + timedelta(seconds=second)
        while pending and pending[0][0] <= second:
            actual_ev = pending.pop(0)[1]
        house = .4 if second < 120 else 3.5
        o = replace(s.observation, at=at, house_kw=house, ev_power_kw=actual_ev,
                    quarter_import_kwh=energy[max(0, second - meter_delay)])
        command = control.tick(o, at, plan, 1)
        if command.ev_kw != requested_ev:
            pending.append((second + latency, command.ev_kw))
            requested_ev = command.ev_kw
        if latency == 0:
            actual_ev = command.ev_kw
        energy.append(energy[-1] + (house + actual_ev) / 3600)
    assert energy[-1] * 4 <= 3.5 + 1e-6
    assert requested_ev == 0


def test_current_quarter_can_use_a_later_peak_reserve_after_ev_curtailment():
    s, plan = example()
    plan["reservations"] = [dict(solar_house_kwh=5, solar_ev_kwh=0, grid_house_kwh=0)] * (len(s.intervals) + 1)
    at = s.observation.at + timedelta(minutes=14)
    o = replace(s.observation, at=at, house_kw=4.5, ess_kwh=7.8, quarter_import_kwh=.82)
    control = FastControl(s.capabilities, s.policy)
    command = control.tick(o, at, plan, 1)
    assert command.current_a == 0
    assert command.ess_kw > 0  # The ordinary reservation floor would prohibit this discharge.
    assert command.ess_kw <= s.capabilities.ac_discharge_kw
    assert control.peak_evidence["unavoidable_kwh"] == 0


def test_unavoidable_household_excess_is_explicit_and_quarter_reset_releases_old_prefix():
    s, plan = example()
    at = s.observation.at + timedelta(minutes=14)
    o = replace(s.observation, at=at, house_kw=8, quarter_import_kwh=.86)
    control = FastControl(s.capabilities, s.policy)
    command = control.tick(o, at, plan, 1)
    assert command.current_a == 0 and command.ess_kw == 0
    assert control.peak_evidence["unavoidable_kwh"] > 0
    later = at + timedelta(minutes=1)
    o = replace(o, at=later, house_kw=.5, quarter_import_kwh=0)
    assert control.tick(o, later, plan, 1).current_a == 10
    assert control.peak_evidence["prefix_kwh"] == 0


def test_frozen_stop_restart_review_preserves_required_energy_and_checked_timeout_fallback():
    from time import monotonic
    from energymanager.optimization import JointModel
    from energymanager.planner import Planner
    from energymanager.validation import validate

    s, _ = example()
    rates = [2.3, 2.3, 0, 2.3] + [0.0] * (len(s.intervals) - 4)
    target = s.observation.ev_kwh + sum(rates[t] * i.hours * s.capabilities.ev_efficiency
                                       for t, i in enumerate(s.intervals))
    s = replace(s, observation=replace(s.observation, ev_power_kw=2.3),
                goals=(replace(s.goals[0], target_soc_percent=target / s.capabilities.ev_capacity_kwh * 100),))
    from copy import deepcopy
    model = JointModel(s)
    fixed = deepcopy(model)
    for t, rate in enumerate(rates):
        for name, value in (("amps_one", rate / .23), ("amps_three", 0)):
            index = fixed.linear.variables[name][t]
            fixed.linear.lower[index] = fixed.linear.upper[index] = value
    solved = fixed.run(2)
    assert solved["feasible"]
    flows = solved["flows"]
    values = model.warm_from(flows)
    assert model.linear.accepts(values) and validate(s, flows) == []
    result = {"flows": flows, "values": values, "status": "SYNTHETIC", "feasible": True}
    planner = Planner()
    planner.started = monotonic()
    planner.deadline = planner.started + 8
    selected, review = planner.review_active_continuation(model, result,
        model.value(model.economic, values), model.value(model.cash, values))
    assert review["state"] == "continued", review
    assert all(selected["flows"]["one"][t] > .5 for t in range(4))
    assert selected["flows"]["ev_energy"][4] == pytest.approx(flows["ev_energy"][4])
    assert validate(s, selected["flows"]) == []
    planner.deadline = monotonic()
    retained, review = planner.review_active_continuation(model, result,
        model.value(model.economic, values), model.value(model.cash, values))
    assert retained is result and review["state"] == "unverified"


def test_measured_dc_can_cover_current_quarter_instead_of_a_future_store_allocation():
    s, plan = example()
    plan["flows"]["dc_store"] = [2.0] * len(s.intervals)
    at = s.observation.at + timedelta(minutes=14)
    o = replace(s.observation, at=at, house_kw=4.5, pv_dc_kw=2, quarter_import_kwh=.82)
    control = FastControl(s.capabilities, s.policy)
    command = control.tick(o, at, plan, 1)
    assert command.current_a == 0 and command.ess_kw > 0
    assert control.peak_evidence["unavoidable_kwh"] == 0


def test_curtailable_grid_precharge_is_not_labelled_unavoidable_household_demand():
    s, plan = example()
    plan["flows"]["grid_store"] = [3.5] * len(s.intervals)
    at = s.observation.at + timedelta(minutes=14)
    control = FastControl(s.capabilities, s.policy)
    command = control.tick(replace(s.observation, at=at, quarter_import_kwh=.82), at, plan, 1)
    assert command.current_a == 0
    assert control.peak_evidence["unavoidable_kwh"] == 0


async def test_real_full_recalculation_keeps_the_running_command_with_a_soc_lead(tmp_path):
    import asyncio
    from time import monotonic
    from energymanager.service import Application
    from energymanager.store import Store

    s, plan = example()
    target = plan["flows"]["ev_energy"][-1]
    s = replace(s, goals=(replace(s.goals[0], target_soc_percent=target / s.capabilities.ev_capacity_kwh * 100),),
                policy=replace(s.policy, planning_budget_seconds=4, daily_soc_percent=0),
                observation=replace(s.observation, ev_kwh=24.6, ev_power_kw=2.3))
    store = Store(tmp_path / "synthetic-recalculation.sqlite")
    app = Application(store, snapshot=s, demo=False)
    origin = monotonic()
    app.now = lambda: s.observation.at + timedelta(seconds=monotonic() - origin)
    app.accepted = plan
    app.ev_valid = app.ess_valid = app.conditional_valid = True
    try:
        await app.start()
        async with asyncio.timeout(15):
            while not app.accepted or app.accepted["id"] == plan["id"]:
                if app.current_command is not None:
                    assert app.current_command.current_a == 10
                await asyncio.sleep(.05)
        before_replacement = [event["body"] for event in store.events(1000)
                              if event["kind"] == "commanded_dry_run" and event["body"]["plan_id"] == plan["id"]]
        assert before_replacement and all(row["current_a"] == 10 for row in before_replacement)
        assert app.accepted["input_digest"]
    finally:
        await app.close()
        store.close()


def test_stop_prepares_for_a_known_next_quarter_load_increase_without_blocking_safe_pulses():
    from energymanager.domain import instant

    s, plan = example(house=.5)
    boundary = s.observation.at + timedelta(minutes=15)
    for interval in plan["intervals"]:
        if instant(interval["start"]) >= boundary:
            interval["house_kw"] = 3.5
    at = boundary - timedelta(seconds=20)
    o = replace(s.observation, at=at, ev_power_kw=2.3, quarter_import_kwh=.6)
    command = FastControl(s.capabilities, s.policy).tick(o, at, plan, 1)
    assert command.current_a == 0
    for interval in plan["intervals"]:
        interval["house_kw"] = .5
    permitted = FastControl(s.capabilities, s.policy).tick(o, at, plan, 1)
    assert permitted.current_a == 10


def test_useful_pv_can_justify_a_near_term_interruption_without_lending_grid_authority():
    from time import monotonic
    from energymanager.optimization import JointModel
    from energymanager.planner import Planner
    from energymanager.validation import validate

    s, _ = example(house=0)
    rates = [2.3 if timedelta(minutes=5) <= i.start - s.observation.at < timedelta(minutes=20) else 0.0
             for i in s.intervals]
    target = s.observation.ev_kwh + sum(rate * i.hours * s.capabilities.ev_efficiency
                                       for rate, i in zip(rates, s.intervals))
    s = replace(s, observation=replace(s.observation, ev_power_kw=2.3, ev_phases=1,
                                      ess_kwh=s.capabilities.ess_min_kwh, ess_grid_kwh=0),
                intervals=tuple(replace(i, pv_ac_kw=rate, pv_dc_kw=0) for i, rate in zip(s.intervals, rates)),
                goals=(replace(s.goals[0], target_soc_percent=target / s.capabilities.ev_capacity_kwh * 100),))
    model = JointModel(s)
    from copy import deepcopy
    fixed = deepcopy(model)
    for t, rate in enumerate(rates):
        for name, value in (("amps_one", rate / .23), ("amps_three", 0)):
            index = fixed.linear.variables[name][t]
            fixed.linear.lower[index] = fixed.linear.upper[index] = value
    solved = fixed.run(2)
    assert solved["feasible"] and validate(s, solved["flows"]) == []
    assert solved["flows"]["grid_cumulative"][-1] == pytest.approx(0, abs=1e-6)
    result = {**solved, "values": model.warm_from(solved["flows"])}
    planner = Planner()
    planner.started = monotonic()
    planner.deadline = planner.started + 4
    selected, review = planner.review_active_continuation(model, result,
        model.value(model.economic, result["values"]), model.value(model.cash, result["values"]))
    assert selected is result and review["state"] == "infeasible", review
    assert review["stop"] == s.intervals[0].start.isoformat()
