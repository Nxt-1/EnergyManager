"""Offline acceptance of the recovered installation model and its runtime boundaries."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from energymanager.adapters import HomeAssistantAdapter, JsonForecastAdapter
from energymanager.forecast_service import InstallationForecast
from energymanager.forecasts import demo_snapshot
from energymanager.load_forecast import BackgroundLoadModel, LoadSample
from energymanager.open_meteo import OpenMeteoClient, OpenMeteoError, parse_plane_response
from energymanager.pv_forecast import PV_PLANES, build_pv_forecast
from energymanager.store import Store
from energymanager.service import Application


def weather_payload(start: datetime, hours: int = 216, irradiance: float = 500) -> dict:
    return {"hourly": {"time": [(start + timedelta(hours=i)).timestamp() for i in range(hours)],
                       "global_tilted_irradiance": [irradiance] * hours,
                       "temperature_2m": [20] * hours}}


@pytest.mark.parametrize("start", [datetime(2026, 10, 24, 22, 58, tzinfo=UTC),
                                   datetime(2026, 3, 28, 22, 58, tzinfo=UTC)])
def test_rolling_seven_days_cover_both_clock_changes_and_current_partial_quarter(tmp_path, start):
    weather_start = start.replace(hour=0, minute=0, second=0)
    series = {plane.key: parse_plane_response(plane.key, weather_payload(weather_start)) for plane in PV_PLANES}
    pv = build_pv_forecast(series, generated_at_utc=start)
    assert len(pv.points) == 216  # Both autumn 02:00 hours survive; spring has no invented local hour.
    assert len({p.period_end_local.astimezone(UTC) for p in pv.points}) == 216
    store = Store(tmp_path / "forecast.sqlite")
    try:
        source = InstallationForecast(HomeAssistantAdapter("http://127.0.0.1/api", {}), store)
        data = source.build_data(pv, (LoadSample(start, 400),), start)
        snapshot = demo_snapshot(start=start, goals=())
        normalized = JsonForecastAdapter.snapshot(data, snapshot.observation, snapshot.capabilities,
                                                  snapshot.policy, (), 1, start)
        assert (normalized.intervals[-1].end - normalized.intervals[0].start).total_seconds() == 168 * 3600
        assert max(i.hours for i in normalized.intervals) <= 1 / 12 + 1e-12
        assert all(i.house_kw == pytest.approx(0.4) for i in normalized.intervals)
        expected_dc = 6180 * 0.5 * (1 - 0.0029 * (20 + 0.0275 * 500 - 25)) / 1000
        assert sum(i.pv_dc_kw * i.hours for i in normalized.intervals) == pytest.approx(expected_dc * 168)
        assert data["forecast_status"]["load_stage"] == "learning"
        assert data["forecast_status"]["load_methods"] == ["recent_baseline"]
    finally:
        store.close()


@pytest.mark.parametrize("fault", ["null", "nan", "duplicate", "gap", "missing", "unaligned", "root"])
def test_missing_or_malformed_weather_is_rejected(fault):
    payload = weather_payload(datetime(2026, 10, 23, tzinfo=UTC), hours=3)
    if fault == "root":
        payload = []
    elif fault == "null":
        payload["hourly"]["global_tilted_irradiance"][1] = None
    elif fault == "nan":
        payload["hourly"]["temperature_2m"][1] = float("nan")
    elif fault in ("duplicate", "gap"):
        payload["hourly"]["time"][1] += -3600 if fault == "duplicate" else 7200
    elif fault == "missing":
        del payload["hourly"]["temperature_2m"]
    else:
        payload["hourly"]["temperature_2m"].pop()
    with pytest.raises(OpenMeteoError):
        parse_plane_response("front_roof", payload)


async def test_original_provider_query_four_setups_and_cached_failure_without_timestamp_laundering(tmp_path):
    at = datetime.now(UTC)
    requests = []
    fail = False

    async def zone(request):
        assert request.match_info["entity"] == "zone.home"
        return web.json_response({"attributes": {"latitude": 50, "longitude": 4}})

    async def weather(request):
        requests.append(dict(request.query))
        if fail:
            raise web.HTTPServiceUnavailable()
        return web.json_response(weather_payload(at.replace(minute=0, second=0, microsecond=0)))

    fake = web.Application()
    fake.add_routes([web.get("/api/states/{entity}", zone), web.get("/weather", weather)])
    store = Store(tmp_path / "inputs.sqlite")
    try:
        async with TestServer(fake) as server:
            async with HomeAssistantAdapter(str(server.make_url("/api")), {}) as ha:
                source = InstallationForecast(ha, store, weather_url=str(server.make_url("/weather")))
                observation = replace(demo_snapshot(start=at).observation, quality="measured", house_kw=0.4,
                                      ev_power_kw=7)
                try:
                    with pytest.raises(ValueError, match="in progress"):
                        await source.read(observation, at)
                    await source.weather_task
                    data = await source.read(observation, at)
                    assert len(requests) == 4
                    assert {(float(r["tilt"]), float(r["azimuth"])) for r in requests} == {
                        (38, 50), (46, -130), (13, -130), (9.5, -40)}
                    assert all(r["models"] == "knmi_seamless" and r["forecast_days"] == "9"
                               and r["timeformat"] == "unixtime" and r["latitude"] == "50.0"
                               and r["timezone"] == "Europe/Brussels" for r in requests)
                    assert data["provenance"].startswith("SYNTHETIC")
                    assert data["intervals"][0]["house_kw"] == 0.4  # EV not counted or subtracted twice.
                    assert store.get("pv_forecast_evidence")["calibration_version"] == "2026-10-03-seed"
                    assert len(store.load_samples(at - timedelta(days=35))) == 1
                    fail = True
                    later = at + timedelta(minutes=31)
                    cached = await source.read(replace(observation, at=later), later)
                    await source.weather_task
                    assert source.status["weather_error"]
                    assert cached["issued_at"] == data["issued_at"]
                    stale = at + timedelta(hours=2, seconds=1)
                    with pytest.raises(ValueError, match="stale"):
                        await source.read(replace(observation, at=stale), stale)
                finally:
                    await source.close()
    finally:
        store.close()


async def test_slow_weather_does_not_block_new_measurements_and_close_cancels_it(tmp_path):
    started, finish = asyncio.Event(), asyncio.Event()

    async def zone(request):
        return web.json_response({"attributes": {"latitude": 50, "longitude": 4}})

    async def slow(request):
        started.set()
        await finish.wait()
        return web.json_response({})

    fake = web.Application()
    fake.add_routes([web.get("/states/zone.home", zone), web.get("/slow", slow)])
    store = Store(tmp_path / "slow.sqlite")
    try:
        async with TestServer(fake) as server:
            async with HomeAssistantAdapter(str(server.make_url("")), {}) as ha:
                source = InstallationForecast(ha, store, weather_url=str(server.make_url("/slow")))
                at = datetime.now(UTC)
                observation = replace(demo_snapshot(start=at).observation, quality="measured")
                try:
                    with pytest.raises(ValueError, match="in progress"):
                        await asyncio.wait_for(source.read(observation, at), 0.25)
                    await asyncio.wait_for(started.wait(), 1)
                    with pytest.raises(ValueError, match="in progress"):
                        await asyncio.wait_for(source.read(observation, at + timedelta(seconds=5)), 0.25)
                    # A separate HA request completes while every weather request is still waiting.
                    assert (await asyncio.wait_for(ha.entity_state("zone.home"), 0.25))["attributes"]
                    await asyncio.wait_for(source.close(), 1)
                    assert source.weather_task.done()
                finally:
                    finish.set()
                    await source.close()
    finally:
        store.close()


def test_load_samples_survive_restart_and_old_or_future_only_history_is_rejected(tmp_path):
    at = datetime.now(UTC)
    path = tmp_path / "history.sqlite"
    store = Store(path)
    store.record_load(LoadSample(at, 400))
    store.record_load(LoadSample(at, 999))  # Duplicate reports do not rewrite evidence.
    store.close()
    reopened = Store(path)
    try:
        samples = reopened.load_samples(at - timedelta(days=35))
        assert samples == (LoadSample(at, 400),)
        source = InstallationForecast(HomeAssistantAdapter("http://127.0.0.1/api", {}), reopened)
        assert source.last_sample == samples
    finally:
        reopened.close()
    for offset in (-36, 1):
        with pytest.raises(ValueError, match="No valid"):
            BackgroundLoadModel().build((LoadSample(at + timedelta(days=offset), 400),), now_local=at)


async def test_missing_home_location_and_partial_horizon_fail_visibly(tmp_path):
    async def zone(request):
        return web.json_response({"attributes": {}})

    fake = web.Application()
    fake.router.add_get("/states/zone.home", zone)
    store = Store(tmp_path / "missing.sqlite")
    try:
        async with TestServer(fake) as server:
            async with HomeAssistantAdapter(str(server.make_url("")), {}) as ha:
                source = InstallationForecast(ha, store)
                await source.refresh_weather(datetime.now(UTC))
                assert source.pv is None and "latitude" in source.status["weather_error"]
                await source.close()
        at = datetime(2026, 10, 23, 23, 58, tzinfo=UTC)
        series = {plane.key: parse_plane_response(plane.key, weather_payload(at.replace(hour=0), hours=192))
                  for plane in PV_PLANES}
        with pytest.raises(ValueError, match="no extrapolation"):
            InstallationForecast.check_coverage(build_pv_forecast(series), at)
    finally:
        store.close()


async def test_weather_remote_gate_is_enforced_before_network_access():
    client = OpenMeteoClient()
    try:
        with pytest.raises(ValueError, match="Remote"):
            await client.fetch_planes(50, 4, PV_PLANES)
        assert client.session is None
    finally:
        await client.close()


async def test_application_keeps_polling_and_controlling_while_weather_is_blocked(tmp_path):
    started, finish = asyncio.Event(), asyncio.Event()
    values = {
        "ev_soc": (45, "%"), "ess_soc": (50, "%"), "connected": ("on", None),
        "house_kw": (0.4, "kW"), "pv_ac_kw": (1, "kW"), "pv_dc_kw": (1, "kW"),
        "ev_kw": (0, "kW"), "ess_kw": (0, "kW"), "quarter_import_kwh": (0, "kWh"),
        "monthly_peak_kw": (2.5, "kW"), "ev_phases": (1, None),
    }
    polls = []

    async def state(request):
        entity = request.match_info["entity"]
        if entity == "zone.home":
            return web.json_response({"attributes": {"latitude": 50, "longitude": 4}})
        if entity == "house_kw":
            polls.append(datetime.now(UTC))
        value, unit = values[entity]
        return web.json_response({"state": str(value), "attributes": {"unit_of_measurement": unit},
                                  "last_updated": datetime.now(UTC).isoformat()})

    async def weather(request):
        started.set()
        await finish.wait()
        return web.json_response({})

    fake = web.Application()
    fake.add_routes([web.get("/states/{entity}", state), web.get("/weather", weather)])
    store = Store(tmp_path / "application.sqlite")
    try:
        async with TestServer(fake) as server:
            ha = HomeAssistantAdapter(str(server.make_url("")), {key: key for key in values})
            source = InstallationForecast(ha, store, weather_url=str(server.make_url("/weather")))
            snapshot = demo_snapshot(start=datetime.now(UTC), goals=())
            application = Application(store, snapshot=snapshot, demo=False, ha=ha, forecast=source)
            await application.start()
            try:
                await asyncio.wait_for(started.wait(), 2)
                async with asyncio.timeout(8):
                    while len(polls) < 2:
                        await asyncio.sleep(0.05)
                assert (polls[-1] - polls[0]).total_seconds() >= 4
                assert application.observation.quality == "measured"
                assert len(application.response_seconds) >= 5
                assert application.last_command is not None
                assert application.accepted is None  # No demonstration forecast can reach the solver.
            finally:
                await application.close()
                finish.set()
    finally:
        store.close()
