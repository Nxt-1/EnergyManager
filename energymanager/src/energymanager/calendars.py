"""Read-only subscribed calendars projected into explicit, provisional EV journeys."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import aiohttp
from aiohttp.resolver import ThreadedResolver
from icalendar import Calendar
import recurring_ical_events

from .domain import Goal, instant, json_data

if TYPE_CHECKING:
    from .service import Application

MAX_BYTES = 2 * 1024 * 1024
SYNC_SECONDS = 4 * 3600


def calendar_sources(value: Any) -> list[dict[str, Any]]:
    """Validate optional labelled feeds without fetching or exposing their contents."""
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 20:
        raise ValueError("Use at most 20 calendar links")
    result: list[dict[str, Any]] = []
    required = {"id", "label", "url"}
    allowed = required | {"routing"}
    for entry in value:
        if not isinstance(entry, dict) or not required.issubset(entry) or set(entry) - allowed:
            raise ValueError("Each calendar needs an ID, label and link")
        if not all(isinstance(entry[key], str) for key in ("id", "label", "url")):
            raise ValueError("Calendar fields must be text")
        if not entry["id"] or len(entry["id"]) > 80 or not entry["label"].strip() or len(entry["label"]) > 100:
            raise ValueError("Give each calendar a short, unique ID and a label")
        if "routing" in entry and type(entry["routing"]) is not bool:
            raise ValueError("Calendar routing must be enabled or disabled")
        url = entry["url"].strip()
        if url.startswith("webcal://"):
            url = "https://" + url[len("webcal://"):]
        validate_url(url)
        if any(item["id"] == entry["id"] or item["url"] == url for item in result):
            raise ValueError("Calendar IDs and links must be unique")
        result.append({"id": entry["id"], "label": entry["label"].strip(), "url": url,
                       **({"routing": entry["routing"]} if "routing" in entry else {})})
    return result


def validate_url(url: str) -> None:
    parts = urlsplit(url)
    if (len(url) > 2000 or parts.scheme != "https" or not parts.hostname or parts.username
            or parts.password or parts.fragment or parts.port not in (None, 443)
            or any(ord(char) <= 32 for char in url)):
        raise ValueError("Use a public HTTPS iCalendar link (or webcal link), without a login or fragment")


class PublicCalendarResolver(ThreadedResolver):
    async def resolve(self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET) -> Any:
        addresses = await super().resolve(host, port, family)
        if not addresses or any(not ipaddress.ip_address(item["host"]).is_global for item in addresses):
            raise ValueError("Calendar links must resolve to a public internet address")
        return addresses


async def fetch_calendar(url: str) -> bytes:
    """Bound downloads and redirects; never forward HA credentials to calendar servers."""
    connector = aiohttp.TCPConnector(resolver=PublicCalendarResolver())
    async with asyncio.timeout(20), aiohttp.ClientSession(
            connector=connector, timeout=aiohttp.ClientTimeout(total=20)) as session:
        for _ in range(4):
            validate_url(url)
            # Literal addresses bypass aiohttp's resolver, so check them here too.
            host = urlsplit(url).hostname or ""
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError("Calendar links must use a public internet address")
            async with session.get(url, allow_redirects=False) as response:
                if response.status in (301, 302, 303, 307, 308):
                    url = urljoin(url, response.headers.get("Location", ""))
                    continue
                if response.status != 200:
                    raise ValueError(f"Calendar server returned HTTP {response.status}")
                body = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise ValueError("Calendar exceeds the 2 MB limit")
                return bytes(body)
    raise ValueError("Calendar redirected too many times")


def parse_calendar(body: bytes, now: datetime, timezone: str) -> tuple[list[dict[str, Any]], int]:
    """Expand timed occurrences for 90 days; all-day entries have no departure time."""
    if len(body) > MAX_BYTES or not body.lstrip().startswith(b"BEGIN:VCALENDAR"):
        raise ValueError("The link did not return an iCalendar feed")
    calendar = Calendar.from_ical(body)
    components = calendar.walk("VEVENT")
    recurring_uids = {str(event.get("UID")) for event in components
                      if any(event.get(key) for key in ("RRULE", "RDATE", "RECURRENCE-ID"))}
    if len(components) > 5000:
        raise ValueError("Calendar contains more than 5000 events")
    component_ids = [(str(event.get("UID")), str(event.get("RECURRENCE-ID", ""))) for event in components]
    if len(set(component_ids)) != len(component_ids):
        raise ValueError("Calendar contains duplicate event identities")
    for event in components:
        if event.errors or not event.get("UID") or not event.get("DTSTART") and str(event.get("STATUS")) != "CANCELLED":
            raise ValueError("Calendar has an invalid event or missing UID/start")
        frequency = event.get("RRULE", {}).get("FREQ", [""])[0]
        if frequency in ("SECONDLY", "MINUTELY", "HOURLY"):
            raise ValueError("Calendar repetitions must be daily or less frequent")
    zone = ZoneInfo(timezone)
    calendar.setdefault("X-WR-TIMEZONE", timezone)
    start, end = now - timedelta(days=1), now + timedelta(days=90)
    events = []
    skipped = 0
    query = recurring_ical_events.of(calendar)
    for component in query.after(start):
        at = component.decoded("DTSTART")
        if not isinstance(at, datetime):
            skipped += 1
            if skipped > 1000:
                raise ValueError("Calendar contains too many all-day occurrences")
            if at > end.date():
                break
            continue
        at = at.replace(tzinfo=zone) if at.tzinfo is None else at
        at = at.astimezone(UTC)
        if at >= end:
            break
        if at + timedelta(days=1) <= now or str(component.get("STATUS", "")) == "CANCELLED":
            continue
        recurrence = component.get("RECURRENCE-ID")
        uid = str(component["UID"])
        recurrence_id = recurrence.to_ical().decode() if recurrence and uid in recurring_uids else ""
        key = sha256(f"{uid}\n{recurrence_id}".encode()).hexdigest()[:32]
        events.append({"key": key, "uid": uid, "recurrence_id": recurrence_id,
                       "start": at.isoformat(), "title": str(component.get("SUMMARY", "Calendar event"))[:300],
                       "location": str(component.get("LOCATION", ""))[:1000]})
        if len(events) > 1000:
            raise ValueError("Calendar has more than 1000 upcoming occurrences")
    # Protect against malformed duplicate identities instead of planning them twice.
    identities = [event["key"] for event in events]
    if len(set(identities)) != len(identities):
        raise ValueError("Calendar contains duplicate event identities")
    return events, skipped


class CalendarSync:
    """Own independent feed refresh, last-good snapshots and managed goal reconciliation."""

    def __init__(self, application: Application, sources: Any) -> None:
        self.application = application
        self.sources = calendar_sources(sources)
        saved = application.store.get("calendar_cache", {})
        self.cache = {source["id"]: saved[source["id"]] for source in self.sources
                      if source["id"] in saved and saved[source["id"]].get("fingerprint") ==
                      sha256(source["url"].encode()).hexdigest()}
        self.lock = asyncio.Lock()
        self.task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self.reconcile()
        if self.sources:
            self.task = asyncio.create_task(self.loop())

    async def close(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    async def loop(self) -> None:
        while True:
            await self.refresh()
            await asyncio.sleep(SYNC_SECONDS)

    async def refresh(self) -> None:
        async with self.lock:
            for source in self.sources:
                identity = source["id"]
                previous = self.cache.get(identity, {})
                try:
                    body = await fetch_calendar(source["url"])
                    events, skipped = await asyncio.to_thread(
                        parse_calendar, body, self.application.now(), self.application.policy.timezone)
                    self.cache[identity] = {"events": events, "skipped": skipped, "error": None,
                                            "last_success": self.application.now().isoformat(),
                                            "fingerprint": sha256(source["url"].encode()).hexdigest()}
                except (aiohttp.ClientError, TimeoutError, ValueError, TypeError, KeyError, OverflowError):
                    # URLs may contain subscription secrets. Never expose exception URLs or feed bodies.
                    self.cache[identity] = {**previous, "error": "Refresh failed; last successful items retained"}
                self.application.store.put("calendar_cache", self.cache)
                self.reconcile()

    def reconcile(self) -> None:
        app = self.application
        old_goals = {goal.id: goal for goal in app.goals}
        managed: list[Goal] = []
        metadata = {}
        duplicates = set()
        routed = set()
        for source in self.sources:
            for event in self.cache.get(source["id"], {}).get("events", []):
                if (not source.get("routing")
                        and instant(event["start"]) + timedelta(hours=4) <= app.now()):
                    continue
                duplicate = (event["uid"], event["start"], event["location"])
                if duplicate in duplicates:
                    continue
                duplicates.add(duplicate)
                identity = "calendar-" + sha256(f"{source['id']}:{event['key']}".encode()).hexdigest()[:32]
                if source.get("routing") and app.journeys is not None:
                    routed.add(identity)
                    app.journeys.calendar(identity, source["label"], event)
                    checked = next((item for item in app.goals if item.id == identity), None)
                    if checked is not None:
                        managed.append(checked)
                    metadata[identity] = {"source": source["label"], "location": event["location"],
                                          "event_start": event["start"], "placeholder": False}
                    continue
                old = old_goals.get(identity)
                goal = Goal(identity, f"{source['label']} · {event['title']}", instant(event["start"]),
                            kind="trip", distance_km=50, return_at=instant(event["start"]) + timedelta(hours=4))
                if old is not None:
                    if (old.title, old.deadline, old.return_at, old.distance_km) == (
                            goal.title, goal.deadline, goal.return_at, goal.distance_km):
                        goal = old
                    else:
                        goal = Goal.from_dict({**json_data(goal), "revision": old.revision + 1})
                managed.append(goal)
                metadata[identity] = {"source": source["label"], "location": event["location"],
                                      "event_start": event["start"], "placeholder": True}
        if app.journeys:
            app.journeys.retain_calendars(routed)
        goals = tuple(goal for goal in app.goals if not goal.id.startswith("calendar-")) + tuple(managed)
        app.calendar_items = metadata
        if goals != app.goals:
            new_goals = {goal.id: goal for goal in goals}
            changed = {identity for identity in old_goals.keys() | new_goals.keys()
                       if old_goals.get(identity) != new_goals.get(identity)}
            for identity in changed:
                app.clear_goal_issues(identity)
            app.goals = goals
            app.store.put("goals", goals)
            app.changed("calendar_journeys_changed", ev=True)

    def status(self) -> list[dict[str, Any]]:
        result = []
        for source in self.sources:
            cached = self.cache.get(source["id"], {})
            success = cached.get("last_success")
            result.append({"id": source["id"], "label": source["label"], "last_success": success,
                           "error": cached.get("error"), "events": len(cached.get("events", [])),
                           "skipped_all_day": cached.get("skipped", 0),
                           "stale": not success or (self.application.now() - instant(success)).total_seconds() > SYNC_SECONDS * 2})
        return result
