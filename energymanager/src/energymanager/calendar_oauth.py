"""Server-owned OAuth authorization state; no tokens are returned to the browser."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urlsplit

import aiohttp

from .domain import instant
from .google_calendar import CalendarError, GoogleCalendarClient
from .store import Store

SCOPES = " ".join(
    (
        "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    )
)


def public_https(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2000 or any(ord(character) <= 32 for character in value):
        raise ValueError("Supply the exact public HTTPS URL without spaces or control characters")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise ValueError("Supply the exact public HTTPS URL from your proxy configuration")
    return value


class CalendarOAuth:
    def __init__(
        self,
        store: Store,
        session: aiohttp.ClientSession,
        token_url: str = "https://oauth2.googleapis.com/token",
    ) -> None:
        self.store, self.session, self.token_url = store, session, token_url
        self.data = store.get("calendar_oauth_private", {})
        self.lock = asyncio.Lock()

    def configure(self, data: dict[str, Any]) -> None:
        client = data.get("client_id", "").strip()
        if not client or len(client) > 500:
            raise ValueError("Supply your Google OAuth web client ID")
        secret = data.get("client_secret") or self.data.get("client_secret")
        if not isinstance(secret, str) or not secret or len(secret) > 500:
            raise ValueError("Supply the OAuth client secret")
        redirect = public_https(data.get("redirect_uri", ""))
        webhook = public_https(data.get("webhook_uri", ""))
        changed = any(
            self.data.get(key) != value
            for key, value in (("client_id", client), ("client_secret", secret), ("redirect_uri", redirect))
        )
        self.data.update(client_id=client, client_secret=secret, redirect_uri=redirect, webhook_uri=webhook)
        if changed:
            self.data["generation"] = self.data.get("generation", 0) + 1
            for key in ("access_token", "refresh_token", "expires_at", "pending"):
                self.data.pop(key, None)
        self.save()

    def save(self) -> None:
        self.store.put("calendar_oauth_private", self.data)

    def begin(self) -> str:
        if not self.data.get("client_id"):
            raise ValueError("Save OAuth setup first")
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        self.data["pending"] = {
            "state": state,
            "verifier": verifier,
            "expires": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        }
        self.save()
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": self.data["client_id"],
                "redirect_uri": self.data["redirect_uri"],
                "response_type": "code",
                "scope": SCOPES,
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )

    async def exchange(self, parameters: dict[str, str]) -> dict[str, Any]:
        generation = self.data.get("generation", 0)
        async with (
            asyncio.timeout(25),
            self.session.post(
                self.token_url,
                data={
                    "client_id": self.data["client_id"],
                    "client_secret": self.data["client_secret"],
                    **parameters,
                },
                allow_redirects=False,
            ) as response,
        ):
            if response.status != 200:
                raise CalendarError(401 if response.status == 400 else response.status)
            result = await response.json()
        if generation != self.data.get("generation", 0):
            raise ValueError("OAuth setup changed while authorization was pending")
        if not isinstance(result, dict) or not isinstance(result.get("access_token"), str):
            raise ValueError("Invalid OAuth token response")
        if parameters.get("grant_type") == "authorization_code" and not result.get("refresh_token"):
            raise ValueError("Google did not grant offline access; authorize again")
        self.data.update(
            access_token=result["access_token"],
            expires_at=(
                datetime.now(UTC) + timedelta(seconds=max(0, min(int(result.get("expires_in", 3600)), 86400)))
            ).isoformat(),
        )
        if result.get("refresh_token"):
            self.data["refresh_token"] = result["refresh_token"]
        self.save()
        return result

    async def callback(self, state: str, code: str) -> None:
        async with self.lock:
            pending = self.data.get("pending", {})
            if (
                not state
                or not secrets.compare_digest(state, pending.get("state", ""))
                or instant(pending.get("expires", "1970-01-01T00:00:00+00:00")) <= datetime.now(UTC)
            ):
                raise ValueError("Authorization expired or state does not match; start again")
            self.data.pop("pending", None)
            self.save()  # One-time valid state, including denied callbacks.
            if not code:
                raise ValueError("Calendar authorization was not granted")
            await self.exchange(
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.data["redirect_uri"],
                    "code_verifier": pending["verifier"],
                }
            )

    async def access_token(self) -> str:
        async with self.lock:
            if not self.data.get("refresh_token"):
                raise CalendarError(401)
            if not self.data.get("access_token") or instant(self.data["expires_at"]) <= datetime.now(
                UTC
            ) + timedelta(seconds=60):
                await self.exchange(
                    {"grant_type": "refresh_token", "refresh_token": self.data["refresh_token"]}
                )
            return str(self.data["access_token"])

    def status(self) -> dict[str, Any]:
        return {
            "configured": bool(self.data.get("client_id")),
            "authorized": bool(self.data.get("refresh_token")),
            **{key: self.data.get(key, "") for key in ("client_id", "redirect_uri", "webhook_uri")},
        }


class AuthorizedCalendar(GoogleCalendarClient):
    def __init__(self, oauth: CalendarOAuth) -> None:
        super().__init__(oauth.session, "")
        self.oauth = oauth

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        etag: str | None = None,
    ) -> dict[str, Any]:
        self.token = await self.oauth.access_token()
        try:
            return await super().request(method, path, body=body, params=params, etag=etag)
        except CalendarError as exc:
            if exc.status == 401:
                self.oauth.data.pop("access_token", None)
                self.oauth.save()
            raise
