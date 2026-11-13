"""Exercise the real adapters against local, explicitly synthetic HTTP endpoints."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from energymanager.calendar_oauth import CalendarOAuth
from energymanager.google_calendar import GoogleCalendarClient
from energymanager.service import Application
from energymanager.store import Store
from energymanager.trip_sync import TripSync
from tools.trip_calendar_preview import SyntheticProviders


@pytest.mark.asyncio
async def test_native_weekly_master_instance_edit_and_delete(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store)
    app.now = lambda: datetime(2026, 11, 12, 9, tzinfo=UTC)
    owner = app.trips
    master = owner.upsert(
        {
            "mode": "distance_only",
            "timing": "fixed",
            "manual_km": 20,
            "start": "2026-11-15T09:00:00+00:00",
            "end": "2026-11-15T10:00:00+00:00",
            "rule": {"weeks": 1, "weekdays": [6], "until": None},
        }
    )
    fake = SyntheticProviders()
    async with TestServer(fake.app()) as endpoint, aiohttp.ClientSession() as session:
        sync = TripSync(
            owner.trips, GoogleCalendarClient(session, "synthetic", str(endpoint.make_url("/calendar/v3")))
        )
        owner.sync = sync
        sync.connect("synthetic-ev")
        await sync.reconcile()
        assert sync.status == "synchronized"
        assert len(fake.events) == 1 and fake.events["em" + master["id"]]["recurrence"]
        child = next(
            trip for trip in owner.trips.state["trips"].values() if trip.get("series") == master["id"]
        )
        owner.upsert({**child, "manual_km": 44}, child["id"])
        await sync.reconcile()
        assert sync.status == "synchronized"
        instance = next(event for event in fake.events.values() if event.get("recurringEventId"))
        assert instance["extendedProperties"]["private"]["em_km"] == "44"
        current = owner.trips.state["trips"][child["id"]]
        # A routed same-endpoint override can return to calculated distance; for
        # this distance-only fixture keep positive km until changing its mode.
        owner.upsert(
            {
                **current,
                "mode": "routed",
                "origin": "Home",
                "destination": "Synthetic city",
                "manual_km": None,
            },
            child["id"],
        )
        await sync.reconcile()
        assert "em_km" not in fake.events[instance["id"]]["extendedProperties"]["private"]
        owner.delete(child["id"])
        await sync.reconcile()
        assert fake.events[instance["id"]]["status"] == "cancelled"
        assert not owner.trips.pending()
        await sync.renew_channel("https://synthetic.invalid/push", app.now())
        assert sync.webhook(
            {
                "x-goog-channel-id": sync.state["channel"]["id"],
                "x-goog-resource-id": "synthetic-resource",
                "x-goog-channel-token": sync.state["channel"]["token"],
            }
        )
    store.close()


@pytest.mark.asyncio
async def test_oauth_state_pkce_refresh_and_secrets_stay_server_side(tmp_path):
    calls = []

    async def token(request):
        body = dict(await request.post())
        calls.append(body)
        return web.json_response(
            {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh", "expires_in": 3600}
        )

    fake = web.Application()
    fake.router.add_post("/token", token)

    async def empty_calendar(request):
        return web.json_response({"nextSyncToken": "synthetic-empty-complete"})

    fake.router.add_get("/empty/calendars/{calendar}/events", empty_calendar)
    store = Store(tmp_path / "synthetic.sqlite")
    async with TestServer(fake) as endpoint, aiohttp.ClientSession() as session:
        empty = GoogleCalendarClient(session, "synthetic", str(endpoint.make_url("/empty")))
        assert await empty.changes("synthetic") == ([], "synthetic-empty-complete")
        oauth = CalendarOAuth(store, session, str(endpoint.make_url("/token")))
        oauth.configure(
            {
                "client_id": "synthetic-client",
                "client_secret": "synthetic-secret",
                "redirect_uri": "https://synthetic.invalid/api/ev/calendar/callback",
                "webhook_uri": "https://synthetic.invalid/api/ev/calendar/push",
            }
        )
        url = oauth.begin()
        query = parse_qs(urlsplit(url).query)
        assert query["code_challenge_method"] == ["S256"] and query["access_type"] == ["offline"]
        with pytest.raises(ValueError):
            await oauth.callback("incorrect-state", "synthetic-code")
        await oauth.callback(query["state"][0], "synthetic-code")
        assert calls[0]["code_verifier"]
        with pytest.raises(ValueError):
            await oauth.callback(query["state"][0], "synthetic-code")
        assert await oauth.access_token() == "synthetic-access"
        oauth.data["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        assert await oauth.access_token() == "synthetic-access"
        assert calls[-1]["grant_type"] == "refresh_token"
        assert "synthetic-secret" not in str(oauth.status()) and "synthetic-refresh" not in str(
            oauth.status()
        )
    store.close()
