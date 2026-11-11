"""Integrated joint-model running corrections, fake service and shared allowance."""

from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.domain import Goal
from energymanager.execution import freeze_execution
from energymanager.optimization import JointModel
from energymanager.planner import Planner
from energymanager.validation import validate
from test_first_slice import tiny
from test_publication_closed_loop import result_for


def running_case(delta=.0666, *, deadline_hours=3, pv=0, price=.3, ess=2.8, vary_current=False):
    s=tiny(hours=deadline_hours,ev=23.4-2.76*2*.9,ess=ess,house=.6,
        planning_budget_seconds=16,completion_margin_minutes=0,normal_soc_percent=50,
        ev_value_eur_kwh=0,ess_value_eur_kwh=0,
        import_eur_kwh=price,export_eur_kwh=min(.05,price))
    start=s.observation.at
    end=start+timedelta(hours=2)
    goal=Goal('g','SYNTHETIC required 50%',s.intervals[-1].end,50)
    s=replace(s,goals=(goal,),capabilities=replace(s.capabilities,ev_capacity_kwh=46.8),
        observation=replace(s.observation,ev_power_kw=3.68 if vary_current else 2.76,monthly_peak_kw=4.95),
        intervals=tuple(replace(i,pv_ac_kw=pv if i.start<start+timedelta(hours=1) else 0) for i in s.intervals))
    model=JointModel(s)
    for t,i in enumerate(s.intervals):
        amps=12 if i.start<end else 0
        if amps and vary_current:
            amps=16 if i.start<start+timedelta(hours=1) else 8
        for name,value in (('one',int(amps>0)),('three',0),('amps_one',amps),('amps_three',0)):
            model.linear.equality([(model.linear.variables[name][t],1)],value)
    seed=model.run(2)
    assert seed['feasible'],seed['status']
    assert not validate(s,seed['flows'])
    old=result_for(s,seed['flows'])
    updated=replace(s,revision=2,observation=replace(s.observation,ev_kwh=s.observation.ev_kwh+delta))
    return freeze_execution(updated,old,{'phase':1,'ready_at':start.isoformat()}),old


@pytest.mark.parametrize('delta,vary_current',[(.0666,False),(-.207,False),(.0666,True)])
def test_small_correction_changes_finish_only_at_equal_useful_delivery(delta,vary_current):
    s,old=running_case(delta,vary_current=vary_current)
    result=Planner().plan(s)
    assert result['valid'],result.get('reason')
    review=result['running_task_review']
    assert review['status']=='finish_only',review
    assert not validate(s,result['flows'],result['service'])
    assert not any(result['flows']['three'])
    assert review['comparison']['matching_stock'][str(len(s.intervals))]==pytest.approx(23.4)
    assert (review['context']['finish_at']<review['context']['old_end'])==(delta>0)
    if vary_current:
        for t,i in enumerate(s.intervals):
            if i.start.isoformat()<review['context']['finish_at']:
                assert result['flows']['amps_one'][t]==pytest.approx(16 if i.start<s.observation.at+timedelta(hours=1) else 8)


def test_earlier_current_change_outranks_later_phase_change_but_necessary_phase_can_serve_required_goal():
    from copy import deepcopy
    from energymanager.deadline_audit import validate_certificate
    s,old=running_case(-.8,deadline_hours=2)
    result=Planner().plan(s)
    assert result['valid'],result.get('reason')
    assert not any(result['flows']['three'])
    assert result['running_task_review']['phase_necessity']['status']=='same_phase_feasible'
    assert any(a!=12 for a in result['flows']['amps_one'] if a>0)
    necessary,old=running_case(-1.932,deadline_hours=2)
    result=Planner().plan(necessary)
    assert result['valid'],(result.get('reason'),result.get('running_task_review'))
    assert result['running_task_review']['phase_necessity']['status']=='Infeasible'
    assert any(result['flows']['three'])
    assert not validate(necessary,result['flows'],result['service'])
    certificate=result['deadline_guard']
    assert certificate['status']=='certified'
    assert not validate_certificate(certificate)
    invalid=deepcopy(certificate)
    invalid.pop('phase_necessity')
    assert any('phase change' in error for error in validate_certificate(invalid))


