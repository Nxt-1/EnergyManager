"""Consolidate historical trim copies by explicit physical-capture provenance."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .domain import instant

if TYPE_CHECKING:
    from .store import Store


def consolidate_captures(store: Store, mode: str, key: str, settings: dict[str, Any]) -> dict[str, Any]:
    rows = [(sequence, json.loads(body)) for sequence, body in store.connection.execute(
        "SELECT rowid,body FROM appliance_recordings WHERE mode=? AND status='saved' ORDER BY rowid", (mode,))]
    by_id = {row["id"]: row for _, row in rows}

    def capture(row: dict[str, Any]) -> str:
        seen: set[str] = set()
        while not row.get("capture_id") and row.get("trimmed_from") in by_id:
            if row["id"] in seen:
                raise ValueError("Cyclic recording provenance; consolidation was not applied")
            seen.add(row["id"])
            row = by_id[row["trimmed_from"]]
        return row.get("capture_id") or row.get("trimmed_from") or row["id"]

    groups: dict[tuple[str, str, str], list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for sequence, row in rows:
        groups[(row["machine"], row["program"], capture(row))].append((sequence, row))
    duplicates = [(identity, group) for (_, _, identity), group in groups.items() if len(group) > 1]
    if not duplicates:
        return settings
    remap: dict[str, str] = {}
    retained: list[tuple[dict[str, Any], list[str]]] = []
    for provenance, group in duplicates:
        original = next((row for _, row in group if row["id"] == provenance), group[0][1])
        # saved_at describes trim acceptance; armed/started_at is shared by every copy.
        _, latest = max(group, key=lambda item: (
            instant(item[1]["saved_at"]) if item[1].get("saved_at") else datetime.min.replace(tzinfo=UTC), item[0]))
        if any(row["started_at"] != original["started_at"] or row["entity_id"] != original["entity_id"]
               for _, row in group):
            raise ValueError("Inconsistent capture provenance; consolidation was not applied")
        current = {**latest, "id": original["id"], "capture_id": provenance}
        current.pop("trimmed_from", None)
        retained.append((current, [row["id"] for _, row in group]))
        remap.update((row["id"], original["id"]) for _, row in group)
    members: dict[str, list[str]] = dict(settings.get("members", {}))
    selected = dict(settings["selected"])
    for program in set(selected) | set(members):
        previous = members.get(program, [selected[program]] if program in selected else [])
        members[program] = list(dict.fromkeys(remap.get(identity, identity) for identity in previous))
        if members[program]:
            selected[program] = remap.get(selected.get(program, ""), selected.get(program, ""))
            if selected[program] not in members[program]:
                selected[program] = members[program][-1]
        else:
            selected.pop(program, None)
    aliases = {alias: remap.get(target, target) for alias, target in settings.get("recording_aliases", {}).items()}
    aliases.update({old: new for old, new in remap.items() if old != new})
    updated = {**settings, "revision": settings["revision"]+1, "members": members,
               "selected": selected, "recording_aliases": aliases}
    with store.connection:
        for row, copies in retained:
            canonical = row["id"]
            for old in copies:
                if old == canonical:
                    continue
                # Historical trims copied the same immutable samples. Reject contradictory
                # evidence rather than silently losing one of two readings at the same time.
                conflict = store.connection.execute(
                    "SELECT 1 FROM appliance_samples a JOIN appliance_samples b ON a.at=b.at "
                    "WHERE a.recording_id=? AND b.recording_id=? "
                    "AND (a.power_w IS NOT b.power_w OR a.error IS NOT b.error) LIMIT 1", (canonical, old)).fetchone()
                if conflict:
                    raise ValueError("Conflicting raw capture evidence; consolidation was not applied")
                store.connection.execute(
                    "INSERT OR IGNORE INTO appliance_samples SELECT ?,at,power_w,error FROM appliance_samples WHERE recording_id=?",
                    (canonical, old))
                store.connection.execute("DELETE FROM appliance_samples WHERE recording_id=?", (old,))
                store.connection.execute("DELETE FROM appliance_recordings WHERE id=? AND mode=?", (old, mode))
            store.connection.execute("UPDATE appliance_recordings SET body=? WHERE id=? AND mode=?",
                                     (json.dumps(row, allow_nan=False), canonical, mode))
        store.connection.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, json.dumps(updated, allow_nan=False)))
    return updated
