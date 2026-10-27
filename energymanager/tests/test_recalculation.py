"""Synthetic workers and local HTTP only; never installation inputs or actuators."""

import asyncio
import os
from dataclasses import replace
from multiprocessing import active_children
from time import sleep

import pytest
from aiohttp.test_utils import TestClient, TestServer

from energymanager import __version__
from energymanager.service import Application
from energymanager.store import Store
from energymanager.web import create_web
from energymanager.worker import PlanningWorker
from test_first_slice import tiny


def synthetic_calculation(data, progress):
    progress("synthetic_started")
    if data.get("crash"):
        os._exit(7)  # Deliberately crash only this synthetic child process.
    if data.get("error"):
        raise ValueError("SYNTHETIC solver failure")
    sleep(data.get("seconds", 0))
    return {"synthetic": True, "pid": os.getpid()}


async def test_real_spawn_cancellation_reaps_child_and_allows_fresh_work():
    worker = PlanningWorker(synthetic_calculation)
    started = asyncio.Event()
    work = asyncio.create_task(worker.run({"seconds": 30}, lambda _: started.set()))
    await asyncio.wait_for(started.wait(), 10)
    pid = worker.process.pid
    work.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(work, 5)
    assert pid not in {child.pid for child in active_children()}
    assert worker.process is None
    result = await asyncio.wait_for(worker.run({}, lambda _: None), 10)
    assert result["synthetic"] and result["pid"] != pid
    assert worker.process is None


@pytest.mark.parametrize("failure", ["error", "crash"])
async def test_failed_child_surfaces_error_and_does_not_poison_next_calculation(failure):
    worker = PlanningWorker(synthetic_calculation)
    with pytest.raises(RuntimeError, match="SYNTHETIC solver failure|without a result"):
        await asyncio.wait_for(worker.run({failure: True}, lambda _: None), 10)
    assert worker.process is None
    assert (await worker.run({}, lambda _: None))["synthetic"]


async def test_cancel_during_spawn_reaps_worker_without_blocking_event_loop(monkeypatch):
    import energymanager.worker as module

    real_context = module.get_context
    real_start = real_context("spawn").Process.start

    def delayed_start(process):
        sleep(.15)  # Simulate slow host process launch, outside the event loop.
        real_start(process)

    monkeypatch.setattr(real_context("spawn").Process, "start", delayed_start)
    worker = PlanningWorker(synthetic_calculation)
    before = {child.pid for child in active_children()}
    work = asyncio.create_task(worker.run({"seconds": 30}, lambda _: None))
    await asyncio.sleep(.02)
    work.cancel()
    ticks = 0
    while not work.done():
        ticks += 1
        await asyncio.sleep(.01)
    with pytest.raises(asyncio.CancelledError):
        await work
    assert ticks >= 5  # Spawn/join did not stall the event loop.
    await worker.close()
    assert worker.process is None
    assert {child.pid for child in active_children()} == before


