"""Synthetic M2 physics and measured-background eligibility; no installation access."""

from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.appliance_plan import CycleCurve, selected_start, resolved_power
from energymanager.background import constant_estimate
from energymanager.domain import json_data, Snapshot
from energymanager.optimization import JointModel
from energymanager.store import Store
from energymanager.validation import validate
from test_first_slice import tiny


def task(snapshot, **changes):
    return {"id":"SYNTHETIC-cycle", "revision":1,"program":"synthetic_eco", "idle_w":5,
            "ready_at":snapshot.intervals[0].start.isoformat(),"deadline":snapshot.intervals[-1].end.isoformat(),
            "mean_duration_seconds":1500,"curve_seconds":1800,"approved_peak_kw":None,
            "points":[{"seconds":0,"power_w":2000},{"seconds":900,"power_w":300},{"seconds":1800,"power_w":0}],**changes}


def test_joint_start_uses_measured_curve_and_conserves_energy_with_partial_intervals():
    s = tiny(hours=2)
    s = replace(s,intervals=tuple(replace(i,pv_ac_kw=2 if i.start>=s.intervals[0].start+timedelta(hours=1) else 0) for i in s.intervals))
    s = replace(s,appliance=task(s))
    restored = Snapshot.from_dict(json_data(s))
    assert restored.digest == s.digest
    model = JointModel(s)
    result = model.run(10)
    assert result["feasible"],result
    assert validate(s,result["flows"]) == []
    at = selected_start(s,result["flows"])
    assert at >= s.intervals[0].start+timedelta(hours=1)
    curve = CycleCurve(s.appliance["points"])
    mapped = sum(p*i.hours for p,i in zip(resolved_power(s,result["flows"]),s.intervals))
    assert mapped == pytest.approx(curve.prefix[-1]/3600000 + .005*1.5)
    corrupt = {**result["flows"],"dishwasher_power":[0]*len(s.intervals)}
    assert "Dishwasher curve/energy conservation" in validate(s,corrupt)


def test_unavoidable_running_curve_keeps_elapsed_phase_and_remaining_energy():
    s=tiny(hours=1)
    beginning=s.intervals[0].start-timedelta(minutes=10)
    s=replace(s,appliance=task(s,started_at=beginning.isoformat()))
    result=JointModel(s).run(5)
    assert result["feasible"] and validate(s,result["flows"])==[]
    assert result["flows"]["dishwasher_power"][0]==pytest.approx(2)
    expected=(300*2000+900*300)/3600000 + .005*(40/60)
    assert sum(p*i.hours for p,i in zip(resolved_power(s,result["flows"]),s.intervals))==pytest.approx(expected)


def test_background_requires_real_coverage_and_does_not_treat_unmatched_history_as_zero(tmp_path):
    store=Store(tmp_path/'SYNTHETIC-background.sqlite')
    now=tiny().observation.at
    for index in range(13):
        at=(now-timedelta(minutes=5*(12-index))).timestamp()
        store.connection.execute("INSERT INTO load_samples VALUES (?,?)",(at,2400))
    store.connection.commit()
    estimate=constant_estimate(store.path,now,None)
    assert estimate["power_w"]==2400 and estimate["covered_seconds"]==3600
    with pytest.raises(ValueError,match="Insufficient"):
        constant_estimate(store.path,now,"sensor.synthetic_dishwasher")
    for index in range(13):
        at=(now-timedelta(minutes=5*(12-index))).timestamp()
        store.connection.execute("INSERT INTO background_samples VALUES (?,?,?,?,?,?)",(at,2400,2000,400,"sensor.synthetic_dishwasher","SYNTHETIC matched"))
    store.connection.commit()
    assert constant_estimate(store.path,now,"sensor.synthetic_dishwasher")["power_w"]==400
    store.connection.execute("DELETE FROM background_samples WHERE at=?",((now-timedelta(minutes=30)).timestamp(),))
    store.connection.commit()
    with pytest.raises(ValueError,match="Insufficient"):
        constant_estimate(store.path,now,"sensor.synthetic_dishwasher")
    store.close()



