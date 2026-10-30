"""Same-origin standalone/HA-ingress API, including the explicit hardware control switch."""

from __future__ import annotations

import asyncio
import sqlite3
from importlib.resources import files
from typing import Any
from urllib.parse import urlsplit

from aiohttp import web

from .domain import instant, json_data
from .service import Application
from .settings import ConfigurationConflict, ConfigurationFile, SettingsValidationError
from .hardware import HardwareControl
from . import __version__
from .dashboard import dashboard_manifest
from .graph_history import graph_history
from .calendars import CalendarSync
from .journeys import Journeys
from .ev_faults import incident_report


def create_web(application: Application, *, configuration: ConfigurationFile | None = None) -> web.Application:
    if configuration:
        application.hardware = HardwareControl(application, configuration)
        if not application.demo and not application.configuration_error:
            application.journeys = Journeys(application, configuration.routing_settings())
            application.calendars = CalendarSync(application, configuration.started_values.get("calendars"))
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
    archive_readers = asyncio.Semaphore(2)

    async def settings(request: web.Request) -> web.Response:
        if configuration is None:
            return web.json_response({"error": "Start EnergyManager with a configuration file to edit settings"},
                                     status=503)
        try:
            if request.method == "GET":
                result = await asyncio.to_thread(configuration.read)
            else:
                body = await request.json()
                if (not isinstance(body, dict) or not isinstance(body.get("revision"), str)
                        or not isinstance(body.get("values"), dict)):
                    raise ValueError("A settings revision and field values are required")
                result = await asyncio.to_thread(configuration.save, body["revision"], body["values"])
                if application.journeys:
                    application.journeys.apply_settings(configuration.routing_settings())
                application.store.event("configuration_saved", {
                    "revision": result["revision"], "fields": sorted(body["values"]),
                    "restart_required": result["restart_required"],
                })
        except ConfigurationConflict as exc:
            return web.json_response({"error": str(exc)}, status=409)
        except SettingsValidationError as exc:
            return web.json_response({"error": str(exc), "errors": exc.errors}, status=400)
        except OSError as exc:
            return web.json_response({"error": f"Cannot access configuration file: {exc.strerror}"}, status=500)
        return web.json_response(result, headers={"Cache-Control": "no-store"})

    async def entities(request: web.Request) -> web.Response:
        if configuration is None:
            return web.json_response({"error": "No configuration file selected"}, status=503)
        try:
            result = await configuration.entities()
        except (RuntimeError, OSError) as exc:
            return web.json_response({"error": str(exc)}, status=503)
        return web.json_response(result, headers={"Cache-Control": "no-store"})

    async def state(request: web.Request) -> web.Response:
        result = application.state()
        if request.query.get("compact") == "1":
            # Archive graphs own older samples; publication/replay evidence stays in decisions.
            result["observed"] = result["observed"][-120:]
            plan = result["accepted"]
            result["accepted_plan_id"] = plan["id"] if plan else None
            result["accepted_unchanged"] = bool(plan and request.query.get("plan_id") == plan["id"])
            if result["accepted_unchanged"]:
                del result["accepted"]
            elif plan:
                display_fields = ("id", "revision", "valid", "status", "seconds", "intervals", "flows",
                                  "goals", "sessions", "summary", "reasons", "stages", "input_digest")
                result["accepted"] = {key: plan[key] for key in display_fields if key in plan}
        return web.json_response(result, headers={"Cache-Control": "no-store"})

    async def sync_calendars(request: web.Request) -> web.Response:
        if application.calendars is None:
            raise ValueError("Calendar sync requires configured mode and complete installation settings")
        await application.calendars.refresh()
        return web.json_response({"calendars": application.calendars.status()})

    async def journeys(request: web.Request) -> web.Response:
        if application.journeys is None:
            raise ValueError("Routed journeys require configured mode")
        identity = request.match_info.get("id")
        if request.method == "DELETE":
            application.journeys.delete(request.match_info["id"])
            return web.json_response({"deleted": True})
        if request.path.endswith("/reset"):
            application.journeys.reset(request.match_info["id"])
            return web.json_response({"reset": True})
        if request.path.endswith("/refresh"):
            application.journeys.request_refresh()
            return web.json_response({"requested": True}, status=202)
        result = application.journeys.upsert(await request.json(), identity)
        return web.json_response(result, status=201)

    async def energy(request: web.Request) -> web.Response:
        now = application.now()
        try:
            result = await application.daily_estimates.recorded(now)
        except (TimeoutError, sqlite3.OperationalError) as exc:
            return web.json_response({"error": f"Daily energy unavailable: {exc}"}, status=503)
        estimate = application.daily_estimates.view(now)
        result["estimate"] = estimate
        result["predicted_kwh"] = estimate["kwh"] if estimate else None
        return web.json_response(result, headers={"Cache-Control": "no-store"})

    async def history(request: web.Request) -> web.Response:
        start = instant(request.query["start"])
        end = instant(request.query["end"])
        points = int(request.query.get("points", "1200"))
        async with archive_readers:
            try:
                result = await asyncio.to_thread(
                    graph_history, application.store.path, start, end, application.now(), points,
                    application.policy.measurement_max_age_seconds,
                    application.snapshot.capabilities.ev_capacity_kwh,
                    application.snapshot.capabilities.ess_capacity_kwh, application.demo)
            except (TimeoutError, sqlite3.OperationalError) as exc:
                return web.json_response({"error": f"Archive history unavailable: {exc}"}, status=503)
        return web.json_response(result, headers={"Cache-Control": "no-store"})

    async def dashboard(request: web.Request) -> web.Response:
        return web.json_response(dashboard_manifest(application), headers={"Cache-Control": "no-store"})

    async def control(request: web.Request) -> web.Response:
        if application.hardware is None:
            return web.json_response({"error": "No installation settings are available"}, status=503)
        body = await request.json()
        if not isinstance(body, dict) or set(body) != {"enabled"} or type(body["enabled"]) is not bool:
            raise ValueError("A hardware control state is required")
        try:
            return web.json_response(await application.hardware.set_requested(body["enabled"]))
        except (RuntimeError, OSError, sqlite3.Error) as exc:
            return web.json_response({"error": str(exc)}, status=503)

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
        return web.json_response(application.request_plan("manual", restart=True), status=202)

    async def decisions(request: web.Request) -> web.Response:
        return web.json_response(application.store.decisions())

    async def decision(request: web.Request) -> web.Response:
        value = application.store.decision(request.match_info["id"])
        if value is None:
            raise web.HTTPNotFound()
        headers = {"Cache-Control": "no-store"}
        if request.query.get("download") == "1":
            headers["Content-Disposition"] = 'attachment; filename="energymanager-decision.json"'
        return web.json_response(value, headers=headers)

    async def events(request: web.Request) -> web.Response:
        return web.json_response(application.store.events())

    async def ev_incidents(request: web.Request) -> web.Response:
        return web.json_response(application.store.ev_incidents(), headers={"Cache-Control": "no-store"})

    async def ev_report(request: web.Request) -> web.Response:
        incident = application.store.ev_incident(request.match_info["id"])
        if incident is None:
            raise web.HTTPNotFound()
        try:
            async with archive_readers:
                report = await asyncio.to_thread(incident_report, application.store.path, incident, application.now())
        except (TimeoutError, sqlite3.Error) as exc:
            return web.json_response({"error": str(exc)}, status=503)
        return web.json_response(report, headers={"Cache-Control": "no-store"})

    async def ev_acknowledge(request: web.Request) -> web.Response:
        if application.ev_faults is None:
            raise ValueError("EV incident recovery is not configured")
        application.ev_faults.acknowledge(request.match_info["id"])
        return web.json_response({"acknowledged": True})

    async def profiles(request: web.Request) -> web.Response:
        library = application.appliance_profiles
        action = request.match_info.get("action")
        if request.method == "GET":
            result = library.library()
        else:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("A JSON object is required")
            if action == "configure":
                result = library.configure(body)
            elif action == "arm":
                result = library.arm(body)
            else:
                raise web.HTTPNotFound()
        return web.json_response(result, headers={"Cache-Control": "no-store"})

    async def recording(request: web.Request) -> web.Response:
        library = application.appliance_profiles
        identity = request.match_info["id"]
        if request.method == "GET":
            result = library.detail(identity)
        else:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("A JSON object is required")
            action = request.match_info["action"]
            if action == "finish":
                result = library.finish(identity)
            elif action == "preview":
                result = library.preview(identity, body)
            elif action == "accept":
                result = {**library.accept(identity, body), "library_revision": library.settings["revision"]}
            elif action == "select":
                library.select(identity, body)
                result = {"selected": True, "library_revision": library.settings["revision"]}
            elif action == "discard":
                library.discard(identity)
                result = {"discarded": True}
            else:
                raise web.HTTPNotFound()
        return web.json_response(result, headers={"Cache-Control": "no-store"})

    async def asset(request: web.Request) -> web.Response:
        if "version" in request.match_info and request.match_info["version"] != __version__:
            raise web.HTTPConflict(text="EnergyManager was updated. Reload the dashboard.")
        name = request.match_info.get("name", "index.html")
        if name not in ("index.html", "app.js", "settings.js", "display.js", "date-time.js",
                        "datetime-picker.js", "ev-schedule.js", "style.css", "ha-card.js",
                        "application-view.js", "view.html", "native-dashboard.js", "native-dashboard.css",
                        "native-live.js", "graph-history.js", "graph-cursor.js", "dashboard-client.js", "planning-activity.js",
                        "text-selection.js", "ev-status.js", "session-details.js", "appliance-profiles.js"):
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
            web.get("/api/profiles", profiles),
            web.post("/api/profiles/{action}", profiles),
            web.get("/api/profile-recordings/{id}", recording),
            web.post("/api/profile-recordings/{id}/{action}", recording),
            web.get("/api/state", state),
            web.get("/api/daily-energy", energy),
            web.get("/api/history", history),
            web.get("/api/dashboard", dashboard),
            web.post("/api/calendars/sync", sync_calendars),
            web.post("/api/journeys/refresh", journeys),
            web.post("/api/journeys", journeys),
            web.post("/api/journeys/{id}/reset", journeys),
            web.post("/api/journeys/{id}", journeys),
            web.delete("/api/journeys/{id}", journeys),
            web.post("/api/control", control),
            web.get("/api/settings", settings),
            web.post("/api/settings", settings),
            web.get("/api/settings/entities", entities),
            web.post("/api/goals", goals),
            web.delete("/api/goals/{id}", delete),
            web.post("/api/goals/{id}/approval", approve),
            web.post("/api/replan", replan),
            web.get("/api/decisions", decisions),
            web.get("/api/decisions/{id}", decision),
            web.get("/api/events", events),
            web.get("/api/ev-incidents", ev_incidents),
            web.get("/api/ev-incidents/{id}", ev_report),
            web.post("/api/ev-incidents/{id}/acknowledge", ev_acknowledge),
            web.get("/", asset),
            web.get("/frontend/{version}/{name}", asset),
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
