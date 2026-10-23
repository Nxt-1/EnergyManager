"""Exercise configured inputs, real full-horizon worker, API, persistence and fake HA writes."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from uuid import uuid4

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from energymanager.configuration import configured_application
from energymanager.control import GuardedActuator
from energymanager.store import Store
from energymanager.web import create_web


async def run(*, serve: bool = False) -> None:
    issued = datetime.now(UTC)
    calls = []
    weather_queries = []
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
    }

    async def state(request: web.Request) -> web.Response:
        if request.match_info["key"] == "zone.home":
            return web.json_response({"attributes": {"latitude": 50, "longitude": 4}})
        value, unit = values[request.match_info["key"]]
        return web.json_response(
            {
                "state": str(value),
                "attributes": {"unit_of_measurement": unit},
                "last_updated": datetime.now(UTC).isoformat(),
            }
        )

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
        if body.get("entity_id") == "phase":
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
    fake.add_routes(
        [
            web.get("/api/states/{key}", state),
            web.get("/weather", weather),
            web.post("/api/services/{domain}/{service}", service),
        ]
    )
    Path("artifacts").mkdir(exist_ok=True)
    stem = Path("artifacts") / f"e2e-{uuid4().hex}"
    async with TestServer(fake) as endpoint:
        config = json.loads(Path("configuration.example.json").read_text(encoding="utf-8"))
        config["home_assistant_url"] = str(endpoint.make_url("/api"))
        config["forecast_url"] = "http://127.0.0.1:1/unused-legacy-feed"
        config["measurements"] = {key: key for key in values if key != "phase"}
        config["actuators"]["phase"] = "phase"
        config["policy"]["planning_budget_seconds"] = 15
        path = stem.with_suffix(".json")
        path.write_text(json.dumps(config), encoding="utf-8")
        store = Store(stem.with_suffix(".sqlite"))
        application = configured_application(path, store, weather_url=str(endpoint.make_url("/weather")))
        assert application.goals == ()
        assert not config["policy"]["control_enabled"] and not config["allow_remote"]
        # Only the hardcoded localhost TestServer receives writes. No real controller is enabled.
        application.actuator = GuardedActuator(
            application.ha,
            {key: key for key in ("force", "phase", "current", "ess_setpoint")},
            application.snapshot.capabilities,
            True,
            generation=lambda: application.revision,
        )
        before = monotonic()
        async with TestClient(TestServer(create_web(application), port=8102 if serve else None)) as client:
            while monotonic() - before < 60 and application.accepted is None:
                await asyncio.sleep(0.2)
            assert application.accepted is not None, (application.status, application.error)
            response = await client.get("/api/state")
            current = await response.json()
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
            assert calls and any(call["entity_id"] == "ess_setpoint" for call in calls)
            assert application.store.decisions()[0]["disposition"] == "accepted"
            assert application.store.decision(application.accepted["id"])["result"]["valid"]
            report = {
                "version": current["version"],
                "provenance": current["provenance"],
                "accepted_seconds": monotonic() - before,
                "intervals": len(current["accepted"]["intervals"]),
                "control_max_seconds": current["control_max_seconds"],
                "fake_service_calls": len(calls),
                "weather_queries": weather_queries,
                "forecast_status": current["forecast_status"],
                "result": "passed",
                "normalization": asdict(application.ha.options),
                "checks": [
                    "configured JSON and HA HTTP inputs",
                    "built-in Open-Meteo pipeline with four original planes and correction tables",
                    "persisted measured household baseline; no prepared forecast endpoint",
                    "separate P1 powers, kW quarter demand and go-e selector readback",
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
                print("SYNTHETIC forecast verification preview: http://127.0.0.1:8102/", flush=True)
                await asyncio.Event().wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", help="Keep synthetic verification UI on localhost:8102")
    asyncio.run(run(serve=parser.parse_args().serve))
