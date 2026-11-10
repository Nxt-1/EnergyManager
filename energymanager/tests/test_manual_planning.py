"""Real joint models for manual completion and non-executable successor demand."""

from dataclasses import replace
from time import monotonic
from datetime import timedelta

import pytest

from energymanager.domain import Snapshot
from energymanager.ev_progress import EVProgress
from energymanager.manual_planning import completion_context
from energymanager.planner import Planner
from energymanager.store import Store
from energymanager.validation import validate
from test_ev_feedback import confirm, goal, manual_update
from test_ev_progress import AT, C, P, update
from test_first_slice import tiny


def context(tmp_path, *, target=55):
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    g = confirm(progress, soc=50)
    o = manual_update(progress, 5, 100, g)
    base = tiny(hours=2, ev=23.4, ess=7)
    shift = o.at - base.observation.at
    later = replace(goal(7200, target), id="synthetic-later")
    s = replace(base, observation=o, capabilities=C, policy=replace(P, planning_budget_seconds=3),
        forecast_at=o.at, goals=(g,later),
        intervals=tuple(replace(i,start=i.start+shift,end=i.end+shift,available=i.start+shift<g.deadline,
                               ev_state_known=i.start+shift<g.deadline) for i in base.intervals))
    return store, progress, s


def test_checked_advisory_preserves_normal_scheduling_and_never_becomes_executable(tmp_path):
    store, progress, s = context(tmp_path)
    planner = Planner()
    planner.started = monotonic()
    planner.deadline = planner.started + 3
    result = planner.manual_advisory(s)
    assert result["status"] == "checked", result
    assert result["executable"] is False
    advisory = Snapshot.from_dict(result["context"])
    assert advisory.digest == result["context_digest"]
    assert not validate(advisory, result["flows"])
    assert "HYPOTHETICAL" in advisory.provenance
    assert not advisory.observation.ev_progress["manual"]["enabled"]
    assert s.observation.ev_progress["manual"]["enabled"]
    demand = result["instruction"]
    assert demand["goal_id"] == "synthetic-later"
    assert demand["power_kw"] > 0
    assert max(result["flows"]["ev_energy"]) > s.ev_ceiling_kwh
    # A future listed goal is insufficient; only the checked actual due instruction
    # can request one new reference, without authorizing any of its extra flows.
    from energymanager.domain import instant
    at = instant(demand["would_start"])
    progress.feedback.request_refresh(at - timedelta(seconds=1), demand)
    assert not progress.feedback.state.get("refresh")
    progress.feedback.request_refresh(at, demand)
    progress.feedback.request_refresh(at, demand)
    assert len(progress.feedback.state["notices"]) == 1
    store.close()


