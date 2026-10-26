"""Synthetic rejected-decision diagnostics and exact offline replay exports."""

import hashlib
import json
import sys

import pytest
from aiohttp.test_utils import TestClient, TestServer

from energymanager.__main__ import main
from energymanager.domain import encode
from energymanager.service import Application
from energymanager.store import Store
from energymanager.web import create_web
from test_first_slice import tiny


async def test_rejected_decision_lists_failure_and_downloads_complete_replay(tmp_path):
    snapshot = tiny()
    store = Store(tmp_path / "synthetic.sqlite")
    result = {"id": "synthetic-rejected", "valid": False, "status": "Time limit reached",
              "reason": "Synthetic first stage timed out", "seconds": 12.0, "summary": {},
              "stages": [{"name": "required_reference", "feasible": False, "seconds": 12.0}]}
    store.record(snapshot, result, "rejected")
    application = Application(store, snapshot=snapshot)
    async with TestClient(TestServer(create_web(application))) as client:
        rows = await (await client.get("/api/decisions")).json()
        row = next(item for item in rows if item["id"] == result["id"])
        assert row["reason"] == result["reason"]
        assert row["status"] == result["status"]
        assert row["seconds"] == result["seconds"]
        assert "snapshot" not in row and "stages" not in row
        response = await client.get("/api/decisions/synthetic-rejected?download=1")
        assert response.status == 200
        assert "attachment" in response.headers["Content-Disposition"]
        assert response.headers["Cache-Control"] == "no-store"
        data = json.loads(await response.text())
        assert data["result"] == result
        assert data["disposition"] == "rejected"
        assert hashlib.sha256(encode(data["snapshot"]).encode()).hexdigest() == data["digest"]
        assert type(data["snapshot"]["observation"]["quarter_import_kwh"]) is float
        assert (await client.get("/api/decisions/missing?download=1")).status == 404


def test_offline_replay_checks_export_digest_even_when_failed_result_has_no_digest(tmp_path, monkeypatch, capsys):
    payload = {"snapshot": json.loads(encode(tiny())), "digest": "corrupted", "result": {"valid": False}}
    path = tmp_path / "synthetic-export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["energymanager", "--fixture", str(path), "--solve", str(tmp_path / "result.json")])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "input checksum mismatch" in capsys.readouterr().err


def test_rejected_publication_reason_is_present_in_history_list(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    errors = ["Unapproved EV peak SYNTHETIC: 5532 W quarter-hour average exceeds 5490 W allowance"]
    store.record(tiny(), {"id": "synthetic-rebase", "valid": True, "status": "Optimal",
                          "publication_errors": errors}, "rejected")
    assert store.decisions()[0]["reason"] == errors[0]
    store.close()