async def test_manual_http_replaces_work_coalesces_clicks_and_retains_valid_control(tmp_path, monkeypatch):
    snapshot = tiny()
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=snapshot)
    app.accepted = {"id": "synthetic-previous"}
    app.ev_valid = app.ess_valid = app.conditional_valid = True
    started = asyncio.Event()
    calls = []
    finished = []

    async def calculate(current, request_id):
        calls.append(request_id)
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            finished.append(request_id)

    monkeypatch.setattr(app, "calculate_plan", calculate)
    # No application start/cleanup hooks: exercise the HTTP route and parent cancellation directly.
    web = create_web(app)
    web.on_startup.clear()
    web.on_cleanup.clear()
    async with TestClient(TestServer(web)) as client:
        for path in ("/planning-activity.js", f"/frontend/{__version__}/planning-activity.js"):
            asset = await client.get(path)
            assert asset.status == 200 and "PlanningActivity" in await asset.text()
        first = app.request_plan("synthetic")
        app.requested.clear()
        work = asyncio.create_task(app.run_calculation(snapshot))
        await started.wait()
        assert app.request_plan("control_deviation")["requested"] is False
        assert not app.requested.is_set()  # Busy same-revision work must not queue a second solve.
        ids = []
        for _ in range(3):
            response = await client.post("/api/replan", json={}, headers={"X-EnergyManager": "1"})
            assert response.status == 202
            reply = await response.json()
            assert reply["requested"]
            ids.append(reply["planning_activity"]["request_id"])
        assert len(set(ids)) == 3
        assert await asyncio.wait_for(work, 2) is None
        assert finished == [first["planning_activity"]["request_id"]]
        assert len(calls) == 1
        assert app.accepted["id"] == "synthetic-previous"
        assert app.ev_valid and app.ess_valid and app.conditional_valid
        assert app.revision == snapshot.revision
        state = await (await client.get("/api/state?compact=1")).json()
        assert state["planning_activity"]["request_id"] == ids[-1]
        app.requested.clear()
        started.clear()
        replacement = asyncio.create_task(app.run_calculation(snapshot))
        await started.wait()
        assert calls == [first["planning_activity"]["request_id"], ids[-1]]
        app.revision += 1
        assert app.request_plan("goal_changed")["requested"]
        assert await asyncio.wait_for(replacement, 2) is None
        assert len([e for e in store.events() if e["kind"] == "planning_cancelled"]) == 2
    store.close()


async def test_shutdown_cancels_active_spawned_solver(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=tiny())
    app.worker = PlanningWorker(synthetic_calculation)
    started = asyncio.Event()
    # Run through the parent's actual worker ownership, but replace the fixture payload.
    async def calculate(snapshot, request_id):
        return await app.worker.run({"seconds": 30}, lambda _: started.set())
    app.calculate_plan = calculate
    app.planning = asyncio.create_task(app.run_calculation(app.snapshot))
    await asyncio.wait_for(started.wait(), 10)
    pid = app.worker.process.pid
    await asyncio.wait_for(app.close(), 5)
    assert app.worker.process is None
    assert pid not in {child.pid for child in active_children()}
    store.close()


async def test_real_planning_loop_only_publishes_latest_request(tmp_path, monkeypatch):
    from energymanager.planner import Planner

    snapshot = tiny(planning_budget_seconds=3)
    valid = Planner().plan(snapshot)
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=snapshot, policy=snapshot.policy)
    monkeypatch.setattr(app, "build_snapshot", lambda: replace(snapshot, revision=app.revision))
    monkeypatch.setattr(app, "now", lambda: snapshot.observation.at)
    started = asyncio.Event()
    calls = []

    async def calculate(current, request_id):
        calls.append(request_id)
        if len(calls) == 1:
            started.set()
            await asyncio.Event().wait()
        return {**valid, "id": request_id}

    async def accepted():
        app.shutdown = True

    monkeypatch.setattr(app, "calculate_plan", calculate)
    monkeypatch.setattr(app, "notify_permission_issues", accepted)
    app.request_plan("synthetic")
    loop = asyncio.create_task(app.planning_loop())
    await started.wait()
    for _ in range(5):
        newest = app.request_plan("manual", restart=True)["planning_activity"]["request_id"]
    await asyncio.wait_for(loop, 5)
    assert len(calls) == 2 and calls[-1] == newest
    assert app.accepted["id"] == newest and app.status == "ready"
    assert len(store.decisions()) == 1
    assert app.state()["planning_activity"]["state"] == "ready"
    store.close()


async def test_crashed_worker_retains_automatic_recovery(tmp_path, monkeypatch):
    from energymanager.worker import WorkerExited

    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=tiny())
    calls = []

    async def calculate(snapshot, request_id):
        calls.append(request_id)
        if len(calls) == 1:
            raise WorkerExited("SYNTHETIC process crash")
        app.shutdown = True
        return None

    monkeypatch.setattr(app, "run_calculation", lambda snapshot: calculate(snapshot, app.planning_request_id))
    app.request_plan("synthetic")
    await asyncio.wait_for(app.planning_loop(), 5)
    assert len(calls) == 2 and calls[0] != calls[1]
    assert any(e["kind"] == "worker_restarted" for e in store.events())
    store.close()
