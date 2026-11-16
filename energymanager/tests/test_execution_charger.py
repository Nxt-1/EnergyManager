"""Actual go-e sequencing with synthetic counters, delayed acknowledgements and adoption."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.control import FastControl
from energymanager.domain import Goal, Interval, Snapshot, time_grid
from energymanager.ev_progress import EVProgress
from energymanager.execution import freeze_execution
from energymanager.live_inputs import Reading
from energymanager.planner import Planner
from energymanager.publication import admit
from energymanager.store import Store
from energymanager.validation import validate
from test_ev_progress import AT, C, P, sample
from test_goe import ChargerFixture


class DelayedPhaseFixture(ChargerFixture):
    def __init__(self, delay):
        self.delay = delay
        self.phase_updates = []
        super().__init__()

    async def service(self, domain, service, data):
        phase = data.get("entity_id") == self.actuators["phase"]
        if phase and self.delay:
            self.ignore.add(self.actuators["phase"])
        await super().service(domain, service, data)
        if phase and self.delay:
            self.ignore.remove(self.actuators["phase"])
            self.phase_updates.append((self.at + timedelta(seconds=self.delay), data["option"]))

    def refresh(self, seconds=5, *, heartbeat=True):
        for when, value in list(self.phase_updates):
            if when <= self.at + timedelta(seconds=seconds):
                self.set("phase", value)
                self.phase_updates.remove((when, value))
        super().refresh(seconds, heartbeat=heartbeat)


def required_three_phase():
    c = replace(C, phases=(3,))
    p = replace(P, planning_budget_seconds=5)
    points = time_grid(AT, 8 / 60)
    observation = replace(sample(), ess_kwh=c.ess_min_kwh, house_kw=.4, monthly_peak_kw=8)
    s = Snapshot("SYNTHETIC-required-phase", 1, observation, AT, "SYNTHETIC grid",
        tuple(Interval(a, b, .4, 0, 0) for a, b in zip(points, points[1:])),
        (Goal("g", "SYNTHETIC near deadline", points[-1], target_soc_percent=50),), c, p)
    return freeze_execution(s, None, {"phase": 1, "ready_at": AT.isoformat()})


@pytest.mark.parametrize("delay,missing,spike", [(0, False, False), (20, False, False),
                                               (0, True, False), (20, False, True)])
async def test_required_switch_through_adoption_keeps_pending_ack_and_live_protection(tmp_path, delay, missing, spike):
    s = required_three_phase()
    plan = Planner().plan(s)
    assert plan["valid"] and validate(s, plan["flows"], plan["service"]) == []
    fixture = DelayedPhaseFixture(delay)
    fixture.at = AT - timedelta(seconds=1)
    fixture.actuator.c = s.capabilities
    fixture.rows[fixture.actuators["ess_setpoint"]] = {"state": "0", "attributes": {}}
    if missing:
        fixture.ignore.add(fixture.actuators["phase"])
    store = Store(tmp_path / "synthetic-progress.sqlite")
    progress = EVProgress(store)
    control = FastControl(s.capabilities, s.policy)
    total = 100.0
    delivered = power = prefix = 0.0
    adopted = False
    maximum_target = max(plan["flows"]["ev_energy"])
    after_spike = []
    for second in range(600):
        fixture.refresh(1)
        at = fixture.at
        house = 10.0 if spike and second >= 80 else .4
        raw = replace(s.observation, at=at, house_kw=house, ev_power_kw=power,
                      ev_phases=1 if fixture.readings.code("phase") == 1 else 3,
                      quarter_import_kwh=prefix)
        reading = Reading.parse("sensor.synthetic_eto", {"state": str(total),
            "attributes": {"unit_of_measurement": "kWh"}}, at, "kWh", 30, nonnegative=True)
        o = progress.update(raw, reading, "sensor.synthetic_eto", s.capabilities, s.policy)
        if second == 75:
            charger = fixture.actuator.goe_control.planning_state(at, o)
            if delay or missing:
                assert charger["phase_committed"] and charger["phase"] == 3
            points = time_grid(at, (s.intervals[-1].end - at).total_seconds() / 3600)
            current = replace(s, observation=o, intervals=tuple(Interval(a, b, .4, 0, 0)
                              for a, b in zip(points, points[1:])), execution=None)
            current = freeze_execution(current, plan, charger)
            replacement = Planner().plan(current)
            assert replacement["valid"], replacement
            before = deepcopy(replacement["flows"])
            snapshot_digest = current.digest
            replacement, errors = admit(current, replacement, o, at, previous_plan=plan,
                                        previous_authority=(True, True, True))
            assert not errors and "execution_handover" in replacement
            assert replacement["flows"] == before and current.digest == snapshot_digest
            maximum_target = max(maximum_target, max(replacement["flows"]["ev_energy"]))
            plan = replacement
            adopted = True
        command = control.tick(o, at, plan, 2 if adopted else 1)
        await fixture.actuator.apply(command, 2 if adopted else 1, o)
        phase = 1 if int(fixture.rows[fixture.actuators["phase"]]["state"]) == 1 else 3
        amps = int(fixture.rows[fixture.actuators["current"]]["state"])
        power = phase * amps * .23 if fixture.rows[fixture.actuators["force"]]["state"] == "2" else 0.0
        total += power / 3600
        delivered += power * s.capabilities.ev_efficiency / 3600
        prefix += (house + power) / 3600
        if spike and second >= 85:
            after_spike.append(command.current_a)
    phase_requests = [call[2]["option"] for call in fixture.calls
                      if call[2].get("entity_id") == fixture.actuators["phase"]]
    assert adopted and phase_requests == ["2"]
    if missing:
        assert delivered == 0 and fixture.actuator.delivery_fault
    elif spike:
        assert after_spike and not any(after_spike)
        assert not fixture.incidents
        assert control.peak_evidence["unavoidable_kwh"] > 0
    else:
        assert delivered >= .468 - .003  # Counter feedback and the one-second control endpoint.
        assert delivered <= maximum_target - s.observation.ev_kwh + .003
        assert power == 0 and not fixture.incidents
    store.close()


async def test_solar_phase_preparation_does_not_purchase_grid_or_bypass_progress():
    from energymanager.optimization import JointModel
    from test_publication_closed_loop import result_for
    s = required_three_phase()
    s = replace(s, intervals=tuple(replace(i, pv_ac_kw=5) for i in s.intervals),
                capabilities=replace(s.capabilities, maximum_current_a=6),
                goals=(replace(s.goals[0], target_soc_percent=49.5),))
    # An independently audited solar-only instruction, followed by actual PV loss.
    model = JointModel(s)
    for index in model.linear.variables["grid_ev"]:
        model.linear.upper[index] = 0
    result = model.run(5)
    assert result["feasible"], result
    plan = {**result_for(s, result["flows"]), "execution": s.execution}
    assert validate(s, plan["flows"], plan["service"]) == []
    assert sum(plan["flows"]["grid_ev"]) < 1e-5
    first = next(t for t, on in enumerate(plan["flows"]["three"]) if on > .5)
    at = s.intervals[first].start
    control = FastControl(s.capabilities, s.policy)
    fixture = ChargerFixture()
    fixture.at = at - timedelta(seconds=1)
    fixture.actuator.c = s.capabilities
    for second in range(60):
        fixture.refresh(1)
        raw = replace(s.observation, at=fixture.at, pv_ac_kw=0, ev_phases=1
                      if fixture.readings.code("phase") == 1 else 3)
        command = control.tick(raw, fixture.at, plan, 1)
        assert command.current_a == 0 and command.prepare_phase
        await fixture.actuator.apply(command, 1, raw)
    assert fixture.rows[fixture.actuators["force"]]["state"] == "1"
    assert not any(data.get("entity_id") == fixture.actuators["force"] and data.get("option") == "2"
                   for _, _, data in fixture.calls)
    unavailable = replace(raw, ev_progress={"usable": False})
    command = control.tick(unavailable, fixture.at, plan, 1)
    assert command.current_a == 0 and not command.prepare_phase
    command = control.tick(raw, fixture.at, plan, 1, ev_valid=False)
    assert command.current_a == 0 and not command.prepare_phase


async def test_one_accepted_plan_drives_a_complete_live_ramp_on_control_and_readback_events():
    from energymanager.optimization import JointModel
    from test_first_slice import tiny
    from test_publication_closed_loop import result_for

    s = tiny(hours=1 / 6)
    s = replace(s, observation=replace(s.observation, ev_power_kw=3.68, monthly_peak_kw=8),
                goals=(Goal("g", "SYNTHETIC fixed-plan ramp", s.intervals[-1].end, target_soc_percent=40.3),))
    s = freeze_execution(s, None, {"phase": 1, "current_a": 16, "ready_at": s.observation.at.isoformat()})
    model = JointModel(s)
    for t in range(len(s.intervals)):
        for name, value in (("amps_one", 16 if t == 0 else 6), ("amps_three", 0)):
            index = model.linear.variables[name][t]
            model.linear.lower[index] = model.linear.upper[index] = value
    result = model.run(5)
    assert result["feasible"], result
    accepted = result_for(s, result["flows"])
    fixture = ChargerFixture()
    fixture.at = s.observation.at - timedelta(seconds=1)
    fixture.set("force", 2)
    fixture.set("current", 16)
    fixture.set("charger_status", 3)
    controller = FastControl(s.capabilities, s.policy)
    original = fixture.service
    reductions = []

    async def traced(domain, service, data):
        if data["entity_id"] == fixture.actuators["current"]:
            reductions.append((fixture.at, data["value"]))
        await original(domain, service, data)

    fixture.service = traced
    stock = s.observation.ev_kwh
    for second in range(120):
        fixture.at += timedelta(seconds=1)
        fixture.set("heartbeat", second + 6)
        fixture.readings.update(deepcopy(fixture.rows), fixture.at)
        power = int(fixture.rows[fixture.actuators["current"]]["state"]) * .23
        observation = replace(s.observation, at=fixture.at, ev_kwh=stock, ev_power_kw=power)
        command = controller.tick(observation, fixture.at, accepted, 1)
        await fixture.actuator.apply(command, 1, observation)
        stock += power / 3600 * s.capabilities.ev_efficiency
    assert [amps for _, amps in reductions] == list(range(15, 5, -1))
    assert all((b[0] - a[0]).total_seconds() >= 5 for a, b in zip(reductions, reductions[1:]))
    assert not any(c[2]["entity_id"] == fixture.actuators["force"] for c in fixture.calls)
    assert not fixture.incidents
    assert sum(c[2]["entity_id"] == fixture.actuators["ess_setpoint"] for c in fixture.calls) == 120
