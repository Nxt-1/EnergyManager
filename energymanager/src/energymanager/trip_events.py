"""Lossless EV-drive wire representation for the dedicated Google calendar."""

from __future__ import annotations

import json
import math
from typing import Any

from .domain import instant


def description_with_origin(description: str, origin: str | None) -> str:
    """Replace our origin line while retaining unrelated description content."""
    lines = description.splitlines(keepends=True)
    retained = "".join(line for line in lines if not line.startswith("From: "))
    if origin is None:
        return retained
    separator = "" if not retained or retained.endswith(("\n", "\r")) else "\n"
    return retained + separator + "From: " + json.dumps(origin, ensure_ascii=False)


def read_origin(description: str) -> str:
    lines = [line[6:] for line in description.splitlines() if line.startswith("From: ")]
    if len(lines) != 1:
        raise ValueError("Supply exactly one From: origin line")
    try:
        origin = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise ValueError("From: must contain a JSON quoted origin") from exc
    if not isinstance(origin, str) or not origin.strip() or len(origin) > 1000:
        raise ValueError("Supply a valid origin")
    return origin


def drive_marker(description: str) -> dict[str, Any] | None:
    lines = [
        line[len("EnergyManager: ") :]
        for line in description.splitlines()
        if line.startswith("EnergyManager: ")
    ]
    if not lines:
        return None
    if len(lines) != 1:
        raise ValueError("Supply exactly one EnergyManager drive marker")
    try:
        marker = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise ValueError("The EnergyManager drive marker must be JSON") from exc
    if (
        not isinstance(marker, dict)
        or type(marker.get("v")) is not int
        or marker.get("v") != 1
        or set(marker) - {"v", "mode", "km", "timing"}
    ):
        raise ValueError("Use the supported version 1 drive marker")
    return marker


def validate_drive(drive: dict[str, Any]) -> dict[str, Any]:
    """Validate explicit drive data without inventing route or endpoint evidence."""
    result = dict(drive)
    if not isinstance(drive.get("title"), str) or not drive["title"].strip() or len(drive["title"]) > 1000:
        raise ValueError("Use a nonempty drive title")
    start, end = instant(drive["start"]), instant(drive["end"])
    if end <= start:
        raise ValueError("Arrival must follow departure")
    if drive.get("mode") not in ("routed", "distance_only"):
        raise ValueError("Select routed or distance-only mode")
    if drive.get("timing") not in ("depart", "arrive", "fixed"):
        raise ValueError("Select a supported timing mode")
    km = drive.get("manual_km")
    if km is not None and (type(km) not in (int, float) or not math.isfinite(km) or km <= 0):
        raise ValueError("Distance must be finite and positive")
    if drive["mode"] == "distance_only":
        if km is None or drive["timing"] != "fixed":
            raise ValueError("Distance-only drives need km and fixed start/end")
        result["origin"] = result["destination"] = None
    elif any(
        not isinstance(drive.get(key), str) or not drive[key].strip() or len(drive[key]) > 1000
        for key in ("origin", "destination")
    ):
        raise ValueError("Routed drives need both endpoints")
    result.update(start=start.isoformat(), end=end.isoformat())
    return result


def google_event(drive: dict[str, Any], description: str = "") -> dict[str, Any]:
    drive = validate_drive(drive)
    identity = drive["id"]
    if (
        not isinstance(identity, str)
        or len(identity) != 32
        or any(c not in "0123456789abcdef" for c in identity)
    ):
        raise ValueError("Use a stable UUID hex trip identity")
    properties = {
        "em_schema": "1",
        "em_trip": identity,
        "em_mode": drive["mode"],
        "em_timing": drive["timing"],
        "em_revision": str(drive["revision"]),
    }
    if drive.get("manual_km") is not None:
        properties["em_km"] = str(drive["manual_km"])
    description = "".join(
        line for line in description.splitlines(keepends=True) if not line.startswith("EnergyManager: ")
    )
    description = description_with_origin(description, drive.get("origin"))
    marker = {"v": 1, "mode": drive["mode"], "km": drive.get("manual_km"), "timing": drive["timing"]}
    description += (
        ("" if not description or description.endswith("\n") else "\n")
        + "EnergyManager: "
        + json.dumps(marker, ensure_ascii=False)
    )
    event = {
        "id": "em" + identity,
        "summary": drive["title"],
        "start": {"dateTime": drive["start"]},
        "end": {"dateTime": drive["end"]},
        "location": drive.get("destination") or "",
        "description": description,
        "extendedProperties": {"private": properties},
    }
    if drive.get("recurrence"):
        event["recurrence"] = drive["recurrence"]
        for key in ("start", "end"):
            event[key]["timeZone"] = drive["timezone"]
    return event


def drive_from_google(event: dict[str, Any], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    properties = event.get("extendedProperties", {}).get("private", {})
    marker = drive_marker(event.get("description", ""))
    mode = marker.get("mode") if marker else properties.get("em_mode", "routed")
    start, end = event["start"]["dateTime"], event["end"]["dateTime"]
    timing = (
        previous["timing"]
        if previous
        else marker.get("timing", "fixed")
        if marker
        else properties.get("em_timing", "fixed")
    )
    if previous and previous.get("mode") != mode and marker:
        timing = marker.get("timing", "fixed")
    if previous and (
        instant(start) != instant(previous["start"])
        or instant(end) != instant(previous["end"])
        or event.get("location") != previous.get("destination")
    ):
        timing = "fixed"
    try:
        km = marker.get("km") if marker else float(properties["em_km"]) if "em_km" in properties else None
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid manual distance") from exc
    data = {
        "id": properties.get("em_trip"),
        "title": event.get("summary")
        or (f"Drive · {km:g} km" if mode == "distance_only" and type(km) in (int, float) else "Drive"),
        "mode": mode,
        "timing": timing,
        "start": start,
        "end": end,
        "manual_km": km,
        "destination": event.get("location"),
        "origin": read_origin(event.get("description", "")) if mode == "routed" else None,
    }
    if previous and previous.get("destination") != data["destination"]:
        data["destination_city"] = ""
    return validate_drive(data)