def test_complete_joint_planner_keeps_frozen_curve_evidence_and_counts_total_house_once():
    from energymanager.planner import Planner
    s=tiny(hours=2,planning_budget_seconds=10)
    s=replace(s,appliance=task(s))
    result=Planner().plan(s)
    assert result["valid"],result
    effective=Snapshot.from_dict(result["effective_snapshot"]) if result.get("effective_snapshot") else s
    assert validate(effective,result["flows"],result["service"])==[]
    assert result["appliance"]["id"]==s.appliance["id"]
    assert result["appliance"]["points"]==s.appliance["points"]
    for interval,power in zip(result["intervals"],result["flows"]["dishwasher_power"]):
        assert interval["house_kw"]==pytest.approx(interval["background_kw"]+power)


def test_conflict_returns_per_run_alternatives_and_retains_a_valid_ev_ess_fallback():
    from energymanager.planner import Planner
    s=tiny(hours=2,house=2,planning_budget_seconds=15,automatic_peak_kw=2.5)
    s=replace(s,appliance=task(s,deadline=(s.intervals[0].start+timedelta(minutes=30)).isoformat(),
        points=[{"seconds":0,"power_w":2000},{"seconds":1800,"power_w":0}],mean_duration_seconds=1800))
    # The second hour has sufficient PV for a later finish at the original allowance.
    s=replace(s,intervals=tuple(replace(i,pv_ac_kw=3 if i.start>=s.intervals[0].start+timedelta(hours=1) else 0) for i in s.intervals))
    result=Planner().plan(s)
    assert result["valid"],result
    conflict=result["appliance_conflict"]
    assert conflict["id"]==s.appliance["id"] and conflict["proposal_id"]
    assert conflict["on_time"]["peak_kw"]>2.5
    assert conflict["later"]["peak_kw"]<=2.5+1e-5
    assert result["appliance"]["planned_start"] is None
    effective=Snapshot.from_dict(result["effective_snapshot"])
    assert validate(effective,result["flows"],result["service"])==[]



def test_ess_support_cannot_use_a_different_possible_appliance_start():
    s = tiny(hours=26, ess=2.8)
    start = s.intervals[0].start + timedelta(hours=25)
    s = replace(s, appliance=task(s, deadline=s.intervals[-1].end.isoformat(),
                points=[{"seconds": 0, "power_w": 3000}, {"seconds": 1800, "power_w": 0}]))
    model = JointModel(s, grid_ess=True)
    from energymanager.appliance_plan import starts_for
    choices = starts_for(s)
    model.linear.equality([(model.linear.variables["dishwasher_start"][choices.index(start)], 1)], 1)
    # Other candidate starts would justify support now, but the selected cycle cannot.
    model.linear.row([(model.linear.variables["grid_store"][0], 1)], lower=.1)
    result = model.run(5)
    assert not result["feasible"] and result["status"] == "Infeasible"


def test_appliance_approval_cannot_raise_an_unrelated_quarter_limit():
    from energymanager.domain import Goal
    s = tiny(hours=2, house=.4, automatic_peak_kw=2.5)
    s = replace(s, goals=(Goal("goal", "SYNTHETIC EV", s.intervals[-1].end, 45),),
                appliance=task(s, approved_peak_kw=8,
                    deadline=(s.intervals[0].start+timedelta(minutes=30)).isoformat()))
    model = JointModel(s)
    # The approved half-hour cycle cannot authorize 4.6 kW EV in hour two.
    index = next(t for t,i in enumerate(s.intervals) if i.start >= s.intervals[0].start+timedelta(hours=1))
    for t in range(index,index+3):
        model.linear.row([(model.linear.variables["grid_ev"][t],1)],lower=4.6)
    result = model.run(5)
    assert not result["feasible"] and result["status"] == "Infeasible"



def test_elapsed_deadline_has_no_start_and_returns_explicit_waiting_alternative():
    from energymanager.planner import Planner
    s = tiny(hours=2, planning_budget_seconds=10)
    s = replace(s, appliance=task(s, deadline=(s.intervals[0].start+timedelta(minutes=5)).isoformat()))
    result = Planner().plan(s)
    assert result["valid"] and result["appliance_conflict"]["later"]
    assert result["appliance_conflict"]["on_time"] is None
