"""Synthetic routing replies only; no paid Google requests."""

from datetime import UTC, datetime, timedelta

import pytest

from energymanager.routing import GoogleRoutesClient, RouteLeg, RoutingUnavailable, journey_estimate, route_leg, waypoint
from energymanager.routing import RefereeJourneyRouter, home_coordinates, referee_journey_estimate


def test_asymmetric_round_trip_and_explicit_margin_cross_dst():
    start = datetime.fromisoformat("2026-10-25T03:30:00+01:00")
    venue_departure = start + timedelta(hours=2)
    estimate = journey_estimate(start, venue_departure, timedelta(hours=1), RouteLeg(42.5, 2700), RouteLeg(47, 3600))
    assert estimate.distance_km == 89.5
    assert estimate.departure == datetime(2026, 10, 25, 0, 45, tzinfo=UTC)
    assert estimate.return_at == datetime(2026, 10, 25, 5, 30, tzinfo=UTC)


def test_referee_policy_uses_elapsed_time_across_clock_change_and_separate_leg_distances():
    start = datetime.fromisoformat("2026-10-25T02:30:00+01:00")
    estimate = referee_journey_estimate(start, RouteLeg(42, 3600), RouteLeg(47, 2700))
    assert estimate.departure == datetime(2026, 10, 24, 23, 30, tzinfo=UTC)
    assert estimate.return_at == datetime(2026, 10, 25, 4, 15, tzinfo=UTC)
    assert estimate.distance_km == 89


@pytest.mark.parametrize("state", [None, [], {}, {"attributes": {"latitude": None, "longitude": 4}},
                                   {"attributes": {"latitude": 50, "longitude": float("nan")}},
                                   {"entity_id": "zone.work", "attributes": {"latitude": 50, "longitude": 4}}])
def test_referee_origin_never_substitutes_missing_or_invalid_home(state):
    with pytest.raises(ValueError):
        home_coordinates(state)


@pytest.mark.parametrize("durations,expected_departure,expected_calls", [
    ([2700, 2700], "2030-01-01T16:14:00+00:00", 3),
    ([2700, 3000, 2900], "2030-01-01T16:09:00+00:00", 4),
])
async def test_referee_router_uses_ha_home_both_ways_and_checks_actual_departure(
        durations, expected_departure, expected_calls):
    calls = []
    event_start = datetime(2030, 1, 1, 18, tzinfo=UTC)

    class SyntheticRoutes(GoogleRoutesClient):
        async def leg(self, origin, destination, departure, *, traffic_aware):
            calls.append((origin, destination, departure, traffic_aware))
            if origin == "SYNTHETIC hall":
                return RouteLeg(47, 3600)
            return RouteLeg(42, durations[len(calls) - 1])

    router = RefereeJourneyRouter(SyntheticRoutes("synthetic-key"))
    home_state = {"entity_id": "zone.home", "attributes": {"latitude": 50, "longitude": 4}}
    estimate = await router.estimate(home_state, "SYNTHETIC hall", event_start, traffic_aware=True)
    assert estimate.departure == datetime.fromisoformat(expected_departure)
    assert estimate.return_at == datetime(2030, 1, 1, 21, tzinfo=UTC)
    assert estimate.distance_km == 89 and len(calls) == expected_calls
    assert calls[0][:2] == ((50, 4), "SYNTHETIC hall")
    assert calls[-1][:3] == ("SYNTHETIC hall", (50, 4), event_start + timedelta(hours=2))
    assert calls[-2][2] == estimate.departure


async def test_referee_static_routing_needs_only_two_legs_and_ignores_event_end():
    calls = []

    class SyntheticRoutes(GoogleRoutesClient):
        async def leg(self, origin, destination, departure, *, traffic_aware):
            calls.append((origin, destination, departure, traffic_aware))
            return RouteLeg(40, 1800)

    router = RefereeJourneyRouter(SyntheticRoutes("synthetic-key"))
    estimate = await router.estimate({"attributes": {"latitude": 50, "longitude": 4}}, "SYNTHETIC hall",
                                     datetime(2030, 1, 1, 18, tzinfo=UTC), traffic_aware=False)
    assert estimate.departure == datetime(2030, 1, 1, 16, 30, tzinfo=UTC)
    assert estimate.return_at == datetime(2030, 1, 1, 20, 30, tzinfo=UTC)
    assert len(calls) == 2 and all(not call[3] for call in calls)


