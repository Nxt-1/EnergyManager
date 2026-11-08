"""Independent cautious witnesses over labelled local scenarios and AC/DC sources."""

from copy import deepcopy
from dataclasses import replace

import pytest

from deadline_fixtures import example
from energymanager.deadline_audit import cautious_context, validate_certificate
from energymanager.deadline_guard import cautious_model, deadline_certificate
from energymanager.optimization import JointModel
from energymanager.validation import validate


@pytest.mark.parametrize("name", ["room_after_pv", "tight_after_pv", "trip", "no_pv", "held_partial", "stored_solar"])
def test_certificates_keep_physics_source_causality_and_explicit_contexts(name):
    s = example(name)
    nominal = JointModel(s).run(2)
    assert nominal["feasible"]
    certificate = deadline_certificate(s, nominal["flows"], 7)
    assert certificate["status"] == "certified", certificate
    assert validate_certificate(certificate) == []
    lifted = deepcopy(certificate["flows"])
    context = certificate["context"]
    for t, interval in enumerate(s.intervals[:len(context["intervals"])]):
        lifted["curtail"][t] += interval.pv_ac_kw - context["intervals"][t]["pv_ac_kw"]
    from energymanager.domain import Snapshot
    assert validate(Snapshot.from_dict(certificate["nominal_context"]), lifted) == []
    if name == "no_pv":
        assert certificate["activation_at"] == s.intervals[0].start.isoformat()
    if name in ("room_after_pv", "tight_after_pv"):
        assert certificate["latest_start_resolved"]


def test_margin_only_shortfall_preserves_permissions_and_timeout_is_not_infeasibility():
    s = example("margin_only_shortfall")
    original = s.digest
    nominal = JointModel(s).run(2)
    assert nominal["feasible"]
    certificate = deadline_certificate(s, nominal["flows"], 4)
    assert certificate["status"] == "margin_shortfall" and s.digest == original
    assert certificate["attempts"][-1]["status"] == "Infeasible"
    assert deadline_certificate(s, nominal["flows"], 0)["status"] == "unverified"


def test_future_dc_stored_before_ev_returns_receives_margin_once_and_initial_stock_gets_full_credit():
    s = example("stored_solar")
    from energymanager.domain import Goal, Interval, time_grid
    grid = time_grid(s.observation.at, 2)
    c = replace(s.capabilities, ac_charge_kw=2.5, dc_charge_kw=6, battery_charge_kw=4)
    base = replace(s, capabilities=c, goals=(Goal("finish", "SYNTHETIC", grid[-1], 22.5 / c.ev_capacity_kwh * 100),),
                   intervals=tuple(Interval(a, b, 0, 0, 0, available=(a - grid[0]).total_seconds() >= 3600)
                                   for a, b in zip(grid, grid[1:])))
    known = cautious_model(base, len(base.intervals))
    known_result = known.run(2, objective={known.linear.variables["grid_cumulative"][-1]: 1})
    assert known_result["feasible"]
    future = replace(base, observation=replace(base.observation, ess_kwh=c.ess_min_kwh),
                     intervals=tuple(replace(i, pv_dc_kw=2 if not i.available else 0) for i in base.intervals))
    model = cautious_model(future, len(future.intervals))
    result = model.run(3, objective={model.linear.variables["grid_cumulative"][-1]: 1})
    assert result["feasible"]
    context = cautious_context(future, result["flows"], len(future.intervals))
    assert validate(context, result["flows"]) == []
    # Captured 2kWh nominal DC becomes 1.6kWh before capture losses, not 1.28kWh.
    assert max(i.pv_dc_kw for i in context.intervals) == pytest.approx(1.6)
    difference = result["flows"]["grid_cumulative"][-1] - known_result["flows"]["grid_cumulative"][-1]
    assert difference == pytest.approx((2 - 1.6 * c.dc_efficiency) * c.ac_discharge_efficiency * c.ev_efficiency,
                                       abs=.002)


def test_certificate_audit_rejects_protected_source_laundering():
    s = example("room_after_pv")
    nominal = JointModel(s).run(2)
    certificate = deadline_certificate(s, nominal["flows"], 5)
    assert certificate["status"] == "certified"
    corrupted = deepcopy(certificate)
    corrupted["flows"]["guard_house_stock"][0] = 1
    assert validate_certificate(corrupted)
    corrupted = deepcopy(certificate)
    corrupted["flows"]["guard_house_stock"][0] = float("nan")
    assert validate_certificate(corrupted)
    corrupted = deepcopy(certificate)
    corrupted["progress_kwh"] = [0] * len(certificate["progress_kwh"])
    assert "Cautious required progress mismatch" in validate_certificate(corrupted)


def test_cautious_fallback_preserves_the_accepted_appliance_commitment():
    from test_appliance_planning import task
    s = example("room_after_pv")
    s = replace(s, appliance=task(s))
    nominal = JointModel(s).run(3)
    assert nominal["feasible"]
    guard = deadline_certificate(s, nominal["flows"], 8)
    assert guard["status"] == "certified", guard
    assert guard["flows"]["dishwasher_start"] == pytest.approx(nominal["flows"]["dishwasher_start"])
    assert guard["flows"]["dishwasher_power"] == pytest.approx(nominal["flows"]["dishwasher_power"])
    assert validate_certificate(guard) == []
