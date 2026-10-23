"""Same-origin standalone/HA-ingress API; no hardware-authority endpoint."""

from __future__ import annotations

from importlib.resources import files
from typing import Any
from urllib.parse import urlsplit

from aiohttp import web

from .domain import json_data
from .service import Application


def create_web(application: Application) -> web.Application:
    @web.middleware
    async def boundary(request: web.Request, handler: Any) -> web.StreamResponse:
        peer = request.transport.get_extra_info("peername") if request.transport else None
        ingress = (
            peer
            and peer[0] == "172.30.32.2"
            and request.headers.get("X-Ingress-Path", "").startswith("/api/hassio_ingress/")
        )
        local = peer and peer[0] in ("127.0.0.1", "::1")
        if not local and not ingress:
            raise web.HTTPForbidden(text="Use local access or authenticated Supervisor ingress")
        if local and urlsplit("http://" + request.host).hostname not in ("localhost", "127.0.0.1", "::1"):
            raise web.HTTPForbidden(text="Local hostname required")
        if request.method not in ("GET", "HEAD"):
            if request.content_type != "application/json" or request.headers.get("X-EnergyManager") != "1":
                raise web.HTTPForbidden(text="Same-origin JSON required")
            origin = request.headers.get("Origin")
            if origin and urlsplit(origin).netloc != request.host:
                raise web.HTTPForbidden(text="Origin mismatch")
        try:
            return await handler(request)
        except (ValueError, TypeError, KeyError, StopIteration) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    app = web.Application(middlewares=[boundary], client_max_size=64 * 1024)

    async def state(request: web.Request) -> web.Response:
        return web.json_response(application.state())

    async def goals(request: web.Request) -> web.Response:
        return web.json_response(json_data(application.upsert_goal(await request.json())), status=201)

    async def delete(request: web.Request) -> web.Response:
        application.delete_goal(request.match_info["id"])
        return web.json_response({"deleted": True})

    async def approve(request: web.Request) -> web.Response:
        body = await request.json()
        return web.json_response(
            json_data(
                application.approve(
                    request.match_info["id"], body["state"], body.get("peak_kw"), body["revision"]
                )
            )
        )

    async def replan(request: web.Request) -> web.Response:
        application.requested.set()
        return web.json_response({"requested": True}, status=202)

    async def decisions(request: web.Request) -> web.Response:
        return web.json_response(application.store.decisions())

    async def decision(request: web.Request) -> web.Response:
        value = application.store.decision(request.match_info["id"])
        if value is None:
            raise web.HTTPNotFound()
        return web.json_response(value)

    async def events(request: web.Request) -> web.Response:
        return web.json_response(application.store.events())

    async def asset(request: web.Request) -> web.Response:
        name = request.match_info.get("name", "index.html")
        if name not in ("index.html", "app.js", "style.css", "ha-card.js"):
            raise web.HTTPNotFound()
        content_type = {"html": "text/html", "js": "text/javascript", "css": "text/css"}[
            name.rsplit(".", 1)[1]
        ]
        response = web.Response(
            body=files("energymanager").joinpath("assets", name).read_bytes(), content_type=content_type
        )
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'self'",
            }
        )
        return response

    app.add_routes(
        [
            web.get("/api/state", state),
            web.post("/api/goals", goals),
            web.delete("/api/goals/{id}", delete),
            web.post("/api/goals/{id}/approval", approve),
            web.post("/api/replan", replan),
            web.get("/api/decisions", decisions),
            web.get("/api/decisions/{id}", decision),
            web.get("/api/events", events),
            web.get("/", asset),
            web.get("/{name}", asset),
        ]
    )

    async def start(app: web.Application) -> None:
        await application.start()

    async def stop(app: web.Application) -> None:
        await application.close()
        application.store.close()

    app.on_startup.append(start)
    app.on_cleanup.append(stop)
    return app
