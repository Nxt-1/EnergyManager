"""Persistent M2 lifecycle against deterministic fake Home Connect and notifications."""

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

from energymanager.appliance_runs import ApplianceRuns
from energymanager.domain import Policy
from test_bosch import bosch as bosch_fixture, cycle, ECO, INTENSIVE
from test_first_slice import tiny


bosch = bosch_fixture


@pytest.fixture
async def managed(bosch):
    identity=await cycle(bosch)
    profiles=bosch.profiles
    profiles.accept(identity,{"revision":profiles.settings["revision"],"reviewed":True})
    app=bosch.app
    app.appliance_profiles=profiles
    app.policy=Policy(control_enabled=True)
    app.revision=1
    app.accepted=None
    app.house_mismatch_since=None
    app.observation=replace(tiny().observation,at=app.now(),quality="measured")
    app.requests=[]
    def changed(reason):
        app.revision+=1
        app.requests.append(reason)
    app.changed=changed
    app.request_plan=lambda reason:app.requests.append(reason)
    async def inform(*args):
        app.notices.append(args)
        return True
    app.notices=[]
    app.notifications=SimpleNamespace(target=None,inform=inform)
    bosch.app.ha.set("operation","ready")
    bosch.app.ha.rows["sensor.synthetic_refoss"]["state"]="5"
    app.appliance_runs=ApplianceRuns(app)
    await bosch.poll()
    yield app.appliance_runs


async def ready(manager,**changes):
    return await manager.action("ready",{"revision":manager.saved["revision"],"program":ECO,
        "deadline":(manager.app.now()+timedelta(hours=1)).isoformat(),**changes})


def accept(manager,seconds=0):
    app=manager.app
    plan={"id":"SYNTHETIC-joint-"+str(app.revision),"revision":app.revision,"forecast_at":app.now().isoformat(),
          "admission":{"passed":True},"appliance":{**manager.context(),
          "planned_start":(app.now()+timedelta(seconds=seconds)).isoformat(),
          "estimated_finish":(app.now()+timedelta(seconds=25)).isoformat()}}
    app.accepted=plan
    manager.accepted(plan)
    return plan


async def test_ready_persists_without_operating_and_native_delay_or_unseen_asap_blocks(managed):
    manager=managed
    app=manager.app
    preview=await manager.action("preview",{"program":ECO,"deadline":(app.now()+timedelta(seconds=1)).isoformat()})
    assert preview["asap"] and preview["warning"]
    with pytest.raises(ValueError,match="warning"):
        await ready(manager,deadline=preview["deadline"])
    assert manager.run is None
    app.ha.set("delay","60")
    with pytest.raises(ValueError,match="native"):
        await ready(manager)
    app.ha.set("delay","0")
    await ready(manager,deadline=preview["deadline"],accept_asap=True)
    restored=ApplianceRuns(app)
    assert restored.run["phase"]=="queued" and restored.run["asap"]
    assert restored.reconciled is False and app.ha.calls==[]


async def test_scheduled_start_is_one_attempt_and_restart_waits_for_feedback(managed):
    manager=managed
    app=manager.app
    await ready(manager)
    accept(manager)
    await app.appliance_profiles.bosch.poll()
    assert manager.run["phase"]=="starting" and len(app.ha.calls)==1
    restored=ApplianceRuns(app)
    app.appliance_runs=restored
    await app.appliance_profiles.bosch.poll()
    assert len(app.ha.calls)==1
    before=app.now()
    app.now=lambda:before+timedelta(seconds=35)
    await app.appliance_profiles.bosch.poll()
    assert restored.run["phase"]=="attention" and len(app.ha.calls)==1
    app.ha.set("operation","run")
    await app.appliance_profiles.bosch.poll()
    assert restored.run["phase"]=="running" and len(app.ha.calls)==1
    app.ha.set("operation","finished")
    app.now=lambda:before+timedelta(seconds=40)
    await app.appliance_profiles.bosch.poll()
    assert restored.run["phase"]=="finished" and restored.peak_limit() is None


async def test_door_reopening_retains_request_and_closing_replans_without_new_ready(managed):
    app=managed.app
    app.ha.set("door","on")
    await ready(managed)
    identity=managed.run["id"]
    await app.appliance_profiles.bosch.poll()
    accept(managed)
    await app.appliance_profiles.bosch.poll()
    assert managed.run["id"]==identity and app.ha.calls==[]
    app.ha.set("door","off")
    await app.appliance_profiles.bosch.poll()
    assert "dishwasher_eligibility_changed" in app.requests
    assert managed.run["phase"]=="queued" and app.ha.calls==[]
    accept(managed)
    await app.appliance_profiles.bosch.poll()
    assert managed.run["phase"]=="starting" and len(app.ha.calls)==1


async def test_program_changes_and_lost_profile_revoke_old_selection_permission(managed):
    app=managed.app
    await ready(managed)
    app.ha.set("selected_program",INTENSIVE)
    await app.appliance_profiles.bosch.poll()
    assert managed.run["program"]==INTENSIVE and managed.run["profile"] is None
    assert managed.context()["points"]==[] and app.ha.calls==[]
    with pytest.raises(ValueError,match="changed"):
        await managed.action("cancel",{"revision":1})
    await managed.action("cancel",{"revision":managed.saved["revision"]})
    assert managed.run["phase"]=="cancelled"


