"""Labelled synthetic Diagnostics export and lifecycle evidence."""
import asyncio
import hashlib
import json
import sqlite3
import time
import zipfile
from datetime import UTC, datetime

import pytest
from aiohttp.test_utils import TestClient, TestServer

from energymanager.diagnostics import Diagnostics, decode_archive
from energymanager.domain import encode
from energymanager.service import Application
from energymanager.store import Store
from energymanager.web import create_web
from test_first_slice import tiny


def fixture(path):
    store = Store(path)
    snapshot = tiny()
    for identity, at, disposition, legacy in (
        ('before', '2026-10-22T12:00:00+00:00', 'accepted', True),
        ('accepted', '2026-10-23T01:00:00+00:00', 'accepted', False),
        ('rejected', '2026-10-23T02:00:00+00:00', 'rejected', True),
        ('corrupt', '2026-10-23T03:00:00+00:00', 'rejected', False),
    ):
        store.record(snapshot, {'id': identity, 'status': 'SYNTHETIC', 'flows': {'ev': [0.123456789012345]}}, disposition)
        store.connection.execute('UPDATE decisions SET at=? WHERE id=?', (at, identity))
        if legacy:
            store.connection.execute('UPDATE decisions SET snapshot=?,result=? WHERE id=?',
                                     (encode(snapshot), json.dumps({'id': identity}), identity))
    store.connection.execute("UPDATE decisions SET digest='bad' WHERE id='corrupt'")
    events = [
        ('2026-10-22T10:00:00+00:00', 'observed', {'at': '2026-10-22T10:00:00+00:00', 'house_kw': 1}),
        ('2026-10-22T13:00:00+00:00', 'hardware_control', {'enabled': False}),
        ('2026-10-23T03:00:00+00:00', 'measurement', {'at': '2026-10-23T01:00:00+00:00', 'house_kw': 2, 'quality': None}),
        ('2026-10-25T03:00:00+00:00', 'measurement', {'at': '2026-10-23T01:01:00+00:00', 'house_kw': 3}),
        ('2026-10-23T04:00:00+00:00', 'measurement', {'at': '2026-10-23T02:00:00+00:00', 'house_kw': 4}),
        ('invalid', 'measurement', {'at': 'invalid', 'house_kw': 5}),
        ('2026-10-23T04:00:00+00:00', 'notification_queued', {'message': 'PRIVATE NOTIFICATION'}),
        ('2026-10-23T04:00:00+00:00', 'actuator_error', {'reason': 'Bearer planted-secret-value'}),
        ('2026-10-23T04:00:00+00:00', 'measurement', {'at': '2026-10-23T04:00:00+00:00', 'token': 'SECRET'}),
    ]
    store.connection.executemany('INSERT INTO events(at,kind,body) VALUES (?,?,?)',
                                 [(at, kind, json.dumps(body)) for at, kind, body in events])
    store.connection.executemany('INSERT INTO load_samples VALUES (?,?)', [(datetime(2026, 10, day, tzinfo=UTC).timestamp(), 123.4) for day in (22, 23, 24)])
    store.put('private', {'token': 'STATE-SECRET'})
    store.connection.commit()
    store.close()


def wait(manager):
    manager.future.result(timeout=20)
    return manager.status()['job']


