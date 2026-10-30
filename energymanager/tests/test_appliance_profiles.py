"""Deterministic synthetic appliance cycles; no installation measurements or HA access."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from energymanager.appliance_profiles import ApplianceProfiles, power_reading
from energymanager.service import Application
from energymanager.store import Store
from energymanager.web import create_web
from test_first_slice import tiny

AT = datetime(2026, 10, 25, 12, tzinfo=UTC)


@pytest.fixture
def profiles(tmp_path):
    store = Store(tmp_path / "synthetic-profiles.sqlite")
    app = SimpleNamespace(store=store, demo=False, ha=object(), now=lambda: AT)
    library = ApplianceProfiles(app)
    library.configure({"revision": 1, "machine": "dishwasher", "entity_id": "sensor.synthetic_dishwasher",
                       "start_threshold_w": 10, "idle_timeout_minutes": 1})
    yield library
    store.close()


def arm(profiles, **changes):
    return profiles.arm({"machine": "dishwasher", "program": "eco", "notes": "SYNTHETIC full load", **changes})["id"]


def ingest(profiles, identity, seconds, power):
    profiles.ingest(identity, AT + timedelta(seconds=seconds), power, "SYNTHETIC unavailable" if power is None else None)


def complete_cycle(profiles):
    identity = arm(profiles)
    for seconds, power in [(0, 0), (5, 1000), (10, 500), *[(s, 0) for s in range(15, 80, 5)]]:
        ingest(profiles, identity, seconds, power)
    return identity


def test_idle_completion_review_trim_energy_and_restart_preserve_original(profiles):
    identity = complete_cycle(profiles)
    recording = profiles.detail(identity)
    assert recording["status"] == "review"
    assert recording["suggested_end_seconds"] == 10
    assert len(recording["points"]) == 15
    assert profiles.library()["profiles"] == {}
    summary = profiles.preview(identity, {})
    assert summary["complete"]
    assert summary["energy_kwh"] == pytest.approx(7500 / 3600000)
    assert summary["peak_w"] == 1000
    saved = profiles.accept(identity, {"reviewed": True, "revision": 2})
    assert saved["summary"] == summary
    restored = ApplianceProfiles(profiles.app)
    assert restored.library()["profiles"]["dishwasher/eco"]["id"] == identity
    assert restored.detail(identity)["points"] == recording["points"]
    assert "demo" not in str(restored.library()["mode"])


def test_arming_waits_for_idle_and_rejects_duplicate_capture(profiles):
    identity = arm(profiles)
    ingest(profiles, identity, 0, 1000)
    ingest(profiles, identity, 5, 2000)
    assert profiles.get(identity)["status"] == "armed"
    with pytest.raises(ValueError, match="already"):
        arm(profiles)
    ingest(profiles, identity, 10, 0)
    ingest(profiles, identity, 15, 500)
    assert profiles.get(identity)["started_at"] == (AT + timedelta(seconds=15)).isoformat()


def test_activity_and_failed_read_reset_idle_timeout(profiles):
    identity = arm(profiles)
    for seconds in range(0, 170, 5):
        power = 0 if seconds != 5 and seconds != 55 else 1000
        if seconds == 100:
            power = None
        ingest(profiles, identity, seconds, power)
        if seconds < 165:
            assert profiles.get(identity)["status"] != "review"
    assert profiles.get(identity)["status"] == "review"
    assert profiles.get(identity)["invalid_samples"] == 1
    with pytest.raises(ValueError, match="missing"):
        profiles.accept(identity, {"reviewed": True, "revision": 2})


def test_failed_reads_are_gaps_and_trimming_cannot_invent_energy(profiles):
    identity = arm(profiles)
    for seconds, power in [(0, 0), (5, 1000), (10, 1000), (15, None), (20, 2000), (25, 2000)]:
        ingest(profiles, identity, seconds, power)
    profiles.finish(identity)
    preview = profiles.preview(identity, {})
    assert not preview["complete"]
    assert preview["covered_seconds"] == 10
    assert preview["energy_kwh"] == pytest.approx(15000 / 3600000)
    trimmed = profiles.preview(identity, {"start_seconds": 15, "end_seconds": 20})
    assert trimmed["complete"] and trimmed["average_w"] == 2000
    with pytest.raises(ValueError, match="missing"):
        profiles.accept(identity, {"reviewed": True, "revision": 2})
    assert profiles.detail(identity)["points"][2]["power_w"] is None


def test_lost_polling_does_not_count_as_idle_or_continuous_coverage(profiles):
    identity = arm(profiles)
    for seconds, power in [(0, 0), (5, 2000), (10, 0), (80, 0)]:
        ingest(profiles, identity, seconds, power)
    assert profiles.get(identity)["status"] == "recording"
    assert profiles.get(identity)["idle_since"] == (AT + timedelta(seconds=80)).isoformat()
    assert not profiles.preview(identity, {})["complete"]


def test_missing_read_before_start_requires_new_idle_evidence(profiles):
    identity = arm(profiles)
    for seconds, power in [(0, 0), (5, None), (10, 2000), (50, 0), (90, 2000)]:
        ingest(profiles, identity, seconds, power)
    assert profiles.get(identity)["status"] == "armed"


def test_restart_interruption_requires_a_new_complete_cycle(profiles):
    identity = arm(profiles)
    for seconds, power in [(0, 0), (5, 1000), (10, 1000)]:
        ingest(profiles, identity, seconds, power)
    restored = ApplianceProfiles(profiles.app)
    assert restored.get(identity)["status"] == "review"
    assert restored.get(identity)["interrupted"]
    with pytest.raises(ValueError, match="interrupted"):
        restored.accept(identity, {"reviewed": True, "revision": 2})
    arm(restored)


def test_discard_and_inflight_sample_cannot_resurrect_recording(profiles):
    identity = arm(profiles)
    profiles.discard(identity)
    ingest(profiles, identity, 0, 0)
    assert profiles.get(identity)["status"] == "discarded"
    assert profiles.library()["recordings"] == []


def test_review_and_revision_required_and_prior_cycles_remain_selectable(profiles):
    first = complete_cycle(profiles)
    with pytest.raises(ValueError, match="review confirmation"):
        profiles.accept(first, {"revision": 2})
    with pytest.raises(ValueError, match="another view"):
        profiles.accept(first, {"revision": 1, "reviewed": True})
    profiles.accept(first, {"revision": 2, "reviewed": True})
    second = complete_cycle(profiles)
    profiles.accept(second, {"revision": 3, "reviewed": True})
    assert profiles.library()["selected"]["dishwasher/eco"] == second
    profiles.select(first, {"revision": 4})
    assert profiles.library()["selected"]["dishwasher/eco"] == first
    assert len(profiles.detail(second)["points"]) == 15
    with pytest.raises(ValueError, match="retained"):
        profiles.discard(first)


def test_mazak_tuning_and_demo_library_are_isolated(profiles):
    profiles.configure({"revision": 2, "machine": "mazak", "powers_w": {"program": 2600, "light": 3600, "production": 7200}})
    assert ApplianceProfiles(profiles.app).library()["mazak"]["program"] == 2600
    demo = ApplianceProfiles(SimpleNamespace(store=profiles.store, demo=True, ha=None, now=lambda: AT))
    assert demo.library()["mazak"] == {"program": 2500, "light": 3500, "production": 7000}
    assert demo.library()["recordings"] == []
    with pytest.raises(ValueError, match="configured mode"):
        arm(demo)


@pytest.mark.parametrize("state", [
    {"state": "unavailable", "attributes": {"unit_of_measurement": "W"}},
    {"state": "NaN", "attributes": {"unit_of_measurement": "W"}},
    {"state": "-2", "attributes": {"unit_of_measurement": "W"}},
    {"state": "100", "attributes": {"unit_of_measurement": "Wh"}},
    {"state": "100", "attributes": None},
])
def test_invalid_sensor_readings_are_never_zero(state):
    with pytest.raises(ValueError):
        power_reading(state)


def test_kw_conversion():
    assert power_reading({"state": "2.5", "attributes": {"unit_of_measurement": "kW"}}) == 2500


async def test_profile_api_security_revision_validation_and_native_asset(tmp_path):
    application = Application(Store(tmp_path / "synthetic-api.sqlite"), snapshot=tiny())
    async with TestClient(TestServer(create_web(application))) as client:
        headers = {"X-EnergyManager": "1"}
        response = await client.get("/api/profiles")
        assert response.status == 200 and response.headers["Cache-Control"] == "no-store"
        assert (await response.json())["mode"] == "demo"
        response = await client.post("/api/profiles/configure", json={"revision": 1, "machine": "mazak", "powers_w": {"program": 2700, "light": 3500, "production": 7000}})
        assert response.status == 403
        response = await client.post("/api/profiles/configure", headers=headers, json={"revision": 1, "machine": "mazak", "powers_w": {"program": 2700, "light": 3500, "production": 7000}})
        assert response.status == 200
        assert (await response.json())["mazak"]["program"] == 2700
        response = await client.post("/api/profiles/arm", headers=headers, json={"machine": "dishwasher", "program": "eco"})
        assert response.status == 400
        response = await client.post("/api/profiles/configure", headers=headers, json=[])
        assert response.status == 400
        response = await client.get("/appliance-profiles.js")
        assert response.status == 200


async def test_sampler_reads_only_explicitly_armed_sensor_from_local_fake_ha(profiles):
    calls = []
    async def state(request):
        calls.append(request.match_info["entity"])
        return web.json_response({"state": "1.5", "attributes": {"unit_of_measurement": "kW"}})
    fake = web.Application()
    fake.router.add_get("/states/{entity}", state)
    from energymanager.adapters import HomeAssistantAdapter
    async with TestServer(fake) as server:
        async with HomeAssistantAdapter(str(server.make_url('/')), {}) as ha:
            profiles.app.ha = ha
            identity = arm(profiles)
            ingest(profiles, identity, 0, 0)
            profiles.app.now = lambda: AT + timedelta(seconds=5)
            await profiles._sample(profiles.get(identity))
            assert profiles.get(identity)["last_power_w"] == 1500
    assert calls == ["sensor.synthetic_dishwasher"]


def test_trim_inside_one_sample_interval_retains_energy_and_peak(profiles):
    identity = arm(profiles)
    for seconds, power in [(0, 0), (5, 2000), (10, 0), (15, 0)]:
        ingest(profiles, identity, seconds, power)
    profiles.finish(identity)
    preview = profiles.preview(identity, {"start_seconds": 1, "end_seconds": 3})
    assert preview["duration_seconds"] == 2
    assert preview["energy_kwh"] == pytest.approx(4000 / 3600000)
    assert preview["average_w"] == preview["peak_w"] == 2000


def test_armed_restart_does_not_start_from_power_already_running(profiles):
    identity = arm(profiles)
    ingest(profiles, identity, 0, 0)
    restored = ApplianceProfiles(profiles.app)
    ingest(restored, identity, 5, 2000)
    assert restored.get(identity)["status"] == "armed"
    assert not restored.get(identity)["idle_seen"]


def test_capture_limit_and_sensor_remapping_guards(profiles):
    identity = arm(profiles)
    with pytest.raises(ValueError, match="Finish or cancel"):
        profiles.configure({"revision": 2, "machine": "dishwasher", "entity_id": "sensor.other",
                            "start_threshold_w": 10, "idle_timeout_minutes": 1})
    ingest(profiles, identity, 24 * 3600, 0)
    assert profiles.get(identity)["status"] == "cancelled"
    assert profiles.get(identity)["interrupted"]
    with pytest.raises(ValueError, match="dedicated power sensor"):
        profiles.configure({"revision": 2, "machine": "washing_machine",
                            "entity_id": "sensor.synthetic_dishwasher",
                            "start_threshold_w": 10, "idle_timeout_minutes": 1})


def test_existing_database_upgrade_preserves_household_state(tmp_path):
    import json
    import sqlite3
    path = tmp_path / "synthetic-previous-version.sqlite"
    original = {"revision": 42, "goals": [{"id": "synthetic-existing-goal"}],
                "accepted": {"id": "synthetic-existing-plan"}, "hardware_requested": False}
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.executemany("INSERT INTO state VALUES (?,?)", [(key, json.dumps(value)) for key, value in original.items()])
    store = Store(path)
    profiles = ApplianceProfiles(SimpleNamespace(store=store, demo=False, ha=object(), now=lambda: AT))
    profiles.configure({"revision": 1, "machine": "dishwasher", "entity_id": "sensor.synthetic_dishwasher",
                        "start_threshold_w": 10, "idle_timeout_minutes": 1})
    identity = complete_cycle(profiles)
    profiles.accept(identity, {"reviewed": True, "revision": 2})
    assert {key: store.get(key) for key in original} == original
    store.close()
    store = Store(path)
    restored = ApplianceProfiles(SimpleNamespace(store=store, demo=False, ha=object(), now=lambda: AT))
    assert restored.library()["selected"]["dishwasher/eco"] == identity
    assert {key: store.get(key) for key in original} == original
    store.close()


def test_failed_profile_save_rolls_back_selection_and_memory(profiles):
    import sqlite3
    identity = complete_cycle(profiles)
    profiles.store.connection.executescript("""
        CREATE TRIGGER synthetic_profile_write_failure BEFORE UPDATE ON appliance_recordings
        WHEN NEW.status='saved' BEGIN SELECT RAISE(FAIL,'SYNTHETIC write failure'); END;
    """)
    with pytest.raises(sqlite3.IntegrityError, match="SYNTHETIC"):
        profiles.accept(identity, {"reviewed": True, "revision": 2})
    assert profiles.settings["revision"] == 2
    assert profiles.settings["selected"] == {}
    assert profiles.store.get(profiles.key)["selected"] == {}
    assert profiles.get(identity)["status"] == "review"
    assert len(profiles.detail(identity)["points"]) == 15
