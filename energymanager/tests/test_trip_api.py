"""Public receiver and local editing boundaries against disposable fake endpoints."""

from datetime import UTC, datetime, timedelta

from aiohttp.test_utils import TestClient, TestServer
import pytest

from energymanager.google_calendar import GoogleCalendarClient
from energymanager.service import Application
from energymanager.store import Store
from energymanager.web import create_web
from tools.trip_calendar_preview import SyntheticProviders


@pytest.mark.asyncio
async def test_context_never_becomes_ev_requirement_and_public_push_requires_token(tmp_path):
    fake = SyntheticProviders()
    async with TestServer(fake.app()) as provider:
        store = Store(tmp_path / "synthetic.sqlite")
        app = Application(store)
        app.goals = ()
        app.request_plan = lambda reason, **kwargs: {"requested": False}
        async with TestClient(TestServer(create_web(app))) as client:
            owner = app.trips
            owner.oauth.data["webhook_uri"] = "https://synthetic.invalid/push"
            owner.sync.client = GoogleCalendarClient(
                owner.session, "synthetic", str(provider.make_url("/calendar/v3"))
            )
            headers = {"X-EnergyManager": "1"}
            response = await client.post(
                "/api/ev/calendar",
                headers=headers,
                json={"action": "connect", "calendar": "synthetic-ev", "selected": ["synthetic-work"]},
            )
            assert response.status == 200
            start = datetime.now(UTC)
            end = start + timedelta(days=7)
            response = await client.get(
                "/api/ev/calendar", params={"start": start.isoformat(), "end": end.isoformat()}
            )
            body = await response.json()
            assert body["context"] and all(item["editable"] is False for item in body["context"])
            assert not [goal for goal in app.goals if goal.kind == "trip"]
            response = await client.post("/api/ev/calendar/push")
            assert response.status == 403
            await owner.sync.renew_channel("https://synthetic.invalid/push", app.now())
            channel = owner.sync.state["channel"]
            response = await client.post(
                "/api/ev/calendar/push",
                headers={
                    "X-Goog-Channel-Id": channel["id"],
                    "X-Goog-Resource-Id": channel["resourceId"],
                    "X-Goog-Channel-Token": channel["token"],
                },
            )
            assert response.status == 204
            response = await client.get(
                "/api/ev/calendar/callback", params={"state": "wrong", "code": "synthetic"}
            )
            assert response.status == 400
            response = await client.post("/api/ev/drives", json={})
            assert response.status == 403
            response = await client.post("/api/ev/drives",headers=headers,json=[])
            assert response.status == 400