def test_unknown_same_phase_search_cannot_authorize_a_phase_switch(monkeypatch):
    s,old=running_case(-1.932,deadline_hours=2)
    original=Planner.run_model
    def timeout(self,name,model,allowance,*args,**kwargs):
        if name.startswith('required_reference'):
            return {'feasible':False,'status':'Time limit reached','values':None,'flows':{}}
        return original(self,name,model,allowance,*args,**kwargs)
    monkeypatch.setattr(Planner,'run_model',timeout)
    result=Planner().plan(s)
    assert not result['valid']
    assert not any(stage['name']=='required_reference_necessary_phase' for stage in result['stages'])


def test_unfinished_joint_support_search_is_not_a_same_phase_necessity_proof(monkeypatch):
    s,old=running_case(-1.932,deadline_hours=2)
    original=Planner.run_model
    def timeout(self,name,model,allowance,*args,**kwargs):
        if name in ('required_ess_support','running_phase_necessity'):
            return {'feasible':False,'status':'Time limit reached','values':None,'flows':{}}
        return original(self,name,model,allowance,*args,**kwargs)
    monkeypatch.setattr(Planner,'run_model',timeout)
    result=Planner().plan(s)
    assert not result['valid']
    assert result['running_task_review']['status']=='unverified'
    assert result['running_task_review']['attempts'][-1]['name']=='running_phase_necessity'


def test_rolling_limits_can_add_origins_without_replacing_old_evidence_or_variables():
    s,old=running_case()
    model=JointModel(s,optional=True)
    reference=JointModel(s).run(2)
    assert reference['feasible']
    model.add_rolling_limits(reference['flows'],origins={0})
    prefix=list(model.linear.variables['rolling_cash_prefix'])
    count=len(model.linear.lower)
    model.add_rolling_limits(reference['flows'],origins={0,1})
    assert model.linear.variables['rolling_cash_prefix']==prefix
    assert set(model.rolling_metadata)=={0,1}
    assert len(model.linear.lower)>count


@pytest.mark.parametrize('price,expected',[(.1,'finish_only'),(.4,'earlier_economic_exception')])
def test_whole_joint_ess_ev_economics_on_both_sides_of_shared_two_cent_envelope(price,expected):
    s,old=running_case(price=price,pv=4.5)
    result=Planner().plan(s)
    assert result['valid'],result.get('running_task_review')
    review=result['running_task_review']
    assert review['status']==expected,review
    assert not any(result['flows']['three'])
    assert not validate(s,result['flows'],result['service'])
    attempts={a['name']:a for a in review['attempts']}
    tail=attempts['running_finish_only']
    seed=attempts['running_economic_seed']
    assert seed['ev_terminal_kwh']==pytest.approx(tail['ev_terminal_kwh'])
    benefit=tail['comparison_eur']-seed['comparison_eur']
    assert (benefit>.02)==(expected=='earlier_economic_exception')
    assert review['allowance']['spent_eur']<=.02


def test_same_running_task_carries_one_allowance_across_updates_and_handover():
    from energymanager.publication import execution_source
    s,old=running_case(price=.1,pv=4.5)
    first=Planner().plan(s)
    assert first['valid']
    allowance=first['running_allowance']
    assert 0<allowance['spent_eur']<=.02
    thin=execution_source(first,s.observation.at)
    assert thin['running_allowance']==allowance
    current=freeze_execution(replace(s,execution=None),first,
        {'phase':1,'ready_at':s.observation.at.isoformat()})
    assert current.execution['running_task']['allowance']=={'task_key':allowance['task_key'],'spent_eur':allowance['spent_eur']}
    second=Planner().plan(current)
    assert second['valid'],second.get('running_task_review')
    assert second['running_allowance']['task_key']==allowance['task_key']
    assert second['running_allowance']['spent_eur']==pytest.approx(allowance['spent_eur'],abs=1e-5)
    assert second['running_allowance']['remaining_eur']<=.02-allowance['spent_eur']+1e-5


