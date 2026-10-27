"""Route user-owned journey requests independently from planning and fast control."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import aiohttp

from .domain import Goal, instant
from .routing import GoogleRoutesClient, RefereeJourneyRouter, RoutingUnavailable

if TYPE_CHECKING:
    from .service import Application

class Journeys:
    """Keep requested attendance/overrides durable and publish only checked trip goals."""

    def __init__(self, application: Application, settings: dict[str, Any] | None = None,
                 *, router: RefereeJourneyRouter | None = None) -> None:
        self.app = application
        self.settings = dict(settings or {})
        self.settings_generation = 0
        key = self.settings.get("api_key", "")
        self.router = router or RefereeJourneyRouter(GoogleRoutesClient(key, allow_requests=bool(key)))
        self.synthetic = router is not None
        self.requests: dict[str, dict[str, Any]] = application.store.get("journey_requests", {})
        self.overrides: dict[str, dict[str, Any]] = application.store.get("journey_overrides", {})
        self.results: dict[str, dict[str, Any]] = {}
        self.restart_goals = {goal.id: goal for goal in application.goals if goal.id in self.requests}
        self.lock = asyncio.Lock()
        self.wake = asyncio.Event()
        self.task: asyncio.Task[None] | None = None
        self.stopped = False
        self.force_refresh = False
        self.revisions: dict[str, int] = application.store.get("journey_revisions", {})
        for goal in application.goals:
            if goal.id in self.requests:
                self.revisions[goal.id] = max(self.revisions.get(goal.id, 0), goal.revision)
        self.notifications_at = application.now() - timedelta(minutes=1)

    def start(self) -> None:
        # Never give cached route goals command authority before fresh reconciliation.
        for identity in self.requests:
            self.remove_goal(identity)
        self.task = asyncio.create_task(self.loop())
        self.wake.set()

    async def close(self) -> None:
        self.stopped = True
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    def save(self) -> None:
        self.app.store.put("journey_requests", self.requests)
        self.app.store.put("journey_overrides", self.overrides)

    def request_refresh(self) -> None:
        self.force_refresh = True
        self.wake.set()

    def apply_settings(self, settings: dict[str, Any]) -> None:
        """Apply a saved key immediately and reject results from an older credential."""
        key = settings.get("api_key", "")
        if key == self.settings.get("api_key", ""):
            return
        if isinstance(self.router, RefereeJourneyRouter):
            self.router.client.allow_requests = False  # Stop later legs using the retired key.
        self.settings = dict(settings)
        self.settings_generation += 1
        self.router = RefereeJourneyRouter(GoogleRoutesClient(key, allow_requests=bool(key)))
        self.synthetic = False
        now = self.app.now()
        for identity in self.requests:
            if self.effective(identity).get("override") is not None:
                continue
            result = self.results.get(identity, {})
            if result.get("state") == "resolved" and instant(result["deadline"]) <= now:
                continue  # Preserve the checked away period of a journey already underway.
            goal = next((item for item in self.app.goals if item.id == identity), None)
            if goal is not None:
                self.restart_goals[identity] = goal
            self.results.pop(identity, None)
            self.remove_goal(identity)
        self.request_refresh()

    def calendar(self, identity: str, source: str, event: dict[str, Any]) -> None:
        start = instant(event["start"])
        request = {"id": identity, "title": f"{source} · {event['title']}",
                   "destination": event["location"], "arrival": (start - timedelta(hours=1)).isoformat(),
                   "venue_departure": (start + timedelta(hours=2)).isoformat(), "priority": 50,
                   "calendar": {"source": source, "event_start": event["start"]}}
        if self.requests.get(identity) != request:
            self.requests[identity] = request
            self.restart_goals.pop(identity, None)
            self.results.pop(identity, None)
            self.remove_goal(identity, changed=True)
            self.save()
            self.wake.set()

    def retain_calendars(self, active: set[str]) -> None:
        for identity in list(self.requests):
            if identity.startswith("calendar-") and identity not in active:
                self.requests.pop(identity)
                self.overrides.pop(identity, None)
                self.results.pop(identity, None)
                self.remove_goal(identity, changed=True)
        self.save()

    def upsert(self, data: dict[str, Any], identity: str | None = None) -> dict[str, Any]:
        allowed = {"id", "title", "destination", "arrival", "venue_departure", "priority", "override"}
        if not isinstance(data, dict) or set(data) - allowed:
            raise ValueError("Use journey destination, attendance times and optional explicit override")
        identity = identity or data.get("id") or "journey-" + uuid4().hex
        if not isinstance(identity, str):
            raise ValueError("Invalid journey identity")
        original = self.requests.get(identity)
        previous_goal = next((goal for goal in self.app.goals if goal.id == identity), None)
        if original is None and not identity.startswith("journey-") and not (
                previous_goal and previous_goal.kind == "trip" and not identity.startswith("calendar-")):
            raise ValueError("Unknown routed journey")
        if original is not None and data.get("id", identity) != identity:
            raise ValueError("Journey identity cannot change")
        request = {**(original or {}), **{key: value for key, value in data.items() if key != "override"},
                   "id": identity}
        if (not isinstance(request.get("title"), str) or not request["title"].strip()
                or len(request["title"]) > 400):
            raise ValueError("Give the journey a name")
        if not isinstance(request.get("destination"), str) or len(request["destination"]) > 1000:
            raise ValueError("Use a destination address")
        if not all(isinstance(request.get(key), str) for key in ("arrival", "venue_departure")):
            raise ValueError("Use venue arrival and departure times with timezone offsets")
        arrival, departure = instant(request["arrival"]), instant(request["venue_departure"])
        if arrival <= self.app.now() or departure < arrival:
            raise ValueError("Venue arrival must be in the future and departure cannot precede arrival")
        if type(request.get("priority", 50)) is not int or not 0 <= request.get("priority", 50) <= 1000:
            raise ValueError("Invalid journey priority")
        request["arrival"], request["venue_departure"] = arrival.isoformat(), departure.isoformat()
        override = data.get("override")
        if override is not None:
            if not isinstance(override, dict) or set(override) != {"deadline", "return_at", "distance_km"}:
                raise ValueError("A manual route override needs home departure, return and total distance")
            if not all(isinstance(override[key], str) for key in ("deadline", "return_at")):
                raise ValueError("Use override departure and return times with timezone offsets")
            trial = Goal.from_dict({"id": identity, "title": request["title"], "kind": "trip", **override})
            if trial.deadline <= self.app.now() or trial.return_at is None:
                raise ValueError("Override departure must be in the future with an explicit return")
        # Calendar edits are overlays, never mutations of the subscription snapshot.
        if original and "calendar" in original:
            self.overrides[identity] = {key: request[key] for key in
                                        ("title", "destination", "arrival", "venue_departure", "priority")
                                        if key in request}
            if override is not None:
                self.overrides[identity]["override"] = override
        else:
            self.requests[identity] = request
            if override is not None:
                self.overrides[identity] = {"override": override}
            else:
                self.overrides.pop(identity, None)
        self.restart_goals.pop(identity, None)
        self.results.pop(identity, None)
        self.remove_goal(identity, changed=True)
        self.save()
        self.wake.set()
        return self.effective(identity)

    def effective(self, identity: str) -> dict[str, Any]:
        return {**self.requests[identity], **self.overrides.get(identity, {})}

    def reset(self, identity: str) -> None:
        if identity not in self.requests:
            raise KeyError(identity)
        self.overrides.pop(identity, None)
        self.restart_goals.pop(identity, None)
        self.results.pop(identity, None)
        self.remove_goal(identity, changed=True)
        self.save()
        self.wake.set()

    def delete(self, identity: str) -> None:
        if identity not in self.requests:
            raise KeyError(identity)
        if "calendar" in self.requests[identity]:
            raise ValueError("Remove subscribed events in their calendar")
        self.requests.pop(identity)
        self.overrides.pop(identity, None)
        self.restart_goals.pop(identity, None)
        self.results.pop(identity, None)
        self.remove_goal(identity, changed=True)
        self.save()

    def remove_goal(self, identity: str, *, changed: bool = False) -> None:
        before = self.app.goals
        for goal in before:
            if goal.id == identity:
                self.revisions[identity] = max(self.revisions.get(identity, 0), goal.revision)
                self.app.store.put("journey_revisions", self.revisions)
        self.app.goals = tuple(goal for goal in before if goal.id != identity)
        if before != self.app.goals:
            self.app.clear_goal_issues(identity)
            self.app.store.put("goals", self.app.goals)
            self.app.changed("journey_requirements_changed", ev=True)
        elif changed:
            # A request without a checked goal does not alter the accepted battery
            # requirements. Other valid work can continue under its existing guards.
            self.app.store.event("journey_request_changed", {"journey_id": identity})

    def status(self) -> dict[str, Any]:
        now = self.app.now()
        items = []
        for identity in self.requests:
            request = self.effective(identity)
            if instant(request["venue_departure"]) + timedelta(days=1) < now:
                continue
            result = self.results.get(identity, {})
            state = result.get("state", "pending")
            if result.get("state") == "resolved" and result.get("return_at") and instant(result["return_at"]) <= now:
                continue
            if instant(request["arrival"]) > now + timedelta(days=7):
                state = "outside_horizon"
            items.append({**request, **result, "state": state,
                          "overridden": identity in self.overrides,
                          "phone_configured": self.app.notifications.target is not None})
        return {"items": items, "live_available": bool(self.settings.get("api_key")),
                "activation_note": None if self.settings.get("api_key") else
                "Enter a Google Routes API key in Settings to activate routing"}

    @property
    def needs_attention(self) -> bool:
        return any(item["state"] in ("pending", "unresolved") for item in self.status()["items"])

    async def loop(self) -> None:
        while not self.stopped:
            try:
                await asyncio.wait_for(self.wake.wait(), timeout=60)
            except TimeoutError:
                pass
            force = self.force_refresh
            self.force_refresh = False
            self.wake.clear()
            await self.refresh(force=force)

    async def refresh(self, *, force: bool = True) -> None:
        async with self.lock:
            now = self.app.now()
            for identity in list(self.requests):
                if identity not in self.requests:
                    continue
                request = self.effective(identity)
                generation, router = self.settings_generation, self.router
                arrival, venue_departure = instant(request["arrival"]), instant(request["venue_departure"])
                if arrival > now + timedelta(days=7) or venue_departure + timedelta(days=1) < now:
                    continue
                previous = self.results.get(identity, {})
                # A journey already underway keeps its checked away period. Never recalculate
                # a past departure or substitute a new trip while the car may be travelling.
                if previous.get("state") == "resolved" and instant(previous["deadline"]) <= now:
                    continue
                if not force and previous.get("checked_at") and (
                        now - instant(previous["checked_at"])).total_seconds() < 86400:
                    continue
                try:
                    override = request.get("override")
                    if override is not None:
                        goal = Goal.from_dict({"id": identity, "title": request["title"], "kind": "trip", **override})
                        provider = "Manual override"
                    else:
                        if not request["destination"].strip():
                            raise RoutingUnavailable("Destination is missing; edit the journey")
                        if not self.synthetic and not self.settings.get("api_key"):
                            raise RoutingUnavailable("Enter a Google Routes API key in Settings")
                        if self.app.ha is None:
                            raise RoutingUnavailable("Home Assistant home location is unavailable")
                        home = await self.app.ha.entity_state("zone.home")
                        if generation != self.settings_generation:
                            continue
                        estimate = await router.journey(home, request["destination"], arrival,
                                                             venue_departure, traffic_aware=True)
                        goal = Goal(identity, request["title"], estimate.departure, kind="trip",
                                    distance_km=estimate.distance_km, return_at=estimate.return_at)
                        provider = "Google Maps"
                    goal = replace(goal, priority=request.get("priority", 50))
                except (RoutingUnavailable, ValueError, OverflowError, aiohttp.ClientError, TimeoutError):
                    # Do not expose addresses, keys or transport exception bodies to event logs.
                    if (generation == self.settings_generation and identity in self.requests
                            and self.effective(identity) == request):
                        self.results[identity] = {"state": "unresolved", "checked_at": now.isoformat(),
                                                  "error": "Route unresolved; check destination, times and Maps settings"}
                        self.remove_goal(identity)
                    continue
                if (generation != self.settings_generation or identity not in self.requests
                        or self.effective(identity) != request):
                    continue  # A changed/deleted event cannot adopt an in-flight stale response.
                current = next((item for item in self.app.goals if item.id == identity), None)
                old = current or self.restart_goals.pop(identity, None)
                material = (goal.title, goal.deadline, goal.return_at, goal.distance_km, goal.priority)
                if old and (old.title, old.deadline, old.return_at, old.distance_km, old.priority) == material:
                    goal = old
                else:
                    revision = max(self.revisions.get(identity, 0), old.revision if old else 0) + 1
                    goal = replace(goal, revision=revision)
                    self.revisions[identity] = revision
                    self.app.store.put("journey_revisions", self.revisions)
                notices = self.app.store.get("notices", {})
                if notices.pop("route:" + identity, None) is not None:
                    self.app.store.put("notices", notices)
                self.results[identity] = {"state": "resolved", "checked_at": now.isoformat(),
                                          "provider": provider, "deadline": goal.deadline.isoformat(),
                                          "return_at": goal.return_at.isoformat() if goal.return_at else None,
                                          "distance_km": goal.distance_km}
                if current != goal:
                    self.app.goals = tuple(item for item in self.app.goals if item.id != identity) + (goal,)
                    self.app.clear_goal_issues(identity)
                    self.app.store.put("goals", self.app.goals)
                    self.app.changed("journey_routed", ev=True)
            if (now - self.notifications_at).total_seconds() >= 60:
                self.notifications_at = now
                for item in self.status()["items"]:
                    if item["state"] == "unresolved":
                        await self.app.notifications.inform("route:" + item["id"], {
                            "kind": "journey_unresolved", "journey_id": item["id"],
                            "message": f"Journey '{item['title']}' has an unresolved route. Open EV to correct it."})
