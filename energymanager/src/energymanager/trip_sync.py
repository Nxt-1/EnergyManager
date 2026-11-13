"""Reconcile local trips with the dedicated calendar without coupling control to I/O."""

from __future__ import annotations

import asyncio
import hmac
import secrets
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import aiohttp

from .domain import instant
from .google_calendar import CalendarError, GoogleCalendarClient
from .trip_events import drive_from_google, google_event
from .trip_store import TripStore
from .trip_recurrence import parse_google_rule


class TripSync:
    def __init__(self, trips: TripStore, client: GoogleCalendarClient) -> None:
        self.trips = trips
        self.client = client
        self.state = trips.store.get("ev_calendar_sync_v1", {"token": None, "remote": {}, "connected": False})
        self.state.setdefault("blocked", {})
        self.lock = asyncio.Lock()
        self.wake = asyncio.Event()
        self.status = "disconnected"

    def save(self) -> None:
        self.trips.store.put_states({"ev_calendar_sync_v1": self.state, "ev_trips_v1": self.trips.state})

    def disconnect(self) -> None:
        self.state["connected"] = False
        self.status = "disconnected"
        self.save()

    def connect(self, calendar: str) -> None:
        self.trips.bind(calendar)
        self.state["connected"] = True
        self.save()
        self.wake.set()

    async def renew_channel(self, webhook: str, now: datetime) -> None:
        channel = self.state.get("channel", {})
        if channel and int(channel.get("expiration", 0)) > (now.timestamp() + 3600) * 1000:
            return
        request = {
            "id": uuid4().hex,
            "type": "web_hook",
            "address": webhook,
            "token": secrets.token_urlsafe(32),
            "expiration": int((now.timestamp() + 86400) * 1000),
        }
        created = await self.client.watch(self.trips.state["binding"], request)
        if not self.state["connected"]:
            await self.client.stop(created["id"], created["resourceId"])
            return
        self.state["channel"] = {**created, "token": request["token"]}
        self.save()
        if channel:
            try:
                await self.client.stop(channel["id"], channel["resourceId"])
            except CalendarError as exc:
                if exc.status not in (404, 410):
                    self.state["retired_channel"] = channel
                    self.save()

    def webhook(self, headers: dict[str, str]) -> bool:
        normalized = {key.lower(): value for key, value in headers.items()}
        channel = self.state.get("channel", {})
        if not self.state["connected"] or not channel:
            return False
        for header, key in (
            ("X-Goog-Channel-ID", "id"),
            ("X-Goog-Resource-ID", "resourceId"),
            ("X-Goog-Channel-Token", "token"),
        ):
            expected, actual = channel.get(key, ""), normalized.get(header.lower(), "")
            if not expected or not hmac.compare_digest(expected, actual):
                return False
        self.wake.set()
        return True

    def ingest(self, event: dict[str, Any]) -> None:
        self.ingest_batch([event])

    def ingest_batch(self, events: list[dict[str, Any]], token: str | None = None) -> None:
        trip_state, sync_state = deepcopy(self.trips.state), deepcopy(self.state)
        self.trips.defer_writes = True
        try:
            for event in events:
                self._ingest(event)
            if token is not None:
                self.state["token"] = token
            self.save()
        except (ValueError, KeyError, TypeError):
            self.trips.state, self.state = trip_state, sync_state
            raise
        finally:
            self.trips.defer_writes = False

    def _ingest(self, event: dict[str, Any]) -> None:
        provider_id = event["id"]
        remote = self.state["remote"].get(provider_id)
        if remote and remote.get("etag") == event.get("etag"):
            return
        identity = (
            remote["trip"]
            if remote
            else event.get("extendedProperties", {}).get("private", {}).get("em_trip")
        )
        series = None
        occurrence = None
        if event.get("recurringEventId"):
            series = self.state["remote"].get(event["recurringEventId"], {}).get("trip")
            master = self.trips.state["trips"].get(series, {})
            if not master:
                raise ValueError("Recurring instance arrived without its master")
            original = event["originalStartTime"]["dateTime"]
            occurrence = instant(original).astimezone(ZoneInfo(master["timezone"])).date().isoformat()
            identity = sha256(f"{series}:{occurrence}".encode()).hexdigest()[:32]
        if (
            not isinstance(identity, str)
            or len(identity) != 32
            or any(c not in "0123456789abcdef" for c in identity)
            or (
                not series
                and any(
                    key != provider_id and item["trip"] == identity
                    for key, item in self.state["remote"].items()
                )
            )
        ):
            # Advanced direct creations get a durable mapping, never a title/time heuristic.
            identity = sha256(f"google:{self.trips.state['binding']}:{provider_id}".encode()).hexdigest()[:32]
        old = self.trips.state["trips"].get(identity)
        at = instant(event.get("updated", datetime.now(UTC).isoformat()))
        pending = identity in self.trips.state["pending"]
        if old and not old["deleted"] and event.get("status") != "cancelled":
            expected = google_event(old, remote.get("body", {}).get("description", "") if remote else "")
            # Recover a response lost after a successful write without manufacturing
            # a human edit, changing provenance or issuing another warning.
            fields = ("summary", "location", "description", "recurrence")
            same_times = all(
                event.get(key, {}).get("dateTime") and instant(event[key]["dateTime"]) == instant(old[key])
                for key in ("start", "end")
            )
            if (
                same_times
                and all(event.get(key) == expected.get(key) for key in fields)
                and {
                    key: value
                    for key, value in event.get("extendedProperties", {}).get("private", {}).items()
                    if key.startswith("em_")
                }
                == expected["extendedProperties"]["private"]
            ):
                self.state["remote"][provider_id] = {
                    "trip": identity,
                    "etag": event.get("etag"),
                    "body": event,
                }
                self.trips.acknowledge(identity, old["revision"])
                return
        if (
            old
            and pending
            and (old.get("source_change") or old["actor"] == "manual" and instant(old["edited_at"]) > at)
        ):
            self.state["remote"][provider_id] = {"trip": identity, "etag": event.get("etag"), "body": event}
            return
        if event.get("status") == "cancelled":
            if old and not old["deleted"]:
                self.trips.delete(identity, at)
                self.trips.acknowledge(identity, self.trips.state["trips"][identity]["revision"])
        else:
            try:
                previous = old
                if series and previous is None:
                    duration = instant(master["end"]) - instant(master["start"])
                    previous = {
                        **master,
                        "start": original,
                        "end": (instant(original) + duration).isoformat(),
                    }
                data = drive_from_google(event, previous)
                if event.get("recurrence"):
                    zone = event["start"].get("timeZone", "UTC")
                    data.update(
                        series_master=True,
                        recurrence=event["recurrence"],
                        timezone=zone,
                        rule=parse_google_rule(event["recurrence"], zone, event["start"]["dateTime"]),
                    )
                elif series:
                    data.update(series=series, occurrence=occurrence, series_master=False, exception=True)
            except (ValueError, KeyError, TypeError):
                # A malformed remote edit is evidence needing correction, never a new route.
                revision = event.get("etag") or event.get("updated") or provider_id
                self.trips.notice(identity, revision, "invalid_endpoints")
                self.state["blocked"][identity] = old["revision"] if old else 0
            else:
                updated = self.trips.edit(data, at, identity=identity)
                self.trips.acknowledge(identity, updated["revision"])
                mirrored = google_event(updated, event.get("description", ""))["extendedProperties"][
                    "private"
                ]
                private = event.get("extendedProperties", {}).get("private", {})
                if any(
                    private.get(key) != mirrored.get(key)
                    for key in ("em_schema", "em_trip", "em_mode", "em_km", "em_timing")
                ):
                    self.trips.state["pending"][identity] = updated["revision"]
                self.state["blocked"].pop(identity, None)
        self.state["remote"][provider_id] = {"trip": identity, "etag": event.get("etag"), "body": event}

    async def reconcile(self) -> None:
        if not self.state["connected"]:
            return
        async with self.lock:
            calendar = self.trips.state["binding"]
            try:
                full_read = self.state["token"] is None
                try:
                    events, token = await self.client.changes(calendar, self.state["token"])
                except CalendarError as exc:
                    if exc.status != 410:
                        raise
                    events, token = await self.client.changes(calendar)
                    full_read = True
                if not self.state["connected"]:
                    return
                # No mutation or inferred deletion happens before every page succeeds.
                if full_read:
                    found = {event["id"] for event in events}
                    events.extend(
                        {
                            "id": key,
                            "status": "cancelled",
                            "updated": datetime.now(UTC).isoformat(),
                            "etag": "missing:" + token,
                        }
                        for key in self.state["remote"]
                        if key not in found
                    )
                events.sort(key=lambda item: bool(item.get("recurringEventId")))
                self.ingest_batch(events, token)
                for trip in self.trips.pending():
                    if not self.state["connected"]:
                        return
                    if self.state["blocked"].get(trip["id"]) == trip["revision"]:
                        continue
                    await self.publish(calendar, trip)
                self.state["auth_required"] = False
                self.save()
                self.status = "needs_correction" if self.state["blocked"] else "synchronized"
            except CalendarError as exc:
                self.status = "reauthorization_required" if exc.status in (401, 403) else "unavailable"
                if self.status == "reauthorization_required":
                    if not self.state.get("auth_required"):
                        self.state["auth_epoch"] = self.state.get("auth_epoch", 0) + 1
                    self.state["auth_required"] = True
                    self.save()
                    self.trips.notice("calendar", self.state["auth_epoch"], "reauthorization")
            except (TimeoutError, OSError, ValueError, aiohttp.ClientError):
                self.status = "unavailable"

    async def publish(self, calendar: str, trip: dict[str, Any]) -> None:
        identity = trip["id"]
        mapping = next(
            ((key, item) for key, item in self.state["remote"].items() if item["trip"] == identity), None
        )
        provider_id = mapping[0] if mapping else "em" + identity
        metadata = mapping[1] if mapping else {}
        etag = metadata.get("etag")
        if trip.get("series") and not mapping:
            master = self.trips.state["trips"][trip["series"]]
            if trip["series"] in self.trips.state["pending"]:
                return  # Master must exist before looking up an occurrence.
            from .trip_recurrence import occurrences

            anchor = instant(master["start"])
            day = datetime.fromisoformat(trip["occurrence"]).replace(tzinfo=ZoneInfo(master["timezone"]))
            template = {
                "id": trip["series"],
                "start": master["start"],
                "end": master["end"],
                "rule": master["rule"],
                "timezone": master["timezone"],
                "template": {},
            }
            candidates = occurrences(template, day, day + timedelta(days=1))
            original_start = candidates[0]["start"] if candidates else anchor.isoformat()
            instances = await self.client.instance(calendar, "em" + trip["series"], original_start)
            matching = [
                item
                for item in instances.get("items", [])
                if instant(item["originalStartTime"]["dateTime"]) == instant(original_start)
            ]
            if len(matching) != 1:
                raise ValueError("Could not resolve recurring occurrence")
            remote_instance = matching[0]
            provider_id, etag = remote_instance["id"], remote_instance["etag"]
            metadata = {"trip": identity, "etag": etag, "body": remote_instance}
            self.state["remote"][provider_id] = metadata
            self.save()
        if trip["deleted"]:
            if etag:
                try:
                    await self.client.delete(calendar, provider_id, etag)
                except CalendarError as exc:
                    if exc.status not in (404, 410):
                        raise
            self.trips.acknowledge(identity, trip["revision"])
            return
        event = google_event(trip, metadata.get("body", {}).get("description", ""))
        event["id"] = provider_id
        if etag:
            old_private = metadata.get("body", {}).get("extendedProperties", {}).get("private", {})
            private = event["extendedProperties"]["private"]
            event["extendedProperties"]["private"] = {
                **{key: value for key, value in old_private.items() if not key.startswith("em_")},
                **{key: None for key in old_private if key.startswith("em_") and key not in private},
                **private,
            }
        try:
            result = await self.client.write(calendar, event, etag)
        except CalendarError as exc:
            if exc.status not in (409, 412):
                raise
            # Includes lost insert responses: discover the stable provider identity, then
            # resolve its latest contents before retrying with an etag on the next pass.
            result = await self.client.get(calendar, provider_id)
            self.ingest(result)
            self.save()
            return
        self.state["remote"][provider_id] = {"trip": identity, "etag": result["etag"], "body": result}
        self.state["blocked"].pop(identity, None)
        self.save()
        self.trips.acknowledge(identity, trip["revision"])
