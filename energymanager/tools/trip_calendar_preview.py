"""Offline-only trip UI with in-memory Calendar, Places, Routes and HA fixtures."""

from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from aiohttp import web
from aiohttp.test_utils import TestServer

from energymanager.adapters import HomeAssistantAdapter
from energymanager.domain import instant
from energymanager.google_calendar import GoogleCalendarClient
from energymanager.forecasts import demo_snapshot
from energymanager.routing import RouteLeg
from energymanager.service import Application
from energymanager.store import Store
from energymanager.trip_places import TripPlaces
from energymanager.trip_recurrence import occurrences, parse_google_rule
from energymanager.web import create_web


class SyntheticProviders:
    def __init__(self) -> None:
        self.events: dict[str, dict[str, Any]] = {}
        self.revision = 0
        self.calls: list[tuple[str, str]] = []
        self.failed = False

    def stamp(self, event: dict[str, Any]) -> dict[str, Any]:
        self.revision += 1
        return {
            **deepcopy(event),
            "etag": f'"synthetic-{self.revision}"',
            "updated": datetime.now(UTC).isoformat(),
        }

    def instances(self, event: dict[str, Any], start: datetime, end: datetime) -> list[dict[str, Any]]:
        zone = event["start"].get("timeZone", "UTC")
        master = {
            "id": event["id"],
            "start": event["start"]["dateTime"],
            "end": event["end"]["dateTime"],
            "timezone": zone,
            "rule": parse_google_rule(event["recurrence"], zone, event["start"]["dateTime"]),
            "template": {},
        }
        result = []
        for item in occurrences(master, start, end):
            identity = event["id"] + "_" + item["occurrence"].replace("-", "")
            result.append(
                self.events.get(identity)
                or {
                    **deepcopy(event),
                    "id": identity,
                    "recurringEventId": event["id"],
                    "originalStartTime": {"dateTime": item["start"]},
                    "start": {"dateTime": item["start"], "timeZone": zone},
                    "end": {"dateTime": item["end"], "timeZone": zone},
                }
            )
        return result

    async def calendar(self, request: web.Request) -> web.Response:
        self.calls.append((request.method, request.path))
        if self.failed:
            return web.json_response({"error": "Synthetic provider outage"}, status=503)
        if request.path.endswith("/calendarList"):
            return web.json_response(
                {
                    "items": [
                        {"id": "synthetic-ev", "summary": "SYNTHETIC EV drives", "accessRole": "owner"},
                        {"id": "synthetic-work", "summary": "SYNTHETIC appointments", "accessRole": "reader"},
                    ]
                }
            )
        if request.path.endswith("/watch"):
            channel = await request.json()
            return web.json_response(
                {
                    "id": channel["id"],
                    "resourceId": "synthetic-resource",
                    "expiration": str(channel["expiration"]),
                }
            )
        if request.path.endswith("/stop"):
            return web.Response(status=204)
        tail = request.match_info.get("tail", "").strip("/")
        if tail.endswith("/instances"):
            identity = tail.split("/")[0]
            start = instant(request.query["originalStart"])
            return web.json_response(
                {"items": self.instances(self.events[identity], start, start + timedelta(days=1))}
            )
        if request.method == "GET" and not tail:
            if request.match_info.get("calendar") == "synthetic-work":
                start = instant(request.query.get("timeMin", datetime.now(UTC).isoformat())) + timedelta(
                    days=1, hours=10
                )
                return web.json_response(
                    {
                        "items": [
                            {
                                "id": "appointment",
                                "summary": "SYNTHETIC read-only appointment",
                                "start": {"dateTime": start.isoformat()},
                                "end": {"dateTime": (start + timedelta(hours=1)).isoformat()},
                            }
                        ],
                        "nextSyncToken": "synthetic-token",
                    }
                )
            return web.json_response(
                {"items": list(self.events.values()), "nextSyncToken": "synthetic-token"}
            )
        if request.method == "GET":
            if tail not in self.events:
                return web.Response(status=404)
            return web.json_response(self.events[tail])
        if request.method == "DELETE":
            old = self.events.get(tail)
            if old is None:
                return web.Response(status=404)
            if request.headers.get("If-Match") != old["etag"]:
                return web.Response(status=412)
            self.events[tail] = self.stamp({**old, "status": "cancelled"})
            return web.Response(status=204)
        event = await request.json()
        identity = tail or event["id"]
        old = self.events.get(identity)
        if old is None and "_" in identity:
            master_id, day = identity.split("_", 1)
            if master_id in self.events:
                at = datetime.strptime(day, "%Y%m%d").replace(tzinfo=UTC)
                old = next(
                    (
                        item
                        for item in self.instances(
                            self.events[master_id], at - timedelta(days=1), at + timedelta(days=2)
                        )
                        if item["id"] == identity
                    ),
                    None,
                )
        if request.method == "POST" and old:
            return web.Response(status=409)
        if old and request.headers.get("If-Match") != old["etag"]:
            return web.Response(status=412)
        merged = {**(old or {}), **event}
        if "extendedProperties" in merged:
            private = merged["extendedProperties"].get("private", {})
            merged["extendedProperties"]["private"] = {
                key: value for key, value in private.items() if value is not None
            }
        self.events[identity] = self.stamp(merged)
        return web.json_response(self.events[identity])

    async def places(self, request: web.Request) -> web.Response:
        if request.method == "POST":
            return web.json_response(
                {
                    "suggestions": [
                        {
                            "placePrediction": {
                                "placeId": "synthetic-antwerp",
                                "text": {"text": "SYNTHETIC Antwerp, Belgium"},
                            }
                        }
                    ]
                }
            )
        return web.json_response(
            {
                "id": "synthetic-antwerp",
                "displayName": {"text": "SYNTHETIC Antwerp"},
                "formattedAddress": "SYNTHETIC Antwerp, Belgium",
                "addressComponents": [{"longText": "Antwerp", "types": ["locality"]}],
            }
        )

    async def home(self, identity: str) -> dict[str, Any]:
        assert identity == "zone.home"
        return {"attributes": {"latitude": 51.2, "longitude": 4.4}}

    async def leg(self, origin: Any, destination: Any, at: datetime, *, traffic_aware: bool) -> RouteLeg:
        return RouteLeg(42, 2700)

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_route("*", "/calendar/v3/users/me/calendarList", self.calendar)
        app.router.add_route("*", "/calendar/v3/channels/stop", self.calendar)
        app.router.add_route("*", "/calendar/v3/calendars/{calendar}/events", self.calendar)
        app.router.add_route("*", "/calendar/v3/calendars/{calendar}/events/{tail:.*}", self.calendar)
        app.router.add_post("/places/v1/places:autocomplete", self.places)
        app.router.add_get("/places/v1/places/{id}", self.places)
        return app


