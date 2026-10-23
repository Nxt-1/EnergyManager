"""Exercise configured inputs, real full-horizon worker, API, persistence and fake HA writes."""

from __future__ import annotations

import asyncio
import json
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


async def run() -> None:
    issued = datetime.now(UTC)
    calls = []
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
        value, unit = values[request.match_info["key"]]
        return web.json_response(
            {
                "state": str(value),
                "attributes": {"unit_of_measurement": unit},
                "last_updated": datetime.now(UTC).isoformat(),
            }
        )

    async def forecast(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "issued_at": issued.isoformat(),
                "revision": "synthetic-configured-1",
                "provenance": "SYNTHETIC local HTTP integration acceptance; constant test signals",
                "intervals": [
                    {
                        "start": issued.isoformat(),
                        "end": (issued + timedelta(hours=169)).isoformat(),
                        "house_kw": 0.4,
                        "pv_ac_kw": 1,
                        "pv_dc_kw": 1,
                    }
                ],
            }
        )

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
            web.get("/forecast", forecast),
            web.post("/api/services/{domain}/{service}", service),
        ]
    )
    Path("artifacts").mkdir(exist_ok=True)
    stem = Path("artifacts") / f"e2e-{uuid4().hex}"
    async with TestServer(fake) as endpoint:
        config = json.loads(Path("configuration.example.json").read_text(encoding="utf-8"))
        config["home_assistant_url"] = str(endpoint.make_url("/api"))
        config["forecast_url"] = str(endpoint.make_url("/forecast"))
        config["measurements"] = {key: key for key in values if key != "phase"}
        config["measurement_options"] = {
            "house_source": "separate_grid", "quarter_source": "fixed_quarter_average",
            "phase_source": "goe_selector",
        }
        config["actuators"]["phase"] = "phase"
        config["policy"]["planning_budget_seconds"] = 15
        path = stem.with_suffix(".json")
        path.write_text(json.dumps(config), encoding="utf-8")
        store = Store(stem.with_suffix(".sqlite"))
        application = configured_application(path, store)
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
        async with TestClient(TestServer(create_web(application))) as client:
            while monotonic() - before < 35 and application.accepted is None:
                await asyncio.sleep(0.2)
            assert application.accepted is not None, (application.status, application.error)
            response = await client.get("/api/state")
            current = await response.json()
            assert current["accepted"]["valid"] and current["provenance"].startswith("SYNTHETIC")
            assert abs(current["observation"]["house_kw"] - 0.4) < 1e-9
            assert current["observation"]["ev_phase_source"] == "goe_selector"
            assert current["observation"]["ev_phase_known"]
            assert current["observation"]["ev_state_known"]
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
                "result": "passed",
                "measurement_options": config["measurement_options"],
                "checks": [
                    "configured JSON and HA HTTP inputs",
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


if __name__ == "__main__":
    asyncio.run(run())
