"""Deterministic synthetic Home Connect/Refoss traces; no installation access."""

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from energymanager.appliance_profiles import ApplianceProfiles
from energymanager.bosch import FIELDS
from energymanager.store import Store

AT = datetime(2026, 11, 2, 12, tzinfo=UTC)
ECO, INTENSIVE = "synthetic_eco_50", "synthetic_intensive_70"


class FakeBoschHA:
    def __init__(self, entities):
        self.calls = []
        self.on_read = None
        self.entities = entities
        self.rows = {entity: {"state": "off", "attributes": {}} for entity in entities.values()}
        self.rows["sensor.synthetic_refoss"] = {"state": "100", "attributes": {"unit_of_measurement": "W"}}
        for key in ("selected_program", "active_program"):
            self.rows[entities[key]] = {"state": ECO, "attributes": {"options": [ECO, INTENSIVE]}}
        self.set("operation", "ready")
        self.set("power", "on")
        self.set("remote_control", "on")
        self.set("remote_start", "on")
        self.set("door", "off")
        self.rows[entities["delay"]] = {"state": "0", "attributes": {"unit_of_measurement": "s"}}

    def set(self, key, state):
        self.rows[self.entities[key]]["state"] = state

    async def entity_state(self, entity):
        if self.on_read:
            self.on_read()
        return deepcopy(self.rows[entity])

    async def service(self, domain, service, data):
        self.calls.append((domain, service, data))


@pytest.fixture
def bosch(tmp_path):
    store = Store(tmp_path / "SYNTHETIC-bosch.sqlite")
    entities = {key: domains[0] + ".synthetic_bosch_" + key for key, (_, domains) in FIELDS.items()}
    ha = FakeBoschHA(entities)
    hardware = SimpleNamespace(epoch=1, lock=asyncio.Lock(), enabled=True)
    hardware.state = lambda: {"enabled": hardware.enabled}
    app = SimpleNamespace(store=store, demo=False, ha=ha, hardware=hardware,
                          policy=SimpleNamespace(control_enabled=True), now=lambda: AT)
    profiles = ApplianceProfiles(app)
    profiles.configure({"revision": 1, "machine": "dishwasher", "entity_id": "sensor.synthetic_refoss",
                        "start_threshold_w": 10, "idle_timeout_minutes": 1})
    profiles.configure_bosch({"revision": 2, "entities": entities})
    yield profiles.bosch
    store.close()


async def tick(bosch, seconds, operation="run", program=ECO, power=100):
    bosch.app.now = lambda: AT + timedelta(seconds=seconds)
    bosch.app.ha.set("operation", operation)
    bosch.app.ha.set("active_program", program)
    bosch.app.ha.rows["sensor.synthetic_refoss"]["state"] = str(power)
    await bosch.poll()


async def cycle(bosch):
    await tick(bosch, 0, "ready")
    for seconds in range(5, 30, 5):
        await tick(bosch, seconds)
    await tick(bosch, 30, "finished")
    return bosch.profiles.library()["recordings"][0]["id"]


@pytest.mark.asyncio
async def test_panel_run_captures_silent_phases_finishes_and_requires_review(bosch):
    bosch.app.hardware.enabled = False  # Observation never requires command authority.
    await tick(bosch, 0, "delayedstart")
    assert bosch.profiles.library()["recordings"] == []
    for seconds in range(5, 95, 5):
        await tick(bosch, seconds, power=0)
    identity = bosch.capture
    assert bosch.profiles.get(identity)["status"] == "recording"  # No idle-timeout finish.
    await tick(bosch, 95, "finished", power=0)
    row = bosch.profiles.detail(identity)
    assert row["status"] == "review" and not row["interrupted"]
    assert row["program"] == ECO and row["source"] == "bosch"
    assert row["modifiers"]["half_load"] == "off"
    assert bosch.profiles.library()["profiles"] == {}
    bosch.profiles.accept(identity, {"revision": bosch.profiles.settings["revision"], "reviewed": True})
    assert bosch.profiles.library()["profiles"]["dishwasher/" + ECO]["recording_count"] == 1
    assert bosch.app.ha.calls == []
    assert "heavy" in bosch.profiles.library()["programs"]["dishwasher"]
    assert INTENSIVE in bosch.profiles.library()["programs"]["dishwasher"]


@pytest.mark.asyncio
async def test_first_seen_running_and_restart_evidence_cannot_enter_average(bosch):
    await tick(bosch, 0)
    old = bosch.capture
    await tick(bosch, 5)
    restored = ApplianceProfiles(bosch.app)
    assert restored.get(old)["interrupted"]
    assert restored.get(old)["status"] == "review"
    await tick(restored.bosch, 10)
    await tick(restored.bosch, 15, "finished")
    new = restored.library()["recordings"][0]["id"]
    assert new != old and restored.get(new)["interrupted"]
    with pytest.raises(ValueError, match="interrupted|missing"):
        restored.accept(new, {"revision": restored.settings["revision"], "reviewed": True})


