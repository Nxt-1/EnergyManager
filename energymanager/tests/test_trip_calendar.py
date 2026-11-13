"""Synthetic drives/routes only; no installation data or provider requests."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from energymanager.calendars import CalendarSync, parse_known_calendar
from energymanager.domain import Goal
from energymanager.routing import RouteLeg, RoutingUnavailable
from energymanager.service import Application
from energymanager.store import Store
from energymanager.trip_recurrence import google_rule, occurrences, parse_google_rule


class SyntheticHome:
    async def entity_state(self, identity):
        assert identity == "zone.home"
        return {"attributes": {"latitude": 51.2, "longitude": 4.4}}


class SyntheticRoutes:
    def __init__(self):
        self.duration = 3600
        self.fail = False
        self.calls = []

    async def leg(self, origin, destination, at, *, traffic_aware):
        self.calls.append((origin, destination, at, traffic_aware))
        if self.fail:
            raise RoutingUnavailable("Synthetic outage")
        return RouteLeg(40, self.duration)


@pytest.fixture
def app(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    application = Application(store)
    application.now = lambda: datetime(2026, 11, 12, 9, tzinfo=UTC)
    application.ha = SyntheticHome()
    application.trips.router = SyntheticRoutes()
    application.goals = ()
    yield application
    store.close()


def drive(**changes):
    return {
        "mode": "routed",
        "origin": "Home",
        "destination": "Synthetic city",
        "timing": "fixed",
        "start": "2026-11-15T09:00:00+00:00",
        "end": "2026-11-15T09:30:00+00:00",
        "manual_km": None,
        **changes,
    }


@pytest.mark.asyncio
async def test_last_good_manual_distance_warning_and_use_calculated(app):
    owner = app.trips
    first = owner.upsert(drive(manual_km=77))
    await owner.refresh_routes()
    assert app.goals[0].distance_km == 77
    last_good = app.goals[0]
    assert owner.data["resolved"][first["id"]]["warning"]
    notices = len(owner.trips.state["notices"])
    await owner.refresh_routes()
    assert len(owner.trips.state["notices"]) == notices
    app.trips.router.fail = True
    edited = owner.upsert(
        {**first, "destination": "Broken address", "revision": first["revision"]}, first["id"]
    )
    await owner.refresh_routes()
    assert app.goals[0].distance_km == 77
    assert owner.data["resolved"][first["id"]]["error"]
    assert app.goals[0] == last_good
    app.trips.router.fail = False
    owner.upsert({**edited, "manual_km": None}, first["id"])
    await owner.refresh_routes()
    assert app.goals[0].distance_km == 40


@pytest.mark.asyncio
async def test_warning_strict_threshold_and_distance_only_has_no_route(app):
    app.trips.router.duration = 2400
    first = app.trips.upsert(drive())
    await app.trips.refresh_routes()
    assert not app.trips.data["resolved"][first["id"]]["warning"]  # Exactly ten minutes.
    app.trips.router.duration = 2401
    app.trips.upsert(first, first["id"])
    await app.trips.refresh_routes()
    assert app.trips.data["resolved"][first["id"]]["warning"]
    calls = len(app.trips.router.calls)
    item = app.trips.upsert(drive(mode="distance_only", origin=None, destination=None, manual_km=30))
    await app.trips.refresh_routes()
    assert len(app.trips.router.calls) == calls
    assert app.trips.data["resolved"][item["id"]]["duration_seconds"] is None


@pytest.mark.asyncio
async def test_referee_changes_deletions_disappearance_and_legacy_replacement(app):
    owner = app.trips
    owner.enable()
    event = {
        "key": "synthetic-match",
        "start": "2026-11-15T12:00:00+00:00",
        "location": "Synthetic stadium",
        "title": "Match",
    }
    owner.sources("referee", [event], True)
    match = next(iter(owner.data["matches"].values()))
    legacy = Goal(
        "calendar-" + match["id"],
        "Old referee",
        datetime(2026, 11, 15, 12, tzinfo=UTC),
        kind="trip",
        distance_km=80,
    )
    manual = Goal("unrelated-manual", "Keep me", datetime(2026, 11, 16, tzinfo=UTC))
    app.goals = (legacy, manual)
    app.trips.router.fail = True
    await owner.refresh_routes()
    assert legacy in app.goals
    app.trips.router.fail = False
    owner.force_routes = True
    await owner.refresh_routes()
    assert len([g for g in app.goals if g.kind == "trip"]) == 2
    assert manual in app.goals and legacy not in app.goals
    outward = owner.trips.state["trips"][owner.leg_id(match["id"], "out")]
    back = owner.trips.state["trips"][owner.leg_id(match["id"], "back")]
    assert outward["start"] == "2026-11-15T09:59:00+00:00"
    assert back["start"] == "2026-11-15T14:30:00+00:00"
    owner.delete(outward["id"])
    await owner.refresh_routes()
    assert owner.trips.state["trips"][outward["id"]]["deleted"]
    owner.sources("referee", [{**event, "location": "Other stadium"}], True)
    await owner.refresh_routes()
    assert not owner.trips.state["trips"][outward["id"]]["deleted"]
    assert any(n["kind"] == "match_changed" for n in owner.trips.state["notices"].values())
    owner.sources("referee", [], False)
    assert not match["missing"]
    owner.sources("referee", [], True)
    current = owner.data["matches"][match["id"]]
    assert current["missing"] and len([g for g in app.goals if g.kind == "trip"]) == 2
    owner.match_action(match["id"], "remove")
    assert not [g for g in app.goals if g.kind == "trip"]


@pytest.mark.asyncio
async def test_away_continuity_and_actual_home_return_survives_disconnect(app):
    owner = app.trips
    first = owner.upsert(drive(destination="Away A"))
    second = owner.upsert(
        drive(
            origin="Away A",
            destination="Away B",
            start="2026-11-16T09:00:00+00:00",
            end="2026-11-16T10:00:00+00:00",
        )
    )
    await owner.refresh_routes()
    assert all(g.return_at is None for g in app.goals)
    third = owner.upsert(
        drive(
            origin="Away B",
            destination="Home",
            start="2026-11-17T09:00:00+00:00",
            end="2026-11-17T10:00:00+00:00",
        )
    )
    await owner.refresh_routes()
    assert all(g.return_at.isoformat() == third["end"] for g in app.goals)
    now = datetime(2026, 11, 16, 12, tzinfo=UTC)
    app.now = lambda: now
    app.observation = replace(
        app.observation, at=now, connected=True, ev_state_known=True, quality="measured"
    )
    owner.project()
    assert {g.id for g in app.goals} == {"drive-" + third["id"]}
    app.observation = replace(app.observation, connected=False)
    owner.project()
    assert not {"drive-" + first["id"], "drive-" + second["id"]} & {g.id for g in app.goals}


@pytest.mark.asyncio
async def test_distant_match_routes_once_without_traffic(app):
    app.trips.enable()
    app.trips.sources(
        "referee",
        [
            {
                "key": "far",
                "start": "2027-07-01T12:00:00+00:00",
                "location": "Far stadium",
                "title": "Far match",
            }
        ],
        True,
    )
    await app.trips.refresh_routes()
    calls = len(app.trips.router.calls)
    assert calls and all(not item[3] for item in app.trips.router.calls)
    await app.trips.refresh_routes()
    assert len(app.trips.router.calls) == calls


def test_finite_source_beyond_90_days_and_unending_rule_bounded():
    body = b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:far\r\nDTSTART:20270701T120000Z\r\nSUMMARY:Far match\r\nLOCATION:Synthetic\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:unending\r\nDTSTART:20261115T120000Z\r\nRRULE:FREQ=WEEKLY\r\nEND:VEVENT\r\nEND:VCALENDAR"
    events, _ = parse_known_calendar(body, datetime(2026, 11, 12, tzinfo=UTC), "Europe/Brussels")
    assert any(item["uid"] == "far" for item in events)
    assert len([item for item in events if item["uid"] == "unending"]) < 15


def test_recurrence_split_and_independent_reverse(app):
    owner = app.trips
    master = owner.upsert(drive(rule={"weeks": 1, "weekdays": [6], "until": None}))
    children = [t for t in owner.trips.state["trips"].values() if t.get("series") == master["id"]]
    assert children
    first = children[0]
    reverse = owner.reverse(first["id"], False, True)
    assert reverse["id"] != master["id"]
    assert reverse["template"]["origin"] == first["destination"]
    owner.upsert(
        {**first, "rule": master["rule"], "scope": "following", "destination": "New destination"}, first["id"]
    )
    assert owner.data["series"][master["id"]]["cutoff"] == first["occurrence"]
    assert reverse["id"] in owner.data["series"]


def test_wall_recurrence_dst_and_google_rule_roundtrip():
    master = {
        "id": "a" * 32,
        "start": "2026-10-18T07:00:00+00:00",
        "end": "2026-10-18T08:00:00+00:00",
        "timezone": "Europe/Brussels",
        "rule": {"weeks": 1, "weekdays": [6], "until": None},
        "template": {},
    }
    items = occurrences(master, datetime(2026, 10, 18, tzinfo=UTC), datetime(2026, 11, 2, tzinfo=UTC))
    assert [item["start"][11:16] for item in items] == ["07:00", "08:00", "08:00"]
    assert parse_google_rule(google_rule(master), "Europe/Brussels") == master["rule"]
    assert parse_google_rule(["RRULE:FREQ=WEEKLY;WKST=SU"], "Europe/Brussels", master["start"])[
        "weekdays"
    ] == [6]


@pytest.mark.asyncio
async def test_arrive_by_near_now_and_source_snapshots_do_not_self_wake(app):
    owner = app.trips
    owner.router.duration = 300
    item = owner.upsert(
        drive(timing="arrive", start="2026-11-12T08:30:00+00:00", end="2026-11-12T09:30:00+00:00")
    )
    await owner.refresh_routes()
    assert owner.data["resolved"][item["id"]]["start"] == "2026-11-12T09:24:00+00:00"
    event = {"key": "stable", "start": "2026-11-15T12:00:00+00:00", "location": "Stadium", "title": "Match"}
    owner.sources("synthetic", [event], True)
    owner.wake.clear()
    owner.sources("synthetic", [event], True)
    assert not owner.wake.is_set()


@pytest.mark.asyncio
async def test_same_endpoint_manual_distance_and_snapshot_withdrawals_count_once(app):
    app.trips.upsert(drive(origin="Home", destination="Home", manual_km=77))
    await app.trips.refresh_routes()
    snapshot = app.build_snapshot()
    assert sum(interval.withdrawal_kwh for interval in snapshot.intervals) == pytest.approx(77 * 0.18)
    with pytest.raises(ValueError, match="fixed start and end"):
        app.trips.upsert(drive(origin="Home", destination="Home", manual_km=77, timing="depart"))


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_routing", [False, True])
async def test_duplicate_feed_occurrence_has_one_match_and_replaces_all_legacy_ids(app, legacy_routing):
    sources = [
        {"id": name, "label": name, "url": f"https://calendar.example/{name}", "routing": legacy_routing}
        for name in ("first", "second")
    ]
    app.calendars = CalendarSync(app, sources)
    event = {
        "uid": "same-source-occurrence",
        "recurrence_id": "",
        "key": "stable-occurrence",
        "title": "Synthetic match",
        "start": "2026-11-15T12:00:00+00:00",
        "location": "Synthetic stadium",
    }
    for source in sources:
        app.calendars.cache[source["id"]] = {
            "events": [event],
            "all_known": True,
            "last_success": app.now().isoformat(),
        }
    app.trips.enable()
    assert len(app.trips.data["matches"]) == 1
    match = next(iter(app.trips.data["matches"].values()))
    assert len(match["event"]["legacy_ids"]) == 2
    app.goals = tuple(
        Goal(identity, "Legacy copy", datetime(2026, 11, 15, tzinfo=UTC), kind="trip", distance_km=80)
        for identity in match["event"]["legacy_ids"]
    )
    await app.trips.refresh_routes()
    assert len(app.goals) == 2 and all(goal.id.startswith("drive-") for goal in app.goals)
    assert sum(goal.distance_km for goal in app.goals) == 80
    app.trips.wake.clear()
    app.calendars.reconcile()
    assert not app.trips.wake.is_set()
