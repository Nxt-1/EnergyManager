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


def short_saved_cycle(profiles, watts, seconds, trim=None):
    identity = arm(profiles)
    ingest(profiles, identity, 0, 0)
    for at in range(5, seconds + 6, 5):
        ingest(profiles, identity, at, watts)
    profiles.finish(identity)
    profiles.accept(identity, {"reviewed": True, "revision": profiles.settings["revision"], **(trim or {})})
    return identity


async def test_average_preserves_mean_energy_real_time_and_completed_zero_tail(profiles):
    first = short_saved_cycle(profiles, 1000, 5)
    second = short_saved_cycle(profiles, 2000, 10)
    average = await profiles.profile_detail("dishwasher", "eco")
    assert average["recording_ids"] == [first, second]
    assert average["recording_count"] == 2
    assert average["summary"]["mean_duration_seconds"] == 7.5
    assert average["summary"]["duration_seconds"] == 10
    assert average["summary"]["peak_w"] == 1500
    assert average["points"] == [{"seconds": 0, "power_w": 1500},
                                  {"seconds": 5, "power_w": 1000},
                                  {"seconds": 10, "power_w": 0}]
    energy = sum((right["seconds"] - left["seconds"]) * left["power_w"] / 3600000
                 for left, right in zip(average["points"], average["points"][1:]))
    expected = (profiles.get(first)["summary"]["energy_kwh"] + profiles.get(second)["summary"]["energy_kwh"]) / 2
    assert energy == pytest.approx(expected)
    assert average["summary"]["energy_kwh"] == pytest.approx(expected)


async def test_trimmed_cycles_are_aligned_to_each_selected_start_without_stretching(profiles):
    short_saved_cycle(profiles, 1000, 10, {"start_seconds": 1.25, "end_seconds": 4.25})
    short_saved_cycle(profiles, 2000, 10, {"start_seconds": 2.5, "end_seconds": 8})
    average = await profiles.profile_detail("dishwasher", "eco")
    assert average["summary"]["duration_seconds"] == 5.5
    assert average["summary"]["mean_duration_seconds"] == 4.25
    assert average["summary"]["energy_kwh"] == pytest.approx(7000 / 3600000)
    assert average["points"] == [{"seconds": 0, "power_w": 1500},
                                  {"seconds": 3, "power_w": 1000},
                                  {"seconds": 5.5, "power_w": 0}]


async def test_average_membership_is_explicit_deduplicated_durable_and_reversible(profiles):
    first = short_saved_cycle(profiles, 1000, 5)
    second = short_saved_cycle(profiles, 2000, 10)
    profiles.select(first, {"revision": profiles.settings["revision"]})
    assert profiles.members("dishwasher/eco") == [first, second]
    profiles.select(first, {"revision": profiles.settings["revision"], "included": False})
    assert profiles.members("dishwasher/eco") == [second]
    restored = ApplianceProfiles(profiles.app)
    assert restored.members("dishwasher/eco") == [second]
    assert len(restored.detail(first)["points"]) == 2
    restored.select(second, {"revision": restored.settings["revision"], "included": False})
    assert restored.library()["profiles"] == {}
    with pytest.raises(ValueError, match="No reviewed"):
        await restored.profile_detail("dishwasher", "eco")
    restored.select(first, {"revision": restored.settings["revision"], "included": True})
    assert (await restored.profile_detail("dishwasher", "eco"))["recording_count"] == 1


async def test_legacy_selection_migrates_as_one_contributor_without_adding_old_evidence(profiles):
    first = short_saved_cycle(profiles, 1000, 5)
    second = short_saved_cycle(profiles, 2000, 10)
    settings = {**profiles.settings, "selected": {"dishwasher/eco": first}}
    settings.pop("members")
    profiles.store.put(profiles.key, settings)
    restored = ApplianceProfiles(profiles.app)
    assert restored.members("dishwasher/eco") == [first]
    assert (await restored.profile_detail("dishwasher", "eco"))["summary"]["peak_w"] == 1000
    assert restored.get(second)["status"] == "saved"
    restored.select(second, {"revision": restored.settings["revision"]})
    assert restored.members("dishwasher/eco") == [first, second]