def test_consistent_archive_selection_boundary_hashes_and_privacy(tmp_path):
    source = tmp_path / 'synthetic.sqlite'
    fixture(source)
    manager = Diagnostics(source, 'Europe/Brussels')
    manager.initialize()
    manager.start('dataset', {'start': '2026-10-23T00:00:00Z', 'end': '2026-10-24T00:00:00Z'})
    job = wait(manager)
    assert job['state'] == 'ready', job
    with zipfile.ZipFile(manager.acquire(job['id'], 'dataset')) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        for name, metadata in manifest['members'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == metadata['sha256']
        decisions = [json.loads(line) for line in archive.read('decisions.jsonl').splitlines()]
        assert {row['id'] for row in decisions} == {'before', 'accepted', 'rejected'}
        for row in decisions:
            assert hashlib.sha256(archive.read(row['snapshot'])).hexdigest() == row['digest']
            assert archive.read(row['snapshot']) == encode(tiny()).encode()
        events = [json.loads(line) for line in archive.read('events.jsonl').splitlines()]
        late = next(row for row in events if row['sequence'] == 4)
        assert late['selection_reasons'] == ['observation_time']
        assert len({row['sequence'] for row in events}) == len(events)
        boundary = [json.loads(line) for line in archive.read('boundary-events.jsonl').splitlines()]
        assert {row['sequence'] for row in boundary} == {1, 2}
        coverage = json.loads(archive.read('coverage.json'))
        assert coverage['boundary']['accepted_decision_included']
        assert coverage['boundary']['missing_observation_context'] == ['measurement']
        assert coverage['omissions']['corrupt_sensitive_or_unsupported_decision'] == 1
        assert coverage['series']['measurement']['gap_count'] >= 1
        assert coverage['event_kinds']['notification_queued']['supported'] is False
        payload = b' '.join(archive.read(name) for name in archive.namelist())
        assert b'planted-secret-value' not in payload and b'STATE-SECRET' not in payload and b'PRIVATE NOTIFICATION' not in payload
        assert b'"token"' not in payload
    manager.release(job['id'])
    assert not (manager.root / job['id'] / 'snapshot.sqlite').exists()
    manager.executor.shutdown()


def test_coverage_empty_period_duplicate_cancel_and_restart(tmp_path):
    source = tmp_path / 'synthetic.sqlite'
    fixture(source)
    manager = Diagnostics(source, 'Europe/Brussels')
    manager.initialize()
    manager.start('coverage', {})
    coverage_job = wait(manager)
    assert coverage_job['state'] == 'ready', coverage_job
    assert coverage_job['coverage']['load_samples']['stored'] == 3
    manager.start('dataset', {'start': '2020-01-01T00:00:00Z', 'end': '2020-01-02T00:00:00Z'})
    job = wait(manager)
    assert job['state'] == 'failed' and 'No records' in job['stage']
    assert not (manager.root / job['id']).exists()
    manager.start('coverage', {})
    identity = manager.job['id']
    manager.start('coverage', {})
    assert manager.job['id'] == identity
    manager.action(identity, 'cancel')
    assert wait(manager)['state'] == 'cancelled'
    assert not (manager.root / identity).exists()
    (manager.root / 'orphan').mkdir()
    (manager.root / 'orphan' / 'partial').write_text('private')
    manager.initialize()
    assert manager.job['state'] == 'interrupted' and not (manager.root / 'orphan').exists()
    manager.executor.shutdown()


def test_disk_failure_and_download_expiry_protection(tmp_path, monkeypatch):
    source = tmp_path / 'synthetic.sqlite'
    fixture(source)
    manager = Diagnostics(source, 'Europe/Brussels')
    manager.initialize()
    manager.start('coverage', {})
    job = wait(manager)
    manager.acquire(job['id'], 'coverage')
    manager.job['expires_epoch'] = time.time() - 1
    manager.artifacts[job['id']]['expires_epoch'] = time.time() - 1
    manager.expire()
    assert manager.job['state'] == 'ready'
    with pytest.raises(ValueError, match='active downloads'):
        manager.action(job['id'], 'delete')
    manager.release(job['id'])
    manager.expire()
    assert manager.job['state'] == 'expired'
    import energymanager.diagnostics as module
    monkeypatch.setattr(module, 'RESERVE_BYTES', 10**30)
    manager.start('coverage', {})
    failed = wait(manager)
    assert failed['state'] == 'failed' and 'headroom' in failed['stage']
    assert not (manager.root / failed['id']).exists()
    manager.executor.shutdown()


def test_bounded_archive_and_unsupported_schema(tmp_path):
    import zlib
    import energymanager.diagnostics as module
    original = module.MAX_RECORD_BYTES
    module.MAX_RECORD_BYTES = 100
    try:
        with pytest.raises(ValueError):
            decode_archive(zlib.compress(b'a' * 1000))
    finally:
        module.MAX_RECORD_BYTES = original
    source = tmp_path / 'old.sqlite'
    sqlite3.connect(source).close()
    manager = Diagnostics(source, 'UTC')
    manager.initialize()
    manager.start('coverage', {})
    assert 'Unsupported SQLite schema' in wait(manager)['stage']
    manager.executor.shutdown()


async def test_browser_api_download_boundary_and_no_operational_mutation(tmp_path):
    store = Store(tmp_path / 'synthetic.sqlite')
    snapshot = tiny()
    store.record(snapshot, {'id': 'synthetic', 'status': 'accepted'}, 'accepted')
    application = Application(store, snapshot=snapshot)
    # Keep this fixture deterministic; exercise the web lifecycle without starting control/planning.
    async def noop():
        pass
    application.start = noop
    application.close = noop
    async with TestClient(TestServer(create_web(application))) as client:
        assert (await (await client.get('/api/diagnostics')).json())['job'] is None
        headers = {'X-EnergyManager': '1'}
        assert (await client.post('/api/diagnostics/coverage', json={})).status == 403
        assert (await client.post('/api/diagnostics/coverage', json={}, headers={**headers, 'Origin': 'https://attacker.invalid'})).status == 403
        result = await (await client.post('/api/diagnostics/coverage', json={}, headers=headers)).json()
        identity = result['job']['id']
        for _ in range(200):
            status = await (await client.get('/api/diagnostics')).json()
            if status['job']['state'] != 'running':
                break
            await asyncio.sleep(.01)
        assert status['job']['state'] == 'ready', status
        response = await client.get(f'/api/diagnostics/{identity}/download/coverage')
        assert response.status == 200 and response.headers['Cache-Control'] == 'no-store'
        assert (await response.json())['capture']['id'] == identity
        assert (await client.get('/api/diagnostics/not-a-job/download/coverage')).status == 400
        assert (await client.get(f'/api/diagnostics/{identity}/download/snapshot')).status == 400
        assert store.connection.execute('SELECT COUNT(*) FROM events').fetchone()[0] == 0
        assert application.revision == 1
        assert (await client.post(f'/api/diagnostics/{identity}/delete', json={}, headers=headers)).status == 200


def test_retained_artifacts_survive_new_jobs_and_source_is_unchanged(tmp_path):
    source = tmp_path / 'synthetic.sqlite'
    fixture(source)
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    manager = Diagnostics(source, 'UTC')
    manager.initialize()
    manager.start('coverage', {})
    first = wait(manager)
    manager.start('coverage', {})
    second = wait(manager)
    assert first['id'] != second['id']
    assert {item['id'] for item in manager.status()['artifacts']} == {first['id'], second['id']}
    path = manager.acquire(first['id'], 'coverage')
    assert path.exists()
    manager.release(first['id'])
    manager.action(first['id'], 'delete')
    assert len(manager.status()['artifacts']) == 1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    manager.initialize()
    assert manager.job['id'] == second['id'] and manager.job['state'] == 'ready'
    manager.executor.shutdown()


def test_missing_context_predecessors_and_sensitive_original_decisions(tmp_path):
    from dataclasses import replace
    source = tmp_path / 'synthetic.sqlite'
    store = Store(source)
    predecessor = tiny()
    store.record(predecessor, {'id': 'predecessor'}, 'rejected')
    snapshot = replace(predecessor, execution={'running_task': {'plan_id': 'predecessor'}})
    store.record(snapshot, {'id': 'selected'}, 'accepted')
    store.record(predecessor, {'id': 'sensitive', 'reason': 'api_key=PLANTED-KEY'}, 'rejected')
    store.connection.execute("UPDATE decisions SET at='2026-10-20T00:00:00Z' WHERE id='predecessor'")
    store.connection.execute("UPDATE decisions SET at='2026-10-23T00:00:00Z' WHERE id!='predecessor'")
    store.connection.commit()
    store.close()
    manager = Diagnostics(source, 'Europe/Brussels')
    manager.initialize()
    manager.start('dataset', {'start': '2026-10-23T00:00:00Z', 'end': '2026-10-24T00:00:00Z'})
    job = wait(manager)
    assert job['state'] == 'ready', job
    with zipfile.ZipFile(manager.acquire(job['id'], 'dataset')) as archive:
        rows = [json.loads(line) for line in archive.read('decisions.jsonl').splitlines()]
        assert {row['id'] for row in rows} == {'selected', 'predecessor'}
        coverage = json.loads(archive.read('coverage.json'))
        assert coverage['boundary']['missing_accepted_baseline']
        assert coverage['omissions']['corrupt_sensitive_or_unsupported_decision'] == 1
        assert b'PLANTED-KEY' not in b''.join(archive.read(name) for name in archive.namelist())
    manager.release(job['id'])
    manager.executor.shutdown()


def test_worker_failure_timeout_and_packaging_cancellation_remove_partials(tmp_path, monkeypatch):
    import energymanager.diagnostics as module
    source = tmp_path / 'synthetic.sqlite'
    fixture(source)
    manager = Diagnostics(source, 'UTC')
    manager.initialize()
    def failed(*args):
        raise RuntimeError('synthetic worker failure')
    with monkeypatch.context() as patch:
        patch.setattr(manager, 'scan', failed)
        manager.start('coverage', {})
        job = wait(manager)
        assert job['state'] == 'failed' and job['stage'] == 'RuntimeError'
        assert not (manager.root / job['id']).exists()
    with monkeypatch.context() as patch:
        patch.setattr(module, 'MAX_SECONDS', -1)
        manager.start('coverage', {})
        job = wait(manager)
        assert job['state'] == 'failed' and not (manager.root / job['id']).exists()
    original_update = manager.update
    def cancel_packaging(**values):
        original_update(**values)
        if values.get('stage') == 'Packaging':
            manager.cancelled.set()
    monkeypatch.setattr(manager, 'update', cancel_packaging)
    manager.start('dataset', {'start': '2026-10-23T00:00:00Z', 'end': '2026-10-24T00:00:00Z'})
    job = wait(manager)
    assert job['state'] == 'cancelled' and not (manager.root / job['id']).exists()
    manager.executor.shutdown()


def test_disk_reserve_failure_during_packaging_removes_partial_zip(tmp_path, monkeypatch):
    from collections import namedtuple
    import energymanager.diagnostics as module
    source = tmp_path / 'synthetic.sqlite'
    fixture(source)
    manager = Diagnostics(source, 'UTC')
    manager.initialize()
    original_update = manager.update
    def exhaust_disk(**values):
        original_update(**values)
        if values.get('stage') == 'Packaging':
            usage = namedtuple('usage', 'total used free')
            monkeypatch.setattr(module.shutil, 'disk_usage', lambda path: usage(1000, 1000, 0))
            manager.last_check = 0
    monkeypatch.setattr(manager, 'update', exhaust_disk)
    manager.start('dataset', {'start': '2026-10-23T00:00:00Z', 'end': '2026-10-24T00:00:00Z'})
    job = wait(manager)
    assert job['state'] == 'failed' and 'disk reserve' in job['stage']
    assert not (manager.root / job['id']).exists() and not manager.artifacts
    manager.executor.shutdown()
