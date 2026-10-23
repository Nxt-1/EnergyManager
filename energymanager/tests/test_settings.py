import json
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web
from aiohttp.abc import AbstractResolver
from aiohttp.test_utils import TestClient, TestServer

from energymanager.configuration import configured_application, create_configuration_if_missing
from energymanager.service import Application
from energymanager.settings import ConfigurationConflict, ConfigurationFile, SettingsValidationError
from energymanager.store import Store
from energymanager.web import create_web
from test_first_slice import tiny


def configuration_file(tmp_path: Path) -> ConfigurationFile:
    path = tmp_path / "energymanager.json"
    create_configuration_if_missing(path)
    return ConfigurationFile(path)


def test_editor_covers_template_and_preserves_future_fields_and_backup(tmp_path):
    editor = configuration_file(tmp_path)
    data = json.loads(editor.path.read_bytes())
    data["future_version"] = {"private_setting": "keep-me"}
    original = json.dumps(data, indent=4).encode()
    editor.path.write_bytes(original)
    loaded = editor.read()
    assert "private_setting" not in json.dumps(loaded)
    paths = set(loaded["values"])
    for key, value in data.items():
        if key == "future_version":
            continue
        if isinstance(value, dict):
            assert {f"{key}.{child}" for child in value} <= paths
        else:
            assert key in paths
    result = editor.save(loaded["revision"], {
        "measurements.ev_soc": "sensor.car_battery", "policy.daily_soc_percent": 61,
    })
    assert result["restart_required"]
    assert result["values"]["measurements.ev_soc"] == "sensor.car_battery"
    assert (editor.path.parent / result["backup"]).read_bytes() == original
    assert json.loads(editor.path.read_bytes())["future_version"] == data["future_version"]
    restarted = ConfigurationFile(editor.path)
    assert not restarted.read()["restart_required"]
    store = Store(tmp_path / "restart.sqlite")
    try:
        application = configured_application(editor.path, store)
        assert application.ha.entities["ev_soc"] == "sensor.car_battery"
        assert application.policy.daily_soc_percent == 61
        assert not application.policy.control_enabled
        assert application.goals == ()  # Configured startup must not inherit demonstration journeys.
    finally:
        store.close()


@pytest.mark.parametrize("changes", [
    {"capabilities.ev_capacity_kwh": -1},
    {"capabilities.ess_min_kwh": 100},
    {"capabilities.minimum_current_a": 20},
    {"capabilities.phases": [2]},
    {"policy.export_eur_kwh": 999},
    {"policy.timezone": "Unknown/Zone"},
    {"policy.daily_time": "25:01"},
    {"policy.control_period_seconds": 0},
    {"policy.import_eur_kwh": float("nan")},
    {"measurements.ev_soc": "sensor.bad entity"},
    {"actuators.current": "sensor.current"},
    {"capabilities.minimum_current_a": 6.5},
])
def test_invalid_settings_never_replace_file_or_create_backup(tmp_path, changes):
    editor = configuration_file(tmp_path)
    original = editor.path.read_bytes()
    with pytest.raises(SettingsValidationError):
        editor.save(editor.read()["revision"], changes)
    assert editor.path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [editor.path]


def test_noop_unknown_fields_and_concurrent_edits(tmp_path):
    editor = configuration_file(tmp_path)
    loaded = editor.read()
    assert editor.save(loaded["revision"], {})["backup"] is None
    with pytest.raises(ValueError, match="Unknown configuration fields"):
        editor.save(loaded["revision"], {"unexpected.token": "anything"})

    def save_target(target):
        try:
            return editor.save(loaded["revision"], {"policy.daily_soc_percent": target})
        except ConfigurationConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(save_target, [51, 52]))
    assert results.count("conflict") == 1
    assert len(list(tmp_path.glob("*.backup-*.json"))) == 1
    assert json.loads(editor.path.read_bytes())["policy"]["daily_soc_percent"] in (51, 52)
    externally_edited = editor.path.read_bytes() + b"\n"
    editor.path.write_bytes(externally_edited)
    with pytest.raises(ConfigurationConflict):
        editor.save(loaded["revision"], {"policy.daily_soc_percent": 60})
    assert editor.path.read_bytes() == externally_edited


