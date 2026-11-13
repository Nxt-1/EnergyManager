from copy import deepcopy
from datetime import UTC, datetime

import pytest

from energymanager.google_calendar import CalendarError
from energymanager.store import Store
from energymanager.trip_events import google_event
from energymanager.trip_store import TripStore
from energymanager.trip_sync import TripSync


class FakeCalendar:
    """Deterministic in-memory provider; never opens a network connection."""

    def __init__(self):
        self.events = {}
        self.failure = None
        self.lost_insert = False
        self.writes = 0

    async def changes(self, calendar, token=None):
        if self.failure:
            raise CalendarError(self.failure)
        return deepcopy(list(self.events.values())), "synthetic-token"

    async def write(self, calendar, event, etag=None):
        if event["id"] in self.events and etag is None:
            raise CalendarError(409)
        if etag and self.events.get(event["id"], {}).get("etag") != etag:
            raise CalendarError(412)
        self.writes += 1
        result = {**deepcopy(event), "etag": f'"{self.writes}"', "updated": "2026-11-12T09:00:00+00:00"}
        self.events[event["id"]] = result
        if self.lost_insert:
            self.lost_insert = False
            raise OSError("Synthetic interrupted response")
        return result

    async def get(self, calendar, identity):
        return deepcopy(self.events[identity])

    async def delete(self, calendar, identity, etag):
        self.events.pop(identity)


def data():
    return {
        "title": "Drive · 20 km",
        "mode": "distance_only",
        "timing": "fixed",
        "manual_km": 20,
        "start": "2026-11-15T10:00:00+00:00",
        "end": "2026-11-15T11:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_interrupted_insert_restart_and_outage(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    trips = TripStore(store)
    trip = trips.edit(data(), datetime(2026, 11, 12, 10, tzinfo=UTC))
    client = FakeCalendar()
    client.lost_insert = True
    sync = TripSync(trips, client)
    sync.connect("synthetic-calendar")
    await sync.reconcile()
    assert sync.status == "unavailable" and len(trips.pending()) == 1
    sync = TripSync(TripStore(store), client)
    await sync.reconcile()
    await sync.reconcile()
    assert len(client.events) == 1 and client.writes == 1
    assert not sync.trips.pending()
    client.failure = 503
    sync.trips.edit({**data(), "manual_km": 30}, datetime(2026, 11, 12, 11, tzinfo=UTC), identity=trip["id"])
    await sync.reconcile()
    assert sync.status == "unavailable" and sync.trips.pending()[0]["manual_km"] == 30
    sync.disconnect()
    assert len(client.events) == 1 and len(sync.trips.pending()) == 1
    store.close()


@pytest.mark.asyncio
async def test_manual_precedence_google_time_edit_and_restart_idempotence(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    trips = TripStore(store)
    local = trips.edit(data(), datetime(2026, 11, 12, 10, tzinfo=UTC))
    client = FakeCalendar()
    sync = TripSync(trips, client)
    sync.connect("synthetic-calendar")
    older = {**google_event(local), "etag": '"older"', "updated": "2026-11-12T09:00:00+00:00"}
    older["end"] = {"dateTime": "2026-11-15T12:00:00+00:00"}
    sync.ingest(older)
    assert trips.state["trips"][local["id"]]["end"] == local["end"]
    newer = {**older, "etag": '"newer"', "updated": "2026-11-12T11:00:00+00:00"}
    sync.ingest(newer)
    changed = deepcopy(trips.state["trips"][local["id"]])
    assert changed["end"].endswith("12:00:00+00:00") and changed["timing"] == "fixed"
    restarted = TripSync(TripStore(store), client)
    restarted.ingest(newer)
    assert restarted.trips.state["trips"][local["id"]] == changed
    # A manual provider edit beats a later automatic adjustment.
    automatic = restarted.trips.edit(
        data(),
        datetime(2026, 11, 12, 12, tzinfo=UTC),
        identity=local["id"],
        actor="automatic",
        source_change=True,
    )
    restarted.trips.acknowledge(local["id"], automatic["revision"])
    restarted.ingest({**newer, "etag": '"manual-again"'})
    assert restarted.trips.state["trips"][local["id"]]["actor"] == "manual"
    store.close()


@pytest.mark.asyncio
async def test_invalid_sync_token_full_read_and_auth_episode_dedup(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    trips = TripStore(store)
    client = FakeCalendar()
    sync = TripSync(trips, client)
    sync.connect("synthetic-calendar")
    local = trips.edit(data(), datetime(2026, 11, 12, 10, tzinfo=UTC))
    await sync.reconcile()
    original = client.changes

    async def expired(calendar, token=None):
        if token:
            raise CalendarError(410)
        return [], "replacement-token"

    client.changes = expired
    await sync.reconcile()
    assert trips.state["trips"][local["id"]]["deleted"]
    assert sync.state["token"] == "replacement-token"
    client.changes = original
    client.failure = 401
    await sync.reconcile()
    await sync.reconcile()
    count = len(trips.state["notices"])
    restarted = TripSync(TripStore(store), client)
    await restarted.reconcile()
    assert len(restarted.trips.state["notices"]) == count
    client.failure = None
    await restarted.reconcile()
    client.failure = 401
    await restarted.reconcile()
    assert len(restarted.trips.state["notices"]) == count + 1
    store.close()


@pytest.mark.asyncio
async def test_pending_invalid_provider_edit_does_not_get_overwritten(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    trips = TripStore(store)
    client = FakeCalendar()
    sync = TripSync(trips, client)
    local = trips.edit(data(), datetime(2026, 11, 12, 8, tzinfo=UTC))
    event = {**google_event(local), "etag": '"invalid-edit"', "updated": "2026-11-12T09:00:00+00:00"}
    event["extendedProperties"]["private"]["em_mode"] = "routed"
    event["description"] = ""
    client.events[event["id"]] = event
    sync.connect("synthetic-calendar")
    await sync.reconcile()
    assert sync.status == "needs_correction" and client.writes == 0
    assert trips.state["trips"][local["id"]]["mode"] == "distance_only"
    corrected = trips.edit(data(), datetime(2026, 11, 12, 10, tzinfo=UTC), identity=local["id"])
    await sync.reconcile()
    assert not trips.pending() and corrected["revision"] > local["revision"]
    store.close()


@pytest.mark.asyncio
async def test_invalid_edit_last_good_and_webhook_validation(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    trips = TripStore(store)
    trip = trips.edit(data(), datetime(2026, 11, 12, 8, tzinfo=UTC))
    client = FakeCalendar()
    event = google_event(trip)
    event.update(etag='"invalid"', updated="2026-11-12T09:00:00+00:00")
    event["extendedProperties"]["private"]["em_mode"] = "routed"
    event["description"] = ""
    client.events[event["id"]] = event
    sync = TripSync(trips, client)
    sync.connect("synthetic-calendar")
    sync.ingest(event)
    sync.ingest(event)
    assert trips.state["trips"][trip["id"]]["manual_km"] == 20
    assert len(trips.state["notices"]) == 1
    sync.state["channel"] = {"id": "synthetic", "resourceId": "resource", "token": "secret"}
    sync.wake.clear()
    assert not sync.webhook({"X-Goog-Channel-ID": "synthetic"})
    assert not sync.wake.is_set()
    assert sync.webhook(
        {"X-Goog-Channel-ID": "synthetic", "X-Goog-Resource-ID": "resource", "X-Goog-Channel-Token": "secret"}
    )
    store.close()
