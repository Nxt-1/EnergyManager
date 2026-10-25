"""SYNTHETIC HA frontend contract preview; proxies only the local offline E2E fixture."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from aiohttp import ClientSession, web


async def preview() -> None:
    fail_requests = False
    ev_scenario = "sampled"
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
                  "pv_dc_kw": (1000, "W"), "ev_kw": (0, "W"), "ess_kw": (0, "W")}
        states = {entity: {"entity_id": entity, "state": str(values[key][0]),
                          "attributes": {"friendly_name": key.replace("_", " "),
                                         "unit_of_measurement": values[key][1]}}
                  for key, entity in manifest["entities"].items() if key in values}

        async def page(request: web.Request) -> web.Response:
            return web.Response(text=Path(__file__).with_name("native-preview.html").read_text(encoding="utf-8"),
                                content_type="text/html", headers={"Permissions-Policy": "clipboard-write=()"}
                                if request.query.get("manual-copy") == "1" else None)

        async def websocket(request: web.Request) -> web.WebSocketResponse:
            nonlocal fail_requests, ev_scenario
            socket = web.WebSocketResponse()
            await socket.prepare(request)
            async for frame in socket:
                if frame.type != web.WSMsgType.TEXT:
                    continue
                message = json.loads(frame.data)
                endpoint = message.get("endpoint")
                if message["type"] == "synthetic/states":
                    result = states
                elif message["type"] == "synthetic/requests":
                    fail_requests = message["fail"] is True
                    result = {"failing": fail_requests}
                elif message["type"] == "synthetic/ev_update":
                    states[manifest["entities"]["ev_soc"]]["state"] = "57"
                    result = states
                elif message["type"] == "synthetic/ev_scenario":
                    ev_scenario = message["scenario"]
                    if ev_scenario not in ("sampled", "charging", "phase_switch", "fault", "stale", "disconnected"):
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
                    if ev_scenario == "fault":
                        fixture["ev_incident"] = {"status": "unresolved", "detected_at": at,
                                                  "reason": "SYNTHETIC delivery fault; fixture only"}
                    body = json.dumps(fixture).encode()
                return web.Response(body=body, status=response.status,
                                    headers={"Content-Type": response.headers["Content-Type"],
                                             "Cache-Control": "no-store"})

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
