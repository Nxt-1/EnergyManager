from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.control import FastControl
from energymanager.demo_plant import DemoPlant
from energymanager.domain import Goal, json_data
from energymanager.optimization import JointModel
from energymanager.planner import Planner
from energymanager.publication import rebase
from energymanager.validation import accounting, validate
from test_first_slice import tiny


def test_elapsed_prefix_and_delivered_energy_are_not_repeated():
    s = tiny(hours=1, ev=24, house=0.4, planning_budget_seconds=5)
    hold = s.observation.at + timedelta(minutes=10)
    s = replace(s, hold_until=hold, goals=(Goal("manual", "Required goal", s.intervals[-1].end, 42),))
    result = Planner().plan(s)
    assert result["valid"], result
    assert sum(result["flows"]["grid_ev"][:2]) == pytest.approx(0)
    at = s.observation.at + timedelta(minutes=6)
    o = replace(s.observation, at=at, quarter_import_kwh=0.04)
    current, adopted, errors = rebase(s, result, o, at)
    assert not errors
    assert adopted["intervals"][0]["start"] == at.isoformat()
    assert adopted["flows"]["ev_energy"][0] == 24
    assert adopted["candidate_at_calculation"]["intervals"][0]["start"] == s.observation.at.isoformat()
    assert validate(current, adopted["flows"]) == []


def test_publication_reconciles_additional_measured_ess_headroom():
    s = tiny(hours=1, ev=50, ess=13, pv=4, dc=4, house=0, planning_budget_seconds=5)
    result = Planner().plan(s)
    at = s.observation.at + timedelta(minutes=1)
    o = replace(s.observation, at=at, ess_kwh=13.5)
    current, adopted, errors = rebase(s, result, o, at)
    assert not errors
    assert max(a + b for a, b in zip(adopted["flows"]["ess_solar"], adopted["flows"]["ess_grid"])) <= 11.20001
    assert validate(current, adopted["flows"]) == []


def test_real_plan_and_fast_control_complete_required_goal_in_closed_loop():
    s = tiny(hours=1, ev=24, house=0.4, planning_budget_seconds=6)
    s = replace(s, goals=(Goal("goal", "50 minute readiness", s.intervals[-1].end, 42),))
    result = Planner().plan(s)
    assert result["valid"]
    plant = DemoPlant(s)
    controller = FastControl(s.capabilities, s.policy)
    command = None
    for second in range(0, 3601, 5):
        at = s.observation.at + timedelta(seconds=second)
        o = plant.step(at, command)
        command = controller.tick(o, at, result, 1)
    assert plant.observation.ev_kwh >= 25.19
    assert plant.observation.monthly_peak_kw <= 4.0001
    assert plant.observation.quality == "SYNTHETIC"


def test_publication_releases_household_discharge_after_measured_balancing():
    s = tiny(hours=2, ev=50, ess=4, house=1, planning_budget_seconds=4)
    result = Planner().plan(s)
    assert result["valid"]
    at = s.observation.at + timedelta(minutes=2)
    o = replace(s.observation, at=at, ess_kwh=s.observation.ess_kwh - 0.04)
    current, adopted, errors = rebase(s, result, o, at)
    assert not errors, errors
    assert min(adopted["flows"]["ess_solar"]) >= -1e-8
    assert not validate(current, adopted["flows"])
    assert adopted["candidate_at_calculation"]["flows"] != adopted["flows"]


def test_lower_measured_ess_rejects_a_new_peak_and_keeps_reconciliation_evidence():
    s = tiny(hours=1, ev=24, ess=3, house=1)
    s = replace(s, observation=replace(s.observation, monthly_peak_kw=4.5),
                goals=(Goal("morning", "Synthetic morning", s.intervals[-1].end, 42),))
    model = JointModel(s)
    for index in model.linear.variables["solar_dis_ev"]:
        model.linear.upper[index] = 0
    for index in model.linear.variables["amps_one"][:4]:
        model.linear.lower[index] = model.linear.upper[index] = 16
    solved = model.run(2)
    assert solved["feasible"]
    assert not validate(s, solved["flows"])
    result = {**solved, "intervals": json_data(s.intervals), "goals": [], "sessions": [],
              "summary": accounting(s, solved["flows"])}
    current, rejected, errors = rebase(s, result, replace(s.observation, ess_kwh=2.81), s.observation.at)
    assert any("Unapproved EV peak" in error and "W allowance" in error for error in errors)
    assert "publication_candidate" in rejected
    assert rejected["flows"] == result["flows"]  # Original solver evidence is untouched.
    assert validate(current, rejected["publication_candidate"]["flows"])


