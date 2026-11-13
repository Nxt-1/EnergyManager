"""Server-side Places search and selection, with bounded responses and session tokens."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import aiohttp

from .routing import RoutingUnavailable


class TripPlaces:
    def __init__(
        self, session: aiohttp.ClientSession, key: str, base_url: str = "https://places.googleapis.com/v1"
    ) -> None:
        self.session, self.key, self.base_url = session, key, base_url

    async def request(
        self,
        method: str,
        path: str,
        mask: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not self.key:
            raise RoutingUnavailable("Places requires a configured Maps key", code="credentials")
        async with (
            asyncio.timeout(15),
            self.session.request(
                method,
                self.base_url + path,
                json=body,
                params=params,
                headers={"X-Goog-Api-Key": self.key, "X-Goog-FieldMask": mask},
                allow_redirects=False,
            ) as response,
        ):
            if response.status != 200:
                raise RoutingUnavailable(
                    "Place search failed",
                    code="access_denied" if response.status in (401, 403) else "provider",
                    http_status=response.status,
                )
            content = bytearray()
            async for chunk in response.content.iter_chunked(16384):
                content.extend(chunk)
                if len(content) > 65536:
                    raise ValueError("Place response exceeds size limit")
            import json

            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("Invalid Places response")
            return result

    async def search(self, text: str, token: str) -> list[dict[str, str]]:
        if not isinstance(text, str) or not 2 <= len(text.strip()) <= 200 or not 16 <= len(token) <= 100:
            raise ValueError("Use a search term and session token")
        result = await self.request(
            "POST",
            "/places:autocomplete",
            "suggestions.placePrediction",
            body={"input": text.strip(), "sessionToken": token},
        )
        return [
            {"id": item["placePrediction"]["placeId"], "label": item["placePrediction"]["text"]["text"]}
            for item in result.get("suggestions", [])
            if "placePrediction" in item
        ][:5]

    async def select(self, identity: str, token: str) -> dict[str, str]:
        if not identity or len(identity) > 300 or not 16 <= len(token) <= 100:
            raise ValueError("Invalid place selection")
        return await self.details(identity, token)

    async def details(self, identity: str, token: str | None = None) -> dict[str, str]:
        result = await self.request(
            "GET",
            "/places/" + quote(identity, safe=""),
            "id,formattedAddress,displayName,addressComponents",
            params={"sessionToken": token} if token else None,
        )
        city = next(
            (
                part["longText"]
                for part in result.get("addressComponents", [])
                if "locality" in part.get("types", [])
            ),
            "",
        )
        return {
            "id": result["id"],
            "address": result["formattedAddress"],
            "city": city,
            "label": result.get("displayName", {}).get("text", result["formattedAddress"]),
        }
