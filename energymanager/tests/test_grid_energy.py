"""Labelled synthetic P1 counters served by local fake HA; no live installation."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from energymanager.adapters import HomeAssistantAdapter
from energymanager.daily_estimates import DailyEstimates
from energymanager.energy import end_of_day_energy
from energymanager.service import Application
from energymanager.settings import SETTING_FIELDS
from energymanager.store import Store
from test_energy_prediction import prediction_fixture
from test_first_slice import tiny


def meter_row(entity, value, at, unit="kWh"):
    return {"entity_id": entity, "state": str(value), "last_changed": at.isoformat(),
            "attributes": {"unit_of_measurement": unit}}


@pytest.fixture
async def meter_app(tmp_path):
    now = datetime(2026, 10, 31, 12, tzinfo=UTC)
    data = {"now": now, "import": 10025.5, "export": 513750,
            "start_import": 10023.0, "start_export": 513000,
            "units": {"import": "kWh", "export": "Wh"}, "history": [], "reads": [],
            "missing_history": False, "invalid_history": False, "late_history": False}
    midnight = now.astimezone(ZoneInfo("Europe/Brussels")).replace(hour=0).astimezone(UTC)
    async def state(request):
        direction = request.match_info["entity"].split(".")[-1]
        data["reads"].append(direction)
        return web.json_response(meter_row("sensor." + direction, data[direction],
                                           data["now"], data["units"][direction]))
    async def history(request):
        assert request.query["filter_entity_id"] in ("sensor.import", "sensor.export")
        assert request.query["significant_changes_only"] == "0"
        at = datetime.fromisoformat(request.match_info["start"])
        assert at.hour == 23 and at.day == 30
        assert datetime.fromisoformat(request.query["end_time"]) - at == timedelta(seconds=1)
        direction = request.query["filter_entity_id"].split(".")[-1]
        data["history"].append(direction)
        if data["missing_history"]:
            return web.json_response([])
        value = "unavailable" if data["invalid_history"] else data["start_" + direction]
        if data["late_history"]:
            at += timedelta(microseconds=1)
        return web.json_response([[meter_row("sensor." + direction, value, at, data["units"][direction])]])
    fake = web.Application()
    fake.router.add_get("/api/states/{entity}", state)
    fake.router.add_get("/api/history/period/{start}", history)
    store = Store(tmp_path / "synthetic.sqlite")
    async with TestServer(fake) as server:
        ha = HomeAssistantAdapter(str(server.make_url("/api")),
              {"grid_import_kwh": "sensor.import", "grid_export_kwh": "sensor.export"})
        async with ha:
            app = Application(store, snapshot=tiny(), demo=False, ha=ha)
            app.now = lambda: data["now"]
            yield app, data, midnight
    store.close()


async def refresh(app):
    app.daily_estimates.grid.read_at = 0
    app.daily_estimates.read_at = 0
    return await app.daily_estimates.recorded(app.now())


async def test_counters_work_without_any_power_archive_and_survive_restart_and_outage(meter_app):
    app, data, midnight = meter_app
    first = await refresh(app)
    assert first["kwh"]["import"] == pytest.approx(2.5)
    assert first["kwh"]["export"] == pytest.approx(.75)
    assert first["kwh"]["house"] is None
    assert not first["channels"]["import"]["partial"]
    assert first["channels"]["import"]["baseline_at"] == midnight.isoformat()
    assert first["partial"]
    assert sorted(data["history"]) == ["export", "import"]
    path = app.store.path
    app.store.close()
    app.store = Store(path)
    app.daily_estimates = DailyEstimates(app)
    try:
        data.update(missing_history=True, now=data["now"] + timedelta(hours=2), **{"import": 10028.0})
        result = await refresh(app)
        assert result["kwh"]["import"] == pytest.approx(5.0)
        assert len(data["history"]) == 2
        assert data["reads"].count("import") == 2
    finally:
        app.store.close()


@pytest.mark.parametrize("problem", ["missing_history", "invalid_history", "late_history"])
async def test_no_midnight_evidence_never_substitutes_first_read_or_power_integral(meter_app, problem):
    app, data, _ = meter_app
    data[problem] = True
    app.store.event("measurement", replace(tiny().observation, at=app.now() - timedelta(seconds=5),
                                          house_kw=100))
    result = await refresh(app)
    assert result["kwh"]["import"] is None and result["kwh"]["export"] is None
    assert result["channels"]["import"]["error"]
    data[problem] = False
    assert (await refresh(app))["kwh"]["import"] == pytest.approx(2.5)


@pytest.mark.parametrize("bad", ["unavailable", "NaN", -1])
async def test_invalid_current_meter_does_not_hide_other_direction_and_can_recover(meter_app, bad):
    app, data, _ = meter_app
    data["import"] = bad
    result = await refresh(app)
    assert result["kwh"]["import"] is None
    assert result["kwh"]["export"] == pytest.approx(.75)
    assert result["channels"]["import"]["error"]
    data["import"] = 10025.5
    assert (await refresh(app))["kwh"]["import"] == pytest.approx(2.5)


async def test_power_units_are_rejected_and_counter_reset_stays_unavailable(meter_app):
    app, data, _ = meter_app
    await refresh(app)
    data["units"]["import"] = "W"
    assert (await refresh(app))["kwh"]["import"] is None
    data["units"]["import"] = "kWh"
    data["import"] = 10025.0
    result = await refresh(app)
    assert result["kwh"]["import"] is None
    assert "reset or decreased" in result["channels"]["import"]["error"]
    app.daily_estimates = DailyEstimates(app)
    data["import"] = 10028.0
    assert (await refresh(app))["kwh"]["import"] is None


async def test_mapping_change_and_demo_cannot_reuse_another_counter_baseline(meter_app):
    app, data, _ = meter_app
    await refresh(app)
    app.demo = True
    result = await refresh(app)
    assert result["kwh"] is None
    assert len(data["reads"]) == 2
    app.demo = False
    app.ha.entities["grid_import_kwh"] = ""
    result = await refresh(app)
    assert result["kwh"]["import"] is None and result["kwh"]["export"] == pytest.approx(.75)
    assert "Select" in result["channels"]["import"]["error"]


async def test_midnight_rollover_uses_new_local_baselines(meter_app, monkeypatch):
    app, data, _ = meter_app
    await refresh(app)
    data["now"] = datetime(2026, 11, 1, 0, 30, tzinfo=UTC)
    async def new_midnight(entity, start, end):
        assert start == datetime(2026, 10, 31, 23, tzinfo=UTC)
        assert end - start == timedelta(seconds=1)
        direction = entity.split(".")[-1]
        return [[meter_row(entity, data[direction], start, data["units"][direction])]]
    monkeypatch.setattr(app.ha, "entity_history", new_midnight)
    result = await refresh(app)
    assert result["date"] == "2026-11-01"
    assert result["kwh"]["import"] == result["kwh"]["export"] == 0


@pytest.mark.parametrize(("day", "expected"), [("2026-03-29", "2026-03-28T23:00:00+00:00"),
                                              ("2026-10-25", "2026-10-24T22:00:00+00:00")])
async def test_dst_midnight_is_installation_local(meter_app, monkeypatch, day, expected):
    app, data, _ = meter_app
    data["now"] = datetime.fromisoformat(day + "T12:00:00+00:00")
    async def initial(entity, start, end):
        assert start.isoformat() == expected
        direction = entity.split(".")[-1]
        return [[meter_row(entity, data[direction], start, data["units"][direction])]]
    monkeypatch.setattr(app.ha, "entity_history", initial)
    assert (await refresh(app))["kwh"]["import"] == 0


def test_missing_grid_subtotals_do_not_poison_other_forecasts():
    summary, plan = prediction_fixture()
    summary["kwh"]["import"] = None
    result = end_of_day_energy(summary, plan, 2, 7200, .95)
    assert result["import"] is None
    assert result["export"] == pytest.approx(4.5)
    assert result["ev"] == pytest.approx(2.9)


def test_two_energy_settings_are_unit_filtered_and_do_not_block_existing_control():
    fields = {field.path: field for field in SETTING_FIELDS}
    for direction in ("import", "export"):
        field = fields[f"measurements.grid_{direction}_kwh"]
        assert field.units == ("Wh", "kWh")
        assert field.kind == "entity" and not field.required


async def test_counter_requests_coalesce_and_http_failure_does_not_fabricate_zero(meter_app, monkeypatch):
    import asyncio
    from aiohttp import ClientResponseError, RequestInfo
    from multidict import CIMultiDict, CIMultiDictProxy
    from yarl import URL

    app, data, _ = meter_app
    await asyncio.gather(*(app.daily_estimates.grid.refresh(app.now()) for _ in range(4)))
    assert len(data["reads"]) == 2 and len(data["history"]) == 2
    original = app.ha.entity_state
    async def denied(entity):
        if entity == "sensor.import":
            url = URL("http://127.0.0.1/api/states/sensor.import")
            headers = CIMultiDictProxy(CIMultiDict())
            raise ClientResponseError(RequestInfo(url, "GET", headers, url), (), status=403)
        return await original(entity)
    monkeypatch.setattr(app.ha, "entity_state", denied)
    result = await refresh(app)
    assert result["kwh"]["import"] is None and result["kwh"]["export"] == pytest.approx(.75)
    assert "403" in result["channels"]["import"]["error"]


def test_old_integrated_fallback_prediction_is_not_reused_as_meter_evidence(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=tiny(), demo=False)
    now = datetime(2026, 10, 31, 12, tzinfo=UTC)
    key = app.daily_estimates.key(now)
    store.put(key, {"kind": "first_available", "kwh": {"import": 9, "export": 1, "ev": 3}})
    assert app.daily_estimates.view(now)["kwh"] == {"import": None, "export": None, "ev": 3}
    assert store.get(key)["kwh"]["import"] == 9  # Original historical evidence retained.
    store.close()


async def test_power_archive_timeout_does_not_hide_valid_p1_counters(meter_app, monkeypatch):
    app, data, _ = meter_app
    def timed_out(*args):
        raise TimeoutError("SYNTHETIC archive timeout")
    monkeypatch.setattr("energymanager.daily_estimates.daily_energy", timed_out)
    result = await refresh(app)
    assert result["kwh"]["import"] == pytest.approx(2.5)
    assert result["kwh"]["export"] == pytest.approx(.75)
    assert result["kwh"]["ev"] is None and "timeout" in result["power_error"]
    assert not result["channels"]["import"]["partial"]


async def test_reset_metadata_invalidates_even_a_higher_cumulative_counter(meter_app, monkeypatch):
    app, data, _ = meter_app
    await refresh(app)
    original = app.ha.entity_state
    async def reset(entity):
        row = await original(entity)
        if entity == "sensor.import":
            row["attributes"]["last_reset"] = app.now().isoformat()
        return row
    monkeypatch.setattr(app.ha, "entity_state", reset)
    assert (await refresh(app))["kwh"]["import"] is None


async def test_different_sensor_never_inherits_previous_mapping_midnight(meter_app):
    app, data, _ = meter_app
    await refresh(app)
    app.ha.entities["grid_import_kwh"] = "sensor.export"
    result = await refresh(app)
    assert result["kwh"]["import"] == pytest.approx(.75)
    assert result["channels"]["import"]["entity_id"] == "sensor.export"
