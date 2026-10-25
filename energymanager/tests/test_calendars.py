"""SYNTHETIC subscriptions and events; never contact a real calendar or HA."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from energymanager import calendars
from energymanager.calendars import CalendarSync, calendar_sources, parse_calendar
from energymanager.domain import Goal
from energymanager.service import Application
from energymanager.settings import SettingsValidationError
from energymanager.store import Store
from test_first_slice import tiny
from test_settings import configuration_file

NOW = datetime(2026, 10, 24, 10, tzinfo=UTC)
SOURCE = {"id": "referee", "label": "SYNTHETIC referee", "url": "https://calendar.example/referee"}


def feed(*events: str) -> bytes:
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + "\r\n".join(
        "BEGIN:VEVENT\r\n" + event + "\r\nEND:VEVENT" for event in events) + "\r\nEND:VCALENDAR\r\n").encode()


def event(start: str = "20261025T180000Z", title: str = "SYNTHETIC match") -> str:
    return f"UID:match-1\r\nDTSTART:{start}\r\nSUMMARY:{title}\r\nLOCATION:Test hall\\, Test town"


def test_settings_multiple_labelled_links_backup_validation_and_legacy_absence(tmp_path):
    editor = configuration_file(tmp_path)
    before = editor.path.read_bytes()
    sources = [SOURCE, {"id": "second", "label": "Another calendar", "url": "webcal://example.org/events"}]
    result = editor.save(editor.read()["revision"], {"calendars": sources})
    assert result["values"]["calendars"][1]["url"] == "https://example.org/events"
    assert (editor.path.parent / result["backup"]).read_bytes() == before
    assert result["restart_required"]
    for invalid in ([SOURCE, SOURCE], [{**SOURCE, "label": ""}], [{**SOURCE, "url": "file:///tmp/events"}],
                    [{**SOURCE, "url": "https://user:secret@example.org/feed"}]):
        with pytest.raises(SettingsValidationError):
            editor.save(editor.read()["revision"], {"calendars": invalid})
    assert calendar_sources(None) == []


def test_invalid_calendar_in_hand_edited_configuration_keeps_editor_available(tmp_path):
    import json
    from energymanager.configuration import configured_application

    editor = configuration_file(tmp_path)
    data = json.loads(editor.path.read_bytes())
    data["calendars"] = [{**SOURCE, "url": "file:///private"}]
    editor.path.write_text(json.dumps(data))
    store = Store(tmp_path / "synthetic.sqlite")
    app = configured_application(editor.path, store)
    assert app.configuration_error and app.ha is None and app.accepted is None
    assert "calendars" in editor.read()["issues"]
    store.close()


def test_parser_folding_escaping_timezone_cancellation_and_all_day():
    body = feed(event().replace("SUMMARY:SYNTHETIC match", "SUMMARY:SYNTHETIC folded\r\n+ title").replace("\r\n+", "\r\n "),
                "UID:all-day\r\nDTSTART;VALUE=DATE:20261026\r\nSUMMARY:No departure time",
                "UID:cancelled\r\nDTSTART:20261026T190000Z\r\nSTATUS:CANCELLED",
                "UID:local\r\nDTSTART;TZID=Europe/Brussels:20261025T190000\r\nSUMMARY:After clock change")
    events, skipped = parse_calendar(body, NOW, "Europe/Brussels")
    assert skipped == 1 and len(events) == 2
    assert events[0]["location"] == "Test hall, Test town"
    assert events[0]["title"] == "SYNTHETIC folded title"
    assert events[1]["start"] == "2026-10-25T18:00:00+00:00"
    shifted, _ = parse_calendar(feed(event("20261026T180000Z")), NOW, "Europe/Brussels")
    assert events[0]["key"] == shifted[0]["key"]  # Nonrecurring UID survives a time change.


def test_recurrence_exceptions_and_cancelled_instance_keep_stable_identity():
    body = feed("UID:weekly\r\nDTSTART;TZID=Europe/Brussels:20261024T190000\r\n"
                "RRULE:FREQ=DAILY;COUNT=4\r\nEXDATE;TZID=Europe/Brussels:20261025T190000\r\nSUMMARY:SYNTHETIC series",
                "UID:weekly\r\nRECURRENCE-ID;TZID=Europe/Brussels:20261026T190000\r\n"
                "DTSTART;TZID=Europe/Brussels:20261026T200000\r\nSUMMARY:Moved instance",
                "UID:weekly\r\nRECURRENCE-ID;TZID=Europe/Brussels:20261027T190000\r\n"
                "DTSTART;TZID=Europe/Brussels:20261027T190000\r\nSTATUS:CANCELLED")
    events, _ = parse_calendar(body, NOW, "Europe/Brussels")
    assert [item["start"] for item in events] == ["2026-10-24T17:00:00+00:00", "2026-10-26T19:00:00+00:00"]
    assert len({item["key"] for item in events}) == 2
    moved, _ = parse_calendar(body.replace(b"20261026T200000", b"20261026T210000"), NOW, "Europe/Brussels")
    assert moved[-1]["key"] == events[-1]["key"]


@pytest.mark.parametrize("body", [b"<html>Login required</html>", feed("DTSTART:20261025T180000Z"),
                                  feed(event() + "\r\nRRULE:FREQ=SECONDLY"), feed(event(), event())])
def test_invalid_feeds_are_not_successful_empty_snapshots(body):
    with pytest.raises(ValueError):
        parse_calendar(body, NOW, "Europe/Brussels")


async def test_sync_revisions_failure_restart_removal_and_source_ownership(tmp_path, monkeypatch):
    store = Store(tmp_path / "synthetic.sqlite")
    snapshot = tiny()
    app = Application(store, snapshot=snapshot, policy=snapshot.policy)
    app.now = lambda: NOW
    manual = Goal("manual", "Keep explicit goal", NOW + timedelta(hours=3))
    app.goals = (manual,)
    body = feed(event())

    async def fetch(url):
        assert url == SOURCE["url"]
        return body

    monkeypatch.setattr(calendars, "fetch_calendar", fetch)
    sync = CalendarSync(app, [SOURCE])
    app.calendars = sync
    await sync.refresh()
    imported = app.goals[1]
    assert imported.kind == "trip" and imported.distance_km == 50
    assert imported.return_at - imported.deadline == timedelta(hours=4)
    assert app.state()["schedule_goals"][1]["calendar"]["placeholder"] is True
    assert sum(i.withdrawal_kwh for i in app.build_snapshot().intervals) == pytest.approx(9)
    revision = app.revision
    await sync.refresh()
    assert app.revision == revision and app.goals[1] == imported
    with pytest.raises(ValueError, match="managed"):
        app.upsert_goal({"id": imported.id})
    with pytest.raises(ValueError, match="managed"):
        app.delete_goal(imported.id)
    app.goals = (manual, replace(imported, approval_state="granted", approval_revision=1, approved_peak_kw=6))
    body = feed(event("20261026T180000Z"))
    await sync.refresh()
    updated = app.goals[1]
    assert updated.id == imported.id and updated.revision == 2 and updated.approval_state == "none"
    body = b"<html>server error with private token</html>"
    await sync.refresh()
    assert app.goals[1] == updated and sync.status()[0]["error"]
    restored = CalendarSync(app, [SOURCE])
    restored.reconcile()
    assert app.goals[1] == updated
    assert "https://" not in str(app.state()["calendars"])
    restarted = Application(store, snapshot=snapshot, policy=snapshot.policy)
    restarted.now = lambda: NOW
    CalendarSync(restarted, [SOURCE]).reconcile()
    assert restarted.goals[1] == updated
    CalendarSync(restarted, [{**SOURCE, "url": "https://calendar.example/new-link"}]).reconcile()
    assert restarted.goals == (manual,)  # Changed URL cannot revive the old feed snapshot.
    body = feed(event("20261026T180000Z") + "\r\nSTATUS:CANCELLED")
    await sync.refresh()
    assert app.goals == (manual,)
    body = feed(event())
    await sync.refresh()
    CalendarSync(app, []).reconcile()
    assert app.goals == (manual,)
    await app.close()
    store.close()


async def test_multiple_feeds_deduplicate_same_occurrence_and_isolate_failure(tmp_path, monkeypatch):
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=tiny())
    app.now = lambda: NOW
    app.goals = ()
    sources = [SOURCE, {"id": "other", "label": "Other", "url": "https://calendar.example/other"}]
    failing = False

    async def fetch(url):
        if failing and url == SOURCE["url"]:
            raise TimeoutError("private subscription URL must not leak")
        return feed(event())

    monkeypatch.setattr(calendars, "fetch_calendar", fetch)
    sync = CalendarSync(app, sources)
    await sync.refresh()
    assert len(app.goals) == 1
    failing = True
    await sync.refresh()
    assert len(app.goals) == 1
    assert sync.status()[0]["error"] and sync.status()[1]["error"] is None
    store.close()


async def test_downloader_rejects_private_literal_and_resolved_addresses(monkeypatch):
    for url in ("https://127.0.0.1/feed", "https://[::1]/feed", "https://169.254.169.254/feed"):
        with pytest.raises(ValueError, match="public"):
            await calendars.fetch_calendar(url)

    async def private(*args, **kwargs):
        return [{"host": "172.30.32.2"}]

    monkeypatch.setattr(calendars.ThreadedResolver, "resolve", private)
    resolver = calendars.PublicCalendarResolver()
    with pytest.raises(ValueError, match="public"):
        await resolver.resolve("synthetic.invalid")
    await resolver.close()


async def test_sync_endpoint_does_not_block_state_and_reports_source_failure(tmp_path, monkeypatch):
    import asyncio
    from aiohttp.test_utils import TestClient, TestServer
    from energymanager.web import create_web

    app = Application(Store(tmp_path / "synthetic.sqlite"), snapshot=tiny())
    app.now = lambda: NOW
    app.goals = ()
    app.calendars = CalendarSync(app, [SOURCE])
    entered, released = asyncio.Event(), asyncio.Event()

    async def fetch(url):
        entered.set()
        await released.wait()
        return feed(event())

    async def no_lifecycle():
        pass

    monkeypatch.setattr(calendars, "fetch_calendar", fetch)
    app.start = no_lifecycle
    app.close = no_lifecycle
    async with TestClient(TestServer(create_web(app))) as client:
        pending = asyncio.create_task(client.post("/api/calendars/sync", json={}, headers={"X-EnergyManager": "1"}))
        await entered.wait()
        async with asyncio.timeout(1):
            response = await client.get("/api/state")
            assert response.status == 200 and (await response.json())["goals"] == []
        released.set()
        response = await pending
        assert response.status == 200
        assert (await response.json())["calendars"][0]["events"] == 1
        assert (await (await client.get("/api/state")).json())["goals"][0]["distance_km"] == 50