async def test_average_rejects_changed_revision_and_corrupt_contributor(profiles, monkeypatch):
    import asyncio
    import threading
    from energymanager import appliance_profiles
    from energymanager.appliance_average import average_recordings
    identity = short_saved_cycle(profiles, 1000, 5)
    entered, release = threading.Event(), threading.Event()
    def delayed(*args):
        entered.set()
        assert release.wait(3)
        return average_recordings(*args)
    monkeypatch.setattr(appliance_profiles, "average_recordings", delayed)
    pending = asyncio.create_task(profiles.profile_detail("dishwasher", "eco"))
    assert await asyncio.to_thread(entered.wait, 2)
    profiles.select(identity, {"revision": profiles.settings["revision"], "included": False})
    release.set()
    with pytest.raises(ValueError, match="changed while loading"):
        await pending
    # Raw evidence is not made valid by averaging if it was subsequently corrupted.
    recording = profiles.get(identity)
    recording["interrupted"] = True
    profiles._save(recording)
    with pytest.raises(ValueError, match="complete reviewed"):
        average_recordings(profiles.store.path, profiles.mode, "dishwasher", "eco", [identity])


async def test_average_endpoint_asset_and_inclusion_revision_security(profiles):
    identity = short_saved_cycle(profiles, 1000, 5)
    application = Application(profiles.store, snapshot=tiny())
    application.appliance_profiles = profiles
    async def no_lifecycle():
        pass
    application.start = application.close = no_lifecycle
    async with TestClient(TestServer(create_web(application))) as client:
        response = await client.get("/api/profiles/dishwasher/eco")
        assert response.status == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert (await response.json())["recording_count"] == 1
        assert (await client.get("/api/profiles/dishwasher/eco", headers={"Host": "outside.test"})).status == 403
        assert (await client.get("/profile-chart.js")).status == 200
        response = await client.post(f"/api/profile-recordings/{identity}/select",
            headers={"X-EnergyManager": "1"}, json={"revision": 1, "included": False})
        assert response.status == 400 and profiles.members("dishwasher/eco") == [identity]


async def test_saved_trim_updates_identity_statistics_and_average_without_copying_samples(profiles):
    first = short_saved_cycle(profiles, 1000, 10)
    second = short_saved_cycle(profiles, 2000, 10)
    original = profiles.detail(first)
    signature = (await profiles.profile_detail("dishwasher", "eco"))["selection_signature"]
    for start, end in ((1, 6), (2, 5)):
        revised = profiles.revise(first, {"reviewed": True, "revision": profiles.settings["revision"],
                                        "start_seconds": start, "end_seconds": end})
        assert revised["id"] == first
        assert len(profiles.library()["recordings"]) == 2
        assert profiles.detail(first)["points"] == original["points"]
        assert profiles.members("dishwasher/eco") == [first, second]
    average = await profiles.profile_detail("dishwasher", "eco")
    assert average["recording_count"] == 2 and average["selection_signature"] != signature
    assert average["summary"]["energy_kwh"] == pytest.approx(11500 / 3600000)
    restored = ApplianceProfiles(profiles.app)
    assert restored.get(first)["summary"]["duration_seconds"] == 3
    assert len(restored.library()["recordings"]) == 2


async def test_saved_trim_preserves_exclusion_until_an_explicit_include(profiles):
    identity = short_saved_cycle(profiles, 1000, 10)
    profiles.select(identity, {"revision": profiles.settings["revision"], "included": False})
    profiles.revise(identity, {"reviewed": True, "revision": profiles.settings["revision"],
                              "start_seconds": 2, "end_seconds": 6})
    assert profiles.members("dishwasher/eco") == []
    assert profiles.library()["profiles"] == {}
    profiles.select(identity, {"revision": profiles.settings["revision"], "included": True})
    assert (await profiles.profile_detail("dishwasher", "eco"))["summary"]["duration_seconds"] == 4