@pytest.mark.asyncio
@pytest.mark.parametrize("ending", ["error", "ready", "inactive", "pause", "unavailable"])
async def test_interrupted_or_missing_operation_is_not_a_complete_cycle(bosch, ending):
    await tick(bosch, 0, "ready")
    await tick(bosch, 5)
    identity = bosch.capture
    await tick(bosch, 10, ending)
    await tick(bosch, 15, "finished")
    row = bosch.profiles.get(identity)
    assert row["interrupted"]
    with pytest.raises(ValueError, match="interrupted|missing"):
        bosch.profiles.accept(identity, {"revision": bosch.profiles.settings["revision"], "reviewed": True})


@pytest.mark.asyncio
async def test_program_changes_and_feedback_gaps_do_not_fabricate_a_complete_start(bosch):
    await tick(bosch, 0, "ready")
    await tick(bosch, 30)  # Start may have occurred while observation was missing.
    first = bosch.capture
    assert bosch.profiles.get(first)["interrupted"]
    await tick(bosch, 35, program=INTENSIVE)
    assert bosch.profiles.get(first)["status"] == "review"
    assert bosch.profiles.get(bosch.capture)["interrupted"]


@pytest.mark.asyncio
async def test_missing_power_remains_a_gap_not_zero(bosch):
    await tick(bosch, 0, "ready")
    await tick(bosch, 5)
    identity = bosch.capture
    await tick(bosch, 10, power="unavailable")
    await tick(bosch, 15)
    await tick(bosch, 20, "finished")
    assert bosch.profiles.detail(identity)["points"][1]["power_w"] is None
    with pytest.raises(ValueError, match="missing"):
        bosch.profiles.accept(identity, {"revision": bosch.profiles.settings["revision"], "reviewed": True})


@pytest.mark.asyncio
async def test_selection_is_not_start_and_start_waits_for_actual_run(bosch):
    result = await bosch.command({"command": "select", "program": ECO})
    assert result["command"]["outcome"] == "pending"
    assert bosch.app.ha.calls == [("select", "select_option", {"entity_id": bosch.config["selected_program"], "option": ECO})]
    assert bosch.profiles.library()["recordings"] == []
    await tick(bosch, 0, "ready")
    await bosch.command({"command": "start", "program": ECO})
    assert bosch.app.ha.calls[-1][2]["entity_id"] == bosch.config["active_program"]
    assert bosch.profiles.library()["recordings"] == []
    with pytest.raises(ValueError, match="Await"):
        await bosch.command({"command": "start", "program": ECO})
    await tick(bosch, 5)
    assert bosch.last_command["outcome"] == "confirmed"
    assert bosch.profiles.get(bosch.capture)["status"] == "recording"


@pytest.mark.asyncio
@pytest.mark.parametrize("key,value", [("door", "on"), ("remote_start", "off"),
    ("remote_control", "unavailable"), ("operation", "run"), ("operation", "delayedstart"),
    ("selected_program", INTENSIVE), ("selected_program", "unknown"), ("delay", "600"), ("delay", "unavailable")])
async def test_start_guards_do_not_write(bosch, key, value):
    bosch.app.ha.set("active_program", "unknown")
    bosch.app.ha.set(key, value)
    with pytest.raises(ValueError):
        await bosch.command({"command": "start", "program": ECO})
    assert bosch.app.ha.calls == []


@pytest.mark.asyncio
async def test_revoked_authority_and_changed_mapping_during_read_do_not_write(bosch):
    def revoke():
        bosch.app.hardware.epoch += 1
    bosch.app.ha.on_read = revoke
    with pytest.raises(ValueError, match="authority"):
        await bosch.command({"command": "start", "program": ECO})
    assert bosch.app.ha.calls == []
    bosch.app.ha.on_read = None
    bosch.app.hardware.enabled = False
    with pytest.raises(ValueError, match="hardware control"):
        await bosch.command({"command": "select", "program": ECO})
    bosch.app.hardware.enabled = True
    bosch.app.demo = True
    with pytest.raises(ValueError, match="configured"):
        await bosch.command({"command": "start", "program": ECO})


@pytest.mark.asyncio
async def test_modifiers_are_explicit_and_power_on_does_not_start(bosch):
    await bosch.command({"command": "modifier", "modifier": "extra_dry", "enabled": True})
    assert bosch.app.ha.calls[-1] == ("switch", "turn_on", {"entity_id": bosch.config["extra_dry"]})
    bosch.app.ha.set("extra_dry", "on")
    await bosch.read()
    bosch.app.ha.set("power", "off")
    await bosch.command({"command": "power_on"})
    assert bosch.app.ha.calls[-1] == ("switch", "turn_on", {"entity_id": bosch.config["power"]})
    assert bosch.profiles.library()["recordings"] == []


