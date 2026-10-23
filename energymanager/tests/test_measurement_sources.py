"""Installation-shaped sensor inputs through the real HTTP and actuator boundaries."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from energymanager.adapters import HomeAssistantAdapter
from energymanager.configuration import configured_application, create_configuration_if_missing
from energymanager.control import Command, FastControl, GuardedActuator
from energymanager.domain import Capabilities, Policy
from energymanager.forecasts import demo_snapshot
from energymanager.measurements import MeasurementOptions
from energymanager.settings import ConfigurationFile, SettingsValidationError
from energymanager.store import Store


def test_quarter_average_denominators_and_exact_boundary():
    at = datetime(2026, 10, 23, 12, 7, 30, tzinfo=UTC)
    assert MeasurementOptions(quarter_source="energy").quarter_energy(0.4, at) == 0.4
    assert MeasurementOptions(quarter_source="elapsed_average").quarter_energy(3.2, at) == 0.4
    assert MeasurementOptions(quarter_source="fixed_quarter_average").quarter_energy(3.2, at) == 0.8
    boundary = at.replace(minute=15, second=0)
    assert MeasurementOptions(quarter_source="elapsed_average").quarter_energy(3.2, boundary) == 0
    with pytest.raises(ValueError):
        MeasurementOptions(quarter_source="energy").quarter_energy(float("nan"), at)


@pytest.mark.parametrize("source,measured,ev,pv,ess,expected", [
    ("direct", 0.7, 2, 3, -1, 0.7),
    ("total_consumption", 2.7, 2, 3, -1, 0.7),
    ("signed_grid", -1.3, 2, 3, 1, 0.7),
    ("separate_grid", 0.7, 2, 3, -1, 0.7),
])
def test_house_reconstruction_with_import_export_and_storage(source, measured, ev, pv, ess, expected):
    assert MeasurementOptions(house_source=source).house_power(measured, ev, pv, ess) == pytest.approx(expected)
    with pytest.raises(ValueError, match="negative"):
        MeasurementOptions(house_source="total_consumption").house_power(1, 2, 0, 0)


def test_settings_migrate_by_explicit_choices_without_losing_user_mappings(tmp_path):
    path = tmp_path / "energymanager.json"
    create_configuration_if_missing(path)
    editor = ConfigurationFile(path)
    original = json.loads(path.read_bytes())
    saved = editor.save(editor.read()["revision"], {
        "measurement_options.house_source": "separate_grid",
        "measurement_options.quarter_source": "fixed_quarter_average",
        "measurement_options.phase_source": "goe_selector",
        "measurements.grid_import_kw": "sensor.p1_dongle_momentary_active_import",
        "measurements.grid_export_kw": "sensor.p1_dongle_momentary_active_export",
        "measurements.quarter_import_kwh": "sensor.p1_dongle_current_quarter_average_demand",
        "actuators.phase": "select.goe_test_psm",
    })
    data = json.loads(path.read_bytes())
    assert data["measurements"]["house_kw"] == original["measurements"]["house_kw"]
    assert data["measurements"]["ev_phases"] == original["measurements"]["ev_phases"]
    assert data["capabilities"] == original["capabilities"]
    store = Store(tmp_path / "test.sqlite")
    try:
        app = configured_application(path, store)
        assert app.ha.entities["ev_phases"] == "select.goe_test_psm"
        assert app.ha.options.house_source == "separate_grid"
        assert not app.policy.control_enabled
    finally:
        store.close()
    with pytest.raises(SettingsValidationError):
        editor.save(saved["revision"], {"measurement_options.house_source": "invented"})
    with pytest.raises(SettingsValidationError):
        editor.save(saved["revision"], {"measurements.grid_export_kw": ""})


async def test_p1_split_powers_and_goe_selector_over_local_http():
    at = datetime(2026, 10, 23, 12, 7, 30, tzinfo=UTC)
    values = {
        "ev_soc": (45, "%"), "ess_soc": (50, "%"), "connected": ("on", None),
        "grid_import_kw": (0, "W"), "grid_export_kw": (1300, "W"),
        "pv_ac_kw": (3, "kW"), "pv_dc_kw": (0.4, "kW"), "ev_kw": (2000, "W"),
        "ess_kw": (1, "kW"), "quarter_import_kwh": (3200, "W"),
        "monthly_peak_kw": (4, "kW"), "phase_selector": ("2", None),
    }
    timestamps = {key: at for key in values}
    calls = []

    async def state(request):
        key = request.match_info["key"]
        calls.append(key)
        value, unit = values[key]
        return web.json_response({"state": str(value), "attributes": {"unit_of_measurement": unit},
                                  "last_updated": timestamps[key].isoformat()})

    fake = web.Application()
    fake.router.add_get("/states/{key}", state)
    async with TestServer(fake) as server:
        options = MeasurementOptions(house_source="separate_grid", quarter_source="elapsed_average",
                                     phase_source="goe_selector")
        async with HomeAssistantAdapter(str(server.make_url("")), {key: key for key in values},
                                        measurement_options=options, phase_entity="phase_selector") as adapter:
            observation = await adapter.observe(Capabilities())
            assert observation.house_kw == pytest.approx(0.7)
            assert observation.quarter_import_kwh == pytest.approx(0.4)
            assert observation.ev_phases == 3 and observation.ev_phase_known
            assert observation.ev_phase_source == "goe_selector"
            assert "house_kw" not in calls and "ev_phases" not in calls
            timestamps["ev_soc"] = at + timedelta(seconds=1)
            assert (await adapter.observe(Capabilities())).ev_state_known
            timestamps["ev_soc"] = at + timedelta(seconds=60)
            assert not (await adapter.observe(Capabilities())).ev_state_known
            timestamps["ev_soc"] = at
            adapter.options = replace(options, quarter_source="fixed_quarter_average")
            assert (await adapter.observe(Capabilities())).quarter_import_kwh == pytest.approx(0.8)
            # Auto is not an observed phase count, but fresh ESS balancing remains usable.
            values["phase_selector"] = ("0", None)
            unknown = await adapter.observe(Capabilities())
            assert not unknown.ev_phase_known and unknown.quality == "measured"
            command = FastControl(Capabilities(), Policy()).tick(unknown, at, None, 1)
            assert command.ev_kw == 0 and command.ess_kw < 0
            assert "phase" in command.reason.lower()
            values["phase_selector"] = ("unavailable", None)
            assert not (await adapter.observe(Capabilities())).ev_phase_known
            timestamps["quarter_import_kwh"] = at.replace(minute=15, second=1)
            with pytest.raises(ValueError, match="boundary"):
                await adapter.observe(Capabilities())


async def test_phase_change_waits_for_readback_before_resuming_charge():
    class Client:
        def __init__(self):
            self.calls = []

        async def service(self, domain, service, data):
            self.calls.append(data)

    client = Client()
    actuator = GuardedActuator(client, {"force": "select.force", "phase": "select.phase",
                                       "current": "number.current", "ess_setpoint": "number.ess"},
                               Capabilities(), enabled=True)
    at = datetime(2026, 10, 23, 12, 7, 30, tzinfo=UTC)
    observation = replace(demo_snapshot(hours=1, goals=()).observation, at=at,
                          ev_power_kw=0, ev_phases=1, ev_phase_source="goe_selector")
    command = Command(1, "synthetic", at, 4.14, 0.3, 3, 6, 4, "test")
    await actuator.apply(command, 1, observation)
    await actuator.apply(replace(command, at=at + timedelta(seconds=10)), 1,
                         replace(observation, at=at + timedelta(seconds=10)))
    assert {"entity_id": "select.phase", "option": "2"} in client.calls
    client.calls.clear()
    await actuator.apply(replace(command, at=at + timedelta(seconds=11)), 1,
                         replace(observation, at=at + timedelta(seconds=11)))
    assert all(call.get("entity_id") != "number.current" for call in client.calls)
    assert client.calls[-1] == {"entity_id": "select.force", "option": "1"}
    # A fresh readback confirms the forced mode; AC hardware telemetry is not fabricated.
    await actuator.apply(replace(command, at=at + timedelta(seconds=12)), 1,
                         replace(observation, at=at + timedelta(seconds=12), ev_phases=3))
    assert client.calls[-1] == {"entity_id": "select.force", "option": "2"}
    assert {"entity_id": "number.current", "value": 6} in client.calls
