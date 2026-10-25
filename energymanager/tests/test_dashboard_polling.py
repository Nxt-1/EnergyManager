"""Synthetic polling payloads through the real local HTTP API; no installation data."""

from aiohttp.test_utils import TestClient, TestServer

from energymanager.domain import json_data
from energymanager.service import Application
from energymanager.store import Store
from energymanager.web import create_web
from test_first_slice import tiny


async def test_compact_poll_reuses_plan_without_shipping_decision_evidence(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=tiny())
    plan = {"id": "synthetic-1", "revision": 1, "valid": True, "status": "Optimal",
            "intervals": [{"start": "2026-10-25T00:00Z", "end": "2026-10-25T00:05Z"}],
            "flows": {"grid_house": [.4]}, "goals": [], "sessions": [], "summary": {},
            "candidate_at_calculation": {"flows": list(range(10000))},
            "adoption_snapshot": {"intervals": list(range(10000))}}
    app.accepted = plan
    app.observed = [json_data(app.observation) for _ in range(2000)]

    async def no_lifecycle():
        pass
    app.start = app.close = no_lifecycle
    try:
        async with TestClient(TestServer(create_web(app))) as client:
            full_response = await client.get("/api/state")
            full = await full_response.read()
            response = await client.get("/api/state?compact=1")
            initial_bytes = await response.read()
            initial = await response.json()
            assert response.headers["Cache-Control"] == "no-store"
            assert initial["accepted"]["flows"] == plan["flows"]
            assert initial["accepted"]["intervals"] == plan["intervals"]
            assert "candidate_at_calculation" not in initial["accepted"]
            assert "adoption_snapshot" not in initial["accepted"]
            assert len(initial["observed"]) == 120 and len(initial_bytes) < len(full) / 5
            same = await (await client.get("/api/state?compact=1&plan_id=synthetic-1")).json()
            assert same["accepted_unchanged"] and same["accepted_plan_id"] == "synthetic-1"
            assert "accepted" not in same
            app.accepted = {**plan, "id": "synthetic-2"}
            replaced = await (await client.get("/api/state?compact=1&plan_id=synthetic-1")).json()
            assert not replaced["accepted_unchanged"] and replaced["accepted"]["id"] == "synthetic-2"
            app.accepted = None
            removed = await (await client.get("/api/state?compact=1&plan_id=synthetic-2")).json()
            assert removed["accepted"] is None and not removed["accepted_unchanged"]
            assert len(app.observed) == 2000 and "adoption_snapshot" in plan
    finally:
        store.close()
