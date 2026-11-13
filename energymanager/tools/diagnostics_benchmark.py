"""Reproducible offline Diagnostics contention benchmark; never accepts an installation DB."""
from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import os
import sqlite3
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from aiohttp.test_utils import TestClient, TestServer

from dev_workspace import create_run
from energymanager.control import FakeActuator
from energymanager.domain import json_data
from energymanager.forecasts import demo_snapshot
from energymanager.service import Application
from energymanager.store import Store
from energymanager.web import create_web


def peak_memory() -> int:
    if os.name != 'nt':
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    class Memory(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('faults', ctypes.c_ulong),
                    *[(name, ctypes.c_size_t) for name in ('peak', 'working', 'peak_paged', 'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile')]]
    result = Memory()
    result.cb = ctypes.sizeof(result)
    read_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    read_memory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    if not read_memory(ctypes.c_void_p(-1), ctypes.byref(result), result.cb):
        raise ctypes.WinError()
    return result.peak


def seed(path: Path, events: int) -> tuple[int, float, float]:
    store = Store(path)
    snapshot = demo_snapshot()
    at = datetime(2026, 10, 20, tzinfo=UTC)
    # A full seven-day forecast and sizeable result archive, repeated over stored dispositions.
    snapshot = replace(snapshot, provenance='SYNTHETIC Diagnostics benchmark')
    for index in range(60):
        identity = f'synthetic-decision-{index}'
        store.record(snapshot, {'id': identity, 'flows': [json_data(interval) for interval in snapshot.intervals],
                                'status': 'SYNTHETIC benchmark; no solve'}, 'rejected' if index % 3 == 0 else 'accepted')
        store.connection.execute('UPDATE decisions SET at=? WHERE id=?', ((at + timedelta(hours=index)).isoformat(), identity))
    body = json.dumps({'at': '2026-10-23T00:00:00+00:00', 'house_kw': .4, 'ev_kwh': 24.,
                       'ess_kwh': 7., 'quality': 'SYNTHETIC', 'source': 'offline fixture'})
    # Native 0.3-second observations across seven days, inserted in bounded batches.
    start = at.timestamp()
    for offset in range(0, events, 5000):
        rows = []
        for index in range(offset, min(offset + 5000, events)):
            timestamp = start + index * 604800 / events
            observation = body.replace('2026-10-23T00:00:00+00:00', datetime.fromtimestamp(timestamp, UTC).isoformat())
            rows.append((datetime.fromtimestamp(timestamp, UTC).isoformat(), 'measurement', observation))
        store.connection.executemany('INSERT INTO events(at,kind,body) VALUES (?,?,?)', rows)
        store.connection.commit()
    store.connection.execute('DELETE FROM state')
    store.connection.commit()
    decoded = len(json.dumps(json_data(snapshot)).encode())
    store.close()
    return decoded, start, start + 604800


class TimedActuator(FakeActuator):
    def __init__(self) -> None:
        super().__init__()
        self.ticks: list[float] = []

    async def apply(self, command: Any, generation: int, observation: Any) -> None:
        self.ticks.append(time.monotonic())
        await super().apply(command, generation, observation)


