"""Durable local EV trips and revision-checked publication outbox."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import uuid4

from .domain import instant
from .store import Store
from .trip_events import validate_drive


class TripStore:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.defer_writes = False
        self.state = store.get("ev_trips_v1", {"trips": {}, "pending": {}, "notices": {}, "binding": None})

    def save(self) -> None:
        # One state row makes trip+outbox and notice dedup atomic across process restarts.
        if not self.defer_writes:
            self.store.put("ev_trips_v1", self.state)

    def edit(
        self,
        data: dict[str, Any],
        at: datetime,
        *,
        identity: str | None = None,
        actor: str = "manual",
        source_change: bool = False,
    ) -> dict[str, Any]:
        if actor not in ("manual", "automatic"):
            raise ValueError("Invalid edit provenance")
        identity = identity or uuid4().hex
        old = self.state["trips"].get(identity)
        if old and not source_change:
            if old["actor"] == "manual" and actor == "automatic":
                return deepcopy(old)
            if old["actor"] == actor and instant(old["edited_at"]) > instant(at):
                return deepcopy(old)
        trip = validate_drive({**(old or {}), **data, "id": identity})
        trip.update(
            revision=old["revision"] + 1 if old else 1,
            actor=actor,
            edited_at=instant(at).isoformat(),
            deleted=False,
            source_change=source_change,
            edit_revision=(old.get("edit_revision", old["revision"]) + 1 if old else 1),
        )
        self.state["trips"][identity] = trip
        self.state["pending"][identity] = trip["revision"]
        self.save()
        return deepcopy(trip)

    def delete(self, identity: str, at: datetime) -> None:
        old = self.state["trips"][identity]
        if old["deleted"]:
            return
        self.state["trips"][identity] = {
            **old,
            "deleted": True,
            "actor": "manual",
            "edited_at": instant(at).isoformat(),
            "revision": old["revision"] + 1,
        }
        self.state["pending"][identity] = old["revision"] + 1
        self.save()

    def pending(self) -> list[dict[str, Any]]:
        return [deepcopy(self.state["trips"][key]) for key in self.state["pending"]]

    def acknowledge(self, identity: str, revision: int) -> bool:
        if self.state["pending"].get(identity) != revision:
            return False
        del self.state["pending"][identity]
        self.save()
        return True

    def notice(self, identity: str, revision: int | str, kind: str) -> bool:
        """Claim one durable notification intent per edit, before asynchronous delivery."""
        key = f"{identity}:{revision}:{kind}"
        if key in self.state["notices"]:
            return False
        self.state["notices"][key] = {
            "trip": identity,
            "revision": revision,
            "kind": kind,
            "delivered": False,
        }
        self.save()
        return True

    def bind(self, calendar: str) -> None:
        if self.state["binding"] not in (None, calendar):
            raise ValueError("Calendar switching requires an explicit migration policy")
        self.state["binding"] = calendar
        self.save()