def test_failed_atomic_replace_keeps_original_and_backup(tmp_path, monkeypatch):
    editor = configuration_file(tmp_path)
    original = editor.path.read_bytes()

    def denied(*args):
        raise PermissionError("File is locked")

    monkeypatch.setattr("energymanager.settings.os.replace", denied)
    with pytest.raises(PermissionError):
        editor.save(editor.read()["revision"], {"policy.daily_soc_percent": 61})
    assert editor.path.read_bytes() == original
    backups = list(tmp_path.glob("*.backup-*.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    assert set(tmp_path.iterdir()) == {editor.path, backups[0]}


async def test_settings_round_trip_http_conflict_validation_and_same_origin(tmp_path):
    editor = configuration_file(tmp_path)
    snapshot = tiny()
    application = Application(Store(tmp_path / "state.sqlite"), snapshot=snapshot, policy=snapshot.policy)
    async with TestClient(TestServer(create_web(application, configuration=editor))) as client:
        response = await client.get("/api/settings")
        assert response.headers["Cache-Control"] == "no-store"
        loaded = await response.json()
        body = {"revision": loaded["revision"], "values": {"measurements.ev_soc": "sensor.real_car"}}
        response = await client.post("/api/settings", json=body)
        assert response.status == 403
        headers = {"X-EnergyManager": "1"}
        response = await client.post("/api/settings", json=body,
                                     headers={**headers, "Origin": "https://other.example"})
        assert response.status == 403
        response = await client.post("/api/settings", json=body, headers=headers)
        assert response.status == 200
        saved = await response.json()
        assert saved["backup"] and saved["restart_required"]
        assert not application.policy.control_enabled
        assert application.snapshot.policy.daily_soc_percent == snapshot.policy.daily_soc_percent
        response = await client.post("/api/settings", json=body, headers=headers)
        assert response.status == 409
        response = await client.post("/api/settings", json={
            "revision": saved["revision"], "values": {"actuators.current": "sensor.bad_domain"},
        }, headers=headers)
        assert response.status == 400
        assert "actuators.current" in (await response.json())["errors"]
        response = await client.post("/api/settings", json={"revision": saved["revision"]}, headers=headers)
        assert response.status == 400
        response = await client.get("/settings.js")
        assert response.status == 200 and "EntityPicker" in await response.text()


async def test_real_ha_entity_discovery_is_read_only_and_keeps_credentials_server_side(tmp_path, monkeypatch):
    editor = configuration_file(tmp_path)
    calls = []

    async def states(request):
        calls.append((request.method, request.path))
        assert request.headers["Authorization"] == "Bearer synthetic-test-credential"
        return web.json_response([
            {"entity_id": "sensor.car_battery", "state": "48", "attributes": {
                "friendly_name": "Car battery", "unit_of_measurement": "%", "private": "omit-this",
            }},
            {"entity_id": "number.charger_current", "state": "6", "attributes": {
                "friendly_name": "Charger current", "unit_of_measurement": "A",
            }},
            {"entity_id": "sensor.offline", "state": "unavailable", "attributes": {}},
        ])

    fake = web.Application()
    fake.router.add_get("/api/states", states)
    monkeypatch.setenv("ENERGY_MANAGER_HA_TOKEN", "synthetic-test-credential")
    async with TestServer(fake) as server:
        document = json.loads(editor.path.read_bytes())
        document["home_assistant_url"] = str(server.make_url("/api"))
        editor.path.write_text(json.dumps(document), encoding="utf-8")
        result = await editor.entities()
        assert calls == [("GET", "/api/states")]
        assert result["entities"][0] == {
            "entity_id": "sensor.car_battery", "name": "Car battery", "state": "48", "unit": "%",
        }
        encoded = json.dumps(result)
        assert "synthetic-test-credential" not in encoded
        assert "omit-this" not in encoded
        assert "unavailable" in encoded


class LocalSupervisorResolver(AbstractResolver):
    def __init__(self, port):
        self.port = port

    async def resolve(self, host, port=0, family=socket.AF_INET):
        assert host == "supervisor"
        return [{"hostname": host, "host": "127.0.0.1", "port": self.port,
                 "family": socket.AF_INET, "proto": 0, "flags": 0}]

    async def close(self):
        pass


async def test_addon_discovers_entities_via_real_local_supervisor_proxy_fixture(tmp_path, monkeypatch):
    editor = configuration_file(tmp_path)
    editor.addon = True
    calls = []

    async def states(request):
        calls.append((request.method, request.path, request.headers.get("Authorization")))
        return web.json_response([{"entity_id": "sensor.real_entity", "state": "on"}])

    fake = web.Application()
    fake.router.add_get("/core/api/states", states)
    monkeypatch.setenv("SUPERVISOR_TOKEN", "synthetic-supervisor-token")
    real_session = aiohttp.ClientSession
    async with TestServer(fake) as server:
        def local_session(**kwargs):
            kwargs.setdefault("connector", aiohttp.TCPConnector(resolver=LocalSupervisorResolver(server.port)))
            return real_session(**kwargs)

        monkeypatch.setattr(aiohttp, "ClientSession", local_session)
        result = await editor.entities()
    assert calls == [("GET", "/core/api/states", "Bearer synthetic-supervisor-token")]
    assert result["entities"][0]["entity_id"] == "sensor.real_entity"
    assert "synthetic-supervisor-token" not in json.dumps(result)
    assert "allow_remote" not in editor.read()["values"]


async def test_discovery_outage_does_not_block_editing_or_expose_error_body(tmp_path):
    editor = configuration_file(tmp_path)

    async def denied(request):
        return web.Response(status=401, text="private backend response")

    fake = web.Application()
    fake.router.add_get("/api/states", denied)
    async with TestServer(fake) as server:
        document = json.loads(editor.path.read_bytes())
        document["home_assistant_url"] = str(server.make_url("/api"))
        editor.path.write_text(json.dumps(document), encoding="utf-8")
        snapshot = tiny()
        application = Application(Store(tmp_path / "state.sqlite"), snapshot=snapshot, policy=snapshot.policy)
        async with TestClient(TestServer(create_web(application, configuration=editor))) as client:
            response = await client.get("/api/settings/entities")
            assert response.status == 503
            body = await response.text()
            assert "401" in body and "private backend response" not in body
            loaded = await (await client.get("/api/settings")).json()
            response = await client.post("/api/settings", json={
                "revision": loaded["revision"], "values": {"policy.daily_soc_percent": 62},
            }, headers={"X-EnergyManager": "1"})
            assert response.status == 200
            assert (await response.json())["values"]["policy.daily_soc_percent"] == 62
