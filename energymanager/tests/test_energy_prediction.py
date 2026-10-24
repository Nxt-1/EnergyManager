"""SYNTHETIC daily subtotal/plan fixtures; no HA or installation measurements."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from energymanager.energy import end_of_day_energy


def prediction_fixture():
    summary = {"as_of": "2026-10-24T21:30:00+00:00", "timezone": "Europe/Brussels", "partial": True,
               "kwh": {"import": 10, "export": 4, "solar_ac": 2, "solar_dc": 1, "solar": 3,
                       "house": 5, "ev": 2, "ess_charge": 1, "ess_discharge": 2}}
    flow = {"grid_ev": 1, "grid_house": 2, "grid_store": 0, "export": 1, "pv_store": .5,
            "solar_dis_ev": .2, "solar_dis_house": .3, "grid_dis_house": .4, "dc_invert": 1, "pv_ev": .6}
    plan = {"id": "synthetic", "revision": 2, "valid": True, "forecast_at": summary["as_of"],
            "intervals": [{"start": "2026-10-24T21:00:00Z", "end": "2026-10-24T23:00:00Z",
                           "pv_ac_kw": 2, "pv_dc_kw": 1, "house_kw": .4}],
            "flows": {key: [value] for key, value in flow.items()}}
    return summary, plan


def test_prediction_adds_only_remaining_day_and_preserves_separate_flows():
    summary, plan = prediction_fixture()
    result = end_of_day_energy(summary, plan, 2, 7200, .95)
    assert result is not None
    assert result["import"] == pytest.approx(11.5)
    assert result["export"] == pytest.approx(4.5)
    assert result["solar_ac"] == pytest.approx(3)
    assert result["solar_dc"] == pytest.approx(1.5)
    assert result["house"] == pytest.approx(5.2)
    assert result["ev"] == pytest.approx(2.9)
    assert result["ess_charge"] == pytest.approx(1.25)
    assert result["ess_discharge"] == pytest.approx(2 + 1.85 / 2)
    assert summary["kwh"]["import"] == 10


def test_prediction_withholds_outdated_or_uncovered_plans():
    summary, plan = prediction_fixture()
    assert end_of_day_energy(summary, plan, 3, 7200, .95) is None
    assert end_of_day_energy({**summary, "kwh": None}, plan, 2, 7200, .95) is None
    assert end_of_day_energy(summary, {**plan, "forecast_at": "2026-10-24T10:00Z"}, 2, 7200, .95) is None
    plan["intervals"][0]["start"] = "2026-10-24T21:31Z"
    assert end_of_day_energy(summary, plan, 2, 7200, .95) is None
    plan["intervals"][0].update(start="2026-10-24T21:00Z", end="2026-10-24T21:45Z")
    assert end_of_day_energy(summary, plan, 2, 7200, .95) is None


@pytest.mark.parametrize(("date", "remaining"), [("2026-03-29", 22.5), ("2026-10-25", 24.5)])
def test_prediction_uses_elapsed_hours_until_local_midnight(date, remaining):
    zone = ZoneInfo("Europe/Brussels")
    local = datetime.fromisoformat(date).replace(tzinfo=zone) + timedelta(minutes=30)
    now = local.astimezone(UTC)
    end = now + timedelta(hours=30)
    summary, plan = prediction_fixture()
    summary.update(as_of=now.isoformat(), kwh=dict.fromkeys(summary["kwh"], 0))
    plan["forecast_at"] = now.isoformat()
    plan["intervals"][0].update(start=now.isoformat(), end=end.isoformat())
    plan["flows"]["grid_ev"] = [0]
    plan["flows"]["grid_house"] = [1]
    result = end_of_day_energy(summary, plan, 2, 7200, .95)
    assert result is not None and result["import"] == pytest.approx(remaining)


async def test_api_keeps_recorded_totals_but_withholds_prediction_until_inputs_are_valid(tmp_path):
    from dataclasses import replace
    from aiohttp.test_utils import TestClient, TestServer
    from energymanager.service import Application
    from energymanager.store import Store
    from energymanager.web import create_web
    from test_first_slice import tiny

    summary, plan = prediction_fixture()
    now = datetime.fromisoformat(summary["as_of"])
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=tiny())
    app.demo = False
    app.now = lambda: now
    app.accepted, app.revision = plan, 2
    async def no_lifecycle():
        pass
    app.start = no_lifecycle
    app.close = no_lifecycle
    app.observation = replace(app.observation, at=now, quality="unknown")
    store.event("measurement", replace(app.observation, at=now-timedelta(seconds=10), quality="measured"))
    async with TestClient(TestServer(create_web(app))) as client:
        response = await client.get("/api/daily-energy")
        data = await response.json()
        assert data["kwh"] is not None and data["predicted_kwh"] is None
        app.observation = replace(app.observation, quality="measured")
        data = await (await client.get("/api/daily-energy")).json()
        assert data["predicted_kwh"] is None  # A restart must reconcile the persisted plan first.
        app.ess_valid = True
        data = await (await client.get("/api/daily-energy")).json()
        assert data["prediction_plan_id"] == "synthetic"
        assert data["prediction_revision"] == 2 and data["predicted_kwh"] is not None
    store.close()
