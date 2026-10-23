"""Configured-mode control and discovery tested against local HA endpoints only."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from energymanager.configuration import configured_application, create_configuration_if_missing
from energymanager.connections import HomeAssistantConnection
from energymanager.control import Command
from energymanager.hardware import HardwareControl
from energymanager.notifications import Notifications, NotificationTarget
from energymanager.settings import ConfigurationFile, SETTING_FIELDS
from energymanager.store import Store


@pytest.fixture
async def installation(tmp_path):
    path = tmp_path / "settings.json"
    create_configuration_if_missing(path)
    data = json.loads(path.read_bytes())
    for field in SETTING_FIELDS:
        if field.kind != "entity":
            continue
        group, key = field.path.split(".")
        data[group][key] = f"{field.domains[0]}.{key}"
    calls = []
    rows = [{"entity_id": data[group][key], "state": "1", "attributes": {
                "friendly_name": field.label,
                "unit_of_measurement": field.units[0] if field.units else ""}}
            for field in SETTING_FIELDS if field.kind == "entity"
            for group, key in [field.path.split(".")]]

    async def states(request):
        return web.json_response(rows)

    async def services(request):
        return web.json_response([{"domain": "notify", "services": {
            "mobile_app_phone": {"name": "Verification phone"}, "send_message": {}, "notify": {}}}])

    async def service(request):
        calls.append({"service": request.match_info["service"], **await request.json()})
        return web.json_response([])

    fake = web.Application()
    fake.add_routes([web.get("/api/states", states), web.get("/api/services", services),
                     web.post("/api/services/{domain}/{service}", service)])
    store = Store(tmp_path / "runtime.sqlite")
    async with TestServer(fake) as endpoint:
        data["home_assistant_url"] = str(endpoint.make_url("/api"))
        path.write_text(json.dumps(data), encoding="utf-8")
        app = configured_application(path, store)
        editor = ConfigurationFile(path, mode="configured")
        control = HardwareControl(app, editor)
        app.hardware = control
        app.observation = replace(app.observation, at=datetime.now(UTC), quality="measured")
        await app.ha.__aenter__()
        try:
            yield app, editor, control, rows, calls
        finally:
            app.shutdown = True
            await control.close()
            for task in app.protective_tasks:
                task.cancel()
            await asyncio.gather(*app.protective_tasks, return_exceptions=True)
            await app.ha.__aexit__()
            store.close()


async def test_single_switch_changes_live_authority_persists_and_stops_both_devices(installation):
    app, editor, control, _, calls = installation
    original = editor.path.read_bytes()
    assert not control.state()["requested"] and not app.actuator.enabled
    assert not editor.read()["issues"]
    await control.set_requested(True)
    assert app.actuator.enabled and app.policy.control_enabled
    assert app.store.get("hardware_control_enabled") is True
    await asyncio.gather(*app.protective_tasks)
    calls.clear()
    await control.set_requested(False)
    assert not app.actuator.enabled and not app.policy.control_enabled
    assert app.store.get("hardware_control_enabled") is False
    assert calls == [{"service": "select_option", "entity_id": "select.force", "option": "1"},
                     {"service": "set_value", "entity_id": "number.ess_setpoint", "value": 0}]
    assert editor.path.read_bytes() == original
    assert not editor.read()["restart_required"]


@pytest.mark.parametrize("problem", ["demo", "stale", "unknown", "settings", "missing_entity", "offline_actuator"])
async def test_control_cannot_enable_until_settings_and_live_inputs_are_ready(installation, problem):
    app, editor, control, rows, calls = installation
    if problem == "demo":
        app.demo = True
    elif problem == "stale":
        app.observation = replace(app.observation, at=datetime.now(UTC) - timedelta(minutes=1))
    elif problem == "unknown":
        app.observation = replace(app.observation, quality="unknown")
    elif problem == "settings":
        editor.save(editor.read()["revision"], {"policy.daily_soc_percent": 61})
    elif problem == "missing_entity":
        rows[:] = [row for row in rows if row["entity_id"] != "number.current"]
    else:
        next(row for row in rows if row["entity_id"] == "number.current")["state"] = "unavailable"
    with pytest.raises(ValueError):
        await control.set_requested(True)
    assert not app.actuator.enabled and not control.requested
    assert app.store.get("hardware_control_enabled", False) is False
    assert not calls


async def test_missing_ev_soc_reading_does_not_block_independent_ess_control(installation):
    app, _, control, _, _ = installation
    app.observation = replace(app.observation, ev_state_known=False, ev_phase_known=False)
    await control.set_requested(True)
    assert app.actuator.enabled
    assert not app.ev_valid


async def test_disable_revokes_inflight_commands_before_the_next_hardware_write(installation):
    app, _, control, _, calls = installation
    await control.set_requested(True)
    await asyncio.gather(*app.protective_tasks)
    calls.clear()
    started, release = asyncio.Event(), asyncio.Event()
    original = app.ha.service

    async def delayed(domain, service, body):
        if body.get("entity_id") == "number.ess_setpoint" and body.get("value") != 0:
            started.set()
            await release.wait()
        await original(domain, service, body)

    app.ha.service = delayed
    command = Command(app.revision, "test", app.now(), 1.38, -0.5, 1, 6, 4, "Verification only")
    dispatch = asyncio.create_task(app.actuator.apply(command, app.revision, app.observation))
    await asyncio.wait_for(started.wait(), 1)
    disabling = asyncio.create_task(control.set_requested(False))
    await asyncio.sleep(0)
    assert not app.actuator.enabled
    release.set()
    await asyncio.gather(dispatch, disabling)
    assert not any(call.get("entity_id") == "number.current" for call in calls)
    assert calls[-2:] == [{"service": "select_option", "entity_id": "select.force", "option": "1"},
                         {"service": "set_value", "entity_id": "number.ess_setpoint", "value": 0}]


async def test_disable_surfaces_stop_failure_and_still_clears_ess(installation):
    app, _, control, _, calls = installation
    await control.set_requested(True)
    await asyncio.gather(*app.protective_tasks)
    calls.clear()
    original = app.ha.service

    async def fail_ev(domain, service, body):
        if body.get("entity_id") == "select.force":
            raise RuntimeError("Verification stop failure")
        await original(domain, service, body)

    app.ha.service = fail_ev
    with pytest.raises(RuntimeError, match="stop command failed"):
        await control.set_requested(False)
    assert not app.actuator.enabled and app.store.get("hardware_control_enabled") is False
    assert calls[-1]["entity_id"] == "number.ess_setpoint" and calls[-1]["value"] == 0
    assert "stop command failed" in control.state()["reason"]


async def test_off_cancels_an_enable_waiting_for_discovery(installation):
    app, editor, control, _, calls = installation
    started, release = asyncio.Event(), asyncio.Event()
    original = editor.entities

    async def delayed():
        started.set()
        await release.wait()
        return await original()

    editor.entities = delayed
    enabling = asyncio.create_task(control.set_requested(True))
    await asyncio.wait_for(started.wait(), 1)
    disabling = asyncio.create_task(control.set_requested(False))
    await asyncio.sleep(0)
    assert not app.actuator.enabled and not control.requested
    release.set()
    with pytest.raises(ValueError, match="superseded"):
        await enabling
    await disabling
    assert not calls and app.store.get("hardware_control_enabled") is False


async def test_enable_persistence_failure_never_grants_authority(installation, monkeypatch):
    app, _, control, _, calls = installation

    def denied(*args):
        raise OSError("Verification disk error")

    monkeypatch.setattr(app.store, "put", denied)
    with pytest.raises(OSError):
        await control.set_requested(True)
    assert not app.actuator.enabled and not control.requested and not calls


async def test_off_still_stops_hardware_when_its_saved_state_cannot_be_written(installation, monkeypatch):
    app, _, control, _, calls = installation
    await control.set_requested(True)
    await asyncio.gather(*app.protective_tasks)
    calls.clear()
    original = app.store.put

    def denied(key, value):
        if key == "hardware_control_enabled":
            raise OSError("Verification disk error")
        return original(key, value)

    monkeypatch.setattr(app.store, "put", denied)
    with pytest.raises(RuntimeError, match="saved state"):
        await control.set_requested(False)
    assert not app.actuator.enabled and not control.requested
    assert calls[-2]["entity_id"] == "select.force" and calls[-1]["value"] == 0


async def test_saved_switch_waits_for_live_inputs_after_restart(installation):
    app, editor, control, _, _ = installation
    await control.set_requested(True)
    await asyncio.gather(*app.protective_tasks)
    app.actuator.enabled = False
    app.observation = replace(app.observation, quality="unknown")
    resumed = HardwareControl(app, editor)
    assert resumed.requested and not resumed.state()["can_enable"]
    app.observation = replace(app.observation, at=datetime.now(UTC), quality="measured")
    resumed.start()
    try:
        async with asyncio.timeout(2):
            while not app.actuator.enabled:
                await asyncio.sleep(0.01)
    finally:
        await resumed.close()
    assert app.actuator.enabled


async def test_control_route_requires_same_origin_json_and_never_enables_demo(installation):
    from energymanager.web import create_web
    app, editor, _, _, calls = installation
    webapp = create_web(app, configuration=editor)
    webapp.on_startup.clear()
    webapp.on_cleanup.clear()
    async with TestClient(TestServer(webapp)) as client:
        assert (await client.post("/api/control", json={"enabled": True})).status == 403
        assert (await client.post("/api/control", json={"enabled": True}, headers={
            "X-EnergyManager": "1", "Origin": "https://other.example"})).status == 403
        assert not calls
        headers = {"X-EnergyManager": "1"}
        assert (await client.post("/api/control", json={"enabled": "true"}, headers=headers)).status == 400
        app.demo = True
        assert (await client.post("/api/control", json={"enabled": True}, headers=headers)).status == 400
        assert not app.actuator.enabled and not calls


@pytest.mark.parametrize("field", ["home_assistant_url", "forecast_url", "token_environment", "allow_remote",
                                   "notification_webhook", "commissioning_reviewed", "exclusive_controller_confirmed",
                                   "policy.control_enabled"])
async def test_retired_controls_cannot_be_posted_through_settings(installation, field):
    _, editor, _, _, _ = installation
    original = editor.path.read_bytes()
    with pytest.raises(ValueError, match="Unknown"):
        editor.save(editor.read()["revision"], {field: True})
    assert editor.path.read_bytes() == original


async def test_legacy_config_is_backed_up_without_retired_controls_or_secret_exposure(installation, monkeypatch):
    app, editor, _, _, _ = installation
    document = json.loads(editor.path.read_bytes())
    document.update(commissioning_reviewed=True, exclusive_controller_confirmed=True,
                    allow_remote=False, home_assistant_url="http://legacy.example/api",
                    token_environment="OLD_TOKEN", forecast_url="http://legacy.example/forecast",
                    notification_webhook="https://legacy.example/notice")
    document["policy"]["control_enabled"] = True
    document["future_option"] = {"keep": "unchanged"}
    editor.path.write_text(json.dumps(document), encoding="utf-8")
    original = editor.path.read_bytes()
    editor.addon = True
    loaded = editor.read()
    assert "legacy.example" not in json.dumps(loaded)
    result = editor.save(loaded["revision"], {"policy.daily_soc_percent": 62})
    assert (editor.path.parent / result["backup"]).read_bytes() == original
    saved = json.loads(editor.path.read_bytes())
    assert saved["future_option"] == document["future_option"]
    assert "control_enabled" not in saved["policy"] and "commissioning_reviewed" not in saved
    assert "home_assistant_url" not in saved and "notification_webhook" not in saved
    assert not app.actuator.enabled
    monkeypatch.setenv("SUPERVISOR_TOKEN", "verification-supervisor-token")
    connection = HomeAssistantConnection.resolve(document, addon=True)
    assert connection.url == "http://supervisor/core/api" and connection.allow_remote
    assert connection.token == "verification-supervisor-token"
    restarted = configured_application(editor.path, app.store, addon=True)
    assert not restarted.actuator.enabled and not restarted.policy.control_enabled


async def test_phone_picker_discovers_actions_and_delivery_uses_selected_ha_target(installation):
    app, editor, _, rows, calls = installation
    rows.append({"entity_id": "notify.phone_entity", "state": "2026-10-23T10:00:00Z",
                 "attributes": {"friendly_name": "Entity phone"}})
    inventory = await editor.entities()
    assert {(t["entity_id"], t["kind"]) for t in inventory["notification_targets"]} == {
        ("notify.phone_entity", "entity"), ("notify.mobile_app_phone", "action")}
    body = {"kind": "peak_precharge", "peak_kw": 3.1, "avoided_peak_kw": 5, "day": "2026-10-23"}
    for kind, identifier in (("entity", "notify.phone_entity"), ("action", "notify.mobile_app_phone")):
        target = NotificationTarget(identifier, kind)
        app.notifications = Notifications(app.store, app.ha, target)
        await app.notifications.inform("peak", body)
        await app.notifications.inform("peak", body)
    assert len(calls) == 2
    assert calls[0]["service"] == "send_message" and calls[0]["entity_id"] == "notify.phone_entity"
    assert calls[1]["service"] == "mobile_app_phone" and "entity_id" not in calls[1]
    assert "3.1 kW" in calls[1]["message"]
    editor.save(editor.read()["revision"], {"notification_target": {"id": "notify.phone_entity", "kind": "entity"}})
    restarted = configured_application(editor.path, app.store)
    assert restarted.notifications.target == NotificationTarget("notify.phone_entity", "entity")


def test_missing_fields_are_reported_on_read_and_zero_values_are_valid(tmp_path):
    path = tmp_path / "settings.json"
    create_configuration_if_missing(path)
    editor = ConfigurationFile(path)
    original = path.read_bytes()
    loaded = editor.read()
    assert "measurements.ev_soc" in loaded["issues"]
    assert "actuators.current" in loaded["issues"]
    assert "policy.arrival_reserve_km" not in loaded["issues"]
    assert "notification_target" not in loaded["issues"]
    assert "Connections" not in {field["group"] for field in loaded["fields"]}
    assert "Commissioning" not in {field["group"] for field in loaded["fields"]}
    assert all(not field["help"] for field in loaded["fields"] if field["kind"] == "entity")
    assert path.read_bytes() == original


async def test_incomplete_saved_settings_keep_the_editor_available_without_planning_or_authority(tmp_path):
    from energymanager.web import create_web
    path = tmp_path / "settings.json"
    create_configuration_if_missing(path)
    document = json.loads(path.read_bytes())
    document["capabilities"].pop("ev_capacity_kwh")
    path.write_text(json.dumps(document), encoding="utf-8")
    store = Store(tmp_path / "runtime.sqlite")
    application = configured_application(path, store)
    assert application.configuration_error and application.observation.quality == "unknown"
    assert application.ha is None
    editor = ConfigurationFile(path, mode="configured")
    async with TestClient(TestServer(create_web(application, configuration=editor))) as client:
        current = await (await client.get("/api/state")).json()
        assert current["accepted"] is None and not current["control_enabled"]
        loaded = await (await client.get("/api/settings")).json()
        assert loaded["values"]["capabilities.ev_capacity_kwh"] is None
        assert "capabilities.ev_capacity_kwh" in loaded["issues"]
        result = await client.post("/api/settings", json={"revision": loaded["revision"],
            "values": {"capabilities.ev_capacity_kwh": 60}}, headers={"X-EnergyManager": "1"})
        assert result.status == 200
        assert (await result.json())["restart_required"]
        assert application.accepted is None and not store.decisions()