@pytest.mark.asyncio
async def test_failed_service_is_visible_and_never_replayed_on_restart(bosch):
    async def fail(*args):
        raise RuntimeError("SYNTHETIC transport failure")
    bosch.app.ha.service = fail
    with pytest.raises(ValueError, match="unknown"):
        await bosch.command({"command": "start", "program": ECO})
    restored = ApplianceProfiles(bosch.app)
    assert restored.bosch.last_command["outcome"] == "failed"
    await tick(restored.bosch, 5, "ready")
    assert bosch.app.ha.calls == []


@pytest.mark.asyncio
async def test_delete_removes_samples_membership_and_survives_restart(bosch):
    identity = await cycle(bosch)
    profiles = bosch.profiles
    profiles.accept(identity, {"revision": profiles.settings["revision"], "reviewed": True})
    before = profiles.settings["revision"]
    with pytest.raises(ValueError, match="Confirm"):
        profiles.delete(identity, {"revision": before})
    with pytest.raises(ValueError, match="another view"):
        profiles.delete(identity, {"revision": before-1, "confirmed": True})
    profiles.delete(identity, {"revision": before, "confirmed": True})
    restored = ApplianceProfiles(bosch.app)
    assert restored.library()["profiles"] == {}
    assert restored.library()["recordings"] == []
    assert profiles.store.connection.execute("SELECT count(*) FROM appliance_samples").fetchone()[0] == 0
    profiles.ingest(identity, AT + timedelta(seconds=35), 0)  # Deleted in-flight reads cannot resurrect it.


@pytest.mark.asyncio
async def test_delete_transaction_rolls_back_membership_and_samples(bosch):
    identity = await cycle(bosch)
    profiles = bosch.profiles
    profiles.accept(identity, {"revision": profiles.settings["revision"], "reviewed": True})
    before = deepcopy(profiles.library())
    profiles.store.connection.execute("CREATE TRIGGER synthetic_delete_failure BEFORE DELETE ON appliance_recordings BEGIN SELECT RAISE(ABORT,'synthetic'); END")
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        profiles.delete(identity, {"revision": profiles.settings["revision"], "confirmed": True})
    assert profiles.library() == before
    assert len(profiles.detail(identity)["points"]) == 6


@pytest.mark.asyncio
async def test_deleting_or_manually_finishing_current_capture_does_not_recapture_same_run(bosch):
    await tick(bosch, 0, "ready")
    await tick(bosch, 5)
    identity = bosch.capture
    bosch.profiles.finish(identity)
    assert bosch.profiles.get(identity)["interrupted"]
    bosch.profiles.delete(identity, {"revision": bosch.profiles.settings["revision"], "confirmed": True})
    await tick(bosch, 10)
    assert bosch.profiles.library()["recordings"] == []
    await tick(bosch, 15, "finished")
    await tick(bosch, 20)
    assert len(bosch.profiles.library()["recordings"]) == 1


def test_selected_and_active_entities_cannot_be_confused(bosch):
    entities = {**bosch.config, "selected_program": bosch.config["active_program"]}
    with pytest.raises(ValueError, match="distinct"):
        bosch.profiles.configure_bosch({"revision": bosch.profiles.settings["revision"], "entities": entities})
    with pytest.raises(ValueError, match="automatically"):
        bosch.profiles.arm({"machine": "dishwasher", "program": "eco", "automatic": True})


@pytest.mark.asyncio
async def test_api_commands_and_permanent_delete_keep_same_origin_and_confirmation_guards(bosch):
    from aiohttp.test_utils import TestClient, TestServer
    from energymanager.service import Application
    from energymanager.web import create_web
    from test_first_slice import tiny

    identity = await cycle(bosch)
    profiles = bosch.profiles
    profiles.accept(identity, {"revision": profiles.settings["revision"], "reviewed": True})
    app = Application(profiles.store, snapshot=tiny())
    app.appliance_profiles = profiles
    async def no_lifecycle():
        pass
    app.start = app.close = no_lifecycle
    async with TestClient(TestServer(create_web(app))) as client:
        url = "/api/profiles/bosch-command"
        body = {"command": "select", "program": ECO}
        assert (await client.post(url, json=body)).status == 403
        headers = {"X-EnergyManager": "1"}
        assert (await client.post(url, json=body, headers={**headers, "Origin": "https://example.invalid"})).status == 403
        assert (await client.post(url, json=body, headers=headers)).status == 200
        url = f"/api/profile-recordings/{identity}/delete"
        revision = profiles.settings["revision"]
        assert (await client.post(url, json={"revision": revision}, headers=headers)).status == 400
        response = await client.post(url, json={"revision": revision, "confirmed": True}, headers=headers)
        assert response.status == 200
        assert (await response.json())["library_revision"] == revision + 1
        assert (await client.get(f"/api/profile-recordings/{identity}")).status == 400
        assert (await client.get("/api/profiles/dishwasher/" + ECO)).status == 400


