"""Independent live values and per-source freshness through a real local HA endpoint."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from energymanager.adapters import HomeAssistantAdapter
from energymanager.control import FastControl
from energymanager.domain import Capabilities
from energymanager.forecasts import demo_snapshot
from energymanager.measurements import MeasurementOptions
from energymanager.service import Application
from energymanager.store import Store


@pytest.fixture
async def inputs():
    at = datetime(2026, 10, 23, 15, 16, tzinfo=UTC)
    values = {
        "ev_soc": (45, "%"), "ess_soc": (50, "%"), "connected": ("on", None),
        "grid_import_kw": (0, "W"), "grid_export_kw": (1300, "W"),
        "pv_ac_kw": (3, "kW"), "pv_dc_kw": (0.4, "kW"), "ev_kw": (2000, "W"),
        "ess_kw": (1, "kW"), "quarter_import_kwh": (0.8, "kW"),
        "monthly_peak_kw": (4, "kW"), "ev_phases": ("2", None),
    }
    rows = {key: {"state": str(value), "attributes": {"unit_of_measurement": unit},
                  "last_reported": at.isoformat(), "last_updated": at.isoformat()}
            for key, (value, unit) in values.items()}

    async def state(request):
        row = rows.get(request.match_info["entity"].split(".", 1)[-1])
        if row is None:
            raise web.HTTPNotFound()
        return web.json_response(row)

    fake = web.Application()
    fake.router.add_get("/states/{entity}", state)
    entities = {key: f"sensor.{key}" for key in values}
    async with TestServer(fake) as server:
        async with HomeAssistantAdapter(str(server.make_url("")), entities,
                measurement_options=MeasurementOptions.installation(), phase_entity=entities["ev_phases"]) as adapter:
            yield adapter, rows, at


async def test_slow_battery_and_static_states_do_not_age_the_power_snapshot(inputs):
    adapter, rows, at = inputs
    rows["ess_soc"]["last_reported"] = (at - timedelta(minutes=8)).isoformat()
    rows["ev_soc"]["last_reported"] = (at - timedelta(minutes=8)).isoformat()
    for key in ("connected", "ev_phases", "monthly_peak_kw"):
        rows[key]["last_reported"] = (at - timedelta(days=1)).isoformat()
    observation = await adapter.observe(Capabilities(), at=at)
    assert observation.at == at and observation.quality == "measured"
    assert observation.house_kw == pytest.approx(0.7)
    assert observation.ev_state_known and observation.ev_phase_known
    assert not any(card["issues"] for card in adapter.inputs.view(at, Capabilities())["cards"].values())


async def test_fresh_power_from_before_reset_can_accompany_current_quarter_energy(inputs):
    adapter, rows, at = inputs
    at = at.replace(minute=15, second=2)
    for row in rows.values():
        row["last_reported"] = (at - timedelta(seconds=3)).isoformat()
    rows["quarter_import_kwh"]["last_reported"] = (at - timedelta(seconds=1)).isoformat()
    observation = await adapter.observe(Capabilities(), at=at)
    assert observation.at == at - timedelta(seconds=1)
    assert observation.quarter_import_kwh == pytest.approx(0.2)
    control = FastControl(Capabilities(), demo_snapshot().policy)
    control.tick(observation, at, None, 1)
    assert control.estimated_quarter_kwh >= 0.2


async def test_previous_quarter_counter_blocks_control_but_not_live_cards(inputs, tmp_path):
    adapter, rows, at = inputs
    rows["quarter_import_kwh"]["last_reported"] = (at.replace(minute=15) - timedelta(seconds=1)).isoformat()
    at = at.replace(minute=15, second=1)
    for key, row in rows.items():
        if key != "quarter_import_kwh":
            row["last_reported"] = at.isoformat()
    with pytest.raises(ValueError, match="sensor.quarter_import_kwh.*different billing quarter"):
        await adapter.observe(Capabilities(), at=at)
    assert adapter.last_observation is None
    store = Store(tmp_path / "readings.sqlite")
    try:
        app = Application(store, demo=False, ha=adapter)
        app.observation = replace(app.observation, quality="unknown")
        app.now = lambda: at
        state = app.state()
        cards = state["live_inputs"]["cards"]
        assert cards["grid"]["value"] == pytest.approx(-1.3)
        assert cards["house"]["value"] == pytest.approx(0.7)
        assert cards["solar"]["value"] == pytest.approx(3.4)
        assert cards["ess"]["value"] == 50 and cards["ev"]["value"] == 45
        assert "different billing quarter" in cards["grid"]["issues"][0]
        command = app.controller.tick(app.observation, at, None, 1)
        assert command.ev_kw == command.ess_kw == 0
    finally:
        store.close()
    rows["quarter_import_kwh"]["last_reported"] = at.isoformat()
    recovered = await adapter.observe(Capabilities(), at=at)
    assert recovered.quality == "measured"
    assert not adapter.inputs.view(at, Capabilities())["cards"]["grid"]["issues"]


async def test_stale_power_names_entity_age_and_limit_and_preserves_other_readings(inputs):
    adapter, rows, at = inputs
    rows["pv_ac_kw"]["last_reported"] = (at - timedelta(seconds=45)).isoformat()
    with pytest.raises(ValueError, match=r"sensor.pv_ac_kw: last reported 45.0 s ago; maximum 30 s"):
        await adapter.observe(Capabilities(), at=at)
    cards = adapter.inputs.view(at, Capabilities())["cards"]
    assert cards["grid"]["value"] == pytest.approx(-1.3) and not cards["grid"]["issues"]
    assert cards["solar"]["value"] == pytest.approx(3.4)
    assert "45.0 s" in cards["solar"]["issues"][0]
    assert cards["ev"]["value"] == 45 and not cards["ev"]["issues"]


async def test_failed_entity_read_preserves_ac_solar_house_grid_and_batteries(inputs):
    adapter, rows, at = inputs
    del rows["pv_dc_kw"]
    with pytest.raises(ValueError, match="sensor.pv_dc_kw.*could not read entity"):
        await adapter.observe(Capabilities(), at=at)
    view = adapter.inputs.view(at, Capabilities())
    cards = view["cards"]
    assert cards["solar"]["value"] is None
    assert cards["solar"]["label"] == "AC 3.00 · DC unavailable kW"
    assert cards["house"]["value"] == pytest.approx(0.7)
    assert cards["grid"]["value"] == pytest.approx(-1.3)
    assert cards["ess"]["value"] == 50 and cards["ev"]["value"] == 45
    json.dumps(view, allow_nan=False)


async def test_fresh_reports_keep_unchanged_zero_power_and_soc_usable(inputs):
    adapter, rows, at = inputs
    for row in rows.values():
        row["last_updated"] = (at - timedelta(hours=3)).isoformat()
    assert (await adapter.observe(Capabilities(), at=at)).house_kw == pytest.approx(0.7)
    del rows["grid_import_kw"]["last_reported"]
    with pytest.raises(ValueError, match="sensor.grid_import_kw.*maximum 30 s.*last_updated"):
        await adapter.observe(Capabilities(), at=at)


async def test_expired_ess_soc_is_named_and_still_visible_as_stale(inputs):
    adapter, rows, at = inputs
    rows["ess_soc"]["last_reported"] = (at - timedelta(seconds=901)).isoformat()
    with pytest.raises(ValueError, match="sensor.ess_soc.*901.0 s.*maximum 900 s"):
        await adapter.observe(Capabilities(), at=at)
    cards = adapter.inputs.view(at, Capabilities())["cards"]
    assert cards["ess"]["value"] == 50 and "901.0 s" in cards["ess"]["issues"][0]
    assert cards["house"]["value"] == pytest.approx(0.7) and not cards["house"]["issues"]


@pytest.mark.parametrize("problem,message", [("nan", "not finite"), ("future", "in the future"),
                                          ("unit", "requires declared kW"), ("missing_time", "timestamp is missing")])
async def test_invalid_input_is_named_without_hiding_unaffected_cards(inputs, problem, message):
    adapter, rows, at = inputs
    if problem == "nan":
        rows["pv_dc_kw"]["state"] = "nan"
    elif problem == "future":
        rows["pv_dc_kw"]["last_reported"] = (at + timedelta(seconds=6)).isoformat()
    elif problem == "unit":
        rows["pv_dc_kw"]["attributes"]["unit_of_measurement"] = "kWh"
    else:
        rows["pv_dc_kw"].pop("last_reported")
        rows["pv_dc_kw"].pop("last_updated")
    with pytest.raises(ValueError, match=f"sensor.pv_dc_kw.*{message}"):
        await adapter.observe(Capabilities(), at=at)
    view = adapter.inputs.view(at, Capabilities())
    assert view["cards"]["grid"]["value"] == pytest.approx(-1.3)
    assert message in view["cards"]["solar"]["issues"][0]
    json.dumps(view, allow_nan=False)


async def test_live_freshness_advances_without_relabelling_cached_values_as_current(inputs):
    adapter, _, at = inputs
    await adapter.observe(Capabilities(), at=at)
    view = adapter.inputs.view(at + timedelta(seconds=40), Capabilities())
    assert "40.0 s ago" in view["cards"]["grid"]["issues"][0]
    assert view["cards"]["grid"]["value"] == pytest.approx(-1.3)
    assert "40.0 s ago" in view["cards"]["ess"]["issues"][0]  # ESS power is stale, its percentage is still usable.
    assert not view["cards"]["ev"]["issues"]
