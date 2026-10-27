"""SYNTHETIC destinations, Google results and phone actions; no installation calls."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from energymanager.calendars import CalendarSync, calendar_sources
from energymanager.domain import Goal
from energymanager.journeys import Journeys
from energymanager.notifications import Notifications, NotificationTarget
from energymanager.routing import JourneyEstimate, RoutingUnavailable
from energymanager.service import Application
from energymanager.store import Store
from test_first_slice import tiny
from test_settings import configuration_file

NOW = datetime(2030, 1, 1, 10, tzinfo=UTC)


class SyntheticInputs:
    def view(self, *args):
        return None


class SyntheticHA:
    inputs = SyntheticInputs()

    def __init__(self):
        self.calls = []

    async def entity_state(self, entity):
        assert entity == "zone.home"
        return {"entity_id": entity, "attributes": {"latitude": 50, "longitude": 4}}

    async def service(self, domain, service, data):
        assert domain == "notify" and service == "mobile_app_synthetic"
        self.calls.append(data)

    async def __aexit__(self):
        pass


class SyntheticRouter:
    def __init__(self):
        self.calls = []
        self.failure = False
        self.wait = None

    async def journey(self, home, destination, arrival, venue_departure, *, traffic_aware):
        self.calls.append((destination, arrival, venue_departure, traffic_aware))
        if self.wait:
            await self.wait.wait()
        if self.failure:
            raise RoutingUnavailable("SYNTHETIC provider failure")
        return JourneyEstimate(arrival - timedelta(minutes=30), venue_departure + timedelta(minutes=40), 89)


@pytest.fixture
async def routed_app(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=tiny(), demo=False)
    app.now = lambda: NOW
    app.ha = SyntheticHA()
    router = SyntheticRouter()
    app.journeys = Journeys(app, router=router)
    app.notifications = Notifications(store, app.ha, NotificationTarget("notify.mobile_app_synthetic", "action"))
    yield app, app.journeys, router
    await app.close()
    store.close()


def request(**changes):
    return {"title": "SYNTHETIC visit", "destination": "SYNTHETIC venue", "priority": 45,
            "arrival": (NOW + timedelta(hours=4)).isoformat(),
            "venue_departure": (NOW + timedelta(hours=6)).isoformat(), **changes}


def source_event(**changes):
    return {"key": "event-1", "uid": "event-1", "start": (NOW + timedelta(hours=5)).isoformat(),
            "location": "SYNTHETIC hall", "title": "SYNTHETIC referee", **changes}


async def test_manual_attendance_routes_separate_legs_into_existing_goal_model(routed_app):
    app, journeys, router = routed_app
    item = journeys.upsert(request())
    assert journeys.needs_attention
    await journeys.refresh()
    goal = next(goal for goal in app.goals if goal.id == item["id"])
    assert goal.deadline == NOW + timedelta(hours=3, minutes=30)
    assert goal.return_at == NOW + timedelta(hours=6, minutes=40)
    assert goal.distance_km == 89 and goal.priority == 45
    assert router.calls[0][3] is True
    assert journeys.status()["items"][0]["provider"] == "Google Maps"
    assert not journeys.needs_attention


async def test_route_failure_never_uses_placeholder_and_notifies_only_once(routed_app):
    app, journeys, router = routed_app
    item = journeys.upsert(request())
    router.failure = True
    await journeys.refresh()
    await journeys.refresh()
    assert not any(goal.id == item["id"] for goal in app.goals)
    assert journeys.needs_attention and journeys.status()["items"][0]["state"] == "unresolved"
    assert len(app.ha.calls) == 1
    assert "unresolved" in app.ha.calls[0]["message"]


async def test_missing_destination_requires_intervention_without_contacting_provider(routed_app):
    app, journeys, router = routed_app
    journeys.upsert(request(destination=""))
    await journeys.refresh()
    assert router.calls == [] and journeys.needs_attention
    assert len(app.ha.calls) == 1


async def test_calendar_enable_routes_and_disabled_calendar_keeps_labelled_legacy_behavior(routed_app):
    app, journeys, router = routed_app
    enabled = {"id": "ref", "label": "SYNTHETIC ref", "url": "https://example.org/ref", "routing": True}
    calendars = CalendarSync(app, [enabled])
    calendars.cache = {"ref": {"events": [source_event()]}}
    calendars.reconcile()
    assert len(journeys.requests) == 1 and not any(goal.id.startswith("calendar-") for goal in app.goals)
    await journeys.refresh()
    assert router.calls[0][1:3] == (NOW + timedelta(hours=4), NOW + timedelta(hours=7))
    calendars.sources[0]["routing"] = False
    calendars.reconcile()
    assert journeys.requests == {}
    goal = next(goal for goal in app.goals if goal.id.startswith("calendar-"))
    assert goal.distance_km == 50 and goal.deadline == NOW + timedelta(hours=5)
    assert app.calendar_items[goal.id]["placeholder"]


async def test_persistent_calendar_override_survives_refresh_and_can_reset(routed_app):
    app, journeys, router = routed_app
    identity = "calendar-synthetic"
    journeys.calendar(identity, "SYNTHETIC", source_event())
    manual = {"deadline": (NOW + timedelta(hours=2)).isoformat(),
              "return_at": (NOW + timedelta(hours=9)).isoformat(), "distance_km": 123}
    journeys.upsert(request(destination="User correction", override=manual), identity)
    journeys.calendar(identity, "SYNTHETIC", source_event(location="Changed source venue"))
    await journeys.refresh()
    goal = next(goal for goal in app.goals if goal.id == identity)
    assert goal.distance_km == 123 and goal.deadline == NOW + timedelta(hours=2)
    assert journeys.effective(identity)["destination"] == "User correction"
    assert router.calls == []
    restarted = Journeys(app, router=router)
    assert restarted.effective(identity)["override"]["distance_km"] == 123
    journeys.reset(identity)
    await journeys.refresh()
    assert router.calls[-1][0] == "Changed source venue"
    assert next(goal for goal in app.goals if goal.id == identity).revision > goal.revision


async def test_cancelled_event_cannot_adopt_in_flight_route(routed_app):
    app, journeys, router = routed_app
    identity = "calendar-synthetic"
    journeys.calendar(identity, "SYNTHETIC", source_event())
    router.wait = asyncio.Event()
    task = asyncio.create_task(journeys.refresh())
    await asyncio.sleep(0)
    journeys.retain_calendars(set())
    router.wait.set()
    await task
    assert identity not in journeys.requests
    assert not any(goal.id == identity for goal in app.goals)


async def test_changed_request_rejects_response_and_revokes_existing_peak_permission(routed_app):
    app, journeys, router = routed_app
    item = journeys.upsert(request())
    await journeys.refresh()
    first = next(goal for goal in app.goals if goal.id == item["id"])
    journeys.upsert(request(destination="SYNTHETIC changed"), item["id"])
    assert journeys.needs_attention and not any(goal.id == first.id for goal in app.goals)
    router.wait = asyncio.Event()
    task = asyncio.create_task(journeys.refresh())
    await asyncio.sleep(0)
    journeys.upsert(request(destination="SYNTHETIC latest"), item["id"])
    router.wait.set()
    await task
    assert not any(goal.id == first.id for goal in app.goals)
    await journeys.refresh()
    current = next(goal for goal in app.goals if goal.id == first.id)
    assert current.revision > first.revision and current.approval_state == "none"


async def test_daily_refresh_horizon_and_in_progress_trip_are_bounded(routed_app):
    app, journeys, router = routed_app
    item = journeys.upsert(request())
    await journeys.refresh()
    await journeys.refresh(force=False)
    assert len(router.calls) == 1
    app.now = lambda: NOW + timedelta(hours=4)
    await journeys.refresh()
    assert len(router.calls) == 1
    future = journeys.upsert(request(arrival=(NOW + timedelta(days=9)).isoformat(),
                                    venue_departure=(NOW + timedelta(days=9, hours=2)).isoformat()))
    await journeys.refresh()
    assert len(router.calls) == 1
    assert next(i for i in journeys.status()["items"] if i["id"] == future["id"])["state"] == "outside_horizon"
    assert next(goal for goal in app.goals if goal.id == item["id"]).deadline < app.now()


async def test_no_key_keeps_routing_inactive_without_contacting_google(routed_app, monkeypatch):
    app, _, _ = routed_app
    def forbidden(*args, **kwargs):
        raise AssertionError("No live request is allowed")
    monkeypatch.setattr("energymanager.routing.aiohttp.ClientSession", forbidden)
    journeys = Journeys(app)
    journeys.upsert(request())
    await journeys.refresh()
    assert journeys.needs_attention and journeys.status()["live_available"] is False
    assert journeys.router.client.allow_requests is False


async def test_existing_manual_trip_can_be_converted_to_destination_request(routed_app):
    app, journeys, _ = routed_app
    old = Goal("user-trip", "SYNTHETIC old", NOW + timedelta(hours=2), kind="trip", distance_km=20)
    app.goals += (old,)
    journeys.upsert(request(), old.id)
    assert not any(goal.id == old.id for goal in app.goals)
    await journeys.refresh()
    assert next(goal for goal in app.goals if goal.id == old.id).revision > old.revision
    with pytest.raises(ValueError):
        app.upsert_goal({"id": old.id, "title": "Bypass", "deadline": (NOW + timedelta(hours=2)).isoformat()})


def test_calendar_toggle_is_optional_strict_and_backwards_compatible():
    source = {"id": "ref", "label": "Ref", "url": "https://example.org/feed"}
    assert calendar_sources([source]) == [source]
    assert calendar_sources([{**source, "routing": True}])[0]["routing"] is True
    with pytest.raises(ValueError):
        calendar_sources([{**source, "routing": "yes"}])


def test_key_is_write_only_preserved_on_blank_replaceable_and_explicitly_clearable(tmp_path):
    editor = configuration_file(tmp_path)
    key = "synthetic-only-secret"
    result = editor.save(editor.read()["revision"], {"maps.api_key": key})
    assert key not in json.dumps(result)
    assert result["secrets"]["maps.api_key"] and not result["restart_required"]
    result = editor.save(result["revision"], {"maps.api_key": ""})
    assert editor.routing_settings()["api_key"] == key
    result = editor.save(result["revision"], {"maps.api_key": None})
    assert not result["secrets"]["maps.api_key"] and editor.routing_settings()["api_key"] == ""


@pytest.mark.parametrize("changes", [
    {"arrival": (NOW - timedelta(hours=1)).isoformat()},
    {"venue_departure": (NOW + timedelta(hours=1)).isoformat()},
    {"priority": True}, {"override": {"distance_km": 10}},
    {"arrival": None}, {"arrival": 42}, {"venue_departure": []},
    {"override": {"deadline": None, "return_at": (NOW + timedelta(hours=8)).isoformat(), "distance_km": 10}},
    {"override": {"deadline": (NOW + timedelta(hours=2)).isoformat(), "return_at": 42, "distance_km": 10}},
])
async def test_invalid_attendance_or_override_cannot_change_requests(routed_app, changes):
    app, journeys, _ = routed_app
    with pytest.raises((ValueError, TypeError)):
        journeys.upsert(request(**changes))
    assert journeys.requests == {}


async def test_notification_retries_independently_and_a_new_episode_can_notify(routed_app):
    app, journeys, router = routed_app
    journeys.upsert(request())
    calls = []
    async def failed_service(*args):
        calls.append(args)
        if len(calls) == 1:
            raise RuntimeError("SYNTHETIC delivery failure")
    app.ha.service = failed_service
    router.failure = True
    await journeys.refresh()
    assert len(calls) == 1
    app.now = lambda: NOW + timedelta(seconds=61)
    await journeys.refresh(force=False)
    assert len(calls) == 2
    router.failure = False
    await journeys.refresh()
    app.now = lambda: NOW + timedelta(seconds=122)
    router.failure = True
    await journeys.refresh()
    assert len(calls) == 3


async def test_new_pending_request_preserves_unrelated_command_authority(routed_app):
    app, journeys, router = routed_app
    before = app.revision
    app.ev_valid = True
    journeys.upsert(request())
    assert app.revision == before and app.ev_valid
    assert router.calls == []


async def test_journey_api_mutations_use_same_origin_boundary_and_async_worker(tmp_path):
    from aiohttp.test_utils import TestClient, TestServer
    from energymanager.web import create_web
    app = Application(Store(tmp_path / "synthetic-api.sqlite"), snapshot=tiny(), demo=False)
    app.now = lambda: NOW
    app.ha = SyntheticHA()
    app.journeys = Journeys(app, router=SyntheticRouter())
    async def start():
        app.journeys.start()
    app.start = start
    async with TestClient(TestServer(create_web(app))) as client:
        denied = await client.post("/api/journeys", json=request())
        assert denied.status == 403
        response = await client.post("/api/journeys", json=request(), headers={"X-EnergyManager": "1"})
        assert response.status == 201
        identity = (await response.json())["id"]
        response = await client.post(f"/api/journeys/{identity}", json={**request(), "approved_peak_kw": 17},
                                     headers={"X-EnergyManager": "1"})
        assert response.status == 400
        state = await (await client.get("/api/state")).json()
        assert state["routes"]["items"][0]["id"] == identity
        response = await client.post("/api/journeys/refresh", json={}, headers={"X-EnergyManager": "1"})
        assert response.status == 202
        response = await client.delete(f"/api/journeys/{identity}", json={}, headers={"X-EnergyManager": "1"})
        assert response.status == 200
        assert app.journeys.requests == {}


async def test_restart_reconciles_unchanged_route_before_retaining_scoped_approval(routed_app):
    from dataclasses import replace
    app, journeys, router = routed_app
    item = journeys.upsert(request())
    await journeys.refresh()
    old = next(goal for goal in app.goals if goal.id == item["id"])
    approved = replace(old, approval_state="granted", approval_revision=old.revision, approved_peak_kw=5)
    app.goals = tuple(approved if goal.id == old.id else goal for goal in app.goals)
    restarted = Journeys(app, router=router)
    restarted.start()
    assert not any(goal.id == old.id for goal in app.goals)
    assert restarted.needs_attention
    await restarted.refresh()
    current = next(goal for goal in app.goals if goal.id == old.id)
    assert current.revision == old.revision and current.approved_peak_kw == 5
    await restarted.close()


async def test_unresolved_route_does_not_stop_a_real_valid_unrelated_ev_plan(routed_app):
    from dataclasses import replace
    from energymanager.domain import json_data
    from energymanager.optimization import JointModel
    app, journeys, router = routed_app
    snapshot = tiny(hours=1, ev=24, ess=2.8, house=0.4)
    goal = Goal("independent", "SYNTHETIC independent readiness", snapshot.intervals[-1].end, 42)
    snapshot = replace(snapshot, goals=(goal,))
    solved = JointModel(snapshot).run(5)
    assert solved["feasible"]
    plan = {"id": "synthetic-independent-plan", "flows": solved["flows"],
            "intervals": json_data(snapshot.intervals), "reasons": [], "goals": []}
    index = next(i for i, power in enumerate(solved["flows"]["grid_ev"]) if power > 0.1)
    at = snapshot.intervals[index].start
    app.now = lambda: at
    app.observation = replace(snapshot.observation, at=at, ev_kwh=solved["flows"]["ev_energy"][index])
    app.goals = (goal,)
    app.accepted = plan
    app.ev_valid = app.ess_valid = app.conditional_valid = True
    item = journeys.upsert(request(arrival=(at + timedelta(hours=4)).isoformat(),
                                   venue_departure=(at + timedelta(hours=6)).isoformat()))
    router.failure = True
    await journeys.refresh()
    assert journeys.needs_attention and not any(g.id == item["id"] for g in app.goals)
    assert app.state()["ev_plan_valid"] is True
    await app.protect("SYNTHETIC independent-work verification")
    assert app.current_command.ev_kw > 0.1
    app.observation = replace(app.observation, connected=False)
    await app.protect("SYNTHETIC disconnect verification")
    from energymanager.control import GuardedActuator
    writes = []
    class SyntheticActuatorClient:
        async def service(self, domain, service, data):
            writes.append((domain, service, data))
    actuator = GuardedActuator(SyntheticActuatorClient(), {
        "force": "select.synthetic_force", "current": "number.synthetic_current",
        "phase": "select.synthetic_phase", "ess_setpoint": "number.synthetic_ess"},
        snapshot.capabilities, enabled=True)
    await actuator.apply(app.current_command, app.revision, app.observation)
    assert any(data.get("entity_id") == "select.synthetic_force" and data.get("option") == "1"
               for _, _, data in writes)
    assert not any(data.get("entity_id") == "select.synthetic_force" and data.get("option") == "2"
                   for _, _, data in writes)


async def test_unrepresentable_route_times_leave_trip_unresolved_and_worker_can_continue(routed_app):
    from energymanager.routing import GoogleRoutesClient, RefereeJourneyRouter, RouteLeg
    app, _, _ = routed_app

    class SyntheticRoutes(GoogleRoutesClient):
        async def leg(self, origin, destination, departure, *, traffic_aware):
            return RouteLeg(40, 1e20 if destination == "SYNTHETIC invalid duration" else 1800)

    journeys = Journeys(app, router=RefereeJourneyRouter(SyntheticRoutes("synthetic-key")))
    app.journeys = journeys
    bad = journeys.upsert(request(destination="SYNTHETIC invalid duration"))
    good = journeys.upsert(request(destination="SYNTHETIC valid venue"))
    await journeys.refresh()
    states = {item["id"]: item["state"] for item in journeys.status()["items"]}
    assert states == {bad["id"]: "unresolved", good["id"]: "resolved"}
    assert [goal.id for goal in app.goals if goal.id in (bad["id"], good["id"])] == [good["id"]]


@pytest.mark.parametrize("checked", [False, True])
async def test_route_edit_respects_latest_planning_replacement_rules(routed_app, monkeypatch, checked):
    from dataclasses import replace
    app, journeys, _ = routed_app
    item = journeys.upsert(request())
    if checked:
        await journeys.refresh()
    app.ev_valid = app.ess_valid = True
    app.accepted = {"id": "synthetic-prior-plan"}
    started = asyncio.Event()

    async def calculate(snapshot, request_id):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(app, "calculate_plan", calculate)
    app.request_plan("synthetic-route-compatibility")
    app.requested.clear()
    revision, request_id = app.revision, app.planning_request_id
    work = asyncio.create_task(app.run_calculation(replace(app.snapshot, revision=revision)))
    try:
        await asyncio.wait_for(started.wait(), 2)
        journeys.upsert(request(destination="SYNTHETIC revised venue"), item["id"])
        if checked:
            assert app.revision > revision and app.planning_request_id != request_id
            assert await asyncio.wait_for(work, 2) is None
            assert not app.ev_valid and app.ess_valid
        else:
            await asyncio.sleep(0)
            assert not work.done() and not app.requested.is_set()
            assert app.revision == revision and app.planning_request_id == request_id
            assert app.ev_valid and app.ess_valid
        assert app.accepted["id"] == "synthetic-prior-plan"
    finally:
        work.cancel()
        await asyncio.gather(work, return_exceptions=True)


async def test_route_warning_and_new_planner_failure_notice_remain_visible_together(routed_app):
    app, journeys, router = routed_app
    issue = {"id": "synthetic-planning-issue", "kind": "planning", "state": "attention_required"}
    app.store.put("planning_issue", issue)
    journeys.upsert(request())
    router.failure = True
    await journeys.refresh()
    state = app.state()
    assert issue in state["issues"]
    assert state["routes"]["items"][0]["state"] == "unresolved"


async def test_saving_key_activates_and_clearing_key_stops_routing_without_restart(tmp_path, monkeypatch):
    from aiohttp.test_utils import TestClient, TestServer
    from energymanager.routing import GoogleRoutesClient, RouteLeg
    from energymanager.web import create_web
    calls = []

    async def synthetic_leg(client, origin, destination, departure, *, traffic_aware):
        assert client.allow_requests and traffic_aware
        calls.append(client.api_key)
        if client.api_key == "synthetic-rejected":
            raise RoutingUnavailable("SYNTHETIC HTTP 403")
        return RouteLeg(40, 1800)

    monkeypatch.setattr(GoogleRoutesClient, "leg", synthetic_leg)
    app = Application(Store(tmp_path / "synthetic-key-activation.sqlite"), snapshot=tiny(), demo=False)
    app.now = lambda: NOW
    app.ha = SyntheticHA()
    editor = configuration_file(tmp_path)
    server = create_web(app, configuration=editor)
    async def start():
        app.journeys.start()
    app.start = start
    headers = {"X-EnergyManager": "1"}
    async with TestClient(TestServer(server)) as client:
        response = await client.post("/api/journeys", json=request(), headers=headers)
        identity = (await response.json())["id"]
        async def wait_for(state):
            async with asyncio.timeout(3):
                while app.journeys.results.get(identity, {}).get("state") != state:
                    await asyncio.sleep(.01)
        await wait_for("unresolved")
        assert not calls
        for key, expected in [("synthetic-rejected", "unresolved"), ("synthetic-valid", "resolved"), (None, "unresolved")]:
            revision = editor.read()["revision"]
            response = await client.post("/api/settings", json={"revision": revision, "values": {"maps.api_key": key}}, headers=headers)
            assert response.status == 200
            saved = await response.json()
            assert not saved["restart_required"]
            assert key is None or key not in json.dumps(saved)
            await wait_for(expected)
            assert app.journeys.status()["live_available"] is (key is not None)
            assert any(goal.id == identity for goal in app.goals) is (expected == "resolved")
        assert calls == ["synthetic-rejected", "synthetic-valid", "synthetic-valid", "synthetic-valid"]


async def test_key_replacement_rejects_old_in_flight_route_results(routed_app, monkeypatch):
    from energymanager.routing import GoogleRoutesClient, RouteLeg
    app, journeys, router = routed_app
    router.wait = asyncio.Event()
    item = journeys.upsert(request())
    task = asyncio.create_task(journeys.refresh())
    await asyncio.sleep(0)
    journeys.apply_settings({"api_key": "synthetic-new"})
    router.wait.set()
    await task
    assert not any(goal.id == item["id"] for goal in app.goals)

    async def synthetic_leg(client, *args, **kwargs):
        assert client.api_key == "synthetic-new" and client.allow_requests
        return RouteLeg(40, 1800)
    monkeypatch.setattr(GoogleRoutesClient, "leg", synthetic_leg)
    await journeys.refresh()
    assert next(goal for goal in app.goals if goal.id == item["id"]).distance_km == 80


async def test_key_clear_revokes_old_client_before_it_can_request_another_leg(routed_app, monkeypatch):
    app, _, _ = routed_app
    journeys = Journeys(app, {"api_key": "synthetic-old"})
    old = journeys.router.client
    def forbidden(*args, **kwargs):
        raise AssertionError("A retired key must not issue another HTTP request")
    monkeypatch.setattr("energymanager.routing.aiohttp.ClientSession", forbidden)
    journeys.apply_settings({"api_key": ""})
    with pytest.raises(RoutingUnavailable, match="not been enabled"):
        await old.leg((50, 4), "SYNTHETIC venue", NOW + timedelta(hours=4), traffic_aware=True)
    assert not journeys.status()["live_available"]
