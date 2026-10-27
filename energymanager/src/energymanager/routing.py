"""Bounded Google Routes transport and explicit home/venue/home timing."""

from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp

from .domain import instant

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = "routes.distanceMeters,routes.duration"
Location = str | tuple[float, float]


class RoutingUnavailable(RuntimeError):
    """No usable routing estimate; callers must retain explicit uncertainty."""


def waypoint(location: Location) -> dict[str, Any]:
    if isinstance(location, str):
        if not location.strip() or len(location) > 1000:
            raise ValueError("A destination address is required")
        return {"address": location.strip()}
    if not isinstance(location, tuple) or len(location) != 2:
        raise ValueError("A routing location must be an address or latitude/longitude pair")
    latitude, longitude = location
    if (any(type(value) not in (int, float) or not math.isfinite(value) for value in location)
            or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
        raise ValueError("Invalid routing coordinates")
    return {"location": {"latLng": {"latitude": latitude, "longitude": longitude}}}


@dataclass(frozen=True)
class RouteLeg:
    distance_km: float
    duration_seconds: float

    def __post_init__(self) -> None:
        if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
               for value in (self.distance_km, self.duration_seconds)):
            raise ValueError("A route needs finite, nonnegative distance and duration")


def route_leg(document: dict[str, Any]) -> RouteLeg:
    """Read metric distance and protobuf seconds without inferring a missing route."""
    routes = document.get("routes")
    if not isinstance(routes, list) or len(routes) != 1 or not isinstance(routes[0], dict):
        raise RoutingUnavailable("Google Routes did not return one usable route")
    distance, duration = routes[0].get("distanceMeters"), routes[0].get("duration")
    if (type(distance) is not int or distance < 0 or not isinstance(duration, str)
            or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,9})?s", duration)):
        raise RoutingUnavailable("Google Routes returned incomplete distance or duration")
    try:
        return RouteLeg(distance / 1000, float(duration[:-1]))
    except (ValueError, OverflowError) as exc:
        raise RoutingUnavailable("Google Routes returned an invalid route") from exc


@dataclass(frozen=True)
class JourneyEstimate:
    departure: datetime
    return_at: datetime
    distance_km: float


def journey_estimate(event_start: datetime, venue_departure: datetime, arrival_margin: timedelta,
                     outward: RouteLeg, homeward: RouteLeg) -> JourneyEstimate:
    """Combine independently routed legs and explicit attendance policy; never double one leg."""
    event_start, venue_departure = instant(event_start), instant(venue_departure)
    if venue_departure < event_start or arrival_margin < timedelta(0):
        raise ValueError("Venue departure must follow event start and arrival margin cannot be negative")
    return JourneyEstimate(event_start - arrival_margin - timedelta(seconds=outward.duration_seconds),
                           venue_departure + timedelta(seconds=homeward.duration_seconds),
                           outward.distance_km + homeward.distance_km)


def referee_journey_estimate(event_start: datetime, outward: RouteLeg, homeward: RouteLeg) -> JourneyEstimate:
    """Arrive one hour early and leave the venue two elapsed hours after event start."""
    event_start = instant(event_start)
    return journey_estimate(event_start, event_start + timedelta(hours=2), timedelta(hours=1),
                            outward, homeward)


def home_coordinates(home_state: dict[str, Any]) -> tuple[float, float]:
    """Read validated zone.home coordinates supplied by the existing HA connection."""
    if not isinstance(home_state, dict):
        raise ValueError("Home Assistant zone.home needs a state object")
    if home_state.get("entity_id", "zone.home") != "zone.home":
        raise ValueError("Referee trips require Home Assistant zone.home")
    attributes = home_state.get("attributes")
    if not isinstance(attributes, dict):
        raise ValueError("Home Assistant zone.home needs latitude and longitude")
    latitude, longitude = attributes.get("latitude"), attributes.get("longitude")
    if (not isinstance(latitude, (int, float)) or isinstance(latitude, bool)
            or not isinstance(longitude, (int, float)) or isinstance(longitude, bool)):
        raise ValueError("Home Assistant zone.home needs numeric latitude and longitude")
    coordinates = (float(latitude), float(longitude))
    waypoint(coordinates)
    return coordinates


