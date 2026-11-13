"""Direct Calendar API transport; callers supply OAuth and own durable sync state."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import quote

import aiohttp


class CalendarError(RuntimeError):
    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"Calendar request failed (HTTP {status})")


class GoogleCalendarClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str,
        base_url: str = "https://www.googleapis.com/calendar/v3",
    ) -> None:
        self.session = session
        self.token = token
        self.base_url = base_url.rstrip("/")

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        etag: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}"}
        if etag:
            headers["If-Match"] = etag
        async with (
            asyncio.timeout(25),
            self.session.request(
                method, self.base_url + path, json=body, params=params, headers=headers, allow_redirects=False
            ) as response,
        ):
            if response.status >= 300:
                # Never expose provider responses, tokens or private appointment details as errors.
                raise CalendarError(response.status)
            if response.status == 204:
                return {}
            content = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                content.extend(chunk)
                if len(content) > 8 * 1024 * 1024:
                    raise ValueError("Calendar page exceeds the response size limit")
            document = json.loads(content)
            if not isinstance(document, dict):
                raise ValueError("Invalid Calendar response")
            return document

    @staticmethod
    def events_path(calendar: str) -> str:
        return "/calendars/" + quote(calendar, safe="") + "/events"

    async def calendars(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        params = {"maxResults": "250"}
        while True:
            page = await self.request("GET", "/users/me/calendarList", params=params)
            result.extend(page.get("items", []))
            if not page.get("nextPageToken"):
                return result
            params["pageToken"] = page["nextPageToken"]

    async def changes(self, calendar: str, token: str | None = None) -> tuple[list[dict[str, Any]], str]:
        """Return a complete multi-page delta; callers commit token only with all changes."""
        params = {"maxResults": "250", "showDeleted": "true"}
        if token:
            params["syncToken"] = token
        result: list[dict[str, Any]] = []
        while True:
            page = await self.request("GET", self.events_path(calendar), params=params)
            items = page.get("items", [])
            if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                raise ValueError("Invalid Calendar event page")
            result.extend(items)
            if not page.get("nextPageToken"):
                next_token = page.get("nextSyncToken")
                if not isinstance(next_token, str) or not next_token:
                    raise ValueError("Calendar response has no reconciliation token")
                return result, next_token
            params["pageToken"] = page["nextPageToken"]

    async def get(self, calendar: str, identity: str) -> dict[str, Any]:
        return await self.request("GET", self.events_path(calendar) + "/" + quote(identity, safe=""))

    async def window(self, calendar: str, start: str, end: str) -> list[dict[str, Any]]:
        params = {"timeMin": start, "timeMax": end, "singleEvents": "true", "maxResults": "250"}
        result: list[dict[str, Any]] = []
        while True:
            page = await self.request("GET", self.events_path(calendar), params=params)
            result.extend(page.get("items", []))
            if not page.get("nextPageToken"):
                return result
            params["pageToken"] = page["nextPageToken"]

    async def instance(self, calendar: str, master: str, original_start: str) -> dict[str, Any]:
        return await self.request(
            "GET",
            self.events_path(calendar) + "/" + quote(master, safe="") + "/instances",
            params={"originalStart": original_start, "showDeleted": "true", "maxResults": "10"},
        )

    async def write(self, calendar: str, event: dict[str, Any], etag: str | None = None) -> dict[str, Any]:
        if etag:
            return await self.request(
                "PATCH", self.events_path(calendar) + "/" + quote(event["id"], safe=""), body=event, etag=etag
            )
        return await self.request("POST", self.events_path(calendar), body=event)

    async def delete(self, calendar: str, identity: str, etag: str) -> None:
        await self.request("DELETE", self.events_path(calendar) + "/" + quote(identity, safe=""), etag=etag)

    async def watch(self, calendar: str, channel: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", self.events_path(calendar) + "/watch", body=channel)

    async def stop(self, identity: str, resource: str) -> None:
        await self.request("POST", "/channels/stop", body={"id": identity, "resourceId": resource})