async def test_ambiguous_service_failure_cannot_replay_and_fresh_revision_is_checked(managed):
    app=managed.app
    await ready(managed)
    accept(managed)
    def revoke():
        app.revision+=1
    app.ha.on_read=revoke
    await managed.execute()
    assert app.ha.calls==[] and managed.run["phase"]=="queued"
    app.ha.on_read=None
    accept(managed)
    async def fail(*args):
        app.ha.calls.append("SYNTHETIC unknown transport outcome")
        raise RuntimeError("SYNTHETIC failure")
    app.ha.service=fail
    await managed.execute()
    assert managed.run["phase"]=="attention" and len(app.ha.calls)==1
    for _ in range(3):
        await app.appliance_profiles.bosch.poll()
    assert len(app.ha.calls)==1


async def test_peak_choice_is_explicit_and_scoped_to_the_displayed_run_proposal(managed):
    await ready(managed)
    run=managed.run
    proposal={"id":run["id"],"revision":run["revision"],"proposal_id":"SYNTHETIC-proposal",
              "on_time":{"peak_kw":6,"estimated_finish":run["deadline"]},
              "later":{"peak_kw":4,"estimated_finish":(managed.app.now()+timedelta(hours=2)).isoformat()}}
    managed.accepted({"appliance_conflict":proposal})
    with pytest.raises(ValueError,match="available"):
        await managed.action("choose",{"revision":managed.saved["revision"],"choice":"on_time","approved":True,"proposal_id":"old"})
    with pytest.raises(ValueError,match="approval"):
        await managed.action("choose",{"revision":managed.saved["revision"],"choice":"on_time","proposal_id":proposal["proposal_id"]})
    await managed.action("choose",{"revision":managed.saved["revision"],"choice":"on_time","proposal_id":proposal["proposal_id"],"approved":True})
    assert managed.run["approved_peak_kw"]==6 and managed.run["conflict"] is None
    assert managed.peak_limit() is None  # A queued approval never raises live EV/ESS permission.


async def test_standby_is_counted_once_and_missing_measurements_do_not_establish_idle(managed):
    app=managed.app
    bosch=app.appliance_profiles.bosch
    from energymanager.background import MeasuredBackground
    background=MeasuredBackground(app.store)
    background.bosch=bosch
    assert managed.context()["idle_w"]==5
    assert background.matched(app.observation)==pytest.approx(app.observation.house_kw-.005)
    bosch.readings["meter"]={"state":None,"error":"SYNTHETIC unavailable"}
    before=app.now()
    app.now=lambda:before+timedelta(seconds=20)
    assert background.matched(replace(app.observation,at=app.now())) is None


async def test_first_seen_running_never_fabricates_elapsed_profile_phase(managed):
    app = managed.app
    bosch = app.appliance_profiles.bosch
    bosch.previous = None
    app.ha.set("operation", "run")
    await bosch.poll()
    assert managed.manual["timing_known"] is False
    with pytest.raises(ValueError, match="elapsed phase is unknown"):
        managed.context()
    assert app.ha.calls == []
    app.ha.set("operation", "finished")
    await bosch.poll()
    assert managed.context()["points"] == []


async def test_ready_rechecks_revision_after_fresh_ha_reads(managed):
    app = managed.app
    app.ha.on_read = lambda: setattr(app.appliance_runs, "saved", {**managed.saved, "revision": 10})
    with pytest.raises(ValueError, match="changed"):
        await ready(managed)
    assert managed.run is None and app.ha.calls == []


async def test_conflict_notifies_and_original_feasibility_resumes_without_another_ready(managed):
    app = managed.app
    await ready(managed)
    run = managed.run
    managed.accepted({"appliance_conflict": {"id": run["id"], "revision": run["revision"],
                                            "proposal_id": "SYNTHETIC-no-choice", "later": None, "on_time": None}})
    await app.appliance_profiles.bosch.poll()
    assert len(app.notices) == 1 and app.ha.calls == []
    await app.appliance_profiles.bosch.poll()
    assert len(app.notices) == 1
    accept(managed)
    assert run["conflict"] is None
    await app.appliance_profiles.bosch.poll()
    assert run["phase"] == "starting" and len(app.ha.calls) == 1



async def test_editing_a_queued_deadline_clears_the_previous_plan_estimate(managed):
    await ready(managed)
    accept(managed, seconds=30)
    await managed.action("edit", {"revision": managed.saved["revision"],
        "deadline": (managed.app.now()+timedelta(hours=2)).isoformat()})
    assert managed.run["planned_start"] is None
    assert managed.run["estimated_finish"] is None and managed.run["plan_id"] is None



@pytest.mark.parametrize("deadline", [None, 0, {}, "2026-11-02T18:00"])
async def test_preview_requires_a_real_deadline_with_explicit_offset(managed, deadline):
    with pytest.raises(ValueError, match="timezone"):
        await managed.preview({"program": ECO, "deadline": deadline})
    assert managed.run is None and managed.app.ha.calls == []



async def test_same_identity_trim_replans_the_queued_run_without_mutating_frozen_evidence(managed):
    from copy import deepcopy
    await ready(managed)
    plan = accept(managed, seconds=60)
    frozen = deepcopy(plan)
    profiles = managed.app.appliance_profiles
    identity = profiles.members("dishwasher/"+ECO)[0]
    old_revision = managed.run["revision"]
    profiles.revise(identity, {"revision": profiles.settings["revision"], "reviewed": True,
                              "start_seconds": 5, "end_seconds": 20})
    await profiles.bosch.poll()
    assert managed.run["revision"] > old_revision and managed.run["planned_start"] is None
    assert managed.run["profile"]["summary"]["mean_duration_seconds"] == 15
    assert plan == frozen and managed.app.ha.calls == []