async def run(port: int) -> None:
    fake = SyntheticProviders()
    async with TestServer(fake.app()) as endpoint:
        with TemporaryDirectory(prefix="energymanager-synthetic-trips-") as temporary:
            application = Application(
                Store(Path(temporary) / "synthetic.sqlite"), snapshot=demo_snapshot(start=datetime.now(UTC))
            )
            # UI fixture only. Full-horizon solver verification runs separately;
            # never compete with its serial timing checks or imply a checked plan.
            application.request_plan = lambda reason, **kwargs: {"requested": False}

            async def ui_only_planning() -> None:
                await asyncio.Event().wait()

            application.planning_loop = ui_only_planning
            application.goals = ()
            application.ha = HomeAssistantAdapter("http://127.0.0.1", {})
            application.ha.entity_state = fake.home
            owner = application.trips
            owner.router = fake
            server = create_web(application)

            async def seed(app: web.Application) -> None:
                owner.oauth.data["webhook_uri"] = "https://synthetic.invalid/api/ev/calendar/push"
                owner.sync.client = GoogleCalendarClient(
                    owner.session, "synthetic-token", str(endpoint.make_url("/calendar/v3"))
                )
                owner.sync.connect("synthetic-ev")
                owner.data["selected"] = ["synthetic-work"]
                owner.places = lambda: TripPlaces(
                    owner.session, "synthetic-key", str(endpoint.make_url("/places/v1"))
                )
                tomorrow = application.now() + timedelta(days=1)
                owner.upsert(
                    {
                        "mode": "routed",
                        "origin": "Home",
                        "destination": "SYNTHETIC Antwerp, Belgium",
                        "destination_city": "Antwerp",
                        "timing": "fixed",
                        "manual_km": None,
                        "start": tomorrow.replace(hour=9, minute=0, second=0, microsecond=0).isoformat(),
                        "end": tomorrow.replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
                    }
                )
                owner.sources(
                    "SYNTHETIC referee",
                    [
                        {
                            "key": "synthetic-match",
                            "title": "SYNTHETIC referee match",
                            "start": (tomorrow + timedelta(days=1))
                            .replace(hour=12, minute=0, second=0, microsecond=0)
                            .isoformat(),
                            "location": "SYNTHETIC stadium",
                        }
                    ],
                    True,
                )
                await owner.refresh_routes()
                print(
                    f"SYNTHETIC trip calendar: http://127.0.0.1:{port} — all providers and storage are fake/local",
                    flush=True,
                )

            server.on_startup.append(seed)
            runner = web.AppRunner(server)
            await runner.setup()
            await web.TCPSite(runner, "127.0.0.1", port).start()
            try:
                await asyncio.Event().wait()
            finally:
                await runner.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8104)
    asyncio.run(run(parser.parse_args().port))
