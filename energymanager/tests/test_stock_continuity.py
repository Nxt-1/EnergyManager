"""Reconstructed synthetic ledgers and actual fake go-e writes; no live installation."""

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

from energymanager.domain import Goal
from energymanager.service import Application
from energymanager.store import Store
from test_ev_progress import AT, C, P, meter, sample
from test_first_slice import tiny
from test_goe import ChargerFixture
from test_publication_closed_loop import result_for, scheduled_flows


def running_app(tmp_path, *, pending=False):
    s = tiny(ev=9.5274, house=.4)
    shift = AT-s.observation.at
    s = replace(s, capabilities=C, policy=P,
        observation=replace(sample(soc=9.126), house_kw=.4, ev_power_kw=0 if pending else 2.76, monthly_peak_kw=8),
        intervals=tuple(replace(i,start=i.start+shift,end=i.end+shift) for i in s.intervals), forecast_at=AT,
        goals=(Goal('g','SYNTHETIC continuing 50% goal',AT+timedelta(hours=1),50),))
    store = Store(tmp_path/'synthetic-continuity.sqlite')
    ha = SimpleNamespace(entities={'ev_total_kwh':'sensor.synthetic_eto'},
                         inputs=SimpleNamespace(readings={'ev_total_kwh':meter(0,100)}))
    app = Application(store,snapshot=s,policy=P,ha=ha,demo=False)
    fixture = ChargerFixture()
    fixture.at=AT
    fixture.set('force',1 if pending else 2)
    fixture.set('current',12)
    fixture.refresh(0)
    fixture.actuator.c=C
    if pending:
        fixture.actuator.resume_after=AT-timedelta(seconds=1)
    fixture.actuator.generation=lambda:app.revision
    app.actuator=fixture.actuator
    app.now=lambda:fixture.at
    app.observe(s.observation)
    # The exported incident lacks a complete installation ledger. This explicitly
    # synthetic reconstruction reproduces its retained stock and baseline5→6.
    app.ev_progress.state.update(estimated_kwh=9.5274,baseline_revision=5,credited_kwh=.4014)
    app.observe(s.observation)
    base=replace(s,observation=app.observation)
    app.accepted=result_for(base,scheduled_flows(base,[2.76]*len(base.intervals)))
    app.ev_valid=app.ess_valid=app.conditional_valid=True
    return app,fixture


async def apply(app,fixture):
    command=app.controller.tick(app.observation,fixture.at,app.accepted,app.revision,
        app.ev_valid,app.ess_valid,app.conditional_valid)
    await app.actuator.apply(command,app.revision,app.observation)
    app.current_command=command
    return command


@pytest.mark.parametrize('pending',[False,True])
async def test_incident_66wh_baseline_update_keeps_current_task_and_pending_ack(tmp_path,pending):
    app,fixture=running_app(tmp_path,pending=pending)
    if pending:
        fixture.ignore.add(fixture.actuators['force'])
    before=await apply(app,fixture)
    assert before.current_a>0 and before.phases==1
    acknowledgement=dict(fixture.actuator.goe_control.pending)
    fixture.calls.clear()
    credited=app.ev_progress.state['credited_kwh']
    fixture.refresh(5)
    app.ha.inputs.readings['ev_total_kwh']=meter(5,100.01)
    app.observe(replace(app.observation,at=fixture.at,ev_kwh=9.594,ev_state_known=True,
        ev_observed_at=None,ev_progress=None))
    assert app.observation.ev_progress['baseline_revision']==6
    assert app.observation.ev_kwh==pytest.approx(9.594)
    assert app.ev_valid and app.ess_valid and app.requested.is_set()
    after=await apply(app,fixture)
    assert after.current_a==before.current_a and after.phases==before.phases
    assert not any(c[2].get('option')=='1' and c[2]['entity_id']==fixture.actuators['force'] for c in fixture.calls)
    assert not any(c[2]['entity_id']==fixture.actuators['phase'] for c in fixture.calls)
    if pending:
        assert fixture.actuator.goe_control.pending['force']==acknowledgement['force']
    assert app.ev_progress.state['credited_kwh']==pytest.approx(credited+.009)
    app.observe(replace(app.observation,ev_kwh=9.594,ev_progress=None))
    assert app.ev_progress.state['baseline_revision']==6
    assert app.ev_progress.state['credited_kwh']==pytest.approx(credited+.009)
    app.store.close()