def held_charging_fixture(*, reference=False, phase=3):
    """Deterministic synthetic schedule; no installation measurements or solver replay."""
    s = tiny(ev=24, house=.4)
    intervals = tuple(replace(s.intervals[-1], start=s.observation.at + timedelta(minutes=t),
                              end=s.observation.at + timedelta(minutes=t + 5)) for t in range(0, 60, 5))
    s = replace(s, intervals=intervals)
    s = replace(s, observation=replace(s.observation, ev_phases=phase, ev_power_kw=1.38 * phase),
                hold_until=s.intervals[0].end, hold_ev_kw=1.38 * phase, hold_phases=phase,
                goals=(Goal("morning", "SYNTHETIC morning", s.intervals[-1].end, 40 + phase / 3),))
    names = ("pv_ev", "pv_house", "pv_store", "export", "curtail", "grid_ev", "grid_house",
             "grid_store", "solar_dis_ev", "solar_dis_house", "grid_dis_house", "dc_store",
             "dc_invert", "one", "three", "amps_one", "amps_three")
    flows = {name: [0.] * len(s.intervals) for name in names}
    flows["grid_house"] = [.4] * len(s.intervals)
    flows["ev_energy"] = [24.]
    flows["ess_grid"] = [0.] * (len(s.intervals) + 1)
    flows["ess_solar"] = [0.] * (len(s.intervals) + 1)
    for t, interval in enumerate(s.intervals):
        if t < 2:
            flows["grid_ev"][t] = 1.38 * phase
            flows["three" if phase == 3 else "one"][t] = 1.
            flows["amps_three" if phase == 3 else "amps_one"][t] = 6.
        flows["ev_energy"].append(flows["ev_energy"][-1] + flows["grid_ev"][t] * interval.hours * .9)
    assert not validate(s, flows)
    result = {"flows": flows, "intervals": json_data(s.intervals), "service": {},
              "summary": accounting(s, flows),
              "goals": [{**json_data(s.goals[0]), "target_kwh": 24 + .2 * phase}],
              "sessions": [{"resource": "ev", "start": s.intervals[0].start.isoformat(),
                            "end": s.intervals[1].end.isoformat()}]}
    if reference:
        from copy import deepcopy
        ref = deepcopy(flows)
        ref["grid_ev"][1] += .69
        ref["amps_three"][1] += 1
        for k in range(2, len(ref["ev_energy"])):
            ref["ev_energy"][k] += .69 / 12 * .9
        assert not validate(s, ref)
        result["reference_flows"] = ref
    at = s.observation.at + timedelta(minutes=2)
    observation = replace(s.observation, at=at, quarter_import_kwh=.15)
    return s, result, observation, at


def test_unconfirmed_held_delivery_extends_existing_session_by_only_missing_energy():
    from copy import deepcopy
    from energymanager.validation import rolling_comparison_errors
    s, result, observation, at = held_charging_fixture(reference=True)
    original = deepcopy(result)
    current, adopted, errors = rebase(s, result, observation, at)
    assert not errors, errors
    assert result == original
    assert not validate(current, adopted["flows"])
    assert not validate(current, adopted["reference_flows"])
    assert not rolling_comparison_errors(current, adopted["reference_flows"], adopted["flows"])
    assert adopted["flows"]["ev_energy"][0] == observation.ev_kwh
    assert adopted["flows"]["ev_energy"][-1] == pytest.approx(24.6)
    assert adopted["publication_repair"]["energy_kwh"] == pytest.approx(.1032)
    assert adopted["reference_publication_repair"]["energy_kwh"] == pytest.approx(.05145)
    assert len(current.intervals) == len(s.intervals) + 2
    session = adopted["sessions"][0]
    assert session["end"] == adopted["publication_repair"]["end"]
    assert session["energy_kwh"] == pytest.approx(.6)
    assert adopted["goals"][0]["completion_at"] == session["end"]
    assert adopted["adoption_snapshot"] == json_data(current)
    assert adopted["adoption_digest"] == current.digest
    assert adopted["candidate_at_calculation"]["flows"] == original["flows"]