async def test_referee_router_rejects_unsettled_traffic_and_passed_arrival_without_guessing():
    calls = []

    class SyntheticRoutes(GoogleRoutesClient):
        async def leg(self, origin, destination, departure, *, traffic_aware):
            calls.append(departure)
            return RouteLeg(40, 1800 + len(calls) * 300)

    router = RefereeJourneyRouter(SyntheticRoutes("synthetic-key"))
    home = {"attributes": {"latitude": 50, "longitude": 4}}
    with pytest.raises(RoutingUnavailable, match="arrival time has already passed"):
        await router.estimate(home, "SYNTHETIC hall", datetime(2020, 1, 1, 18, tzinfo=UTC), traffic_aware=True)
    assert calls == []
    with pytest.raises(RoutingUnavailable, match="could not establish") as failure:
        await router.estimate(home, "SYNTHETIC hall", datetime(2030, 1, 1, 18, tzinfo=UTC), traffic_aware=True)
    assert failure.value.code == "traffic_timing"
    assert len(calls) == 3  # No unbounded fixed-point loop and no invented return estimate.


def test_response_units_and_unknown_route_are_explicit():
    assert route_leg({"routes": [{"distanceMeters": 42345, "duration": "1234.5s"}]}) == RouteLeg(42.345, 1234.5)
    assert route_leg({"routes": [{"distanceMeters": 0, "duration": "0s"}]}) == RouteLeg(0, 0)
    for document in ({}, {"routes": []}, {"routes": [{"distanceMeters": 100}]},
                     {"routes": [{"distanceMeters": -1, "duration": "12s"}]},
                     {"routes": [{"distanceMeters": True, "duration": "12s"}]},
                     {"routes": [{"distanceMeters": 1, "duration": "NaNs"}]}):
        with pytest.raises(RoutingUnavailable):
            route_leg(document)
    with pytest.raises(ValueError):
        waypoint((float("nan"), 4))
    with pytest.raises(ValueError):
        waypoint("")
    assert waypoint((50, 4)) == {"location": {"latLng": {"latitude": 50, "longitude": 4}}}


