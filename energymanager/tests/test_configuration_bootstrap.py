import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from energymanager import __main__ as entrypoint
from energymanager.configuration import configured_application, create_configuration_if_missing
from energymanager.control import FakeActuator
from energymanager.store import Store


def test_missing_configuration_creates_complete_disabled_starter(tmp_path: Path) -> None:
    path = tmp_path / "new folder" / "energymanager.json"
    assert create_configuration_if_missing(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    example = Path(__file__).parents[1] / "configuration.example.json"
    assert data == json.loads(example.read_text(encoding="utf-8"))
    assert data["_description"].startswith("SYNTHETIC EXAMPLE ONLY")
    assert not data["allow_remote"]
    assert not data["commissioning_reviewed"]
    assert not data["exclusive_controller_confirmed"]
    assert not data["policy"]["control_enabled"]
    store = Store(tmp_path / "state.sqlite")
    try:
        application = configured_application(path, store)
        assert isinstance(application.actuator, FakeActuator)
        assert not application.demo
        assert application.observation.quality == "unknown"
    finally:
        store.close()


@pytest.mark.parametrize("content", [b"", b"unfinished user edits", b'{"custom": "settings"}\n'])
def test_existing_configuration_is_never_replaced(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "energymanager.json"
    path.write_bytes(content)
    assert not create_configuration_if_missing(path)
    assert path.read_bytes() == content


def test_concurrent_startups_do_not_replace_each_others_configuration(tmp_path: Path) -> None:
    path = tmp_path / "new folder" / "energymanager.json"
    with ThreadPoolExecutor(max_workers=8) as workers:
        created = list(workers.map(create_configuration_if_missing, [path] * 8))
    assert created.count(True) == 1
    assert json.loads(path.read_text(encoding="utf-8"))["policy"]["control_enabled"] is False


@pytest.mark.parametrize("mode", ["demo", "configured"])
def test_addon_startup_creates_selected_configuration_and_preserves_it_on_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], mode: str
) -> None:
    configuration = tmp_path / "app config" / "energymanager.json"
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps({"mode": mode, "configuration_file": str(configuration), "planning_budget_seconds": 10}),
        encoding="utf-8",
    )

    def addon_path(value: str | Path) -> Path:
        # Supply Supervisor's options file locally; all configuration writes use the real filesystem.
        return options if str(value) == "/data/options.json" else Path(value)

    def run_local_server(app: web.Application, **kwargs: Any) -> None:
        async def verify_state() -> None:
            async with TestClient(TestServer(app)) as client:
                response = await client.get("/api/state")
                assert response.status == 200
                state = await response.json()
                assert state["demo"] is (mode == "demo")
                assert not state["control_enabled"]

        asyncio.run(verify_state())

    monkeypatch.setattr(entrypoint, "Path", addon_path)
    monkeypatch.setattr(entrypoint.web, "run_app", run_local_server)
    monkeypatch.setattr(sys, "argv", ["energymanager", "--addon", "--data", str(tmp_path / "state.sqlite")])
    entrypoint.main()
    assert f"Created starter configuration at {configuration}" in capsys.readouterr().out
    data = json.loads(configuration.read_text(encoding="utf-8"))
    data["policy"]["daily_soc_percent"] = 61
    data["_description"] = "User settings: réserve"
    configuration.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    original = configuration.read_bytes()
    entrypoint.main()
    assert "Created starter configuration" not in capsys.readouterr().out
    assert configuration.read_bytes() == original


def test_cli_creates_configuration_without_supervisor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "standalone" / "energymanager.json"

    def run_local_server(app: web.Application, **kwargs: Any) -> None:
        async def verify_state() -> None:
            async with TestClient(TestServer(app)) as client:
                response = await client.get("/api/state")
                assert response.status == 200
                state = await response.json()
                assert not state["demo"]
                assert not state["control_enabled"]
                assert path.is_file()

        asyncio.run(verify_state())

    monkeypatch.setattr(entrypoint.web, "run_app", run_local_server)
    monkeypatch.setattr(
        sys, "argv", ["energymanager", "--config", str(path), "--data", str(tmp_path / "state.sqlite")]
    )
    entrypoint.main()
    assert not json.loads(path.read_text(encoding="utf-8"))["policy"]["control_enabled"]


def test_configuration_creation_error_is_reported_before_service_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    parent = tmp_path / "not a directory"
    parent.write_text("keep this", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["energymanager", "--config", str(parent / "energymanager.json")])
    with pytest.raises(SystemExit) as error:
        entrypoint.main()
    assert error.value.code == 2
    assert "Cannot create configuration at" in capsys.readouterr().err
    assert parent.read_text(encoding="utf-8") == "keep this"
