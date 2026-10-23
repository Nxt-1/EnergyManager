"""Deduplicated informational notices; local evidence is the default destination."""

from __future__ import annotations

from typing import Any

import aiohttp

from .adapters import checked_url
from .domain import encode
from .store import Store


class Notifications:
    def __init__(self, store: Store, url: str | None = None, *, allow_remote: bool = False) -> None:
        self.store = store
        self.url = checked_url(url, allow_remote) if url else None

    async def inform(self, key: str, body: dict[str, Any]) -> None:
        # Tenths of kW and the affected peak identify material updates, not solver IDs.
        material = {
            k: (round(v, 1) if isinstance(v, float) else v)
            for k, v in body.items()
            if k not in ("forecast_id", "plan_id")
        }
        signature = encode(material)
        notices = self.store.get("notices", {})
        if notices.get(key) == signature:
            return
        self.store.event("notification_queued", {"key": key, **body})
        if self.url:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    async with session.post(
                        self.url, json={"key": key, **body}, allow_redirects=False
                    ) as response:
                        response.raise_for_status()
            except (aiohttp.ClientError, TimeoutError) as exc:
                self.store.event("notification_failed", {"key": key, "error": type(exc).__name__})
                return  # Retry on the next adoption, without falsely recording delivery.
        self.store.event(
            "local_notification" if self.url is None else "notification_delivered", {"key": key, **body}
        )
        notices[key] = signature
        self.store.put("notices", notices)