@pytest.mark.asyncio
async def test_deleting_a_retrimmed_capture_removes_its_single_physical_recording(bosch):
    identity = await cycle(bosch)
    profiles = bosch.profiles
    profiles.accept(identity, {"revision": profiles.settings["revision"], "reviewed": True})
    revised = profiles.revise(identity, {"reviewed": True, "revision": profiles.settings["revision"],
                                       "start_seconds": 5, "end_seconds": 20})
    assert revised["id"] == identity and len(profiles.detail(identity)["points"]) == 6
    profiles.delete(identity, {"confirmed": True, "revision": profiles.settings["revision"]})
    assert profiles.library()["profiles"] == {} and profiles.library()["recordings"] == []


@pytest.mark.asyncio
async def test_missing_meter_blocks_start_and_late_feedback_resolves_unconfirmed_command(bosch):
    bosch.app.ha.rows["sensor.synthetic_refoss"]["state"] = "unavailable"
    with pytest.raises(ValueError, match="measurement"):
        await bosch.command({"command": "start", "program": ECO})
    assert bosch.app.ha.calls == []
    bosch.app.ha.rows["sensor.synthetic_refoss"]["state"] = "0"
    await bosch.command({"command": "start", "program": ECO})
    await tick(bosch, 35, "ready")
    assert bosch.last_command["outcome"] == "unconfirmed"
    await tick(bosch, 40)
    assert bosch.last_command["outcome"] == "confirmed"
    assert len(bosch.app.ha.calls) == 1


@pytest.mark.asyncio
async def test_unavailable_program_cannot_be_assigned_to_legacy_eco(bosch):
    await tick(bosch, 0, "ready")
    await tick(bosch, 5, program="unavailable")
    assert bosch.profiles.library()["recordings"] == []
    assert bosch.capture_error
    await tick(bosch, 10, program=INTENSIVE)
    row = bosch.profiles.get(bosch.capture)
    assert row["program"] == INTENSIVE and row["interrupted"]


@pytest.mark.asyncio
async def test_unknown_active_program_preserves_capabilities_without_inventing_execution(bosch):
    # Actual HA option spelling; every entity/measurement and service is still a local fake.
    eco = "dishcare_dishwasher_program_eco_50"
    ha = bosch.app.ha
    ha.rows[bosch.config["selected_program"]] = {"state": eco, "attributes": {"options": [eco]}}
    ha.rows[bosch.config["active_program"]] = {"state": "unknown", "attributes": {"options": [eco]}}
    await bosch.poll()
    assert bosch.value("active_program") is None
    assert bosch.readings["active_program"]["options"] == [eco]
    assert bosch.profiles.library()["recordings"] == []
    assert ha.calls == []
    await bosch.command({"command": "start", "program": eco})
    assert ha.calls == [("select", "select_option", {"entity_id": bosch.config["active_program"], "option": eco})]
    assert bosch.value("active_program") is None
    assert bosch.last_command["outcome"] == "pending"
    assert bosch.profiles.library()["recordings"] == []
    await tick(bosch, 5, program=eco)
    assert bosch.last_command["outcome"] == "confirmed"
    assert bosch.profiles.get(bosch.capture)["program"] == eco


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["unavailable", "failed_read", "malformed_attributes", "malformed_options",
                                    "mixed_options", "missing_options", "missing_program"])
async def test_unknown_active_program_does_not_reuse_invalid_or_stale_capabilities(bosch, case):
    ha = bosch.app.ha
    await bosch.read()  # A previous successful options read must not authorize a failed new read.
    active = ha.rows[bosch.config["active_program"]]
    active["state"] = "unknown"
    if case == "unavailable":
        active["state"] = "unavailable"
    elif case == "failed_read":
        original = ha.entity_state
        async def failed_read(entity):
            if entity == bosch.config["active_program"]:
                raise TimeoutError("SYNTHETIC failed HA read")
            return await original(entity)
        ha.entity_state = failed_read
    elif case == "malformed_attributes":
        active["attributes"] = "invalid"
    elif case == "malformed_options":
        active["attributes"]["options"] = ECO
    elif case == "mixed_options":
        active["attributes"]["options"] = [ECO, None]
    elif case == "missing_options":
        active["attributes"] = {}
    else:
        active["attributes"]["options"] = [INTENSIVE]
    with pytest.raises(ValueError, match="active-program start control"):
        await bosch.command({"command": "start", "program": ECO})
    assert ha.calls == []
    assert bosch.value("active_program") is None
    assert bosch.profiles.library()["recordings"] == []