def test_saved_retrim_keeps_review_revision_and_complete_coverage_guards(profiles):
    original = short_saved_cycle(profiles, 1000, 10)
    before = profiles.detail(original)
    revision = profiles.settings["revision"]
    for body, reason in (({"revision": revision}, "review confirmation"),
                         ({"revision": revision - 1, "reviewed": True}, "another view"),
                         ({"revision": revision, "reviewed": True, "start_seconds": 8, "end_seconds": 2}, "after")):
        with pytest.raises(ValueError, match=reason):
            profiles.revise(original, body)
    assert profiles.detail(original) == before
    assert profiles.settings["revision"] == revision
    assert len(profiles.library()["recordings"]) == 1


def test_failed_trim_update_rolls_back_statistics_revision_and_membership(profiles):
    import sqlite3
    original = short_saved_cycle(profiles, 1000, 10)
    before = profiles.detail(original)
    revision = profiles.settings["revision"]
    profiles.store.connection.executescript("""
        CREATE TRIGGER synthetic_retrim_failure BEFORE UPDATE ON appliance_recordings
        BEGIN SELECT RAISE(FAIL,'SYNTHETIC selection-write failure'); END;
    """)
    with pytest.raises(sqlite3.IntegrityError, match="selection-write failure"):
        profiles.revise(original, {"reviewed": True, "revision": revision,
                                  "start_seconds": 1, "end_seconds": 6})
    assert profiles.settings["revision"] == revision
    assert profiles.store.get(profiles.key)["revision"] == revision
    assert profiles.members("dishwasher/eco") == [original]
    assert len(profiles.library()["recordings"]) == 1
    assert profiles.detail(original) == before


async def test_saved_trim_api_checks_origin_and_returns_same_identity_and_new_revision(profiles):
    identity = short_saved_cycle(profiles, 1000, 10)
    application = Application(profiles.store, snapshot=tiny())
    application.appliance_profiles = profiles
    async def no_lifecycle():
        pass
    application.start = application.close = no_lifecycle
    async with TestClient(TestServer(create_web(application))) as client:
        url = f"/api/profile-recordings/{identity}/revise"
        body = {"reviewed": True, "revision": profiles.settings["revision"],
                "start_seconds": 1, "end_seconds": 5}
        assert (await client.post(url, json=body)).status == 403
        response = await client.post(url, json=body, headers={"X-EnergyManager": "1"})
        assert response.status == 200
        saved = await response.json()
        assert saved["id"] == identity
        assert saved["library_revision"] == body["revision"] + 1
        assert (await client.post(url, json=body, headers={"X-EnergyManager": "1"})).status == 400
        assert profiles.members("dishwasher/eco") == [saved["id"]]



def legacy_trim_copy(profiles, original, identity, start, end, saved_seconds):
    """Build a labelled pre-ARCH-018 immutable copy without the new save path."""
    import json
    row = profiles.get(original)
    summary = profiles.preview(original, {"start_seconds": start, "end_seconds": end})
    copied = {**row, "id": identity, "capture_id": row.get("capture_id", original),
              "trimmed_from": original, "summary": summary,
              "saved_at": (AT+timedelta(seconds=saved_seconds)).isoformat()}
    with profiles.store.connection:
        profiles.store.connection.execute("INSERT INTO appliance_recordings VALUES (?,?,?,?)",
            (identity, profiles.mode, "saved", json.dumps(copied)))
        profiles.store.connection.execute("INSERT INTO appliance_samples SELECT ?,at,power_w,error FROM appliance_samples WHERE recording_id=?",
            (identity, original))
    return copied


async def test_consolidation_uses_latest_trim_save_time_preserves_raw_inclusion_and_frozen_plans(profiles):
    original = short_saved_cycle(profiles, 1000, 10)
    distinct = short_saved_cycle(profiles, 1000, 10)
    before = profiles.detail(original)
    legacy_trim_copy(profiles, original, "SYNTHETIC-latest-saved", 2, 6, 300)
    legacy_trim_copy(profiles, original, "SYNTHETIC-inserted-later-but-older", 1, 9, 100)
    profiles.store.record(tiny(), {"id": "SYNTHETIC-frozen-plan", "curve": before}, "accepted")
    frozen = profiles.store.connection.execute("SELECT snapshot,result FROM decisions").fetchone()
    migrated = ApplianceProfiles(profiles.app)
    assert len(migrated.library()["recordings"]) == 2  # Equal notes/times do not merge distinct runs.
    assert migrated.get(original)["summary"]["duration_seconds"] == 4
    assert migrated.detail(original)["points"] == before["points"]
    assert migrated.detail("SYNTHETIC-latest-saved")["id"] == original
    assert migrated.members("dishwasher/eco") == [original, distinct]
    assert (await migrated.profile_detail("dishwasher", "eco"))["summary"]["energy_kwh"] == pytest.approx(7000/3600000)
    assert profiles.store.connection.execute("SELECT snapshot,result FROM decisions").fetchone() == frozen
    revision = migrated.settings["revision"]
    again = ApplianceProfiles(profiles.app)
    assert again.settings["revision"] == revision
    assert len(again.library()["recordings"]) == 2


