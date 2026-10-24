"""Deterministic archive fixtures; no installation database or HA access."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import sqlite3

import pytest
from aiohttp.test_utils import TestClient, TestServer

from energymanager.domain import encode
from energymanager.energy import daily_energy
from energymanager.service import Application
from energymanager.store import Store
from energymanager.web import create_web
from test_first_slice import tiny


def test_daily_energy_uses_legacy_archive_and_survives_restart(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    start = datetime(2026, 10, 23, 22, tzinfo=UTC)  # Brussels midnight.
    observation = replace(tiny().observation, at=start, house_kw=2, pv_ac_kw=1,
                          pv_dc_kw=0.5, ev_power_kw=3, ess_power_kw=-1)
    # Existing releases already wrote these events. Creating the index must include them.
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE events (sequence INTEGER PRIMARY KEY, at TEXT, kind TEXT, body TEXT)")
        for seconds in range(-5, 61, 5):
            sample = replace(observation, at=start + timedelta(seconds=seconds))
            for _ in range(5):
                connection.execute("INSERT INTO events(at,kind,body) VALUES (?, 'measurement',?)",
                                   (start.isoformat(), encode(sample)))
    store = Store(path)
    store.close()
    result = daily_energy(path, start + timedelta(seconds=60), "Europe/Brussels", 30, False)
    assert not result["partial"]
    assert result["covered_seconds"] == 60
    assert result["kwh"]["import"] == pytest.approx(5 / 60)
    assert result["kwh"]["solar"] == pytest.approx(1.5 / 60)
    assert result["kwh"]["ess_charge"] == pytest.approx(1 / 60)
    assert result["kwh"]["ev"] == pytest.approx(3 / 60)
    assert result["kwh"]["export"] == result["kwh"]["ess_discharge"] == 0


def test_daily_energy_leaves_out_gaps_invalid_and_synthetic_measurements(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    start = datetime(2026, 10, 24, 0, tzinfo=UTC)
    observation = replace(tiny().observation, at=start, house_kw=0.5, pv_ac_kw=2, ess_power_kw=1)
    for seconds, quality in ((0, "measured"), (10, "unknown"), (20, "SYNTHETIC"), (30, "measured")):
        store.event("measurement", replace(observation, at=start + timedelta(seconds=seconds), quality=quality))
    store.event("measurement", replace(observation, quality="unknown"))  # Cached failure must not erase read.
    result = daily_energy(store.path, start + timedelta(seconds=100), "UTC", 30, False)
    assert result["partial"]
    assert result["covered_seconds"] == 40
    assert result["kwh"]["export"] == pytest.approx(2.5 * 40 / 3600)
    assert result["kwh"]["ess_discharge"] == pytest.approx(40 / 3600)
    demo = daily_energy(store.path, start + timedelta(seconds=100), "UTC", 30, True)
    assert demo["covered_seconds"] == 10
    store.close()


@pytest.mark.parametrize(("date", "hours"), [("2026-03-30", 23), ("2026-10-26", 25)])
def test_local_day_handles_dst_and_missing_data(tmp_path, date, hours):
    from zoneinfo import ZoneInfo

    store = Store(tmp_path / "synthetic.sqlite")
    end = datetime.fromisoformat(date).replace(tzinfo=ZoneInfo("Europe/Brussels"))
    now = end.astimezone(UTC) - timedelta(seconds=1)
    result = daily_energy(store.path, now, "Europe/Brussels", 30, False)
    assert result["elapsed_seconds"] == hours * 3600 - 1
    assert result["partial"] and result["kwh"] is None
    store.close()


async def test_daily_energy_endpoint_is_read_only_and_protected(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    application = Application(store, snapshot=tiny())
    store.event("measurement", replace(application.observation, quality="SYNTHETIC"))
    async with TestClient(TestServer(create_web(application))) as client:
        response = await client.get("/api/daily-energy")
        assert response.status == 200
        assert response.headers["Cache-Control"] == "no-store"
        result = await response.json()
        assert result["source"] == "SYNTHETIC power integration"
        assert result["kwh"]["house"] >= 0
        response = await client.get("/api/daily-energy", headers={"Host": "outside.test"})
        assert response.status == 403
        assert (await client.post("/api/daily-energy", json={}, headers={"X-EnergyManager": "1"})).status == 405
    store.close()
