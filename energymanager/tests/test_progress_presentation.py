"""Current source warnings with synthetic stores; saved decisions/notifications stay intact."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

from energymanager.domain import Goal
from energymanager.ev_progress import EVProgress, progress_warning
from energymanager.service import Application
from energymanager.store import Store
from test_ev_progress import AT, C, P, meter, sample
from test_first_slice import tiny


def test_one_current_source_warning_recovers_without_replanning_or_changing_other_issues(tmp_path):
    store = Store(tmp_path / 'synthetic.sqlite')
    s = tiny()
    app = Application(store, snapshot=replace(s, observation=sample()))
    app.now = lambda: AT
    app.goals = (Goal('g1', 'SYNTHETIC trip', AT + timedelta(hours=1), 60),
                 Goal('g2', 'SYNTHETIC trip', AT + timedelta(hours=3), 70))
    app.observation = app.ev_progress.update(sample(), None, '', C, P)
    blocked = [{'id': g.id, 'revision': g.revision, 'status': 'progress_unavailable', 'shortfall_kwh': None}
               for g in app.goals]
    app.accepted = {'id': 'SYNTHETIC frozen result', 'goals': blocked}
    app.update_issues({'goals': blocked})
    other = [{'goal_id': 'independent', 'revision': 1, 'state': 'pending', 'shortfall_kwh': 2, 'proposed_peak_kw': 5},
             {'kind': 'deadline_margin', 'id': 'margin'}, {'kind': 'planning', 'id': 'failure'}]
    raw = store.get('issues')
    raw.update({str(t): row for t, row in enumerate(other)})
    store.put('issues', raw)
    before = deepcopy(store.get('issues'))
    state = app.state()
    warning = state['display_issues'][0]
    assert warning['cause'] == 'counter_unmapped' and 'save and restart' in warning['action']
    assert len(state['display_issues']) == 4
    affected = warning['affected_goals']
    assert {'g1', 'g2'} <= {g['id'] for g in affected}
    assert len({g['id'] for g in affected}) == len(affected)
    assert [g['deadline'] for g in affected] == sorted(g['deadline'] for g in affected)
    assert len([g for g in affected if g['title'] == 'Morning minimum']) >= 6
    app.goals = (replace(app.goals[0], revision=2), app.goals[1])
    assert app.state()['display_issues'][0]['id'] == warning['id']
    assert next(g for g in app.state()['display_issues'][0]['affected_goals'] if g['id'] == 'g1')['revision'] == 2
    app.observation = app.ev_progress.update(sample(), meter(0, 100), 'sensor.synthetic_eto', C, P)
    recovered = app.state()
    assert recovered['ev_progress_usable'] and recovered['display_issues'] == other
    assert app.accepted['id'] == 'SYNTHETIC frozen result'
    assert app.accepted['goals'] == blocked  # No result or fulfillment repair.
    assert store.get('issues') == before
    assert recovered['plan_authority'] == {'ev': False, 'ess': False, 'conditional': False}
    app.ess_valid = True
    assert app.state()['plan_authority']['ess'] and not app.state()['plan_authority']['ev']
    store.close()


def test_failure_stall_and_true_return_have_different_source_causes_and_actions(tmp_path):
    store = Store(tmp_path / 'synthetic.sqlite')
    progress = EVProgress(store)
    progress.update(sample(), meter(0, 100), 'sensor.synthetic_eto', C, P)
    failed = progress.update(sample(31), None, 'sensor.synthetic_eto', C, P)
    warning = progress_warning(failed, failed.at, ())
    assert warning['cause'] == 'counter_unavailable' and 'Wh/kWh' in warning['action']
    assert 'reconnect' not in warning['action'].lower()
    progress.update(replace(sample(40), ev_power_kw=1.38), meter(40, 100), 'sensor.synthetic_eto', C, P)
    stalled = progress.update(replace(sample(71), ev_power_kw=1.38), meter(71, 100), 'sensor.synthetic_eto', C, P)
    assert progress_warning(stalled, stalled.at, ())['cause'] == 'counter_stalled'
    trip = Goal('trip', 'SYNTHETIC departure', AT + timedelta(seconds=80), kind='trip', distance_km=20)
    progress.update(sample(75, connected=False), meter(75, 100), 'sensor.synthetic_eto', C, P, (trip,))
    returned = progress.update(sample(85), meter(85, 100), 'sensor.synthetic_eto', C, P, (trip,))
    warning = progress_warning(returned, returned.at, ())
    assert warning['cause'] == 'post_trip' and 'post-trip vehicle SoC' in warning['action']
    assert 'counter' not in warning['title'].lower()
    store.close()


def test_read_watchdog_updates_operational_warning_without_a_new_observation(tmp_path):
    store = Store(tmp_path / 'synthetic.sqlite')
    o = EVProgress(store).update(sample(), meter(0, 100), 'sensor.synthetic_eto', C, P)
    assert progress_warning(o, AT, ()) is None
    assert progress_warning(o, AT + timedelta(seconds=31), ())['cause'] == 'counter_unavailable'
    fresh_vehicle = EVProgress(store).update(sample(vehicle_at=AT), None, '', C, P)
    assert progress_warning(fresh_vehicle, AT, ()) is None
    assert progress_warning(fresh_vehicle, AT + timedelta(seconds=31), ())['cause'] == 'counter_unmapped'
    store.close()
