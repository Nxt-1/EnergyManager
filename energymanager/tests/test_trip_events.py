from datetime import UTC, datetime

import pytest

from energymanager.store import Store
from energymanager.trip_events import description_with_origin, drive_from_google, google_event, read_origin
from energymanager.trip_store import TripStore


def drive():
    return {
        "id": "a" * 32,
        "revision": 1,
        "title": "Drive to Antwerp",
        "mode": "routed",
        "timing": "depart",
        "start": "2026-11-15T10:00:00+01:00",
        "end": "2026-11-15T11:00:00+01:00",
        "origin": 'Home\n"North"',
        "destination": "Antwerp",
        "manual_km": 42,
    }


def test_wire_roundtrip_and_manual_google_time_change():
    original = drive()
    event = google_event(original, "Personal notes\n")
    restored = drive_from_google(event)
    assert restored["origin"] == original["origin"]
    assert restored["manual_km"] == 42
    assert event["description"].startswith("Personal notes\n")
    event["end"]["dateTime"] = "2026-11-15T11:15:00+01:00"
    assert drive_from_google(event, original)["timing"] == "fixed"
    event["location"] = "Brussels"
    assert drive_from_google(event, original)["end"].endswith("10:15:00+00:00")


def test_origin_and_distance_only_validation():
    assert description_with_origin('Notes\nFrom: "old"\nTail', "new").startswith("Notes\nTail\n")
    with pytest.raises(ValueError):
        read_origin('From: "one"\nFrom: "two"')
    data = {**drive(), "mode": "distance_only", "timing": "fixed", "origin": None, "destination": None}
    assert drive_from_google(google_event(data))["manual_km"] == 42
    with pytest.raises(ValueError):
        google_event({**data, "manual_km": float("nan")})
    with pytest.raises(ValueError):
        google_event({**drive(), "origin": ""})
    direct = {
        "start": {"dateTime": data["start"]},
        "end": {"dateTime": data["end"]},
        "description": 'Personal notes\nEnergyManager: {"v":1,"mode":"distance_only","km":65,"timing":"fixed"}',
    }
    assert drive_from_google(direct)["manual_km"] == 65


def test_outbox_restart_and_stale_ack(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    store = Store(path)
    trips = TripStore(store)
    at = datetime(2026, 11, 12, tzinfo=UTC)
    first = trips.edit(drive(), at, identity="a" * 32)
    second = trips.edit({**drive(), "manual_km": 55}, at, identity=first["id"])
    assert not trips.acknowledge(first["id"], first["revision"])
    assert trips.notice(first["id"], second["revision"], "duration")
    store.close()
    store = Store(path)
    trips = TripStore(store)
    assert trips.pending()[0]["manual_km"] == 55
    assert not trips.notice(first["id"], second["revision"], "duration")
    trips.delete(first["id"], at)
    assert trips.pending()[0]["deleted"]
    automatic = trips.edit(drive(), at, identity=first["id"], actor="automatic")
    assert automatic["deleted"]
    regenerated = trips.edit(drive(), at, identity=first["id"], actor="automatic", source_change=True)
    assert not regenerated["deleted"]
    store.close()
