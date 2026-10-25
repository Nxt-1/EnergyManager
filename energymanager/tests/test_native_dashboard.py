"""Synthetic native-dashboard discovery and versioned asset delivery."""

from types import SimpleNamespace

from aiohttp.test_utils import TestClient, TestServer

from energymanager import __version__
from energymanager.dashboard import dashboard_manifest
from energymanager.service import Application
from energymanager.store import Store
from energymanager.web import create_web
from test_first_slice import tiny


def test_manifest_uses_active_entities_and_never_exposes_credentials(tmp_path):
    snapshot = tiny()
    application = Application(Store(tmp_path / "synthetic.sqlite"), snapshot=snapshot)
    application.ha = SimpleNamespace(entities={"ev_soc": "sensor.synthetic_car"}, token="PRIVATE")
    assert dashboard_manifest(application)["entities"] == {}  # Never mix HA with demo inputs.
    application.demo = False
    manifest = dashboard_manifest(application)
    assert manifest == {"protocol": 1, "version": __version__, "demo": False,
                        "entities": {"ev_soc": "sensor.synthetic_car"}}
    application.store.close()


async def test_versioned_native_bundle_is_complete_and_rejects_stale_versions(tmp_path):
    application = Application(Store(tmp_path / "synthetic.sqlite"), snapshot=tiny())
    async with TestClient(TestServer(create_web(application))) as client:
        response = await client.get("/api/dashboard")
        assert response.headers["Cache-Control"] == "no-store"
        assert (await response.json())["version"] == __version__
        for name in ("native-dashboard.js", "native-live.js", "native-dashboard.css", "dashboard-client.js", "text-selection.js", "ev-status.js",
                     "application-view.js", "graph-history.js", "graph-cursor.js", "view.html", "settings.js", "datetime-picker.js", "style.css"):
            response = await client.get(f"/frontend/{__version__}/{name}")
            assert response.status == 200, name
            assert response.headers["Cache-Control"] == "no-cache"
            assert await response.read()
        response = await client.get("/frontend/0.0.0/native-dashboard.js")
        assert response.status == 409
        response = await client.get(f"/frontend/{__version__}/configuration.example.json")
        assert response.status == 404
        response = await client.get(f"/frontend/{__version__}/native-dashboard.js", headers={"Host": "outside.test"})
        assert response.status == 403


def test_installed_loader_and_managed_yaml_are_self_contained():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    packaged = root / "energymanager/src/energymanager/assets/ha-card.js"
    assert packaged.read_bytes() == (root / "energymanager-dashboard/energymanager-card.js").read_bytes()
    yaml = (root / "energymanager-dashboard/energymanager-dashboard.yaml").read_text(encoding="utf-8")
    assert "type: custom:energymanager" in yaml
    assert "iframe" not in yaml and "REPLACE_WITH" not in yaml