async def test_correction_to_endpoint_stops_and_a_later_lower_reference_cannot_rebuy_completed_work(tmp_path):
    app,fixture=running_app(tmp_path)
    await apply(app,fixture)
    endpoint=app.controller.ev_task['target']
    app.accepted['conditional_tasks']=[{'deadline':app.accepted['goals'][0]['deadline'],
        'target_ev_kwh':endpoint+1,'quantity_kwh':1}]
    for seconds,value in ((5,endpoint+.1),(10,9.0)):
        fixture.refresh(5)
        app.ha.inputs.readings['ev_total_kwh']=meter(seconds,100)
        app.observe(replace(app.observation,at=fixture.at,ev_kwh=value,ev_state_known=True,pv_ac_kw=20,
                            ev_observed_at=None,ev_progress=None))
        assert app.ev_valid
        command=await apply(app,fixture)
        assert command.current_a==0 and not command.prepare_phase
    assert app.controller.ev_task['completed']
    snapshot=app.build_snapshot()
    assert snapshot.execution['running_task'] is None
    assert not any(item['power_kw'] for item in snapshot.execution['commitments'])
    assert any(c[2].get('option')=='1' and c[2]['entity_id']==fixture.actuators['force'] for c in fixture.calls)
    app.store.close()


def test_completed_task_does_not_block_a_distinct_future_task_in_the_same_accepted_plan():
    from energymanager.control import FastControl
    s=tiny(hours=1)
    powers=[2.3 if t<2 or 6<=t<8 else 0 for t in range(len(s.intervals))]
    plan=result_for(s,scheduled_flows(s,powers))
    control=FastControl(s.capabilities,s.policy)
    assert control.tick(s.observation,s.observation.at,plan,1).current_a>0
    endpoint=control.ev_task['target']
    completed=replace(s.observation,at=s.observation.at+timedelta(seconds=5),ev_kwh=endpoint)
    assert control.tick(completed,completed.at,plan,1).current_a==0
    assert control.ev_task['completed']
    later=replace(s.observation,at=s.intervals[6].start,ev_kwh=endpoint-.1)
    assert control.tick(later,later.at,plan,1).current_a>0
    assert not control.ev_task.get('completed')


@pytest.mark.parametrize('cause',['unknown','disconnect','revoked','expired','peak'])
async def test_continuity_keeps_required_stops_and_real_fake_actuator_protection(tmp_path,cause):
    app,fixture=running_app(tmp_path)
    await apply(app,fixture)
    fixture.calls.clear()
    fixture.refresh(3601 if cause=='expired' else 5)
    observation=replace(app.observation,at=fixture.at,ev_kwh=9.594,ev_state_known=True,
        ev_observed_at=None,ev_progress=None)
    app.ha.inputs.readings['ev_total_kwh']=meter((fixture.at-AT).total_seconds(),100)
    app.observe(observation)
    if cause=='unknown':
        app.observation=replace(app.observation,ev_state_known=False)
    elif cause=='disconnect':
        app.observe(replace(observation,connected=False))
    elif cause=='revoked':
        app.invalidate('SYNTHETIC revoked goal/source permission',ev=True,ess=False)
    elif cause=='peak':
        app.observation=replace(app.observation,house_kw=30)
    command=await apply(app,fixture)
    assert command.current_a==0
    assert any(c[2].get('option')=='1' and c[2]['entity_id']==fixture.actuators['force'] for c in fixture.calls)
    app.store.close()