async def test_consolidation_preserves_excluded_capture_and_alias_actions_use_canonical_identity(profiles):
    original = short_saved_cycle(profiles, 1000, 10)
    profiles.select(original, {"revision": profiles.settings["revision"], "included": False})
    legacy_trim_copy(profiles, original, "SYNTHETIC-excluded-trim", 1, 5, 200)
    migrated = ApplianceProfiles(profiles.app)
    assert migrated.members("dishwasher/eco") == [] and migrated.library()["profiles"] == {}
    migrated.select("SYNTHETIC-excluded-trim", {"revision": migrated.settings["revision"]})
    assert migrated.members("dishwasher/eco") == [original]
    assert (await migrated.profile_detail("dishwasher", "eco"))["summary"]["duration_seconds"] == 4
    migrated.delete("SYNTHETIC-excluded-trim", {"revision": migrated.settings["revision"], "confirmed": True})
    assert migrated.library()["recordings"] == [] and migrated.library()["profiles"] == {}
    assert migrated.settings["recording_aliases"] == {}


def test_failed_consolidation_rolls_back_samples_rows_membership_and_revision(profiles):
    import sqlite3
    original = short_saved_cycle(profiles, 1000, 10)
    legacy_trim_copy(profiles, original, "SYNTHETIC-rollback", 1, 5, 200)
    before = list(profiles.store.connection.iterdump())
    profiles.store.connection.executescript("""
        CREATE TRIGGER synthetic_consolidation_failure BEFORE DELETE ON appliance_recordings
        BEGIN SELECT RAISE(FAIL,'SYNTHETIC consolidation failure'); END;
    """)
    with pytest.raises(sqlite3.IntegrityError, match="consolidation failure"):
        ApplianceProfiles(profiles.app)
    profiles.store.connection.execute("DROP TRIGGER synthetic_consolidation_failure")
    profiles.store.connection.commit()
    assert list(profiles.store.connection.iterdump()) == before
    assert profiles.members("dishwasher/eco") == [original]
    migrated = ApplianceProfiles(profiles.app)
    assert len(migrated.library()["recordings"]) == 1


def test_consolidation_rejects_conflicting_raw_evidence_without_partial_changes(profiles):
    original = short_saved_cycle(profiles, 1000, 10)
    legacy_trim_copy(profiles, original, "SYNTHETIC-conflicting-copy", 1, 5, 200)
    profiles.store.connection.execute("UPDATE appliance_samples SET power_w=77 WHERE recording_id=?",
                                     ("SYNTHETIC-conflicting-copy",))
    profiles.store.connection.commit()
    before = list(profiles.store.connection.iterdump())
    with pytest.raises(ValueError, match="Conflicting raw"):
        ApplianceProfiles(profiles.app)
    assert list(profiles.store.connection.iterdump()) == before


def test_consolidation_retains_surviving_raw_evidence_when_the_original_was_deleted(profiles):
    original = short_saved_cycle(profiles, 1000, 10)
    first = legacy_trim_copy(profiles, original, "SYNTHETIC-survivor", 1, 8, 100)
    latest = legacy_trim_copy(profiles, original, "SYNTHETIC-survivor-latest", 2, 6, 300)
    profiles.select(latest["id"], {"revision": profiles.settings["revision"]})
    profiles.delete(original, {"revision": profiles.settings["revision"], "confirmed": True})
    before = profiles.detail(first["id"])["points"]
    migrated = ApplianceProfiles(profiles.app)
    assert len(migrated.library()["recordings"]) == 1
    assert migrated.members("dishwasher/eco") == [first["id"]]
    assert migrated.detail(latest["id"])["points"] == before
    assert migrated.get(first["id"])["summary"]["duration_seconds"] == 4