def test_small_manual_quantity_includes_a_phase_wait_spanning_the_completion_slot(tmp_path):
    from energymanager.domain import Interval, instant
    from energymanager.publication import admit
    store = Store(tmp_path / "synthetic-phase.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    g = confirm(progress, soc=49.9, g=goal(3600))
    o = manual_update(progress, 0, 100, g)
    base = tiny(hours=1)
    shift = AT-base.observation.at
    intervals = tuple(replace(i,start=i.start+shift,end=i.end+shift) for i in base.intervals)
    first = intervals[0]
    if first.end > AT+timedelta(seconds=15):
        intervals = (replace(first,end=AT+timedelta(seconds=15)),
                     Interval(AT+timedelta(seconds=15),first.end,first.house_kw,first.pv_ac_kw,first.pv_dc_kw),*intervals[1:])
    execution = {"protocol":1,"phase_switch_seconds":130,"initial_phase":1,"ready_at":AT.isoformat(),
        "commitment_until":(AT+timedelta(seconds=15)).isoformat(),"charger":{"phase":1},
        "commitments":[{"start":AT.isoformat(),"end":(AT+timedelta(seconds=15)).isoformat(),"power_kw":0,"phases":1}]}
    s = replace(base,observation=o,capabilities=replace(C,phases=(3,)),policy=replace(P,planning_budget_seconds=4),
                forecast_at=AT,goals=(g,),intervals=intervals,execution=execution)
    result = Planner().plan(s)
    assert result["valid"], result
    effective = Snapshot.from_dict(result["effective_snapshot"])
    assert not validate(effective,result["flows"],result["service"])
    assert not admit(effective,result,o,AT)[1]
    completion = instant(effective.observation.ev_progress["manual"]["completion_at"])
    assert completion >= AT+timedelta(seconds=145)
    assert max(result["flows"]["ev_energy"]) == pytest.approx(23.4)
    assert any(result["flows"]["amps_three"])
    assert not any(result["flows"]["amps_one"])
    store.close()


def test_advisory_timeout_missing_candidate_and_satisfied_successor_cannot_fabricate_prompt_times(tmp_path):
    store, progress, s = context(tmp_path)
    planner = Planner()
    planner.started = monotonic()
    planner.deadline = planner.started
    assert planner.manual_advisory(s)["status"] == "unverified"
    assert not progress.feedback.state.get("refresh")
    planner.deadline = monotonic() + 3
    impossible = replace(s, goals=(replace(s.goals[-1], deadline=s.intervals[1].end, target_soc_percent=100),))
    result = planner.manual_advisory(impossible)
    assert result["status"] == "unverified" and not result.get("instruction")
    satisfied = replace(s, goals=(replace(s.goals[-1], target_soc_percent=40),))
    assert planner.manual_advisory(satisfied)["status"] in ("not_applicable", "unverified")
    assert not progress.feedback.state.get("refresh")
    store.close()


def test_refresh_pipeline_requires_due_audited_evidence_current_sources_and_current_revision(tmp_path):
    from energymanager.domain import instant, json_data
    from energymanager.service import Application
    store, progress, s = context(tmp_path)
    planner = Planner()
    planner.started = monotonic()
    planner.deadline = planner.started + 3
    advisory = planner.manual_advisory(s)
    assert advisory["status"] == "checked"
    at = instant(advisory["instruction"]["would_start"])
    app = Application(store,snapshot=s,policy=s.policy,demo=False)
    app.now = lambda: at
    app.accepted = {"id":"SYNTHETIC bounded plan","revision":app.revision,"manual_advisory":advisory,
                    "intervals":json_data(s.intervals),"flows":{k:[0]*len(s.intervals) for k in ("pv_ev","grid_ev","solar_dis_ev")}}
    original_goal = goal()
    before = at-timedelta(seconds=1)
    seconds = (before-AT).total_seconds()
    app.observation = manual_update(app.ev_progress,seconds,100,original_goal)
    app.check_manual_demand(before)
    assert not app.ev_progress.feedback.state.get("refresh")
    app.observation = manual_update(app.ev_progress,(at-AT).total_seconds(),100,original_goal)
    revision = app.accepted["revision"]
    app.accepted["revision"] = revision-1
    app.check_manual_demand(at)
    assert not app.ev_progress.feedback.state.get("refresh")
    app.accepted["revision"] = revision
    current = app.observation
    app.observation = replace(current,quality="unknown")
    app.check_manual_demand(at)
    assert not app.ev_progress.feedback.state.get("refresh")
    app.observation = current
    app.check_manual_demand(at)
    app.check_manual_demand(at)
    assert app.ev_progress.feedback.state["refresh"]["demand"]["goal_id"] == "synthetic-later"
    assert len(app.ev_progress.feedback.state["notices"]) == 1
    store.close()


@pytest.mark.parametrize("phases,amount", [((1,), .414), ((1,), .468), ((3,), .468)])
def test_manual_completion_refines_integer_current_quantity_without_reusing_old_arrays(tmp_path, phases, amount):
    store, progress, s = context(tmp_path)
    c = replace(C, phases=phases)
    manual = dict(s.observation.ev_progress["manual"])
    # Explicit artificial seed quantities exercise exact and interior event boundaries.
    manual.update(limit_kwh=s.observation.ev_kwh+amount,quantity_kwh=amount,status="active")
    s = replace(s, capabilities=c, observation=replace(s.observation,
        ev_progress={**s.observation.ev_progress,"manual":manual}), goals=())
    n=len(s.intervals)
    f={"ev_energy":[s.observation.ev_kwh]+[s.observation.ev_kwh+1]*(n),
       "one":[1 if phases==(1,) else 0]*n,"three":[1 if phases==(3,) else 0]*n,
       "amps_one":[6 if phases==(1,) else 0]*n,"amps_three":[6 if phases==(3,) else 0]*n}
    # Choose a seed with enough stock increase only by the physically correct interval.
    kw=6*phases[0]*c.voltage/1000
    f["ev_energy"]=[s.observation.ev_kwh+kw*c.ev_efficiency*sum(i.hours for i in s.intervals[:t]) for t in range(n+1)]
    refined=completion_context(s,s,f)
    assert refined.digest!=s.digest
    assert all(i.hours<=5/60+1e-9 for i in refined.intervals)
    assert refined.observation.ev_progress["manual"]["completion_at"]
    assert all(p["power_kw"]==0 for p in refined.observation.ev_progress["manual"]["schedule"]
               if p["start"]>=refined.observation.ev_progress["manual"]["completion_at"])
    store.close()