async def run(events: int, output: Path | None) -> None:
    directory = create_run('diagnostics-stress', output)
    print(f'SYNTHETIC output: {directory}', flush=True)
    path = directory / 'synthetic.sqlite'
    decoded, start, end = await asyncio.to_thread(seed, path, events)
    source_bytes = path.stat().st_size
    store = Store(path)
    snapshot = demo_snapshot()
    application = Application(store, snapshot=snapshot, policy=replace(snapshot.policy, control_period_seconds=1.0))
    actuator = TimedActuator()
    application.actuator = actuator
    async def start_control() -> None:
        application.control_task = asyncio.create_task(application.control_loop())
    async def stop_control() -> None:
        application.shutdown = True
        application.control_task.cancel()
        await asyncio.gather(application.control_task, return_exceptions=True)
    application.start = start_control  # Only actual control loop; no solver/calendar/network tasks.
    application.close = stop_control
    stop = threading.Event()
    writes = [0]
    def writer() -> None:
        with sqlite3.connect(path, timeout=3) as db:
            while not stop.wait(.05):
                db.execute('INSERT INTO events(at,kind,body) VALUES (?,?,?)',
                           (datetime.now(UTC).isoformat(), 'hardware_control', '{"enabled":false}'))
                db.commit()
                writes[0] += 1
    thread = threading.Thread(target=writer)
    thread.start()
    try:
        async with TestClient(TestServer(create_web(application))) as client:
            latencies: dict[str, list[float]] = {'baseline': [], 'export': []}
            async def observe(phase: str, seconds: float = 0) -> None:
                until = time.monotonic() + seconds
                while True:
                    before = time.monotonic()
                    response = await client.get('/api/state?compact=1')
                    assert response.status == 200
                    await response.read()
                    latencies[phase].append(time.monotonic() - before)
                    if time.monotonic() >= until:
                        break
                    await asyncio.sleep(.05)
            await observe('baseline', 6)
            assert not application.control_task.done(), application.control_task.exception()
            baseline_ticks = list(actuator.ticks)
            assert len(baseline_ticks) >= 5, 'Baseline control did not run'
            actuator.ticks.clear()
            before_revision = application.revision
            before_requests = store.connection.execute("SELECT COUNT(*) FROM events WHERE kind='planning_requested'").fetchone()[0]
            before = time.monotonic()
            response = await client.post('/api/diagnostics/dataset', json={
                'start': datetime.fromtimestamp(start, UTC).isoformat(), 'end': datetime.fromtimestamp(end, UTC).isoformat()},
                headers={'X-EnergyManager': '1'})
            assert response.status == 200
            identity = (await response.json())['job']['id']
            while True:
                await observe('export', .1)
                job = (await (await client.get('/api/diagnostics')).json())['job']
                if job['state'] != 'running':
                    break
            elapsed = time.monotonic() - before
            assert job['state'] == 'ready', job
            assert application.revision == before_revision
            assert store.connection.execute("SELECT COUNT(*) FROM events WHERE kind='planning_requested'").fetchone()[0] == before_requests
            archive_path = directory / 'diagnostics-exports' / identity / 'dataset.zip'
            with ZipFile(archive_path) as archive:
                manifest = json.loads(archive.read('manifest.json'))
                count = sum(1 for line in archive.open('events.jsonl') if json.loads(line)['sequence'] <= events)
                assert count == events
                assert manifest['capture']['backup_started_at'] <= manifest['capture']['backup_completed_at']
                assert all(info.filename != 'snapshot.sqlite' for info in archive.infolist())
            def max_tick(ticks: list[float]) -> float:
                return max(b - a for a, b in zip(ticks, ticks[1:])) if len(ticks) > 1 else 0
            assert not application.control_task.done(), application.control_task.exception()
            assert len(actuator.ticks) >= 2, 'Control did not continue during export'
            baseline_delay, export_delay = max_tick(baseline_ticks), max_tick(actuator.ticks)
            report = {'synthetic': True, 'events': events, 'source_database_bytes': source_bytes,
                      'decision_count': 60, 'decoded_snapshot_bytes': decoded, 'archive_bytes': job['bytes'],
                      'duration_seconds': elapsed, 'peak_process_memory_bytes': peak_memory(),
                      'concurrent_commits': writes[0], 'baseline_api_max_seconds': max(latencies['baseline']),
                      'export_api_max_seconds': max(latencies['export']), 'baseline_control_ticks': len(baseline_ticks), 'export_control_ticks': len(actuator.ticks),
                      'baseline_tick_max_seconds': baseline_delay,
                      'export_tick_max_seconds': export_delay, 'configured_control_period_seconds': 1,
                      'cadence_failure_threshold_seconds': 1.1, 'selected_events_independently_counted': count,
                      'source_revision_unchanged': True, 'export_induced_replans': 0,
                      'note': 'Actual control loop with fake actuator; no installation performance claim.'}
            (directory / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report, indent=2), flush=True)
            assert export_delay <= 1.1, 'Diagnostics missed configured synthetic control cadence (100 ms scheduling tolerance)'
    finally:
        stop.set()
        await asyncio.to_thread(thread.join)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=2_000_000)
    parser.add_argument('--artifacts-dir', type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.events, args.artifacts_dir))
