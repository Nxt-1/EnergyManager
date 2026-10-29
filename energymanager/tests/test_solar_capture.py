"""Synthetic solar-capture regressions; no installation or provider access."""

from copy import deepcopy
from dataclasses import replace
from time import monotonic

import pytest

from energymanager.incumbent import seed
from energymanager.optimization import JointModel
from energymanager.planner import Planner
from energymanager.solar_capture import SolarCapture
from energymanager.validation import accounting, rolling_comparison_errors, validate
from test_first_slice import tiny


def starting_result(model):
    values = seed(model)
    assert values is not None, model.seed_issue
    flows = {name: [values[index] for index in indexes] for name, indexes in model.linear.variables.items()}
    assert not validate(model.snapshot, flows)
    return {"status": "Time limit reached", "feasible": True, "values": values, "flows": flows}


def normal_model(snapshot, reference):
    ceilings = [max(snapshot.policy.normal_soc_percent / 100 * snapshot.capabilities.ev_capacity_kwh, value)
                for value in reference["ev_energy"][1:]]
    model = JointModel(snapshot, optional=True, ceilings=ceilings, tight_ceilings=True)
    model.add_optional_peak_limits(reference)
    return model


def test_unused_dc_export_seed_keeps_stocks_sources_and_original_evidence():
    s = tiny(ess=14, pv=1, dc=3)
    model = JointModel(s)
    original = starting_result(model)
    evidence = deepcopy(original["flows"])
    optional = normal_model(s, evidence)
    values = SolarCapture(optional, evidence).export_seed()
    flows = {name: [values[k] for k in indexes] for name, indexes in optional.linear.variables.items()}
    assert optional.linear.accepts(values)
    assert not validate(s, flows)
    assert not rolling_comparison_errors(s, evidence, flows)
    assert accounting(s, flows)["export_income_eur"] > accounting(s, evidence)["export_income_eur"] + .05
    for name in ("ev_energy", "ess_solar", "ess_grid", "grid_ev", "grid_store", "grid_house", "dc_store"):
        assert flows[name] == evidence[name]
    assert original["flows"] == evidence
    assert all(power <= s.capabilities.ac_discharge_kw + 1e-6
               for power in (v * s.capabilities.ac_discharge_efficiency for v in flows["dc_invert"]))


def test_export_seed_does_not_reverse_an_ac_charging_converter():
    s = tiny(pv=4, dc=3)
    model = JointModel(s)
    result = starting_result(model)
    values = SolarCapture(model, result["flows"]).export_seed()
    assert model.linear.accepts(values)
    for t, charging in enumerate(result["flows"]["converter_charge"]):
        if charging > .5:
            assert values[model.linear.variables["dc_invert"][t]] == result["flows"]["dc_invert"][t]
    assert any(v > .5 for v in result["flows"]["converter_charge"])


def test_later_dc_capture_can_replace_early_ac_filling_without_ev_or_stored_export():
    s = tiny(hours=8, ess=6, house=.4)
    s = replace(s, intervals=tuple(replace(i, available=False, pv_ac_kw=3 if t < 48 else .4,
                                         pv_dc_kw=0 if t < 48 else 3)
                                   for t, i in enumerate(s.intervals)))
    baseline = starting_result(JointModel(s))
    model = normal_model(s, baseline["flows"])
    planner = Planner()
    planner.deadline = monotonic() + 5
    planner.reference_flows = baseline["flows"]
    improved = planner.prefer_solar(model, baseline, 3)
    f = improved["flows"]
    assert not validate(s, f) and not rolling_comparison_errors(s, baseline["flows"], f)
    assert accounting(s, f)["exports_kwh"] > accounting(s, baseline["flows"])["exports_kwh"] + 1
    assert f["ess_solar"][-1] == pytest.approx(baseline["flows"]["ess_solar"][-1])
    assert f["ess_grid"][-1] == pytest.approx(baseline["flows"]["ess_grid"][-1])
    assert not any(v > 1e-6 for v in f["pv_ev"] + f["solar_dis_ev"] + f["grid_ev"])
    # The extra export is routed incoming solar, never a new battery-to-grid source.
    assert set(f) == set(baseline["flows"])


@pytest.mark.parametrize("available", [True, False])
def test_normal_capture_uses_available_ev_and_keeps_future_ess_supply(available):
    s = tiny(hours=30, ev=30, ess=6, pv=0, planning_budget_seconds=8)
    s = replace(s, intervals=tuple(replace(i, available=available, pv_ac_kw=4 if t < 36 else 0,
                                         pv_dc_kw=2 if t < 36 else 0)
                                   for t, i in enumerate(s.intervals)))
    baseline = starting_result(JointModel(s))
    model = normal_model(s, baseline["flows"])
    capture = SolarCapture(model, baseline["flows"])
    local = capture.neighborhood(*capture.windows()[0])
    trial = local.run(2, warm=local.warm_from(baseline["flows"]))
    assert trial["feasible"]
    f = trial["flows"]
    assert model.linear.accepts(model.warm_from(f))
    assert not validate(s, f) and not rolling_comparison_errors(s, baseline["flows"], f)
    assert max(f["ev_energy"]) <= 48 + 1e-6
    assert max(f["grid_ev"]) < 1e-6
    assert f["ess_solar"][288:] == pytest.approx(baseline["flows"]["ess_solar"][288:])
    assert f["ess_grid"][288:] == pytest.approx(baseline["flows"]["ess_grid"][288:])
    if available:
        assert f["ev_energy"][-1] > 35
    else:
        assert f["ev_energy"][-1] == pytest.approx(30)


