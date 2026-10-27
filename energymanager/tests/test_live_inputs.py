"""Independent HA states and successful-read watchdog through a real local HA endpoint."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from energymanager.adapters import HomeAssistantAdapter
from energymanager.control import FastControl
from energymanager.domain import Capabilities, Policy, json_data
from energymanager.forecasts import demo_snapshot
from energymanager.measurements import HousePowerMismatch, MeasurementOptions
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


async def test_old_unchanged_available_states_are_usable_without_zero_exceptions(inputs):
    adapter, rows, at = inputs
    for row in rows.values():
        row["last_reported"] = (at - timedelta(hours=3)).isoformat()
        row["last_updated"] = row["last_reported"]
    observation = await adapter.observe(Capabilities(), at=at)
    assert observation.at == at and observation.quality == "measured"
    assert observation.house_kw == pytest.approx(0.7)
    assert observation.ev_state_known and observation.ev_phase_known
    view = adapter.inputs.view(at, Capabilities())
    assert not any(card["issues"] for card in view["cards"].values())
    assert view["readings"]["ess_soc"]["report_age_seconds"] == 10800
    assert view["readings"]["ess_soc"]["read_age_seconds"] == 0


@pytest.mark.parametrize("power_w", [-1, -35, -2300])
async def test_signed_ev_power_is_a_valid_observation_and_survives_history_projection(inputs, power_w):
    from energymanager.graph_history import graph_values

    adapter, rows, at = inputs
    rows["ev_kw"]["state"] = str(power_w)
    observation = await adapter.observe(Capabilities(), at=at)
    assert observation.ev_power_kw == pytest.approx(power_w / 1000)
    assert observation.quality == "measured" and adapter.last_observation is observation
    view = adapter.inputs.view(at, Capabilities())
    assert not any(card["issues"] for card in view["cards"].values())
    assert view["readings"]["ev_kw"]["value"] == pytest.approx(power_w / 1000)
    history = graph_values(json_data(observation), 60, 14, False)
    assert history["ev"] == pytest.approx(power_w)
    assert history["grid"] == pytest.approx(-1300)  # Signed power still reconstructs the actual P1 balance.
    assert all(value is not None for value in history.values())


@pytest.mark.parametrize("key", ["pv_ac_kw", "pv_dc_kw", "grid_import_kw", "grid_export_kw",
                                 "quarter_import_kwh", "monthly_peak_kw"])
async def test_other_negative_inputs_name_source_raw_value_unit_and_read_time(inputs, key):
    adapter, rows, at = inputs
    rows[key]["state"] = "-0.125"
    with pytest.raises(ValueError) as failure:
        await adapter.observe(Capabilities(), at=at)
    message = str(failure.value)
    assert f"sensor.{key}: value must be nonnegative" in message
    assert "state='-0.125'" in message
    assert f"unit={rows[key]['attributes']['unit_of_measurement']!r}" in message
    assert f"read_at={at.isoformat()}" in message
    assert adapter.inputs.readings[key].raw_state == "-0.125"
    assert adapter.last_observation is None


@pytest.mark.parametrize("key,state", [("ev_kw", "nan"), ("ev_kw", "unavailable"),
                                      ("ess_soc", "-1"), ("ess_soc", "101")])
async def test_remaining_invalid_values_report_original_read_context(inputs, key, state):
    adapter, rows, at = inputs
    rows[key]["state"] = state
    with pytest.raises(ValueError) as failure:
        await adapter.observe(Capabilities(), at=at)
    message = str(failure.value)
    assert f"sensor.{key}:" in message and f"state={state!r}" in message
    assert f"unit={rows[key]['attributes']['unit_of_measurement']!r}" in message
    assert f"read_at={at.isoformat()}" in message


async def test_derived_house_failure_preserves_settling_type_and_identifies_contributing_inputs(inputs):
    adapter, rows, at = inputs
    rows["grid_export_kw"]["state"] = "3000"
    with pytest.raises(HousePowerMismatch) as failure:
        await adapter.observe(Capabilities(), at=at)
    message = str(failure.value)
    assert "Derived house demand is negative (-1.000 kW)" in message
    for key in ("grid_import_kw", "grid_export_kw", "pv_ac_kw", "ev_kw", "ess_kw"):
        assert f"sensor.{key} (state={rows[key]['state']!r}" in message
    assert f"read_at={at.isoformat()}" in message


@pytest.mark.parametrize("source,power,contributors", [
    ("direct", -1, ("house_kw",)),
    ("total_consumption", .5, ("house_kw", "ev_kw")),
    ("signed_grid", -5, ("house_kw", "ev_kw", "pv_ac_kw", "ess_kw")),
])
async def test_house_error_names_only_inputs_used_by_the_configured_topology(inputs, source, power, contributors):
    adapter, rows, at = inputs
    adapter.options = replace(adapter.options, house_source=source)
    adapter.entities["house_kw"] = "sensor.house_kw"
    rows["house_kw"] = {"state": str(power), "attributes": {"unit_of_measurement": "kW"}}
    with pytest.raises(ValueError) as failure:
        await adapter.observe(Capabilities(), at=at)
    assert isinstance(failure.value, HousePowerMismatch) == (source != "direct")
    message = str(failure.value)
    for key in ("house_kw", "ev_kw", "pv_ac_kw", "ess_kw", "grid_import_kw", "grid_export_kw"):
        assert (f"sensor.{key} (" in message) == (key in contributors)
    assert f"read_at={at.isoformat()}" in message


@pytest.mark.parametrize("negative_ev", [True, False])
async def test_input_loop_preserves_control_for_signed_ev_and_records_sensor_context_for_real_failure(
        inputs, tmp_path, monkeypatch, negative_ev):
    adapter, rows, at = inputs
    original_observe = adapter.observe
    previous = await original_observe(Capabilities(), at=at)
    now = at + timedelta(seconds=5)

    async def observe(capabilities):
        return await original_observe(capabilities, at=now)

    class Forecast:
        async def read(self, observation, at):
            raise asyncio.CancelledError  # A valid input reaches forecasting; no network or solver needed.

    async def stop_loop(seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(adapter, "observe", observe)
    monkeypatch.setattr(asyncio, "sleep", stop_loop)
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=demo_snapshot(goals=()), demo=False, ha=adapter, forecast=Forecast())
    app.now = lambda: now
    app.observation, app.forecast_data, app.status = previous, {}, "ready"
    app.ev_valid = app.ess_valid = True
    revision = app.revision
    rows["ev_kw" if negative_ev else "pv_dc_kw"]["state"] = "-35"
    try:
        with pytest.raises(asyncio.CancelledError):
            await app.input_loop()
        events = store.events()
        if negative_ev:
            assert app.observation.ev_power_kw == -.035 and app.observation.at == now
            assert app.error is None and app.ev_valid and app.ess_valid and app.revision == revision
            assert not any(event["kind"] == "input_error" for event in events)
            assert next(event["body"] for event in events if event["kind"] == "observed")["ev_power_kw"] == -.035
        else:
            assert app.status == "inputs_unavailable" and not app.ev_valid and not app.ess_valid
            message = app.state()["error"]
            assert "sensor.pv_dc_kw: value must be nonnegative" in message
            assert "state='-35', unit='kW'" in message and f"read_at={now.isoformat()}" in message
            assert next(event["body"] for event in events if event["kind"] == "input_error")["reason"] == message
    finally:
        await asyncio.gather(*app.protective_tasks, return_exceptions=True)
        store.close()


async def test_unchanged_zero_values_and_quarter_counter_remain_valid_across_quarters(inputs):
    adapter, rows, at = inputs
    for key in ("grid_import_kw", "pv_ac_kw", "pv_dc_kw", "ev_kw", "ess_kw", "quarter_import_kwh"):
        rows[key]["state"] = "0"
    rows["grid_export_kw"]["state"] = "0"
    for row in rows.values():
        row["last_reported"] = (at - timedelta(hours=2)).isoformat()
    for polled_at in (at, at + timedelta(minutes=15), at + timedelta(hours=1)):
        observation = await adapter.observe(Capabilities(), at=polled_at)
        assert observation.at == polled_at and observation.quarter_import_kwh == 0
        assert observation.house_kw == observation.pv_ac_kw == observation.pv_dc_kw == 0
        assert not any(card["issues"] for card in adapter.inputs.view(polled_at, Capabilities())["cards"].values())


async def test_quarter_energy_uses_current_ha_value_and_resets_independently_of_metadata(inputs):
    adapter, rows, at = inputs
    metadata = (at - timedelta(hours=2)).isoformat()
    rows["quarter_import_kwh"]["last_reported"] = metadata
    control = FastControl(Capabilities(), Policy())
    before = await adapter.observe(Capabilities(), at=at)
    assert before.quarter_import_kwh == pytest.approx(0.2)
    control.tick(before, at, None, 1)
    assert control.estimated_quarter_kwh == pytest.approx(0.2)
    next_quarter = at.replace(minute=30, second=1)
    rows["quarter_import_kwh"]["state"] = "0"
    after = await adapter.observe(Capabilities(), at=next_quarter)
    control.tick(after, next_quarter, None, 1)
    assert after.at == next_quarter and control.estimated_quarter_kwh == 0
    assert adapter.inputs.readings["quarter_import_kwh"].reported_at.isoformat() == metadata


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


@pytest.mark.parametrize("state", ["unknown", "unavailable"])
async def test_critical_ha_availability_blocks_snapshot_and_names_entity(inputs, state):
    adapter, rows, at = inputs
    rows["ess_soc"]["state"] = state
    with pytest.raises(ValueError, match=f"sensor.ess_soc: state is {state}"):
        await adapter.observe(Capabilities(), at=at)
    assert adapter.last_observation is None
    cards = adapter.inputs.view(at, Capabilities())["cards"]
    assert cards["ess"]["value"] is None and f"state is {state}" in cards["ess"]["issues"][0]
    assert cards["grid"]["value"] == pytest.approx(-1.3)
    assert cards["house"]["value"] == pytest.approx(0.7)


async def test_unknown_ev_soc_holds_ev_but_available_shared_states_still_allow_ess(inputs):
    adapter, rows, at = inputs
    rows["ev_soc"]["state"] = "unavailable"
    observation = await adapter.observe(Capabilities(), at=at)
    assert not observation.ev_state_known and observation.quality == "measured"
    command = FastControl(Capabilities(), Policy()).tick(observation, at, None, 1)
    assert command.ev_kw == 0 and command.ess_kw < 0


@pytest.mark.parametrize("metadata", ["old", "future", "missing", "malformed"])
async def test_report_timestamps_are_diagnostic_and_never_substitute_for_read_time(inputs, metadata):
    adapter, rows, at = inputs
    for row in rows.values():
        if metadata == "missing":
            row.pop("last_reported")
            row.pop("last_updated")
        else:
            row["last_reported"] = (at + timedelta(days=1)).isoformat() if metadata == "future" else (
                (at - timedelta(days=1)).isoformat() if metadata == "old" else "no timestamp")
    observation = await adapter.observe(Capabilities(), at=at)
    assert observation.at == at and observation.house_kw == pytest.approx(0.7)
    assert observation.ev_state_known and observation.ev_phase_known
    assert not any(card["issues"] for card in adapter.inputs.view(at, Capabilities())["cards"].values())


@pytest.mark.parametrize("problem,message", [("nan", "not finite"), ("unit", "requires declared kW")])
async def test_invalid_values_still_block_control_without_hiding_unaffected_cards(inputs, problem, message):
    adapter, rows, at = inputs
    if problem == "nan":
        rows["pv_dc_kw"]["state"] = "nan"
    else:
        rows["pv_dc_kw"]["attributes"]["unit_of_measurement"] = "kWh"
    with pytest.raises(ValueError, match=f"sensor.pv_dc_kw.*{message}"):
        await adapter.observe(Capabilities(), at=at)
    view = adapter.inputs.view(at, Capabilities())
    assert view["cards"]["grid"]["value"] == pytest.approx(-1.3)
    assert message in view["cards"]["solar"]["issues"][0]
    json.dumps(view, allow_nan=False)


async def test_read_watchdog_expires_when_successful_polls_stop(inputs):
    adapter, _, at = inputs
    observation = await adapter.observe(Capabilities(), at=at)
    control = FastControl(Capabilities(), Policy())
    assert control.tick(observation, at, None, 1).ess_kw < 0
    later = at + timedelta(seconds=31)
    command = control.tick(observation, later, None, 1)
    assert command.ev_kw == command.ess_kw == 0 and "stale" in command.reason.lower()
    view = adapter.inputs.view(later, Capabilities())
    assert "last read from HA 31.0 s ago; watchdog limit 30 s" in view["cards"]["grid"]["issues"][0]
    assert view["cards"]["grid"]["value"] == pytest.approx(-1.3)
    renewed = await adapter.observe(Capabilities(), at=later)
    assert renewed.at == later and control.tick(renewed, later, None, 1).ess_kw < 0
    assert not adapter.inputs.view(later, Capabilities())["cards"]["grid"]["issues"]


async def test_independent_control_stops_when_the_input_loop_cannot_complete_another_read(inputs, tmp_path):
    adapter, _, _ = inputs
    entered = asyncio.Event()

    class BlockedForecast:
        async def read(self, observation, at):
            entered.set()
            await asyncio.Event().wait()

    store = Store(tmp_path / "watchdog.sqlite")
    policy = replace(Policy(), control_period_seconds=0.02)
    snapshot = replace(demo_snapshot(goals=()), policy=policy)
    app = Application(store, snapshot=snapshot, policy=policy, demo=False, ha=adapter, forecast=BlockedForecast())
    app.observation = replace(app.observation, quality="unknown")
    clock = [datetime.now(UTC)]
    app.now = lambda: clock[0]
    tasks = [asyncio.create_task(app.input_loop()), asyncio.create_task(app.control_loop())]
    try:
        await asyncio.wait_for(entered.wait(), 2)
        clock[0] = app.observation.at
        async with asyncio.timeout(2):
            while not any(command.ess_kw < 0 for command in app.actuator.commands):
                await asyncio.sleep(0.01)
        clock[0] = app.observation.at + timedelta(seconds=31)
        async with asyncio.timeout(2):
            while not app.last_command or "stale" not in app.last_command["reason"].lower():
                await asyncio.sleep(0.01)
        assert app.last_command["ev_kw"] == app.last_command["ess_kw"] == 0
        assert app.observation.quality == "measured"  # The independent watchdog, not an error callback, stopped control.
    finally:
        app.shutdown = True
        for task in (*tasks, *app.protective_tasks):
            task.cancel()
        await asyncio.gather(*tasks, *app.protective_tasks, return_exceptions=True)
        store.close()


@pytest.mark.parametrize("persistent", [False, True])
async def test_negative_derived_balance_settles_without_replan_but_persistent_failure_escalates(inputs, tmp_path, monkeypatch, persistent):
    adapter, rows, at = inputs
    observation = await adapter.observe(Capabilities(), at=at)
    clock = [at + timedelta(seconds=5)]
    original_observe = adapter.observe

    async def observe(capabilities):
        return await original_observe(capabilities, at=clock[0])

    class Forecast:
        async def read(self, observation, at):
            raise asyncio.CancelledError  # Reaching forecast read proves a validated recovery.

    monkeypatch.setattr(adapter, "observe", observe)
    store = Store(tmp_path / "balance.sqlite")
    app = Application(store, snapshot=demo_snapshot(goals=()), demo=False, ha=adapter, forecast=Forecast())
    app.now = lambda: clock[0]
    app.observation, app.forecast_data, app.status = observation, {}, "ready"
    app.ev_valid = app.ess_valid = True
    revision = app.revision
    rows["grid_export_kw"]["state"] = "3000"  # Residual -1kW while independent readings settle.
    sleeps = 0

    async def advance(seconds):
        nonlocal sleeps
        sleeps += 1
        if sleeps == 1:
            assert app.observation.quality == "settling"
            assert app.observation.at == observation.at  # Failed reads cannot refresh a valid timestamp.
            assert app.error is None and app.revision == revision
            command = app.controller.tick(app.observation, clock[0], None, revision)
            assert command.ev_kw == command.ess_kw == 0 and "settling" in command.reason
            assert app.ev_valid and app.ess_valid
            clock[0] += timedelta(seconds=30 if persistent else 5)
            if not persistent:
                rows["grid_export_kw"]["state"] = "1300"
        else:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", advance)
    try:
        with pytest.raises(asyncio.CancelledError):
            await app.input_loop()
        events = [event["kind"] for event in store.events()]
        assert "power_balance_settling" in events
        if persistent:
            assert app.status == "inputs_unavailable" and "negative" in app.error
            assert app.observation.quality == "unknown"
            assert not app.ev_valid and not app.ess_valid and app.revision == revision + 1
            assert "input_error" in events
        else:
            assert app.observation.quality == "measured" and app.error is None
            assert app.revision == revision and app.ev_valid and app.ess_valid
            assert "power_balance_recovered" in events and "input_error" not in events
    finally:
        for task in app.protective_tasks:
            task.cancel()
        await asyncio.gather(*app.protective_tasks, return_exceptions=True)
        store.close()
