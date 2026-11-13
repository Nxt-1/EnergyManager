"""Local-drive application owner, route projection, referee generation and sync lifecycle."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import aiohttp

from .calendar_oauth import AuthorizedCalendar, CalendarOAuth
from .domain import Goal, instant
from .google_calendar import CalendarError
from .routing import GoogleRoutesClient, Location, RouteLeg, RoutingUnavailable, home_coordinates
from .trip_events import validate_drive
from .trip_places import TripPlaces
from .trip_recurrence import google_rule, occurrences, weekly_rule
from .trip_store import TripStore
from .trip_sync import TripSync

if TYPE_CHECKING:
    from .service import Application


class TripCalendar:
    def __init__(self, app: Application) -> None:
        self.app = app
        self.trips = TripStore(app.store)
        self.data = app.store.get(
            "trip_calendar_v1",
            {"enabled": False, "series": {}, "matches": {}, "resolved": {}, "context": [], "selected": []},
        )
        self.session: aiohttp.ClientSession | None = None
        self.oauth: CalendarOAuth | None = None
        self.sync: TripSync | None = None
        self.task: asyncio.Task[None] | None = None
        self.wake = asyncio.Event()
        self.lock = asyncio.Lock()
        self.router: GoogleRoutesClient | None = None
        self.last_sync: datetime | None = None
        self.force_routes = False

    def save(self) -> None:
        self.app.store.put("trip_calendar_v1", self.data)

    def start(self) -> None:
        self.session = aiohttp.ClientSession()
        self.oauth = CalendarOAuth(self.app.store, self.session)
        self.sync = TripSync(self.trips, AuthorizedCalendar(self.oauth))
        # One wakeup source handles both verified push notices and local mutations.
        self.sync.wake = self.wake
        self.task = asyncio.create_task(self.loop())
        self.wake.set()

    async def close(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.session:
            await self.session.close()

    def enable(self) -> None:
        self.data["enabled"] = True
        self.save()
        if self.app.calendars:
            self.app.calendars.reconcile()
        self.wake.set()

    def upsert(self, data: dict[str, Any], identity: str | None = None) -> dict[str, Any]:
        original = self.trips.state["trips"].get(identity) if identity else None
        if identity and original is None:
            raise ValueError("Unknown drive")
        expected = data.get("revision")
        if original and expected != original["revision"]:
            raise ValueError("This drive changed; reopen it before saving")
        mutable = {
            "mode",
            "origin",
            "destination",
            "origin_city",
            "destination_city",
            "timing",
            "start",
            "end",
            "manual_km",
            "rule",
            "scope",
            "revision",
        }
        data = {**(original or {}), **{key: value for key, value in data.items() if key in mutable}}
        data["title"] = (
            f"Drive · {data.get('manual_km')} km"
            if data.get("mode") == "distance_only"
            else "Drive to " + (data.get("destination_city") or data.get("destination") or "destination")
        )
        validate_drive(data)
        if data["mode"] == "routed" and data["origin"] == data["destination"] and data["timing"] != "fixed":
            raise ValueError("For a same-endpoint round trip, supply fixed start and end times")
        if data.get("rule") and (not original or data.get("scope") == "following"):
            rule = weekly_rule(data["rule"])
            series_id = data.get("series") or uuid4().hex
            trial = {
                "id": series_id,
                "start": data["start"],
                "end": data["end"],
                "timezone": self.app.policy.timezone,
                "rule": rule,
                "template": {},
            }
            candidates = occurrences(
                trial, instant(data["start"]), instant(data["start"]) + timedelta(weeks=rule["weeks"] + 1)
            )
            if not candidates:
                raise ValueError("No recurrence occurs before the selected end date")
            data.update(start=candidates[0]["start"], end=candidates[0]["end"])
            if original and data.get("scope") == "following":
                if instant(original["start"]) <= self.app.now():
                    raise ValueError("Select a future occurrence; past drives remain unchanged")
                master = self.data["series"][original["series"]]
                master["cutoff"] = original["occurrence"]
                self.publish_master(master)
                for key, trip in list(self.trips.state["trips"].items()):
                    if (
                        trip.get("series") == original["series"]
                        and trip["occurrence"] >= original["occurrence"]
                        and instant(trip["start"]) > self.app.now()
                    ):
                        self.trips.delete(key, self.app.now())
                        self.trips.acknowledge(key, self.trips.state["trips"][key]["revision"])
                series_id = uuid4().hex
            master = {
                "id": series_id,
                "start": data["start"],
                "end": data["end"],
                "timezone": self.app.policy.timezone,
                "rule": rule,
                "template": {
                    key: value
                    for key, value in data.items()
                    if key not in ("id", "series", "occurrence", "rule", "scope", "revision")
                },
            }
            validate_drive(data)
            self.data["series"][series_id] = master
            self.publish_master(master)
            self.save()
            self.expand(self.app.now(), self.app.now() + timedelta(days=7))
            self.enable()
            return master
        data.pop("rule", None)
        data.pop("scope", None)
        if original and original.get("series"):
            data["exception"] = True
        result = self.trips.edit(data, self.app.now(), identity=identity)
        self.enable()
        return result

    def delete(self, identity: str, scope: str = "occurrence") -> None:
        original = self.trips.state["trips"][identity]
        if scope == "following" and original.get("series"):
            if instant(original["start"]) <= self.app.now():
                raise ValueError("Select a future occurrence; past drives remain unchanged")
            self.data["series"][original["series"]]["cutoff"] = original["occurrence"]
            self.publish_master(self.data["series"][original["series"]])
            for key, trip in list(self.trips.state["trips"].items()):
                if (
                    trip.get("series") == original["series"]
                    and trip["occurrence"] >= original["occurrence"]
                    and instant(trip["start"]) > self.app.now()
                ):
                    self.trips.delete(key, self.app.now())
                    self.trips.acknowledge(key, self.trips.state["trips"][key]["revision"])
        else:
            self.trips.delete(identity, self.app.now())
        self.save()
        if self.app.calendars:
            self.app.calendars.reconcile()
        self.project()
        self.wake.set()

    def reverse(self, identity: str, before: bool, recurring: bool) -> dict[str, Any]:
        original = self.trips.state["trips"][identity]
        duration = instant(original["end"]) - instant(original["start"])
        start = instant(original["start"]) - duration if before else instant(original["end"])
        data = {
            key: value
            for key, value in original.items()
            if key not in ("id", "revision", "series", "occurrence", "source", "deleted", "source_change")
        }
        data.update(
            origin=original.get("destination"),
            destination=original.get("origin"),
            destination_city=original.get("origin_city", ""),
            start=start.isoformat(),
            end=(start + duration).isoformat(),
            timing="fixed",
        )
        if recurring and original.get("series"):
            data["rule"] = deepcopy(self.data["series"][original["series"]]["rule"])
            zone = ZoneInfo(self.app.policy.timezone)
            shift = (start.astimezone(zone).date() - instant(original["start"]).astimezone(zone).date()).days
            data["rule"]["weekdays"] = [(day + shift) % 7 for day in data["rule"]["weekdays"]]
            if shift % 7:
                data["rule"]["week_start"] = (data["rule"].get("week_start", 0) + shift) % 7
            if data["rule"].get("until"):
                data["rule"]["until"] = (
                    datetime.fromisoformat(data["rule"]["until"]).date() + timedelta(days=shift)
                ).isoformat()
        return self.upsert(data)

    def expand(self, start: datetime, end: datetime) -> None:
        if end - start > timedelta(days=370) or end <= start:
            raise ValueError("Request at most one year of calendar occurrences")
        for master in self.data["series"].values():
            for item in occurrences(master, start, end):
                if item["id"] not in self.trips.state["trips"]:
                    self.trips.edit(item, self.app.now(), identity=item["id"], actor="automatic")
                    # Native RRULE represents untouched occurrences remotely. Only
                    # actual edits and route-derived exceptions need an instance write.
                    self.trips.acknowledge(item["id"], self.trips.state["trips"][item["id"]]["revision"])

    def publish_master(self, master: dict[str, Any]) -> None:
        if (
            master.get("cutoff")
            and master["cutoff"]
            <= instant(master["start"]).astimezone(ZoneInfo(master["timezone"])).date().isoformat()
        ):
            self.trips.delete(master["id"], self.app.now())
            master["master_revision"] = self.trips.state["trips"][master["id"]]["revision"]
            return
        trip = self.trips.edit(
            {
                **master["template"],
                "series_master": True,
                "rule": master["rule"],
                "timezone": master["timezone"],
                "recurrence": google_rule(master),
                "start": master["start"],
                "end": master["end"],
            },
            self.app.now(),
            identity=master["id"],
        )
        master["master_revision"] = trip["revision"]

    def adopt_series(self) -> None:
        for key, trip in list(self.trips.state["trips"].items()):
            if not trip.get("series_master"):
                continue
            old = self.data["series"].get(key)
            if old and old.get("master_revision") == trip["revision"]:
                continue
            if trip["deleted"]:
                if old:
                    old["cutoff"] = self.app.now().astimezone(ZoneInfo(old["timezone"])).date().isoformat()
                    old["master_revision"] = trip["revision"]
                for identity, child in list(self.trips.state["trips"].items()):
                    if child.get("series") == key and instant(child["start"]) > self.app.now():
                        self.trips.delete(identity, self.app.now())
                continue
            master = {
                "id": key,
                "start": trip["start"],
                "end": trip["end"],
                "rule": trip["rule"],
                "timezone": trip["timezone"],
                "master_revision": trip["revision"],
                "template": {
                    name: value
                    for name, value in trip.items()
                    if name not in ("id", "revision", "series_master", "recurrence", "rule", "timezone")
                },
            }
            self.data["series"][key] = master
            for identity, child in list(self.trips.state["trips"].items()):
                if child.get("series") != key or instant(child["start"]) <= self.app.now():
                    continue
                if child.get("exception") and instant(child["edited_at"]) > instant(trip["edited_at"]):
                    continue
                day = datetime.fromisoformat(child["occurrence"]).replace(tzinfo=ZoneInfo(master["timezone"]))
                expected = occurrences(master, day, day + timedelta(days=1))
                if not expected:
                    self.trips.delete(identity, self.app.now())
                elif not child["deleted"]:
                    self.trips.edit(expected[0], instant(trip["edited_at"]), identity=identity)
                self.trips.acknowledge(identity, self.trips.state["trips"][identity]["revision"])
            # Historical occurrences retain their recorded wall date and contents.
            for child in occurrences(master, self.app.now(), self.app.now() + timedelta(days=7)):
                previous = self.trips.state["trips"].get(child["id"])
                if previous is None:
                    self.trips.edit(child, self.app.now(), identity=child["id"], actor="automatic")
                    self.trips.acknowledge(child["id"], self.trips.state["trips"][child["id"]]["revision"])
            self.save()

    def sources(self, source: str, events: list[dict[str, Any]], complete: bool) -> None:
        known = set()
        changed = False
        for event in events:
            key = sha256(f"{source}:{event['key']}".encode()).hexdigest()[:32]
            known.add(key)
            previous = self.data["matches"].get(key)
            fingerprint = sha256(f"{event['start']}:{event['location']}".encode()).hexdigest()
            if previous is None or previous["fingerprint"] != fingerprint:
                changed = True
                self.data["matches"][key] = {
                    "id": key,
                    "source": source,
                    "event": event,
                    "fingerprint": fingerprint,
                    "regenerate": True,
                    "changed": previous is not None,
                    "missing": False,
                    "removed": False,
                }
            elif previous.get("missing"):
                previous["missing"] = False
                changed = True
            elif previous.get("event") != event:
                previous["event"] = event
                changed = True
        if complete:
            for key, item in self.data["matches"].items():
                if (
                    item["source"] == source
                    and key not in known
                    and not item.get("removed")
                    and instant(item["event"]["start"]) + timedelta(hours=3) > self.app.now()
                ):
                    if not item.get("missing"):
                        item["missing"] = True
                        changed = True
        if changed:
            self.save()
            self.wake.set()

    def match_action(self, identity: str, action: str) -> None:
        match = self.data["matches"][identity]
        if action == "regenerate":
            match.update(regenerate=True, removed=False)
            match.pop("retry_at", None)
            match.pop("failures", None)
        elif action == "remove":
            if not match.get("missing"):
                raise ValueError("Match is still present; delete individual drives instead")
            for leg in ("out", "back"):
                key = self.leg_id(identity, leg)
                if key in self.trips.state["trips"]:
                    self.trips.delete(key, self.app.now())
            match["removed"] = True
        elif action == "retain":
            match["removed"] = True  # Dismiss confirmation, retain local drives.
        else:
            raise ValueError("Unknown match action")
        self.save()
        self.project()
        self.wake.set()

    @staticmethod
    def leg_id(match: str, leg: str) -> str:
        return sha256(f"{match}:{leg}".encode()).hexdigest()[:32]

    async def leg(self, origin: str, destination: str, at: datetime, traffic: bool) -> RouteLeg:
        settings = self.app.journeys.settings if self.app.journeys else {}
        router = self.router or GoogleRoutesClient(
            settings.get("api_key", ""), allow_requests=bool(settings.get("api_key"))
        )
        left: Location = origin
        right: Location = destination
        if "Home" in (origin, destination):
            if self.app.ha is None:
                raise RoutingUnavailable("Home not available", code="home_location")
            home = home_coordinates(await self.app.ha.entity_state("zone.home"))
            if origin == "Home":
                left = home
            if destination == "Home":
                right = home
        return await router.leg(left, right, at, traffic_aware=traffic)

    async def estimate(self, drive: dict[str, Any]) -> dict[str, Any]:
        start, end = instant(drive["start"]), instant(drive["end"])
        if drive["mode"] == "distance_only":
            return {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "distance_km": drive["manual_km"],
                "duration_seconds": None,
                "origin": "Home",
                "destination": "Home",
            }
        traffic = start <= self.app.now() + timedelta(days=7)
        seed = end if drive["timing"] == "arrive" else start
        route = await self.leg(drive["origin"], drive["destination"], seed, traffic)
        if drive["timing"] == "arrive":
            budget = route.duration_seconds + (60 if traffic else 0)
            start = end - timedelta(seconds=budget)
            if start <= self.app.now():
                raise RoutingUnavailable("Required departure has passed", code="past_departure")
            if traffic:
                for _ in range(2):
                    route = await self.leg(drive["origin"], drive["destination"], start, True)
                    if route.duration_seconds <= budget:
                        break
                    budget = route.duration_seconds + 60
                    start = end - timedelta(seconds=budget)
                    if start <= self.app.now():
                        raise RoutingUnavailable("Required departure has passed", code="past_departure")
                else:
                    raise RoutingUnavailable("Arrival could not be confirmed", code="traffic_timing")
        elif drive["timing"] == "depart":
            end = start + timedelta(seconds=route.duration_seconds)
        if end <= start:
            raise RoutingUnavailable(
                "A drive needs a positive away period; enter fixed start and end", code="invalid_journey"
            )
        city = drive.get("destination_city") or ("Home" if drive["destination"] == "Home" else "")
        if not city and route.destination_place_id:
            place = await self.places().details(route.destination_place_id)
            city = place["city"] or place["label"]
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "distance_km": drive.get("manual_km")
            if drive.get("manual_km") is not None
            else route.distance_km,
            "duration_seconds": route.duration_seconds,
            "calculated_km": route.distance_km,
            "origin": drive["origin"],
            "destination": drive["destination"],
            "destination_city": city,
            "title": "Drive to " + (city or drive["destination"]),
        }

    async def generate(self, match: dict[str, Any]) -> None:
        event, key = match["event"], match["id"]
        start = instant(event["start"])
        if start + timedelta(hours=3) <= self.app.now():
            return
        outward = {
            "mode": "routed",
            "origin": "Home",
            "destination": event["location"],
            "timing": "arrive",
            "start": (start - timedelta(hours=2)).isoformat(),
            "end": (start - timedelta(hours=1)).isoformat(),
            "manual_km": None,
            "title": "Drive to " + event["location"],
            "source": key,
        }
        back = {
            **outward,
            "origin": event["location"],
            "destination": "Home",
            "timing": "depart",
            "title": "Drive to Home",
            "start": (start + timedelta(hours=2.5)).isoformat(),
            "end": (start + timedelta(hours=3.5)).isoformat(),
        }
        estimates = [await self.estimate(outward), await self.estimate(back)]
        if self.data["matches"].get(key) is not match:
            return  # Ignore route responses for a superseded source revision.
        # Both routes must be checked before replacing either last-good drive.
        for leg, drive, estimate in zip(("out", "back"), (outward, back), estimates, strict=True):
            identity = self.leg_id(key, leg)
            drive.update(
                {
                    field: estimate[field]
                    for field in ("start", "end", "title", "destination_city")
                    if field in estimate
                }
            )
            trip = self.trips.edit(
                drive, self.app.now(), identity=identity, actor="automatic", source_change=True
            )
            self.data["resolved"][identity] = {
                **estimate,
                "revision": trip["revision"],
                "checked_at": self.app.now().isoformat(),
            }
        match["regenerate"] = False
        match.pop("error", None)
        if match["changed"]:
            self.trips.notice(key, match["fingerprint"], "match_changed")
        self.save()

    async def refresh_routes(self) -> None:
        for match in list(self.data["matches"].values()):
            if match.get("regenerate") and not match.get("removed"):
                if (
                    match.get("retry_at")
                    and instant(match["retry_at"]) > self.app.now()
                    and not self.force_routes
                ):
                    continue
                try:
                    await self.generate(match)
                except (RoutingUnavailable, ValueError, aiohttp.ClientError, TimeoutError):
                    match["error"] = "Routes unavailable; previous drives retained"
                    match["failures"] = match.get("failures", 0) + 1
                    delay = min(14400, 300 * 2 ** min(6, match["failures"] - 1))
                    match["retry_at"] = (self.app.now() + timedelta(seconds=delay)).isoformat()
        for key, drive in list(self.trips.state["trips"].items()):
            old = self.data["resolved"].get(key, {})
            anchor = drive["end"] if drive["timing"] == "arrive" else drive["start"]
            underway = (
                old.get("revision") == drive["revision"]
                and old.get("start")
                and instant(old["start"]) <= self.app.now()
            )
            if (
                drive["deleted"]
                or drive.get("series_master")
                or instant(anchor) <= self.app.now()
                or underway
            ):
                continue
            if (
                not old.get("error")
                and old.get("revision") == drive["revision"]
                and (
                    instant(drive["start"]) > self.app.now() + timedelta(days=7)
                    or self.app.now() - instant(old["checked_at"]) < timedelta(hours=4)
                )
                and not self.force_routes
            ):
                continue
            revision = drive["revision"]
            if (
                old.get("attempt_revision") == revision
                and old.get("retry_at")
                and instant(old["retry_at"]) > self.app.now()
                and not self.force_routes
            ):
                continue
            try:
                estimate = await self.estimate(drive)
            except (RoutingUnavailable, ValueError, aiohttp.ClientError, TimeoutError):
                failures = old.get("failures", 0) + 1 if old.get("attempt_revision") == revision else 1
                delay = min(14400, 300 * 2 ** min(6, failures - 1))
                self.data["resolved"][key] = {
                    **old,
                    "error": "Route needs correction or Maps is unavailable",
                    "attempt_revision": revision,
                    "failures": failures,
                    "retry_at": (self.app.now() + timedelta(seconds=delay)).isoformat(),
                }
                self.trips.notice(key, revision, "invalid_endpoints")
                continue
            if self.trips.state["trips"][key]["revision"] != revision:
                continue
            changed = {
                field: estimate[field]
                for field in ("start", "end", "title", "destination_city")
                if field in estimate
                and estimate[field] != drive.get(field)
                and (field != "destination_city" or estimate[field])
            }
            if changed:
                drive.update(**changed, revision=revision + 1)
                self.trips.state["pending"][key] = drive["revision"]
                self.trips.save()
            duration = estimate["duration_seconds"]
            warning = (
                drive["timing"] == "fixed"
                and duration is not None
                and (duration - (instant(drive["end"]) - instant(drive["start"])).total_seconds() > 600)
            )
            self.data["resolved"][key] = {
                **estimate,
                "revision": drive["revision"],
                "planning_revision": (
                    old.get("planning_revision", 0) + 1
                    if any(
                        old.get(field) != estimate.get(field)
                        for field in ("start", "end", "distance_km", "destination")
                    )
                    else old.get("planning_revision", 1)
                ),
                "title": drive["title"],
                "warning": warning,
                "checked_at": self.app.now().isoformat(),
            }
            if warning:
                self.trips.notice(key, drive.get("edit_revision", revision), "duration")
        self.save()
        self.force_routes = False
        if self.app.calendars:
            self.app.calendars.reconcile()
        self.project()

    def project(self) -> None:
        if not self.data["enabled"]:
            return
        checked = [
            (key, drive, self.data["resolved"].get(key, {}))
            for key, drive in self.trips.state["trips"].items()
            if not drive["deleted"]
            and not drive.get("series_master")
            and self.data["resolved"].get(key, {}).get("distance_km") is not None
        ]
        checked.sort(key=lambda item: instant(item[2]["start"]))
        now, observed = self.app.now(), self.app.observation
        if (
            observed.connected
            and observed.ev_state_known
            and observed.quality not in ("unknown", "stale", "settling")
            and (now - observed.at).total_seconds() <= self.app.policy.measurement_max_age_seconds
        ):
            self.data["returned_through"] = observed.at.isoformat()
            self.save()
        goals = []
        for key, drive, route in checked:
            start = instant(route["start"])
            home_return = next(
                (
                    instant(other[2]["end"])
                    for other in checked
                    if instant(other[2]["start"]) >= start and other[2]["destination"] == "Home"
                ),
                None,
            )
            actual_return = (
                observed.connected
                and observed.ev_state_known
                and observed.at > start
                and (now - observed.at).total_seconds() <= self.app.policy.measurement_max_age_seconds
                and observed.quality not in ("unknown", "stale", "settling")
            )
            returned_through = self.data.get("returned_through")
            if (
                actual_return
                or (returned_through and start < instant(returned_through))
                or home_return
                and home_return <= now
            ):
                continue
            goals.append(
                Goal(
                    "drive-" + key,
                    route.get("title", drive["title"]),
                    start,
                    kind="trip",
                    revision=route.get("planning_revision", route["revision"]),
                    distance_km=route["distance_km"],
                    return_at=home_return,
                )
            )
        replaced = {
            identity
            for key, match in self.data["matches"].items()
            if not match.get("regenerate")
            for identity in match["event"].get("legacy_ids", ["calendar-" + key])
        }
        preserved = tuple(
            goal for goal in self.app.goals if not goal.id.startswith("drive-") and goal.id not in replaced
        )
        updated = preserved + tuple(goals)
        if updated != self.app.goals:
            previous = {goal.id: goal for goal in self.app.goals}
            current = {goal.id: goal for goal in updated}
            for key in previous.keys() | current.keys():
                if previous.get(key) != current.get(key):
                    self.app.clear_goal_issues(key)
            self.app.goals = updated
            self.app.store.put("goals", updated)
            self.app.changed("drive_projection_changed", ev=True)

    async def deliver_notices(self) -> None:
        messages = {
            "duration": "A drive's calculated travel time exceeds its allotted duration by more than 10 minutes.",
            "invalid_endpoints": "A drive needs correction. Open the EV trip calendar; last valid planning data is retained.",
            "match_changed": "A referee match changed time or location. Both drives were regenerated.",
            "reauthorization": "Google Calendar authorization needs attention. Reconnect in the EV trip calendar.",
            "calendar_setup": "Google Calendar push setup was rejected. Check the webhook URL and reverse proxy; periodic synchronization continues.",
        }
        for key, notice in self.trips.state["notices"].items():
            if not notice["delivered"]:
                if await self.app.notifications.inform(
                    "drive:" + key, {"kind": notice["kind"], "message": messages[notice["kind"]]}
                ):
                    notice["delivered"] = True
                    self.trips.save()

    async def loop(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self.wake.wait(), timeout=60)
            except TimeoutError:
                pass
            triggered = self.wake.is_set()
            self.wake.clear()
            if not self.data["enabled"]:
                continue
            async with self.lock:
                self.adopt_series()
                self.expand(self.app.now(), self.app.now() + timedelta(days=7))
                await self.refresh_routes()
                if (
                    self.sync
                    and self.sync.state["connected"]
                    and (
                        triggered
                        or self.last_sync is None
                        or self.app.now() - self.last_sync >= timedelta(minutes=5)
                    )
                ):
                    await self.sync.reconcile()
                    self.adopt_series()
                    self.last_sync = self.app.now()
                    if self.oauth and self.sync.status in ("synchronized", "needs_correction"):
                        try:
                            await self.sync.renew_channel(self.oauth.data["webhook_uri"], self.app.now())
                        except CalendarError as exc:
                            if exc.status in (400, 403, 404):
                                setup = sha256(self.oauth.data["webhook_uri"].encode()).hexdigest()[:16]
                                self.trips.notice("calendar", setup, "calendar_setup")
                            self.sync.status = "push_unavailable_reconciling"
                        except (aiohttp.ClientError, TimeoutError, ValueError):
                            self.sync.status = "push_unavailable_reconciling"
                await self.refresh_routes()
                if (
                    self.sync
                    and self.sync.state["connected"]
                    and self.sync.status
                    in ("synchronized", "needs_correction", "push_unavailable_reconciling")
                    and any(
                        self.sync.state["blocked"].get(item["id"]) != item["revision"]
                        for item in self.trips.pending()
                    )
                ):
                    self.wake.set()
                await self.deliver_notices()

    def status(self) -> dict[str, Any]:
        notices = []
        for key, notice in self.trips.state["notices"].items():
            identity = notice["trip"]
            route = self.data["resolved"].get(identity, {})
            if notice.get("dismissed"):
                continue
            active = (
                notice["kind"] == "match_changed"
                or notice["kind"] == "calendar_setup"
                and self.sync
                and self.sync.status == "push_unavailable_reconciling"
                or notice["kind"] == "reauthorization"
                and self.sync
                and self.sync.status == "reauthorization_required"
                or notice["kind"] == "invalid_endpoints"
                and (route.get("error") or self.sync and identity in self.sync.state["blocked"])
                or notice["kind"] == "duration"
                and route.get("warning")
            )
            if active:
                notices.append({"key": key, **notice})
        return {
            "enabled": self.data["enabled"],
            "trips": list(self.trips.state["trips"].values()),
            "resolved": self.data["resolved"],
            "matches": list(self.data["matches"].values()),
            "series": self.data["series"],
            "notices": notices,
            "sync": self.sync.status if self.sync else "disconnected",
            "pending": len(self.trips.pending()),
            "calendar": self.trips.state["binding"],
            "selected": self.data["selected"],
            "oauth": self.oauth.status() if self.oauth else {"configured": False, "authorized": False},
        }

    def places(self) -> TripPlaces:
        if not self.session:
            raise ValueError("Calendar service is starting")
        settings = self.app.journeys.settings if self.app.journeys else {}
        return TripPlaces(self.session, settings.get("api_key", ""))
