"""Same-origin standalone/HA-ingress API, including the explicit hardware control switch."""

from __future__ import annotations

import asyncio
import sqlite3
from importlib.resources import files
from typing import Any
from urllib.parse import urlsplit

import aiohttp
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
from .google_calendar import CalendarError
from .diagnostics import Diagnostics


def create_web(application: Application, *, configuration: ConfigurationFile | None = None) -> web.Application:
    if configuration:
        application.hardware = HardwareControl(application, configuration)
        if not application.demo and not application.configuration_error:
            application.journeys = Journeys(application, configuration.routing_settings())
            application.calendars = CalendarSync(application, configuration.started_values.get("calendars"))
    @web.middleware
    async def boundary(request: web.Request, handler: Any) -> web.StreamResponse:
        # These two exact endpoints are the only proxy-exposed exceptions. OAuth
        # validates one-time state; push validates its channel/resource/token tuple.
        if request.path == "/api/ev/calendar/push" and request.method == "POST":
            sync = application.trips.sync
            if sync is None or not sync.webhook(dict(request.headers)):
                raise web.HTTPForbidden()
            return web.Response(status=204)
        if request.path == "/api/ev/calendar/callback" and request.method == "GET":
            oauth = application.trips.oauth
            if oauth is None:
                raise web.HTTPServiceUnavailable()
            try:
                await oauth.callback(request.query.get("state", ""), request.query.get("code", ""))
            except (ValueError, CalendarError, aiohttp.ClientError, TimeoutError):
                return web.Response(text="Authorization failed or expired. Return to EnergyManager and try again.", status=400)
            return web.Response(text="Calendar authorized. Return to EnergyManager to select your calendars.")
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
        except CalendarError as exc:
            return web.json_response({"error": str(exc)}, status=503)

    app = web.Application(middlewares=[boundary], client_max_size=64 * 1024)
    archive_readers = asyncio.Semaphore(2)
    diagnostics = Diagnostics(application.store.path, application.policy.timezone)
    diagnostics_cleanup: asyncio.Task[None] | None = None

    async def diagnostics_status(request: web.Request) -> web.Response:
        return web.json_response(diagnostics.status(), headers={"Cache-Control": "no-store"})

    async def diagnostics_start(request: web.Request) -> web.Response:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("A JSON object is required")
        return web.json_response(diagnostics.start(request.match_info["kind"], body), headers={"Cache-Control": "no-store"})

    async def diagnostics_action(request: web.Request) -> web.Response:
        result = await asyncio.to_thread(diagnostics.action, request.match_info["id"], request.match_info["action"])
        return web.json_response(result, headers={"Cache-Control": "no-store"})

    async def diagnostics_download(request: web.Request) -> web.StreamResponse:
        identity, member = request.match_info["id"], request.match_info["member"]
        path = diagnostics.acquire(identity, member)
        response = web.StreamResponse(headers={
            "Cache-Control": "no-store", "Content-Type": "application/zip" if member == "dataset" else "application/json",
            "Content-Disposition": f'attachment; filename="energymanager-{member}.{ "zip" if member == "dataset" else "json"}"',
            "X-Content-Type-Options": "nosniff"})
        try:
            async with archive_readers:
                stream = await asyncio.to_thread(path.open, 'rb')
                try:
                    response.content_length = await asyncio.to_thread(lambda: path.stat().st_size)
                    await response.prepare(request)
                    while chunk := await asyncio.to_thread(stream.read, 256 * 1024):
                        await response.write(chunk)
                    await response.write_eof()
                finally:
                    await asyncio.to_thread(stream.close)
        finally:
            diagnostics.release(identity)
        return response

    async def trip_calendar(request: web.Request) -> web.Response:
        owner = application.trips
        if request.method == "GET":
            start, end = instant(request.query["start"]), instant(request.query["end"])
            owner.expand(start, end)
            owner.wake.set()
            context: list[dict[str, Any]] = []
            if owner.sync and owner.sync.state["connected"]:
                try:
                    for calendar in owner.data["selected"]:
                        if calendar == owner.trips.state["binding"]:
                            continue
                        events = await owner.sync.client.window(calendar, start.isoformat(), end.isoformat())
                        context.extend({"id": calendar + ":" + item["id"], "title": item.get("summary", "Appointment"),
                                        "start": item["start"].get("dateTime", item["start"].get("date")),
                                        "end": item["end"].get("dateTime", item["end"].get("date")), "editable": False}
                                       for item in events if item.get("status") != "cancelled")
                    owner.data["context"] = {"start": start.isoformat(), "end": end.isoformat(), "events": context}
                    owner.save()
                except (CalendarError, aiohttp.ClientError, TimeoutError):
                    owner.sync.status = "unavailable"
                    cached = owner.data.get("context", {})
                    context = cached.get("events", []) if isinstance(cached, dict) else []
            return web.json_response({**owner.status(), "context": context}, headers={"Cache-Control": "no-store"})
        data = await request.json()
        if not isinstance(data,dict):
            raise ValueError("Use a JSON object for calendar actions")
        action = data.get("action")
        if action == "setup":
            if not owner.oauth:
                raise ValueError("Calendar service is starting")
            owner.oauth.configure(data)
        elif action == "authorize":
            if not owner.oauth:
                raise ValueError("Calendar service is starting")
            return web.json_response({"url": owner.oauth.begin()})
        elif action == "calendars":
            if not owner.sync:
                raise ValueError("Calendar service is starting")
            calendars = await owner.sync.client.calendars()
            return web.json_response({"calendars": [{key: item.get(key) for key in ("id", "summary", "accessRole")}
                                                     for item in calendars]})
        elif action == "connect":
            if not owner.sync:
                raise ValueError("Calendar service is starting")
            calendars = await owner.sync.client.calendars()
            if not any(item["id"] == data["calendar"] and item["accessRole"] in ("owner", "writer") for item in calendars):
                raise ValueError("Select a writable dedicated EV calendar")
            selected = data.get("selected", [])
            if (not isinstance(selected, list) or len(selected) > 20 or
                    any(not any(item["id"] == key for item in calendars) for key in selected)):
                raise ValueError("Choose visible Google calendars")
            owner.data["selected"] = selected
            owner.sync.connect(data["calendar"])
            owner.enable()
        elif action == "disconnect":
            if owner.sync:
                owner.sync.disconnect()
        elif action == "sync":
            owner.force_routes = True
            owner.wake.set()
        elif action == "match":
            owner.match_action(data["id"], data["operation"])
        elif action == "dismiss":
            owner.trips.state["notices"][data["key"]]["dismissed"] = True
            owner.trips.save()
        else:
            raise ValueError("Unknown trip calendar action")
        return web.json_response(owner.status())

    async def drives(request: web.Request) -> web.Response:
        identity = request.match_info.get("id")
        data = await request.json()
        if not isinstance(data,dict):
            raise ValueError("Use a JSON object for a drive")
        owner = application.trips
        if request.method == "DELETE":
            owner.delete(identity or "", data.get("scope", "occurrence"))
            return web.json_response({"deleted": True})
        if request.path.endswith("/reverse"):
            result = owner.reverse(identity or "", bool(data.get("before")), bool(data.get("recurring")))
        else:
            result = owner.upsert(data, identity)
        return web.json_response(result, status=201)

    async def places(request: web.Request) -> web.Response:
        data = await request.json()
        if not isinstance(data,dict):
            raise ValueError("Use a JSON object for place search")
        client = application.trips.places()
        try:
            result = (await client.select(data["id"], data["token"]) if "id" in data
                      else await client.search(data["text"], data["token"]))
        except (RuntimeError, aiohttp.ClientError, TimeoutError) as exc:
            return web.json_response({"error": str(exc) if isinstance(exc, RuntimeError) else "Place search unavailable"}, status=503)
        return web.json_response({"result": result})

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
                routing_before = configuration.routing_settings()
                result = await asyncio.to_thread(configuration.save, body["revision"], body["values"])
                if application.journeys:
                    application.journeys.apply_settings(configuration.routing_settings())
                if routing_before != configuration.routing_settings():
                    application.trips.force_routes = True
                    application.trips.wake.set()
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
                                  "goals", "sessions", "summary", "reasons", "stages", "input_digest", "forecast_at")
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

    async def manual_soc(request: web.Request) -> web.Response:
        return web.json_response(application.manual_soc(await request.json()))

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
            elif action in ("program-create", "program-rename"):
                result = library.save_program(body, create=action == "program-create")
            elif action == "bosch-configure":
                result = library.configure_bosch(body)
            elif action in ("run-preview","run-ready","run-cancel","run-edit","run-choose"):
                result = await application.appliance_runs.action(action[4:],body)
            elif action == "bosch-command":
                result = await library.bosch.command(body)
            else:
                raise web.HTTPNotFound()
        return web.json_response(result, headers={"Cache-Control": "no-store"})

    async def averaged_profile(request: web.Request) -> web.Response:
        try:
            result = await application.appliance_profiles.profile_detail(
                request.match_info["machine"], request.match_info["program"])
        except (TimeoutError, sqlite3.OperationalError) as exc:
            return web.json_response({"error": f"Profile unavailable: {exc}"}, status=503)
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
            elif action == "revise":
                result = {**library.revise(identity, body), "library_revision": library.settings["revision"]}
            elif action == "select":
                library.select(identity, body)
                result = {"selected": True, "library_revision": library.settings["revision"]}
            elif action == "delete":
                library.delete(identity, body)
                result = {"deleted": True, "library_revision": library.settings["revision"]}
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
        if name not in ("diagnostics.js", "trip-calendar.js", "fullcalendar.global.min.js", "fullcalendar-luxon.global.min.js", "luxon.min.js",
                        "index.html", "app.js", "settings.js", "display.js", "date-time.js",
                        "datetime-picker.js", "ev-schedule.js", "style.css", "ha-card.js",
                        "application-view.js", "peak-display.js", "ha-history.js", "view.html", "native-dashboard.js", "native-dashboard.css",
                        "native-live.js", "graph-history.js", "graph-cursor.js", "dashboard-client.js", "planning-activity.js",
                        "text-selection.js", "ev-status.js", "manual-soc.js", "session-details.js", "appliance-profiles.js", "profile-chart.js", "appliance-deadline.js"):
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
            web.post("/api/ev/calendar/push", trip_calendar),
            web.get("/api/ev/calendar/callback", trip_calendar),
            web.get("/api/ev/calendar", trip_calendar),
            web.post("/api/ev/calendar", trip_calendar),
            web.post("/api/ev/drives", drives),
            web.post("/api/ev/drives/{id}", drives),
            web.delete("/api/ev/drives/{id}", drives),
            web.post("/api/ev/drives/{id}/reverse", drives),
            web.post("/api/ev/places", places),
            web.get("/api/profiles", profiles),
            web.get("/api/profiles/{machine}/{program}", averaged_profile),
            web.post("/api/profiles/{action}", profiles),
            web.get("/api/profile-recordings/{id}", recording),
            web.post("/api/profile-recordings/{id}/{action}", recording),
            web.get("/api/diagnostics", diagnostics_status),
            web.post("/api/diagnostics/{kind}", diagnostics_start),
            web.post("/api/diagnostics/{id}/{action}", diagnostics_action),
            web.get("/api/diagnostics/{id}/download/{member}", diagnostics_download),
            web.get("/api/state", state),
            web.post("/api/ev/manual-soc", manual_soc),
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

    async def clean_diagnostics() -> None:
        while True:
            await asyncio.sleep(30)
            await asyncio.to_thread(diagnostics.expire)

    async def start(app: web.Application) -> None:
        nonlocal diagnostics_cleanup
        await asyncio.to_thread(diagnostics.initialize)
        diagnostics_cleanup = asyncio.create_task(clean_diagnostics())
        await application.start()

    async def stop(app: web.Application) -> None:
        if diagnostics_cleanup:
            diagnostics_cleanup.cancel()
            await asyncio.gather(diagnostics_cleanup, return_exceptions=True)
        await diagnostics.close()
        await application.close()
        application.store.close()

    app.on_startup.append(start)
    app.on_cleanup.append(stop)
    return app