def test_recording_library_keeps_older_records_and_does_not_consolidate_equal_dates_or_notes(profiles):
    import json
    original = short_saved_cycle(profiles, 1000, 10)
    row = profiles.get(original)
    with profiles.store.connection:
        for index in range(110):
            identity = f"SYNTHETIC-distinct-capture-{index}"
            profiles.store.connection.execute("INSERT INTO appliance_recordings VALUES (?,?,?,?)",
                (identity, profiles.mode, "saved", json.dumps({**row, "id": identity})))
    migrated = ApplianceProfiles(profiles.app)
    assert len(migrated.library()["recordings"]) == 111
    assert original in {r["id"] for r in migrated.library()["recordings"]}
    assert migrated.members("dishwasher/eco") == [original]



async def test_washing_program_metadata_preserves_legacy_capture_average_and_frozen_evidence(profiles):
    profiles.configure({"revision": profiles.settings["revision"], "machine": "washing_machine",
                        "entity_id": "sensor.synthetic_washer", "start_threshold_w": 10, "idle_timeout_minutes": 1})
    row = profiles.arm({"machine": "washing_machine", "program": "whites_60", "notes": "SYNTHETIC legacy washer"})
    for seconds, power in ((0, 0), (5, 1000), (10, 500), (15, 0)):
        profiles.ingest(row["id"], AT+timedelta(seconds=seconds), power)
    profiles.finish(row["id"])
    profiles.accept(row["id"], {"revision": profiles.settings["revision"], "reviewed": True})
    before = profiles.detail(row["id"])
    average = await profiles.profile_detail("washing_machine", "whites_60")
    profiles.store.record(tiny(), {"id": "SYNTHETIC-frozen-program", "curve": average}, "accepted")
    frozen = profiles.store.connection.execute("SELECT snapshot,result FROM decisions").fetchone()
    selected, members = dict(profiles.settings["selected"]), dict(profiles.settings["members"])
    result = profiles.save_program({"revision": profiles.settings["revision"], "machine": "washing_machine",
                                   "program": "whites_60", "name": "Cotton / 60°C"}, create=False)
    assert result["program"] == {"id": "whites_60", "name": "Cotton / 60°C"}
    assert profiles.detail(row["id"]) == before
    assert profiles.settings["selected"] == selected and profiles.settings["members"] == members
    restored = ApplianceProfiles(profiles.app)
    assert restored.programs()["washing_machine"]["whites_60"] == "Cotton / 60°C"
    current = await restored.profile_detail("washing_machine", "whites_60")
    assert current["points"] == average["points"] and current["summary"] == average["summary"]
    assert profiles.store.connection.execute("SELECT snapshot,result FROM decisions").fetchone() == frozen


def test_new_washing_program_has_stable_identity_no_invented_profile_and_is_immediately_recordable(profiles):
    defaults = dict(profiles.programs()["washing_machine"])
    created = profiles.save_program({"revision": profiles.settings["revision"], "machine": "washing_machine",
                                    "name": "  Silk   30°C  "}, create=True)
    identity = created["program"]["id"]
    assert identity not in defaults and created["program"]["name"] == "Silk 30°C"
    assert not created["library"]["profiles"] and not created["library"]["recordings"]
    renamed = profiles.save_program({"revision": profiles.settings["revision"], "machine": "washing_machine",
                                    "program": identity, "name": "Wool & silk 30"}, create=False)
    assert renamed["program"]["id"] == identity
    from contextlib import closing
    with closing(Store(profiles.store.path)) as restarted_store:
        restored = ApplianceProfiles(SimpleNamespace(store=restarted_store, demo=False, ha=object(), now=lambda: AT))
        assert restored.programs()["washing_machine"] == {**defaults, identity: "Wool & silk 30"}
        restored.configure({"revision": restored.settings["revision"], "machine": "washing_machine",
                            "entity_id": "sensor.synthetic_washer", "start_threshold_w": 10, "idle_timeout_minutes": 1})
        row = restored.arm({"machine": "washing_machine", "program": identity})
        assert row["program"] == identity and row["status"] == "armed"