def test_confirmed_held_delivery_needs_no_extension():
    s, result, observation, at = held_charging_fixture()
    observation = replace(observation, ev_kwh=24 + 4.14 * 2 / 60 * .9)
    current, adopted, errors = rebase(s, result, observation, at)
    assert not errors
    assert "publication_repair" not in adopted
    assert not validate(current, adopted["flows"])
    assert adopted["sessions"][0]["end"] == result["sessions"][0]["end"]


@pytest.mark.parametrize("blocker", ["inventory_loss", "peak", "deadline", "away", "no_future_session", "disconnected"])
def test_delivery_repair_does_not_bypass_existing_guards(blocker):
    s, result, observation, at = held_charging_fixture()
    if blocker == "inventory_loss":
        observation = replace(observation, ev_kwh=23.8)
    elif blocker == "peak":
        observation = replace(observation, quarter_import_kwh=.3)
    elif blocker == "disconnected":
        observation = replace(observation, connected=False)
    elif blocker == "deadline":
        s = replace(s, goals=(replace(s.goals[0], deadline=s.intervals[1].end),))
    elif blocker == "away":
        intervals = list(s.intervals)
        intervals[2] = replace(intervals[2], available=False)
        s = replace(s, intervals=tuple(intervals))
    else:
        at = s.observation.at + timedelta(minutes=11)
        observation = replace(observation, at=at, quarter_import_kwh=.15)
    current, rejected, errors = rebase(s, result, observation, at)
    assert errors
    assert rejected["flows"] == result["flows"]
    assert "publication_candidate" in rejected
    assert "publication_repair" not in rejected
    assert validate(current, rejected["publication_candidate"]["flows"])


def test_lost_delivery_can_extend_one_phase_without_switching_modes():
    s, result, observation, at = held_charging_fixture(phase=1)
    current, adopted, errors = rebase(s, result, observation, at)
    assert not errors, errors
    assert not validate(current, adopted["flows"])
    assert adopted["flows"]["ev_energy"][-1] == pytest.approx(24.2)
    assert not any(adopted["flows"]["three"])
    assert adopted["publication_repair"]["energy_kwh"] == pytest.approx(.0344)
    assert adopted["publication_repair"]["phases"] == 1


def test_failed_reference_preserves_original_candidate_and_labels_repair_evidence():
    from copy import deepcopy
    s, result, observation, at = held_charging_fixture(reference=True)
    # A deliberately invalid comparison trajectory cannot authorize publication.
    result["reference_flows"]["grid_house"][3] += 1
    original = deepcopy(result)
    current, rejected, errors = rebase(s, result, observation, at)
    assert any("Reference cannot be reconciled" in error for error in errors)
    assert rejected["flows"] == original["flows"]
    assert rejected["publication_candidate"]["flows"] != rejected["flows"]
    assert not validate(current, rejected["publication_candidate"]["flows"])
    assert result == original
    assert rejected["adoption_snapshot"] == json_data(current)
    assert rejected["adoption_digest"] == current.digest


def test_split_inventory_keeps_withdrawal_at_its_original_end_boundary():
    from energymanager.publication import split_interval
    s, result, _, _ = held_charging_fixture()
    flows = result["flows"]
    intervals = list(s.intervals)
    intervals[2] = replace(intervals[2], withdrawal_kwh=2)
    s = replace(s, intervals=tuple(intervals), goals=(replace(s.goals[0], deadline=intervals[1].end),))
    for k in range(3, len(flows["ev_energy"])):
        flows["ev_energy"][k] -= 2
    assert not validate(s, flows)
    boundary = intervals[2].start + timedelta(minutes=2)
    split = split_interval(s, flows, boundary)
    assert sum(i.withdrawal_kwh for i in split.intervals) == 2
    assert flows["ev_energy"][3] == pytest.approx(flows["ev_energy"][2])
    assert flows["ev_energy"][4] == pytest.approx(flows["ev_energy"][3] - 2)
    assert not validate(split, flows)