def test_later_window_preserves_earlier_delivery_and_captures_later_surplus():
    s = tiny(hours=30, ev=30, ess=14)
    s = replace(s, intervals=tuple(replace(i, pv_ac_kw=4 if t >= 288 else .4)
                                   for t, i in enumerate(s.intervals)))
    baseline = starting_result(JointModel(s))
    model = normal_model(s, baseline["flows"])
    capture = SolarCapture(model, baseline["flows"])
    local = capture.neighborhood(*capture.windows()[-1])
    trial = local.run(2, warm=local.warm_from(baseline["flows"]))
    assert trial["feasible"] and not validate(s, trial["flows"])
    assert trial["flows"]["ev_energy"][:289] == pytest.approx(baseline["flows"]["ev_energy"][:289])
    assert trial["flows"]["ev_energy"][-1] > 40
    assert model.linear.accepts(model.warm_from(trial["flows"]))


def test_timeout_retains_checked_export_candidate_and_raw_solver_status(monkeypatch):
    s = tiny(ess=14, pv=1, dc=3)
    baseline = starting_result(JointModel(s))
    model = normal_model(s, baseline["flows"])
    monkeypatch.setattr(JointModel, "run", lambda *a, **k:
                        {"status": "Time limit reached", "feasible": False, "seconds": 0})
    planner = Planner()
    planner.deadline = monotonic() + 3
    planner.reference_flows = baseline["flows"]
    result = planner.prefer_solar(model, baseline, 2)
    assert not validate(s, result["flows"])
    assert accounting(s, result["flows"])["comparison_eur"] < accounting(s, baseline["flows"])["comparison_eur"]
    assert planner.stages[-1]["feasible"] is False
    assert planner.stages[-1]["retained_starting_candidate"] is True
    assert result["status"] == "Time limit reached"


def test_planner_retains_solar_capture_when_full_searches_return_no_incumbent(monkeypatch):
    s = tiny(hours=2, ev=30, ess=14, pv=4, dc=2, planning_budget_seconds=4)
    monkeypatch.setattr(JointModel, "run", lambda *a, **k:
                        {"status": "Time limit reached", "feasible": False, "seconds": 0})
    planner = Planner()
    result = planner.plan(s)
    assert result["valid"], result
    assert result["flows"]["ev_energy"][-1] > 35
    assert max(result["flows"]["grid_ev"]) < 1e-6
    assert not validate(s, result["flows"], result.get("service"))
    assert result["status"] == "Time limit reached"
    assert result["seconds"] <= s.policy.planning_budget_seconds + .5


def test_capture_does_not_force_economically_unhelpful_ev_energy():
    s = tiny(ev=30, ess=14, pv=4, ev_value_eur_kwh=0)
    baseline = starting_result(JointModel(s))
    model = normal_model(s, baseline["flows"])
    planner = Planner()
    planner.deadline = monotonic() + 3
    planner.reference_flows = baseline["flows"]
    result = planner.prefer_solar(model, baseline, 2)
    assert result["flows"]["ev_energy"][-1] == pytest.approx(30)
    assert not validate(s, result["flows"])


def test_export_seed_can_release_idle_direction_flags_without_changing_real_flows():
    s = tiny(ess=14, pv=.4, dc=2)
    model = JointModel(s)
    result = starting_result(model)
    for t in range(len(s.intervals)):
        result["flows"]["converter_charge"][t] = 1
        result["flows"]["grid_direction"][t] = 1
    assert model.linear.accepts(model.warm_from(result["flows"]))
    values = SolarCapture(model, result["flows"]).export_seed()
    assert model.linear.accepts(values)
    assert sum(values[k] for k in model.linear.variables["export"]) > 1


def test_invalid_solver_candidate_cannot_replace_checked_flows(monkeypatch):
    s = tiny(ess=14, pv=1, dc=2)
    baseline = starting_result(JointModel(s))
    model = normal_model(s, baseline["flows"])
    invalid = deepcopy(baseline["flows"])
    invalid["grid_ev"][0] = 7
    monkeypatch.setattr(JointModel, "run", lambda *a, **k:
                        {"status": "Time limit reached", "feasible": True, "seconds": 0,
                         "values": model.warm_from(invalid), "flows": invalid})
    planner = Planner()
    planner.deadline = monotonic() + 3
    planner.reference_flows = baseline["flows"]
    result = planner.prefer_solar(model, baseline, 2)
    assert not validate(s, result["flows"])
    assert max(result["flows"]["grid_ev"]) == 0
