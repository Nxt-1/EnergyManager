"""SYNTHETIC HA frontend contract preview; proxies only the local offline E2E fixture."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aiohttp import ClientSession, web


async def preview() -> None:
    fail_requests = False
    ev_scenario = "sampled"
    ev_scenario_at = datetime.now(UTC)
    async with ClientSession() as session:
        backend = "http://127.0.0.1:8102/"
        async with session.get(backend + "api/state") as response:
            state = await response.json()
        if "SYNTHETIC" not in state["provenance"]:
            raise RuntimeError("Native preview requires the labelled offline_e2e.py --serve fixture")
        async with session.get(backend + "api/dashboard") as response:
            manifest = await response.json()
        values = {"ev_soc": (45, "%"), "ess_soc": (50, "%"), "connected": ("on", None),
                  "grid_import_kw": (0, "W"), "grid_export_kw": (600, "W"), "pv_ac_kw": (1000, "W"),
                  "pv_dc_kw": (1000, "W"), "ev_kw": (0, "W"), "ess_kw": (0, "W"),
                  "monthly_peak_kw": (2500, "W")}
        states = {entity: {"entity_id": entity, "state": str(values[key][0]),
                          "attributes": {"friendly_name": key.replace("_", " "),
                                         "unit_of_measurement": values[key][1]}}
                  for key, entity in manifest["entities"].items() if key in values}
        if selector := manifest.get("phase_selector"):
            states[selector] = {"entity_id": selector, "state": "1",
                                "attributes": {"options": ["0", "1", "2"], "friendly_name": "SYNTHETIC phase mode"}}

        async def page(request: web.Request) -> web.Response:
            return web.Response(text=Path(__file__).with_name("native-preview.html").read_text(encoding="utf-8"),
                                content_type="text/html", headers={"Permissions-Policy": "clipboard-write=()"}
                                if request.query.get("manual-copy") == "1" else None)

        async def websocket(request: web.Request) -> web.WebSocketResponse:
            nonlocal fail_requests, ev_scenario, ev_scenario_at
            socket = web.WebSocketResponse()
            await socket.prepare(request)
            async for frame in socket:
                if frame.type != web.WSMsgType.TEXT:
                    continue
                message = json.loads(frame.data)
                endpoint = message.get("endpoint")
                if message["type"] == "synthetic/states":
                    result = states
                elif message["type"] == "synthetic/phase":
                    if (message.get("domain") != "select" or message.get("service") != "select_option"
                            or message.get("data", {}).get("entity_id") != manifest.get("phase_selector")
                            or message.get("data", {}).get("option") not in ("0", "1", "2")):
                        raise ValueError("Unexpected synthetic phase action")
                    states[manifest["phase_selector"]] = {**states[manifest["phase_selector"]],
                                                         "state": message["data"]["option"]}
                    result = states  # Display-only fake HA action, never forwarded to the backend.
                elif message["type"] == "synthetic/requests":
                    fail_requests = message["fail"] is True
                    result = {"failing": fail_requests}
                elif message["type"] == "synthetic/ev_update":
                    states[manifest["entities"]["ev_soc"]]["state"] = "57"
                    result = states
                elif message["type"] == "synthetic/peak_update":
                    if message["value"] not in ("2500", "7500", "0", "unavailable"):
                        raise ValueError("Unknown synthetic peak value")
                    states[manifest["entities"]["monthly_peak_kw"]]["state"] = message["value"]
                    result = states
                elif message["type"] == "synthetic/ev_scenario":
                    ev_scenario = message["scenario"]
                    ev_scenario_at = datetime.now(UTC)
                    if ev_scenario not in ("sampled", "charging", "phase_switch", "fault", "device_fault",
                                           "stopped", "stale", "disconnected", "settling"):
                        raise ValueError("Unknown synthetic EV display scenario")
                    for key, value in {"ev_kw": "4140" if ev_scenario == "charging" else "0",
                                       "ev_soc": "57", "connected": "off" if ev_scenario == "disconnected" else "on"}.items():
                        states[manifest["entities"][key]]["state"] = "unavailable" if ev_scenario == "stale" else value
                    result = states
                elif message["type"] != "supervisor/api":
                    raise ValueError("Unexpected synthetic WS command")
                elif endpoint == "/addons":
                    result = {"addons": [{"slug": "synthetic_energy_manager"}]}
                elif endpoint == "/addons/synthetic_energy_manager/info":
                    result = {"ingress_url": "/api/hassio_ingress/synthetic-token/"}
                elif endpoint == "/ingress/session" and message["method"] == "post":
                    result = {"session": "synthetic-session"}
                else:
                    raise ValueError("Unexpected synthetic Supervisor endpoint")
                await socket.send_json({"id": message["id"], "result": result})
            return socket

        async def proxy(request: web.Request) -> web.Response:
            if request.cookies.get("ingress_session") != "synthetic-session":
                return web.json_response({"error": "Synthetic ingress session required"}, status=401)
            if request.match_info["path"] == "api/state" and fail_requests:
                await asyncio.sleep(16)  # Exercise the installed loader's real15s AbortSignal deadline.
            headers = {"Host": request.host, "X-EnergyManager": request.headers.get("X-EnergyManager", "")}
            for key in ("Origin", "Content-Type"):
                if key in request.headers:
                    headers[key] = request.headers[key]
            async with session.request(request.method, backend + request.match_info["path"],
                                       headers=headers, params=request.query, data=await request.read()) as response:
                body = await response.read()
                if request.match_info["path"] == "api/state" and response.status == 200 and ev_scenario != "sampled":
                    # Display-only projection: never change the application or call an actuator.
                    fixture = json.loads(body)
                    at = fixture["now"]
                    old = (datetime.fromisoformat(at) - timedelta(minutes=2)).isoformat()
                    fixture["charger"] = {"at": old if ev_scenario == "stale" else at,
                                          "device_at": old if ev_scenario == "stale" else at,
                                          "issue": "SYNTHETIC stale device frame" if ev_scenario == "stale" else None,
                                          "waiting": None, "control": "SYNTHETIC EV display fixture",
                                          "states": {"phase": "1" if ev_scenario == "phase_switch" else "2",
                                                     "current": "6", "force": "2", "ev_status": "2",
                                                     "charger_status": "3", "charger_error": "0",
                                                     "charge_allowed": "on", "heartbeat": "42"}}
                    fixture["command"] = {"at": at, "generation": fixture["revision"], "ev_kw": 4.14,
                                          "current_a": 6, "phases": 3, "reason": "SYNTHETIC requested power"}
                    if ev_scenario == "settling":
                        fixture["control_enabled"] = True  # Display only; backend hardware remains off.
                        fixture["charger"]["states"].update(force="1", charger_status="4", ev_status="3")
                        fixture["charger"]["activity"] = {"as_of": at, "stage": "settling",
                            "label": "Settling before restart", "detail": "SYNTHETIC thirty-second restart hold.",
                            "until": (ev_scenario_at + timedelta(seconds=30)).isoformat(),
                            "duration_seconds": 30, "timer": "Restart hold"}
                    if ev_scenario == "fault":
                        fixture["ev_incident"] = {"status": "unresolved", "detected_at": at,
                                                  "reason": "SYNTHETIC delivery fault; fixture only"}
                    elif ev_scenario == "device_fault":
                        fixture["charger"]["states"].update(charger_error="8", ev_status="5", charger_status="1")
                    elif ev_scenario == "stopped":
                        fixture["charger"]["states"].update(force="1", ev_status="3", charger_status="4",
                                                            charge_allowed="off")
                        fixture["command"].update(ev_kw=0, current_a=0)
                    body = json.dumps(fixture).encode()
                return web.Response(body=body, status=response.status,
                                    headers={"Content-Type": response.headers["Content-Type"],
                                             "Cache-Control": "no-store",
                                             **({"Content-Disposition": response.headers["Content-Disposition"]}
                                                if "Content-Disposition" in response.headers else {})})

        async def loader(request: web.Request) -> web.Response:
            async with session.get(backend + "ha-card.js") as response:
                return web.Response(body=await response.read(), content_type="text/javascript")

        app = web.Application()
        app.router.add_get("/native-preview", page)
        app.router.add_get("/native-preview/{view}", page)
        app.router.add_get("/ha-card.js", loader)
        app.router.add_get("/api/websocket", websocket)
        app.router.add_route("*", "/api/hassio_ingress/synthetic-token/{path:.*}", proxy)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", 8103).start()
        print("SYNTHETIC HA-contract preview: http://127.0.0.1:8103/native-preview", flush=True)
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(preview())
