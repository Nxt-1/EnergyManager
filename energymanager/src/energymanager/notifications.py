"""Deduplicated informational notices; local evidence is the default destination."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .control import ServiceClient
from .domain import encode
from .store import Store


@dataclass(frozen=True)
class NotificationTarget:
    id: str
    kind: str

    @classmethod
    def from_data(cls, value: Any) -> NotificationTarget | None:
        if value is None or value == "":
            return None
        if (not isinstance(value, dict) or set(value) != {"id", "kind"}
                or not isinstance(value["id"], str) or not re.fullmatch(r"notify\.[a-z0-9_]+", value["id"])
                or value["kind"] not in ("entity", "action")):
            raise ValueError("Choose a phone notification destination")
        if value["kind"] == "action" and value["id"] in ("notify.notify", "notify.send_message"):
            raise ValueError("Choose a specific notification destination")
        return cls(value["id"], value["kind"])


class Notifications:
    def __init__(self, store: Store, client: ServiceClient | None = None,
                 target: NotificationTarget | None = None) -> None:
        self.store, self.client, self.target = store, client, target

    async def inform(self, key: str, body: dict[str, Any]) -> None:
        # Tenths of kW and the affected peak identify material updates, not solver IDs.
        material = {
            k: (round(v, 1) if isinstance(v, float) else v)
            for k, v in body.items()
            if k not in ("forecast_id", "plan_id")
        }
        signature = encode({"destination": asdict(self.target) if self.target else None, "notice": material})
        notices = self.store.get("notices", {})
        if notices.get(key) == signature:
            return
        self.store.event("notification_queued", {"key": key, **body})
        if self.target:
            try:
                if self.client is None:
                    raise RuntimeError("Home Assistant is not connected")
                data = {"title": "EnergyManager", "message": self.message(body)}
                service = self.target.id.split(".", 1)[1]
                if self.target.kind == "entity":
                    data["entity_id"] = self.target.id
                    service = "send_message"
                await self.client.service("notify", service, data)
            except (OSError, RuntimeError, TimeoutError) as exc:
                self.store.event("notification_failed", {"key": key, "error": type(exc).__name__})
                return  # Retry on the next adoption, without falsely recording delivery.
        self.store.event(
            "local_notification" if self.target is None else "notification_delivered", {"key": key, **body}
        )
        notices[key] = signature
        self.store.put("notices", notices)

    @staticmethod
    def message(body: dict[str, Any]) -> str:
        if body.get("kind") == "peak_precharge":
            return (f"Battery charging is planned with a {float(body['peak_kw']):.1f} kW import peak "
                    f"to avoid an estimated {float(body['avoided_peak_kw']):.1f} kW peak later.")
        return str(body.get("message", "A new EnergyManager decision needs your attention."))