def test_ev_pv_alone_cannot_buy_an_earlier_change_at_the_expense_of_useful_ess_stock():
    from copy import deepcopy
    from time import monotonic
    from energymanager.running_task import earlier_current_profile, phase_lock, pin_profile, profile_on_grid, review_running
    s,old=running_case(price=.4,pv=4.5,ess=7)
    s=replace(s,policy=replace(s.policy,ess_value_eur_kwh=1))
    model=JointModel(s)
    phase_lock(model,1,s.execution['running_task']['deadline'])
    selected=model.run(2)
    assert selected['feasible']
    planner=Planner()
    planner.started=monotonic()
    planner.deadline=planner.started+20
    chosen,review=review_running(planner,model,selected,
        model.value(model.economic,selected['values']),model.value(model.cash,selected['values']))
    assert chosen and review['status']=='finish_only',review
    assert not validate(s,chosen['flows'])
    scope=len(s.intervals)
    modes=profile_on_grid(model,s.execution['running_task'])
    finish=s.execution['running_task']['finish_at']
    modes=[mode if i.start.isoformat()<finish else (0,0) for mode,i in zip(modes,s.intervals)]
    seed=earlier_current_profile(model,modes,scope)
    assert seed is not None
    candidate=deepcopy(model)
    pin_profile(candidate,seed,scope)
    candidate.linear.equality([(candidate.linear.variables['ev_energy'][-1],1)],chosen['flows']['ev_energy'][-1])
    solar=sum(chosen['flows']['pv_ev'][t]*i.hours for t,i in enumerate(s.intervals))
    candidate.linear.row([(candidate.linear.variables['pv_ev'][t],i.hours) for t,i in enumerate(s.intervals)],
        lower=solar+.2)
    alternative=candidate.run(2,objective=candidate.economic)
    assert alternative['feasible'] and not validate(s,alternative['flows'])
    assert candidate.value(candidate.economic,alternative['values'])>=review['comparison']['economic_eur']-1e-5
    assert alternative['flows']['ess_solar'][-1]<chosen['flows']['ess_solar'][-1]


@pytest.mark.parametrize('pending',[False,True])
async def test_checked_running_replacement_handover_preserves_actual_fake_charger_sequence(pending):
    from energymanager.control import FastControl
    from energymanager.publication import admit
    from test_goe import ChargerFixture
    s,old=running_case()
    if pending:
        s=replace(s,observation=replace(s.observation,ev_power_kw=0))
    control=FastControl(s.capabilities,s.policy)
    fixture=ChargerFixture()
    fixture.at=s.observation.at
    fixture.actuator.now=lambda:fixture.at
    fixture.set('force',1 if pending else 2)
    fixture.set('current',12)
    fixture.actuator.c=s.capabilities
    fixture.actuator.resume_after=fixture.at-timedelta(seconds=1)
    generation=1
    fixture.actuator.generation=lambda:generation
    fixture.set('heartbeat',1)
    fixture.readings.heartbeat=0
    fixture.refresh(0,heartbeat=False)
    if pending:
        fixture.ignore.add(fixture.actuators['force'])
    before=control.tick(s.observation,fixture.at,old,generation)
    await fixture.actuator.apply(before,generation,s.observation)
    acknowledgement=dict(fixture.actuator.goe_control.pending)
    assert not fixture.actuator.delivery_fault
    if pending:
        assert 'force' in acknowledgement
    fixture.calls.clear()
    result=Planner().plan(s)
    assert result['valid']
    accepted,errors=admit(s,result,s.observation,fixture.at,previous_plan=old,previous_authority=(True,True,True))
    assert not errors,errors
    generation=2
    after=control.tick(s.observation,fixture.at,accepted,generation)
    await fixture.actuator.apply(after,generation,s.observation)
    assert before.current_a==after.current_a==12 and before.phases==after.phases==1
    assert not any(call[2]['entity_id'] in (fixture.actuators['force'],fixture.actuators['phase']) for call in fixture.calls)
    if pending:
        assert fixture.actuator.goe_control.pending['force']==acknowledgement['force']
