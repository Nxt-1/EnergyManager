"""Offline archive regressions, including gaps, bounded payloads and worker isolation."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest
from aiohttp.test_utils import TestClient, TestServer

from energymanager.domain import json_data
from energymanager.energy import measurements
from energymanager.graph_history import graph_history
from energymanager.service import Application
from energymanager.store import Store
from energymanager.web import create_web
from test_first_slice import tiny


def archive(store, start, end, now=None, points=100, demo=False):
    return graph_history(store.path, start, end, now or end, points, 30, 60, 14, demo)


def test_history_loads_beyond_ring_buffer_and_bounds_output_without_hiding_peak(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    at = datetime(2026, 10, 20, tzinfo=UTC)
    for second in range(7201):
        sample = replace(tiny().observation, at=at + timedelta(seconds=second),
                         house_kw=100 if second == 123 else 0.4)
        store.event("measurement", sample)
    # The range is days old; no in-memory Application history is involved.
    result = archive(store, at, at + timedelta(hours=2), at + timedelta(days=4))
    assert result["sample_count"] == 7201
    assert all(len(series) <= 100 for series in result["series"].values())
    assert max(value for _, value in result["series"]["house"] if value is not None) == 100000
    assert result["series"]["house"][0][0] == at.timestamp() * 1000
    assert result["series"]["house"][-1][0] == (at + timedelta(hours=2)).timestamp() * 1000
    plan = store.connection.execute(
        "EXPLAIN QUERY PLAN SELECT body FROM events WHERE kind='measurement' "
        "AND julianday(json_extract(body,'$.at')) BETWEEN julianday(?) AND julianday(?) "
        "ORDER BY julianday(json_extract(body,'$.at')), sequence", (at.isoformat(), at.isoformat())
    ).fetchall()
    assert any("SEARCH" in row[3] and "measurement_time" in row[3] for row in plan)
    store.close()


def test_history_preserves_quality_gaps_unknown_ev_and_recorded_capacities(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    at = datetime(2026, 10, 24, tzinfo=UTC)
    sample = tiny().observation
    for second in (0, 5, 10, 20, 60, 65, 70):
        observation = replace(sample, at=at + timedelta(seconds=second), ev_state_known=second != 65,
                              quality="SYNTHETIC" if second == 20 else "measured")
        store.event("measurement", {**json_data(observation), "ev_capacity_kwh": 48, "ess_capacity_kwh": 7})
    result = archive(store, at, at + timedelta(seconds=100), points=400)
    assert result["capacity_fallback"] is False
    ev = dict(result["series"]["ev_soc"])
    assert ev[at.timestamp() * 1000] == 50
    assert ev[(at + timedelta(seconds=65)).timestamp() * 1000] is None
    assert any(value is None for _, value in result["series"]["house"])
    assert all(value is None or value == 400 for _, value in result["series"]["house"])
    # Every outage must lift the pen before subsequent readings, including within one bucket.
    coarse = archive(store, at, at + timedelta(hours=1))
    assert coarse["series"]["house"][0][1] is None
    demo = archive(store, at, at + timedelta(seconds=100), points=400, demo=True)
    assert demo["sample_count"] == 1
    store.close()


def test_history_returns_empty_future_and_missing_ranges_and_rejects_unbounded_queries(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    at = datetime(2026, 10, 24, tzinfo=UTC)
    assert all(not rows for rows in archive(store, at, at + timedelta(days=1), at)["series"].values())
    with pytest.raises(ValueError, match="eight"):
        archive(store, at, at + timedelta(days=9))
    with pytest.raises(ValueError, match="points"):
        archive(store, at, at + timedelta(days=1), points=10000)
    store.event("measurement", replace(tiny().observation, at=at))
    with pytest.raises(TimeoutError):
        list(measurements(store.path, at, at + timedelta(hours=1), timeout_seconds=1e-9))
    store.close()


async def test_history_api_is_validated_and_worker_does_not_block_state(tmp_path, monkeypatch):
    from energymanager import web as module

    store = Store(tmp_path / "synthetic.sqlite")
    application = Application(store, snapshot=tiny())
    at = application.now()
    store.event("measurement", replace(application.observation, quality="SYNTHETIC"))
    query = {"start": (at - timedelta(hours=6)).isoformat(), "end": at.isoformat()}
    async with TestClient(TestServer(create_web(application))) as client:
        response = await client.get("/api/history", params=query)
        assert response.status == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert (await response.json())["sample_count"] == 1
        for invalid in ({}, {**query, "points": "nan"}, {**query, "points": "0"},
                        {**query, "start": "2026-10-24T00:00"}):
            assert (await client.get("/api/history", params=invalid)).status == 400
        assert (await client.get("/api/history", params=query, headers={"Host": "outside.test"})).status == 403
        started = asyncio.Event()
        release = Event()
        loop = asyncio.get_running_loop()
        original = module.graph_history

        def held_read(*args):
            loop.call_soon_threadsafe(started.set)
            assert release.wait(timeout=5)
            return original(*args)

        monkeypatch.setattr(module, "graph_history", held_read)
        pending = asyncio.create_task(client.get("/api/history", params=query))
        try:
            async with asyncio.timeout(2):
                await started.wait()
                assert (await client.get("/api/state")).status == 200
        finally:
            release.set()
            await pending
        def timed_out(*args):
            raise TimeoutError("SYNTHETIC query deadline")

        monkeypatch.setattr(module, "graph_history", timed_out)
        response = await client.get("/api/history", params=query)
        assert response.status == 503
        assert "unavailable" in (await response.json())["error"]
    store.close()
