"""Ingress boundary and GUI HTTP contract, using real archives and isolated HiGHS workers."""
import asyncio
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer
from test_v3 import NOW, frame, snapshot

from energymanager.decision_store import DecisionStore
from energymanager.explanation_api import ExplanationAPI
from energymanager.requirements import explain_ev_tasks

HEADERS = {"X-Ingress-Path": "/api/hassio_ingress/test-token", "X-EnergyManager-Request": "1"}


@pytest.fixture
def archive(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(Path('energymanager/src').resolve()))
    base = frame()
    base = replace(base, requirements=explain_ev_tasks(base.tasks, base.actuator_snapshots, NOW))
    frozen = snapshot(base, previous_plan=base)
    store = DecisionStore(tmp_path)
    store.save(frozen, frozen.solve(), disposition="accepted", changes={"trigger": "test"})
    return store, frozen


async def client_for(store, **kwargs):
    api = ExplanationAPI(store, trusted_peer="127.0.0.1", cooldown=0, **kwargs)
    client = TestClient(TestServer(api.app()))
    await client.start_server()
    return api, client


@pytest.mark.asyncio
async def test_history_selection_counterfactual_and_no_archive_mutation(archive):
    store, snapshot = archive
    before = {p.name: p.read_bytes() for p in store.root.iterdir()}
    api, client = await client_for(store)
    try:
        history = await (await client.get('/api/decisions', headers=HEADERS)).json()
        assert history['decisions'][0]['snapshot_id'] == snapshot.snapshot_id
        decision = await (await client.get('/api/decisions/' + snapshot.snapshot_id, headers=HEADERS)).json()
        assert decision['evaluation']['quality']['physical_validation'] == 'passed'
        assert {'Requirement', 'Interval', 'EV session'}.issubset({s['kind'] for s in decision['selections']})
        assert decision['previous_intervals'] and decision['requirements'][0]['provenance']['formula']
        assert 'unique reason' in decision['limitation']
        response = await client.post('/api/counterfactuals', headers=HEADERS, json={
            'snapshot_id': snapshot.snapshot_id, 'kind': 'forbid_ess_discharge', 'start_index': 0, 'end_index': 4})
        assert response.status == 202, await response.text()
        job = (await response.json())['job_id']
        await asyncio.wait_for(api.task, 15)
        result = await (await client.get('/api/counterfactuals/' + job, headers=HEADERS)).json()
        assert result['status'] == 'completed', result
        assert result['result']['alternative']['adoption_ready']
        assert all((slot['ess_ac_power_w'] or 0) <= 1e-4
                   for slot in result['result']['alternative']['intervals'][:4])
        assert result['result']['economic_confidence']['baseline']['status']
        assert before == {p.name: p.read_bytes() for p in store.root.iterdir()}
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_auth_csrf_invalid_input_corruption_and_retention(archive):
    store, frozen = archive
    api, client = await client_for(store)
    try:
        assert (await client.get('/api/decisions')).status == 401
        assert (await client.get('/api/decisions', headers={'X-Forwarded-For': '172.30.32.2'})).status == 401
        assert (await client.post('/api/counterfactuals', headers={'X-Ingress-Path': HEADERS['X-Ingress-Path']},
                                  json={})).status == 403
        assert (await client.get('/api/decisions?offset=-1', headers=HEADERS)).status == 400
        assert (await client.post('/api/counterfactuals', headers=HEADERS, json={
            'snapshot_id': frozen.snapshot_id, 'kind': 'forbid_ev', 'start_index': True, 'end_index': 4})).status == 400
        assert (await client.post('/api/counterfactuals', headers=HEADERS, data='x' * 3000)).status == 415
        assert (await client.post('/api/counterfactuals',
                                  headers={**HEADERS, 'Content-Type': 'application/json'},
                                  data='{"padding":"' + 'x' * 3000 + '"}')).status == 413
        api.reading = 2
        assert (await client.get('/api/decisions', headers=HEADERS)).status == 429
        api.reading = 0
        api.trusted_peer = '172.30.32.2'
        assert (await client.get('/api/decisions', headers=HEADERS)).status == 401
        api.trusted_peer = '127.0.0.1'
        path = store.root / (frozen.snapshot_id + '.json.gz')
        path.write_bytes(b'corrupt')
        assert (await client.get('/api/decisions/' + frozen.snapshot_id, headers=HEADERS)).status == 400
        history = await (await client.get('/api/decisions', headers=HEADERS)).json()
        assert history['decisions'][0]['status'] == 'unavailable_or_corrupt'
        path.unlink()
        assert (await client.get('/api/decisions/' + frozen.snapshot_id, headers=HEADERS)).status == 404
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_concurrency_live_priority_timeout_expiry_and_cleanup(archive):
    store, frozen = archive
    api, client = await client_for(store, timeout=.001)
    body = {'snapshot_id': frozen.snapshot_id, 'kind': 'forbid_ev', 'start_index': 0, 'end_index': 4}
    try:
        api.live_busy = lambda: True
        assert (await client.post('/api/counterfactuals', headers=HEADERS, json=body)).status == 409
        api.live_busy = lambda: False
        responses = await asyncio.gather(*[client.post('/api/counterfactuals', headers=HEADERS, json=body)
                                           for _ in range(2)])
        assert sorted(r.status for r in responses) in ([202, 429], [202, 409])
        accepted = next(r for r in responses if r.status == 202)
        job = (await accepted.json())['job_id']
        await api.task
        assert api.jobs[job]['status'] == 'timeout'
        api.cooldown = 30
        assert (await client.post('/api/counterfactuals', headers=HEADERS, json=body)).status == 429
        api.jobs[job]['created'] -= 901
        assert (await client.get('/api/counterfactuals/' + job, headers=HEADERS)).status == 404
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_dashboard_javascript_through_real_http_backend(archive):
    store, _ = archive
    api, client = await client_for(store)
    try:
        environment = {**os.environ, 'V3_API_URL': str(client.make_url('')).rstrip('/')}
        process = await asyncio.create_subprocess_exec('node', 'tools/check_v3_dashboard.cjs', env=environment,
                                                       stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        stdout, _ = await asyncio.wait_for(process.communicate(), 20)
        assert process.returncode == 0, stdout.decode()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_failed_worker_result_is_reported(archive, monkeypatch):
    store, frozen = archive
    api, client = await client_for(store)
    original = asyncio.create_subprocess_exec

    async def failed(*args, **kwargs):
        return await original(sys.executable, '-c', 'import sys; sys.exit(2)', **kwargs)
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', failed)
    try:
        response = await client.post('/api/counterfactuals', headers=HEADERS, json={
            'snapshot_id': frozen.snapshot_id, 'kind': 'forbid_ev', 'start_index': 0, 'end_index': 4})
        job = (await response.json())['job_id']
        await api.task
        assert api.jobs[job]['status'] == 'failed'
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_history_pagination_and_generic_job_storage_selection(archive):
    from datetime import timedelta

    from energymanager.requirements import FlexibleJob, Provenance, Requirement, StorageResource

    store, frozen = archive
    _, document = store.read(frozen.snapshot_id)
    for index in range(21):
        later = snapshot(replace(frame(), generated_at_utc=NOW + timedelta(seconds=index + 1)))
        store.save(later, document['evaluation'], disposition='superseded')
    provenance = Provenance('test', '1', NOW, (), 'valid', 'energy / efficiency', ())
    job = FlexibleJob('wash', 'washer', NOW, NOW + timedelta(hours=2), 1, 2, provenance)
    resource = StorageResource('thermal', 5, 1, 0, .9)
    requirement = Requirement('water', 'thermal', 'state_by_deadline', True, 2, 'kWh', NOW,
                              NOW + timedelta(hours=2), True, provenance)
    generic = snapshot(replace(frame(), jobs=(job,), resources=(resource,), requirements=(requirement,)))
    store.save(generic, generic.solve(), disposition='accepted')
    _, client = await client_for(store)
    try:
        first = await (await client.get('/api/decisions', headers=HEADERS)).json()
        assert len(first['decisions']) == 20 and first['next_offset'] == 20
        last = await (await client.get('/api/decisions?offset=20', headers=HEADERS)).json()
        assert len(last['decisions']) == 3 and last['next_offset'] is None
        view = await (await client.get('/api/decisions/' + generic.snapshot_id, headers=HEADERS)).json()
        assert any(s['kind'] == 'Job' and s['label'] == 'wash' for s in view['selections'])
        assert view['resources'][0]['resource_id'] == 'thermal'
        assert view['stage_intervals']
        assert view['evaluation']['quality']['stages'][1]['objective_improvement'] is not None
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_shutdown_terminates_and_reaps_diagnostic_worker(archive, monkeypatch):
    store, frozen = archive
    api, client = await client_for(store)
    original = asyncio.create_subprocess_exec
    started = asyncio.Event()
    processes = []

    async def slow_worker(*args, **kwargs):
        process = await original(sys.executable, '-c', 'import time; time.sleep(30)', **kwargs)
        processes.append(process)
        started.set()
        return process
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', slow_worker)
    response = await client.post('/api/counterfactuals', headers=HEADERS, json={
        'snapshot_id': frozen.snapshot_id, 'kind': 'forbid_ev', 'start_index': 0, 'end_index': 4})
    assert response.status == 202
    await asyncio.wait_for(started.wait(), 2)
    await client.close()
    assert api.task.done()
    assert processes[0].returncode is not None
