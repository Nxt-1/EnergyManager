"""Exercise configured inputs, real full-horizon worker, API, persistence and fake HA writes."""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from uuid import uuid4
from unittest.mock import patch

import aiohttp
from aiohttp import web
from aiohttp.abc import AbstractResolver
from aiohttp.test_utils import TestClient, TestServer

from energymanager.configuration import configured_application
from energymanager.settings import ConfigurationFile, SETTING_FIELDS
from energymanager.notifications import Notifications, NotificationTarget
from energymanager.store import Store
from energymanager.web import create_web


class VerificationResolver(AbstractResolver):
    def __init__(self, port: int) -> None:
        self.port = port

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET) -> list[dict]:
        if host != "supervisor":
            raise OSError("Verification permits only the local fake Supervisor")
        return [{"hostname": host, "host": "127.0.0.1", "port": self.port,
                 "family": socket.AF_INET, "proto": 0, "flags": 0}]

    async def close(self) -> None:
        pass


async def run(*, serve: bool = False, preview_fault: str | None = None,
              history_fixture: bool = False, calendar_fixture: bool = False, ev_fault_fixture: bool = False) -> None:
    issued = datetime.now(UTC)
    calls = []
    weather_queries = []
    active_fault: str | None = None
    values = {
        "ev_soc": (45, "%"),
        "ess_soc": (50, "%"),
        "connected": ("on", None),
        "grid_import_kw": (0, "W"),
        "grid_export_kw": (600, "W"),
        "pv_ac_kw": (1, "kW"),
        "pv_dc_kw": (1, "kW"),
        "ev_kw": (0, "kW"),
        "ess_kw": (0, "kW"),
        "quarter_import_kwh": (0, "kW"),
        "monthly_peak_kw": (2.5, "kW"),
        "phase": (1, None),
        "force": (1, None), "current": (6, "A"), "ess_setpoint": (0, "W"),
    }
    if calendar_fixture:
        values["ev_soc"] = (90, "%")  # Enough measured energy for both provisional trips and daily readiness.

    def state_row(entity: str) -> dict:
        key = entity.split(".", 1)[-1]
        value, unit = values[key]
        now = datetime.now(UTC)
        reported_at = issued - timedelta(hours=3)
        if active_fault == "quarter" and key == "quarter_import_kwh":
            reported_at = now.replace(minute=now.minute // 15 * 15, second=0, microsecond=0) - timedelta(seconds=1)
        elif active_fault == "stale" and key == "pv_ac_kw":
            reported_at = now - timedelta(seconds=45)
        elif active_fault == "unavailable" and key == "pv_dc_kw":
            value = "unavailable"
        return {"entity_id": entity, "state": str(value),
                "attributes": {"unit_of_measurement": unit, "friendly_name": key.replace("_", " ")},
                "last_updated": (issued - timedelta(hours=2)).isoformat(), "last_reported": reported_at.isoformat()}

    async def states(request: web.Request) -> web.Response:
        assert request.headers.get("Authorization") == "Bearer synthetic-supervisor-credential"
        return web.json_response([state_row(entity) for group in ("measurements", "actuators")
                                  for entity in config[group].values() if entity])

    async def services(request: web.Request) -> web.Response:
        return web.json_response([{"domain": "notify", "services": {
            "mobile_app_verification_phone": {"name": "Verification phone"}}}])

    async def state(request: web.Request) -> web.Response:
        if active_fault == "read_failure":
            raise web.HTTPServiceUnavailable()
        if request.match_info["key"] == "zone.home":
            return web.json_response({"attributes": {"latitude": 50, "longitude": 4}})
        return web.json_response(state_row(request.match_info["key"]))

    async def weather(request: web.Request) -> web.Response:
        weather_queries.append(dict(request.query))
        beginning = issued.replace(hour=0, minute=0, second=0, microsecond=0)
        hours = 9 * 24
        return web.json_response({"hourly": {
            "time": [(beginning + timedelta(hours=i)).timestamp() for i in range(hours)],
            "global_tilted_irradiance": [150] * hours,
            "temperature_2m": [15] * hours,
            "cloud_cover": [25] * hours,
            "direct_radiation": [100] * hours,
            "diffuse_radiation": [50] * hours,
        }})

    async def service(request: web.Request) -> web.Response:
        body = await request.json()
        if body.get("entity_id") == "select.phase":
            values["phase"] = (int(body["option"]), None)
        calls.append(
            {
                "domain": request.match_info["domain"],
                "service": request.match_info["service"],
                **body,
            }
        )
        return web.json_response([])

    fake = web.Application()
    async def calendar_feed(request: web.Request) -> web.Response:
        def item(uid: str, hours: int) -> str:
            start = (issued + timedelta(hours=hours)).strftime("%Y%m%dT%H%M%SZ")
            return f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART:{start}\r\nSUMMARY:SYNTHETIC {uid}\r\nLOCATION:Fixture hall, Test town\r\nEND:VEVENT\r\n"
        events = item("referee-match", 24)
        if request.match_info["name"] == "second":
            events += item("second-match", 48)
        return web.Response(text="BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + events + "END:VCALENDAR\r\n")
    fake.add_routes(
        [
            web.get("/core/api/states/{key}", state),
            web.get("/core/api/states", states),
            web.get("/core/api/services", services),
            web.get("/weather", weather),
            web.get("/calendar/{name}", calendar_feed),
            web.post("/core/api/services/{domain}/{service}", service),
        ]
    )
    Path("artifacts").mkdir(exist_ok=True)
    stem = Path("artifacts") / f"e2e-{uuid4().hex}"
    async with TestServer(fake) as endpoint:
        config = json.loads(Path("configuration.example.json").read_text(encoding="utf-8"))
        config["home_assistant_url"] = str(endpoint.make_url("/api"))
        config["forecast_url"] = "http://127.0.0.1:1/unused-legacy-feed"
        for field in SETTING_FIELDS:
            if field.kind == "entity" and field.required:
                group, key = field.path.split(".")
                config[group][key] = f"{field.domains[0]}.{key}"
        config["token_environment"] = "UNUSED_LEGACY_TOKEN"
        config["allow_remote"] = False
        config["policy"]["planning_budget_seconds"] = 15
        if calendar_fixture:
            config["policy"]["planning_budget_seconds"] = 60
            config["calendars"] = [{"id": name, "label": f"SYNTHETIC {name}",
                                     "url": f"https://calendar.example/{name}"} for name in ("referee", "second")]
        path = stem.with_suffix(".json")
        path.write_text(json.dumps(config), encoding="utf-8")
        store = Store(stem.with_suffix(".sqlite"))
        original_session = aiohttp.ClientSession

        def local_session(*args, **kwargs):
            kwargs.setdefault("connector", aiohttp.TCPConnector(resolver=VerificationResolver(endpoint.port)))
            return original_session(*args, **kwargs)

        async def local_calendar(url: str) -> bytes:
            assert calendar_fixture and url in ("https://calendar.example/referee", "https://calendar.example/second")
            async with original_session() as session:
                async with session.get(endpoint.make_url("/calendar/" + url.rsplit("/", 1)[-1])) as response:
                    assert response.status == 200
                    return await response.read()

        with patch("aiohttp.ClientSession", local_session), patch("energymanager.calendars.fetch_calendar", local_calendar), patch.dict("os.environ", {
            "SUPERVISOR_TOKEN": "synthetic-supervisor-credential"
        }):
            application = configured_application(path, store, addon=True,
                                                  weather_url=str(endpoint.make_url("/weather")))
            if history_fixture:
                from graph_history_fixture import seed_history

                seeded = seed_history(store, issued, application.snapshot.capabilities)
                print(f"SYNTHETIC archived graph fixture: {seeded} records; intentional gaps", flush=True)
            assert application.goals == ()
            assert not application.actuator.enabled
            assert application.ha.url == "http://supervisor/core/api"
            configuration = ConfigurationFile(path, addon=True, mode="configured")
            before = monotonic()
            async with TestClient(TestServer(create_web(application, configuration=configuration), port=8102 if serve else None)) as client:
                while monotonic() - before < (180 if calendar_fixture else 60) and application.accepted is None:
                    await asyncio.sleep(0.2)
                assert application.accepted is not None, (application.status, application.error)
                response = await client.get("/api/state")
                current = await response.json()
                if calendar_fixture:
                    assert len([goal for goal in current["goals"] if goal.get("calendar")]) == 2
                    assert len(current["calendars"]) == 2 and not any(item["error"] for item in current["calendars"])
                    assert all(goal["distance_km"] == 50 for goal in current["goals"])
                assert current["accepted"]["valid"] and current["provenance"].startswith("SYNTHETIC")
                assert abs(current["observation"]["house_kw"] - 0.4) < 1e-9
                assert current["observation"]["ev_phase_source"] == "goe_selector"
                assert current["observation"]["ev_phase_known"]
                assert current["observation"]["ev_state_known"]
                assert len(weather_queries) == 4
                assert all(q["models"] == "knmi_seamless" and q["forecast_days"] == "9" for q in weather_queries)
                assert current["forecast_status"]["load_stage"] == "learning"
                assert current["forecast_status"]["load_samples"] >= 1
                assert current["forecast_status"]["weather_error"] is None
                assert application.forecast_data["intervals"][0]["pv_ac_kw"] > 0
                assert application.forecast_data["intervals"][0]["pv_dc_kw"] > 0
                assert not calls  # Startup and planning do not enable hardware.
                baseline_control_max = max(application.response_seconds, default=0)
                baseline_ticks = len(application.response_seconds)
                headers = {"X-EnergyManager": "1"}
                response = await client.post("/api/control", json={"enabled": True}, headers=headers)
                assert response.status == 200, await response.text()
                await asyncio.sleep(0.05)
                assert application.actuator.enabled
                assert calls and any(call.get("entity_id") == "number.ess_setpoint" for call in calls)
                response = await client.post("/api/control", json={"enabled": False}, headers=headers)
                assert response.status == 200
                assert not application.actuator.enabled
                assert calls[-2]["entity_id"] == "select.force" and calls[-2]["option"] == "1"
                assert calls[-1]["entity_id"] == "number.ess_setpoint" and calls[-1]["value"] == 0
                # Observe a completed tick after switching; zero samples must not imply zero latency.
                async with asyncio.timeout(10):
                    while len(application.response_seconds) == baseline_ticks:
                        await asyncio.sleep(0.05)
                application.notifications = Notifications(store, application.ha,
                    NotificationTarget("notify.mobile_app_verification_phone", "action"))
                await application.notifications.inform("verification-only", {"message": "SYNTHETIC local test only"})
                assert calls[-1]["domain"] == "notify"
                assert application.store.decisions()[0]["disposition"] == "accepted"
                assert application.store.decision(application.accepted["id"])["result"]["valid"]
                report = {
                    "version": current["version"],
                    "provenance": current["provenance"],
                    "accepted_seconds": monotonic() - before,
                    "intervals": len(current["accepted"]["intervals"]),
                    "control_max_seconds": max(application.response_seconds, default=0),
                    "baseline_control_max_seconds": baseline_control_max,
                    "switch_control_max_seconds": max(application.response_seconds[baseline_ticks:], default=0),
                    "switch_control_ticks": len(application.response_seconds) - baseline_ticks,
                    "fake_service_calls": len(calls),
                    "calendar_imports": len([goal for goal in current["goals"] if goal.get("calendar")]),
                    "calendar_fixture": calendar_fixture,
                    "initial_ev_soc_percent": values["ev_soc"][0],
                    "weather_queries": weather_queries,
                    "forecast_status": current["forecast_status"],
                    "result": "passed",
                    "normalization": asdict(application.ha.options),
                    "checks": [
                        "configured JSON and automatic Supervisor connection with local fake DNS/auth",
                        "no hardware calls before the Overview switch; immediate enable and stop/clear on disable",
                        "phone notification action delivered only to local fake HA",
                        "built-in Open-Meteo pipeline with four original planes and correction tables",
                        "persisted measured household baseline; no prepared forecast endpoint",
                        "separate P1 powers, kW quarter demand and go-e selector readback",
                        "all HA states carry three-hour-old report metadata; validated input reads still drive forecasting/control",
                        "spawned real full-horizon HiGHS plan",
                        "publication against current measurements",
                        "independent guarded calls to local fake only",
                        "API state",
                        "persisted input checksum and accepted result",
                    ],
                }
                Path("docs/offline-e2e.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2), flush=True)
                if serve:
                    if ev_fault_fixture:
                        from energymanager.control import Command

                        detected = application.now()
                        incident_command = Command(application.revision, None, detected, 1.38, 0, 1, 6, 4,
                                                   "SYNTHETIC EV non-delivery fixture")
                        for seconds in range(300, 0, -5):
                            at = detected - timedelta(seconds=seconds)
                            body = {"at": at.isoformat(), "provenance": "SYNTHETIC EV incident fixture",
                                    "entities": {"sensor.ev_kw": {"state": "0", "unit": "kW"},
                                                 "select.force": {"state": "2"}}}
                            with store.connection:
                                store.connection.execute("INSERT INTO events(at,kind,body) VALUES (?,'ev_diagnostics',?)",
                                                         (at.isoformat(), json.dumps(body)))
                        application.ev_faults.capture(incident_command, application.observation,
                                                      detected - timedelta(seconds=90))
                        application.ev_faults.unresolved("SYNTHETIC verification incident; no real device fault")
                    active_fault = preview_fault
                    print("SYNTHETIC forecast verification preview: http://127.0.0.1:8102/", flush=True)
                    await asyncio.Event().wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", help="Keep synthetic verification UI on localhost:8102")
    parser.add_argument("--history-fixture", action="store_true",
                        help="Seed explicitly SYNTHETIC old graph measurements, including gaps")
    parser.add_argument("--calendar-fixture", action="store_true",
                        help="Sync two SYNTHETIC calendar feeds served only by the local fake endpoint")
    parser.add_argument("--ev-fault-fixture", action="store_true",
                        help="Show a SYNTHETIC unresolved EV incident and five-minute diagnostic trace")
    parser.add_argument("--input-fault", choices=("quarter", "stale", "unavailable", "read_failure"),
                        help="Inject old metadata, unavailability or HA read failure after local verification")
    arguments = parser.parse_args()
    if arguments.input_fault and not arguments.serve:
        parser.error("--input-fault requires --serve")
    if arguments.ev_fault_fixture and not arguments.serve:
        parser.error("--ev-fault-fixture requires --serve")
    asyncio.run(run(serve=arguments.serve, preview_fault=arguments.input_fault,
                    history_fixture=arguments.history_fixture, calendar_fixture=arguments.calendar_fixture,
                    ev_fault_fixture=arguments.ev_fault_fixture))