async def test_requests_are_disabled_without_explicit_enabling(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No Google connection is allowed in this test")

    monkeypatch.setattr("energymanager.routing.aiohttp.ClientSession", forbidden)
    with pytest.raises(RoutingUnavailable, match="not been enabled"):
        await GoogleRoutesClient("synthetic-key").leg((50, 4), "SYNTHETIC venue", datetime(2030, 1, 1, tzinfo=UTC),
                                                     traffic_aware=True)


@pytest.mark.parametrize("status", [200, 403, 429, 302])
async def test_synthetic_transport_field_mask_key_and_no_retry_or_redirect(monkeypatch, status):
    from energymanager.routing import FIELD_MASK, ROUTES_URL

    calls = []

    class Content:
        async def iter_chunked(self, size):
            yield b'{"routes":[{"distanceMeters":51234,"duration":"3600.5s"}]}'

    class Response:
        content = Content()

        async def __aenter__(self):
            self.status = status
            return self

        async def __aexit__(self, *args):
            pass

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return Response()

    monkeypatch.setattr("energymanager.routing.aiohttp.ClientSession", Session)
    client = GoogleRoutesClient("synthetic-key", allow_requests=True)
    request = client.leg((50, 4), "SYNTHETIC venue", datetime(2030, 1, 1, tzinfo=UTC), traffic_aware=True)
    if status == 200:
        assert await request == RouteLeg(51.234, 3600.5)
    else:
        with pytest.raises(RoutingUnavailable, match=f"HTTP {status}"):
            await request
    assert len(calls) == 1 and calls[0][0] == ROUTES_URL
    payload = calls[0][1]
    assert payload["headers"] == {"X-Goog-Api-Key": "synthetic-key", "X-Goog-FieldMask": FIELD_MASK}
    assert payload["allow_redirects"] is False
    assert payload["json"]["departureTime"] == "2030-01-01T00:00:00Z"
    assert payload["json"]["routingPreference"] == "TRAFFIC_AWARE"


async def test_real_transport_against_local_synthetic_google_endpoint(monkeypatch):
    from aiohttp import web
    from aiohttp.test_utils import TestServer
    from energymanager import routing
    calls = []
    async def fake_google(request):
        calls.append({"key": request.headers.get("X-Goog-Api-Key"), "body": await request.json()})
        return web.json_response({"routes": [{"distanceMeters": 42345, "duration": "1800s"}]})
    server_app = web.Application()
    server_app.router.add_post("/synthetic-routes", fake_google)
    async with TestServer(server_app) as server:
        monkeypatch.setattr(routing, "ROUTES_URL", str(server.make_url("/synthetic-routes")))
        result = await GoogleRoutesClient("synthetic-key", allow_requests=True).leg(
            (50, 4), "SYNTHETIC venue", datetime(2030, 1, 1, tzinfo=UTC), traffic_aware=True)
    assert result == RouteLeg(42.345, 1800)
    assert len(calls) == 1 and calls[0]["key"] == "synthetic-key"
    assert calls[0]["body"]["routingPreference"] == "TRAFFIC_AWARE"
    assert calls[0]["body"]["departureTime"] == "2030-01-01T00:00:00Z"


@pytest.mark.parametrize(
    "durations", [[1800, 1801], [1800, 1799], [1800, 1800.001], [1800, 1860], [1800, 1861, 1862]]
)
async def test_small_traffic_changes_still_have_a_checked_on_time_departure(durations):
    calls = []
    arrival = datetime(2030, 1, 1, 17, tzinfo=UTC)

    class SyntheticRoutes(GoogleRoutesClient):
        async def leg(self, origin, destination, departure, *, traffic_aware):
            if origin == "SYNTHETIC venue":
                return RouteLeg(45, 2000)
            duration = durations[len(calls)]
            calls.append((departure, duration))
            return RouteLeg(40 + len(calls), duration)

    router = RefereeJourneyRouter(SyntheticRoutes("synthetic-key"))
    estimate = await router.journey(
        {"attributes": {"latitude": 50, "longitude": 4}},
        "SYNTHETIC venue",
        arrival,
        arrival + timedelta(hours=3),
    )
    assert len(calls) <= 3
    assert calls[-1][0] == estimate.departure
    assert estimate.departure + timedelta(seconds=calls[-1][1]) <= arrival
    assert estimate.distance_km == 45 + 40 + len(calls)  # Distance from the checked departure response.


async def test_traffic_allowance_cannot_turn_a_past_departure_into_an_accepted_route():
    class SyntheticRoutes(GoogleRoutesClient):
        async def leg(self, *args, **kwargs):
            return RouteLeg(40, 120)

    router = RefereeJourneyRouter(SyntheticRoutes("synthetic-key"))
    now = datetime.now(UTC)
    with pytest.raises(RoutingUnavailable) as failure:
        await router.journey(
            {"attributes": {"latitude": 50, "longitude": 4}},
            "SYNTHETIC venue",
            now + timedelta(seconds=150),
            now + timedelta(hours=3),
        )
    assert failure.value.code == "past_departure"


@pytest.mark.parametrize(
    "status,code",
    [
        (400, "request_rejected"),
        (401, "access_denied"),
        (403, "access_denied"),
        (429, "quota"),
        (500, "provider"),
        (503, "provider"),
        (302, "request_rejected"),
    ],
)
async def test_provider_failures_have_safe_categories_without_reading_the_error_body(
    monkeypatch, status, code
):
    class Content:
        async def iter_chunked(self, size):
            raise AssertionError("Private Google error body must never be read")
            yield b""

    class Response:
        content = Content()

        async def __aenter__(self):
            self.status = status
            return self

        async def __aexit__(self, *args):
            pass

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr("energymanager.routing.aiohttp.ClientSession", Session)
    with pytest.raises(RoutingUnavailable) as failure:
        await GoogleRoutesClient("synthetic-key", allow_requests=True).leg(
            (50, 4), "SYNTHETIC venue", datetime(2030, 1, 1, tzinfo=UTC), traffic_aware=True
        )
    assert failure.value.code == code
    assert failure.value.http_status == status
    assert f"HTTP {status}" in failure.value.public_message
    assert "synthetic-key" not in failure.value.public_message


@pytest.mark.parametrize(
    "problem,code",
    [
        ("timeout", "timeout"),
        ("connection", "connection"),
        ("json", "invalid_response"),
        ("no_route", "no_route"),
    ],
)
async def test_transport_and_route_errors_remain_distinct_and_sanitized(monkeypatch, problem, code):
    import aiohttp

    class Content:
        async def iter_chunked(self, size):
            yield b"private-provider-text" if problem == "json" else b'{"routes":[]}'

    class Response:
        status = 200
        content = Content()

        async def __aenter__(self):
            if problem == "timeout":
                raise TimeoutError("private-provider-text")
            if problem == "connection":
                raise aiohttp.ClientConnectionError("private-provider-text")
            return self

        async def __aexit__(self, *args):
            pass

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr("energymanager.routing.aiohttp.ClientSession", Session)
    with pytest.raises(RoutingUnavailable) as failure:
        await GoogleRoutesClient("synthetic-key", allow_requests=True).leg(
            (50, 4), "SYNTHETIC venue", datetime(2030, 1, 1, tzinfo=UTC), traffic_aware=True
        )
    assert failure.value.code == code
    assert "private-provider-text" not in failure.value.public_message
    assert "synthetic-key" not in failure.value.public_message


def test_unknown_failure_code_and_invalid_http_status_cannot_inject_public_details():
    failure = RoutingUnavailable(
        "private-provider-text", code="private-provider-text", http_status="private-provider-text"
    )
    assert failure.code == "unavailable" and failure.http_status is None
    assert "private-provider-text" not in failure.public_message