class GoogleRoutesClient:
    """Explicitly enabled server-side requests; no retries, redirects, logging or persistence."""

    def __init__(self, api_key: str, *, allow_requests: bool = False) -> None:
        self.api_key = api_key
        self.allow_requests = allow_requests

    async def leg(self, origin: Location, destination: Location, departure: datetime,
                  *, traffic_aware: bool) -> RouteLeg:
        if self.allow_requests is not True:
            raise RoutingUnavailable("Google routing requests have not been enabled")
        if not self.api_key.strip() or "\n" in self.api_key or "\r" in self.api_key:
            raise RoutingUnavailable("A server-side Google Routes API key is required")
        departure = instant(departure)
        if departure < datetime.now(UTC):
            raise ValueError("Google driving estimates require a future departure")
        body = {"origin": waypoint(origin), "destination": waypoint(destination), "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_AWARE" if traffic_aware else "TRAFFIC_UNAWARE",
                "computeAlternativeRoutes": False, "units": "METRIC"}
        if traffic_aware:
            body["departureTime"] = departure.isoformat().replace("+00:00", "Z")
        headers = {"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": FIELD_MASK}
        try:
            async with asyncio.timeout(15), aiohttp.ClientSession() as session:
                async with session.post(ROUTES_URL, json=body, headers=headers, allow_redirects=False) as response:
                    if response.status != 200:
                        raise RoutingUnavailable(f"Google Routes returned HTTP {response.status}")
                    result = bytearray()
                    async for chunk in response.content.iter_chunked(16384):
                        result.extend(chunk)
                        if len(result) > 65536:
                            raise RoutingUnavailable("Google Routes response exceeds the size limit")
                    document = json.loads(result)
            if not isinstance(document, dict):
                raise RoutingUnavailable("Google Routes returned invalid data")
            return route_leg(document)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            # Neither addresses nor the API key belong in user-visible transport errors.
            raise RoutingUnavailable("Google Routes could not provide an estimate") from exc


class RefereeJourneyRouter:
    """Prepare home–venue–home estimates; activation remains separate from calendar import."""

    def __init__(self, client: GoogleRoutesClient) -> None:
        self.client = client

    async def estimate(self, home_state: dict[str, Any], venue: str, event_start: datetime,
                       *, traffic_aware: bool) -> JourneyEstimate:
        event_start = instant(event_start)
        return await self.journey(home_state, venue, event_start - timedelta(hours=1),
                                  event_start + timedelta(hours=2), traffic_aware=traffic_aware)

    async def journey(self, home_state: dict[str, Any], venue: str, arrival: datetime,
                      venue_departure: datetime, *, traffic_aware: bool = True) -> JourneyEstimate:
        """Check an arrival deadline using at most three outward queries and one return query."""
        home = home_coordinates(home_state)
        waypoint(venue)
        arrival, venue_departure = instant(arrival), instant(venue_departure)
        if venue_departure < arrival:
            raise ValueError("Venue departure cannot precede arrival")
        if arrival <= datetime.now(UTC):
            raise RoutingUnavailable("The referee arrival time has already passed")

        # DRIVE has no arrival-time routing. Seed a duration, then check the resulting departure.
        outward = await self.client.leg(home, venue, arrival, traffic_aware=traffic_aware)
        duration_budget = outward.duration_seconds
        departure = arrival - timedelta(seconds=duration_budget)
        if departure <= datetime.now(UTC):
            raise RoutingUnavailable("The estimated home departure has already passed")
        if traffic_aware:
            for _ in range(2):
                outward = await self.client.leg(home, venue, departure, traffic_aware=True)
                if outward.duration_seconds <= duration_budget:
                    break  # This request predicts arrival by the required time, with any slack retained.
                duration_budget = outward.duration_seconds
                departure = arrival - timedelta(seconds=duration_budget)
                if departure <= datetime.now(UTC):
                    raise RoutingUnavailable("The estimated home departure has already passed")
            else:
                raise RoutingUnavailable("Traffic estimates could not establish the required arrival time")

        homeward = await self.client.leg(venue, home, venue_departure, traffic_aware=traffic_aware)
        return JourneyEstimate(departure, venue_departure + timedelta(seconds=homeward.duration_seconds),
                               outward.distance_km + homeward.distance_km)