@pytest.mark.parametrize("name", [None, 42, "", "   ", "\x00", "Silk\u200b30", "a"*81])
def test_invalid_program_names_do_not_change_the_catalogue(profiles, name):
    before = profiles.library()
    with pytest.raises(ValueError, match="name"):
        profiles.save_program({"revision": profiles.settings["revision"], "machine": "washing_machine", "name": name}, create=True)
    assert profiles.library() == before


def test_duplicate_normalization_unknown_programs_bosch_and_stale_edits_are_rejected(profiles):
    created = profiles.save_program({"revision": profiles.settings["revision"], "machine": "washing_machine", "name": "Café"}, create=True)
    revision = profiles.settings["revision"]
    for name in ("  WHITES  60°C  ", "Cafe\u0301", "Ｃａｆé"):
        with pytest.raises(ValueError, match="already exists"):
            profiles.save_program({"revision": revision, "machine": "washing_machine", "name": name}, create=True)
    for machine in ("dishwasher", "mazak"):
        with pytest.raises(ValueError, match="Only washing-machine"):
            profiles.save_program({"revision": revision, "machine": machine, "name": "Test"}, create=True)
    with pytest.raises(ValueError, match="already exists"):
        profiles.save_program({"revision": revision, "machine": "washing_machine", "program": created["program"]["id"], "name": "Darks 40°C"}, create=False)
    with pytest.raises(ValueError, match="existing"):
        profiles.save_program({"revision": revision, "machine": "washing_machine", "program": "absent", "name": "Test"}, create=False)
    with pytest.raises(ValueError, match="another view"):
        profiles.save_program({"revision": revision-1, "machine": "washing_machine", "name": "Test"}, create=True)
    assert profiles.settings["revision"] == revision


def test_program_write_failure_is_atomic_and_demo_catalogue_is_independent(profiles):
    import sqlite3
    before = profiles.library()
    profiles.store.connection.executescript("""
        CREATE TRIGGER synthetic_program_failure BEFORE INSERT ON state
        BEGIN SELECT RAISE(FAIL,'SYNTHETIC program write failure'); END;
    """)
    with pytest.raises(sqlite3.IntegrityError, match="program write failure"):
        profiles.save_program({"revision": profiles.settings["revision"], "machine": "washing_machine", "name": "Silk"}, create=True)
    assert profiles.library() == before
    profiles.store.connection.execute("DROP TRIGGER synthetic_program_failure")
    profiles.store.connection.commit()
    demo = ApplianceProfiles(SimpleNamespace(store=profiles.store, demo=True, ha=None, now=lambda: AT))
    demo.save_program({"revision": demo.settings["revision"], "machine": "washing_machine", "name": "Silk"}, create=True)
    assert "Silk" not in profiles.programs()["washing_machine"].values()
    assert demo.library()["recordings"] == []


async def test_program_api_origin_revision_and_metadata_edits_never_send_appliance_commands(profiles):
    application = Application(profiles.store, snapshot=tiny())
    application.appliance_profiles = profiles
    calls = []
    async def forbid_command(*args):
        calls.append(args)
        raise AssertionError("Metadata must not command an appliance")
    async def no_lifecycle():
        pass
    profiles.bosch.command = forbid_command
    application.start = application.close = no_lifecycle
    async with TestClient(TestServer(create_web(application))) as client:
        body = {"revision": profiles.settings["revision"], "machine": "washing_machine", "name": "SYNTHETIC Handwash"}
        assert (await client.post("/api/profiles/program-create", json=body)).status == 403
        response = await client.post("/api/profiles/program-create", json=body, headers={"X-EnergyManager": "1"})
        assert response.status == 200
        created = await response.json()
        assert (await client.post("/api/profiles/program-create", json=body, headers={"X-EnergyManager": "1"})).status == 400
        response = await client.post("/api/profiles/program-rename", headers={"X-EnergyManager": "1"}, json={
            "revision": created["library"]["revision"], "machine": "washing_machine", "program": created["program"]["id"], "name": "SYNTHETIC Handwash renamed"})
        assert response.status == 200 and not calls
        assert (await response.json())["program"]["id"] == created["program"]["id"]
