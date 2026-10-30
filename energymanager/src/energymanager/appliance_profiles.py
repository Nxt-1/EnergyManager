"""Explicitly armed appliance recordings and reviewed, versioned profile selections."""

from __future__ import annotations

import asyncio
import math
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import aiohttp

from .domain import instant

if TYPE_CHECKING:
    from .service import Application
    from .store import Store

SAMPLE_SECONDS = 5
MAX_GAP_SECONDS = 15
MAX_CAPTURE_SECONDS = 24 * 3600
PROGRAMS = {
    "dishwasher": {"eco": "Eco", "heavy": "Heavy (optional)"},
    "washing_machine": {"whites_60": "Whites 60°C", "darks_40": "Darks 40°C",
                        "darks_30": "Darks 30°C", "coloured_40": "Coloured 40°C"},
}
MAZAK = {"program": 2500.0, "light": 3500.0, "production": 7000.0}


def number(value: Any, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")
    return result


def power_reading(state: dict[str, Any]) -> float:
    try:
        power = float(state["state"])
        unit = state["attributes"]["unit_of_measurement"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Power sensor must supply an available numeric W or kW reading") from exc
    if unit not in ("W", "kW"):
        raise ValueError("Power sensor must use W or kW")
    return number(power * (1000 if unit == "kW" else 1), "Power (W)", 0, 100000)


class ApplianceProfiles:
    """Capture only the machine/program the user arms; never recognize other loads."""

    def __init__(self, application: Application) -> None:
        self.app: Application = application
        self.store: Store = application.store
        self.mode = "demo" if application.demo else "configured"
        self.key = f"appliance_profiles_{self.mode}"
        self.task: asyncio.Task[None] | None = None
        self.settings: dict[str, Any] = self.store.get(self.key, {
            "revision": 1,
            "machines": {machine: {"entity_id": "", "start_threshold_w": 10.0, "idle_timeout_minutes": 15.0} for machine in PROGRAMS},
            "mazak": dict(MAZAK), "selected": {},
        })
        # A stopped service cannot establish what happened in its absence.
        for row in self._rows("status='recording'"):
            row.update(status="review", interrupted=True, error="Service restarted during recording")
            self._save(row)
        for row in self._rows("status='armed'"):
            row.update(idle_seen=False, idle_since=None, last_at=None,
                       error="Service restarted while armed; waiting for idle again")
            self._save(row)

    def start(self) -> None:
        self.task = asyncio.create_task(self._loop())

    async def close(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        for row in self._rows("status='recording'"):
            row.update(status="review", interrupted=True, error="Service stopped during recording")
            self._save(row)

    def _rows(self, where: str = "1", parameters: tuple[Any, ...] = (), limit: int = 1000000) -> list[dict[str, Any]]:
        rows = self.store.connection.execute(
            f"SELECT body FROM appliance_recordings WHERE mode=? AND ({where}) ORDER BY rowid DESC LIMIT ?",
            (self.mode, *parameters, limit))
        return [json.loads(row[0]) for row in rows]

    def _save(self, recording: dict[str, Any], *, select: bool = False) -> None:
        settings = None
        if select:
            key = f"{recording['machine']}/{recording['program']}"
            settings = {**self.settings, "revision": self.settings["revision"] + 1,
                        "selected": {**self.settings["selected"], key: recording["id"]}}
        with self.store.connection:
            if settings is not None:
                self.store.connection.execute("INSERT OR REPLACE INTO state VALUES (?,?)",
                                              (self.key, json.dumps(settings, allow_nan=False)))
            self.store.connection.execute(
                "INSERT INTO appliance_recordings(id,mode,status,body) VALUES (?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status,body=excluded.body",
                (recording["id"], self.mode, recording["status"], json.dumps(recording, allow_nan=False)))
        if settings is not None:
            self.settings = settings

    def _persist_settings(self, values: dict[str, Any]) -> None:
        settings = {**values, "revision": self.settings["revision"] + 1}
        self.store.put(self.key, settings)
        self.settings = settings

    def library(self) -> dict[str, Any]:
        selected = {key: self.get(identity) for key, identity in self.settings["selected"].items()}
        sampler_error = None
        if self.task and self.task.done() and not self.task.cancelled() and self.task.exception():
            sampler_error = f"Recorder stopped: {self.task.exception()}"
        return {"mode": self.mode, "programs": PROGRAMS, **self.settings, "profiles": selected,
                "sampler_error": sampler_error,
                "recordings": self._rows("status != 'discarded'", limit=100),
                "sample_seconds": SAMPLE_SECONDS, "maximum_gap_seconds": MAX_GAP_SECONDS}

    def configure(self, body: dict[str, Any]) -> dict[str, Any]:
        if type(body.get("revision")) is not int or body["revision"] != self.settings["revision"]:
            raise ValueError("Profiles changed in another view; reload before saving")
        settings = {**self.settings, "machines": dict(self.settings["machines"])}
        if body.get("machine") == "mazak":
            values = body.get("powers_w")
            if not isinstance(values, dict) or set(values) != set(MAZAK):
                raise ValueError("Supply all three Mazak average powers")
            powers = {key: number(value, key + " W", 0, 100000) for key, value in values.items()}
            settings["mazak"] = powers
        else:
            machine = body.get("machine")
            if machine not in PROGRAMS:
                raise ValueError("Unknown appliance")
            if any(row["machine"] == machine for row in self._rows("status IN ('armed','recording')")):
                raise ValueError("Finish or cancel this machine's recording before changing its sensor")
            entity = str(body.get("entity_id", "")).strip()
            if entity and not re.fullmatch(r"sensor\.[a-z0-9_]+", entity):
                raise ValueError("Select a power sensor entity, or leave it empty")
            if entity and any(key != machine and value["entity_id"] == entity
                              for key, value in self.settings["machines"].items()):
                raise ValueError("Each machine needs its own dedicated power sensor")
            threshold = number(body.get("start_threshold_w"), "Start threshold W", 0.1, 100000)
            timeout = number(body.get("idle_timeout_minutes"), "Idle timeout minutes", 1, 120)
            settings["machines"][machine] = {"entity_id": entity, "start_threshold_w": threshold,
                                                   "idle_timeout_minutes": timeout}
        self._persist_settings(settings)
        return self.library()

    def get(self, identity: str) -> dict[str, Any]:
        rows = self._rows("id=?", (identity,))
        if not rows:
            raise ValueError("Unknown recording")
        return rows[0]

    def arm(self, body: dict[str, Any]) -> dict[str, Any]:
        machine, program = body.get("machine"), body.get("program")
        if machine not in PROGRAMS or program not in PROGRAMS[machine]:
            raise ValueError("Choose a supported appliance program")
        if self.app.demo or self.app.ha is None:
            raise ValueError("Recording requires configured mode and a mapped HA power sensor")
        settings = self.settings["machines"][machine]
        if not settings["entity_id"]:
            raise ValueError("Map this machine's power sensor first")
        if any(row["machine"] == machine for row in self._rows("status IN ('armed','recording')")):
            raise ValueError("This machine already has an armed or running recording")
        notes = str(body.get("notes", "")).strip()
        if len(notes) > 500:
            raise ValueError("Recording notes must be at most 500 characters")
        recording = {"id": uuid4().hex, "machine": machine, "program": program,
                     "notes": notes, "entity_id": settings["entity_id"],
                     "start_threshold_w": settings["start_threshold_w"],
                     "idle_timeout_minutes": settings["idle_timeout_minutes"], "idle_since": None,
                     "suggested_end_seconds": None, "status": "armed",
                     "armed_at": self.app.now().isoformat(), "started_at": None, "last_at": None,
                     "idle_seen": False, "interrupted": False, "error": None,
                     "sample_count": 0, "invalid_samples": 0, "last_power_w": None}
        self._save(recording)
        return recording

    def ingest(self, identity: str, at: datetime, power_w: float | None, error: str | None = None) -> None:
        """Persist one read, including explicit failures; repeated HA states remain valid."""
        recording = self.get(identity)
        if recording["status"] not in ("armed", "recording"):
            return  # An in-flight read must not resurrect a finished or discarded recording.
        if at.tzinfo is None:
            raise ValueError("Recording times must be timezone-aware")
        if power_w is not None:
            power_w = number(power_w, "Power W", 0, 100000)
        if recording["last_at"] and at <= instant(recording["last_at"]):
            return
        if at < instant(recording["armed_at"]):
            return
        previous_at = instant(recording["last_at"]) if recording["last_at"] else None
        if previous_at and (at - previous_at).total_seconds() > MAX_GAP_SECONDS:
            recording["idle_since"] = None
            if recording["status"] == "armed":
                recording["idle_seen"] = False
        if power_w is None and recording["status"] == "armed":
            recording["idle_seen"] = False
        recording.update(last_at=at.isoformat(), last_power_w=power_w, error=error)
        if (at - instant(recording["armed_at"])).total_seconds() >= MAX_CAPTURE_SECONDS:
            recording.update(status="review" if recording["started_at"] else "cancelled",
                             interrupted=True, error="24-hour recording limit reached")
            self._save(recording)
            return
        if recording["status"] == "armed":
            if power_w is not None and power_w <= recording["start_threshold_w"]:
                recording["idle_seen"] = True
            elif power_w is not None and recording["idle_seen"]:
                recording.update(status="recording", started_at=at.isoformat())
        if recording["status"] == "recording":
            self.store.connection.execute(
                "INSERT INTO appliance_samples(recording_id,at,power_w,error) VALUES (?,?,?,?)",
                (identity, at.timestamp(), power_w, error))
            recording["sample_count"] += 1
            recording["invalid_samples"] += int(power_w is None)
            if power_w is None or power_w > recording["start_threshold_w"]:
                recording["idle_since"] = None
            else:
                recording["idle_since"] = recording["idle_since"] or at.isoformat()
                idle_since = instant(recording["idle_since"])
                if (at - idle_since).total_seconds() >= recording["idle_timeout_minutes"] * 60:
                    recording.update(status="review", finished_at=at.isoformat(),
                                     suggested_end_seconds=(idle_since - instant(recording["started_at"])).total_seconds())
        self._save(recording)

    def finish(self, identity: str) -> dict[str, Any]:
        recording = self.get(identity)
        if recording["status"] != "recording":
            raise ValueError("Only a running recording can be finished")
        recording.update(status="review", finished_at=self.app.now().isoformat())
        self._save(recording)
        return self.detail(identity)

    def discard(self, identity: str) -> None:
        recording = self.get(identity)
        if recording["status"] == "saved":
            raise ValueError("Saved profile evidence is retained; select another recording to replace it")
        recording["status"] = "discarded"
        self._save(recording)

    def detail(self, identity: str) -> dict[str, Any]:
        recording = self.get(identity)
        samples = self.store.connection.execute(
            "SELECT at,power_w,error FROM appliance_samples WHERE recording_id=? ORDER BY at", (identity,))
        origin = instant(recording["started_at"]).timestamp() if recording["started_at"] else 0
        points = [{"seconds": at - origin, "power_w": power, "error": error} for at, power, error in samples]
        return {**recording, "points": points}

    def preview(self, identity: str, body: dict[str, Any]) -> dict[str, Any]:
        recording = self.detail(identity)
        points = recording["points"]
        if len(points) < 2:
            raise ValueError("At least two measured samples are needed")
        maximum = points[-1]["seconds"]
        start = number(body.get("start_seconds", 0), "Trim start seconds", 0, maximum)
        suggested_end = recording.get("suggested_end_seconds")
        end = number(body.get("end_seconds", suggested_end if suggested_end is not None else maximum), "Trim end seconds", 0, maximum)
        if end <= start:
            raise ValueError("Trim end must be after trim start")
        energy_ws, covered = 0.0, 0.0
        peak: float | None = None
        for left, right in zip(points, points[1:]):
            seconds = min(end, right["seconds"]) - max(start, left["seconds"])
            if seconds <= 0:
                continue
            if (left["power_w"] is not None and right["power_w"] is not None
                    and right["seconds"] - left["seconds"] <= MAX_GAP_SECONDS):
                energy_ws += seconds * left["power_w"]
                covered += seconds
                peak = max(peak or 0, left["power_w"])
        duration = end - start
        complete = abs(covered - duration) < 0.001
        return {"start_seconds": start, "end_seconds": end, "duration_seconds": duration,
                "covered_seconds": covered, "complete": complete, "energy_kwh": energy_ws / 3600000,
                "average_w": energy_ws / covered if covered else None,
                "peak_w": peak}

    def accept(self, identity: str, body: dict[str, Any]) -> dict[str, Any]:
        recording = self.get(identity)
        if recording["status"] != "review":
            raise ValueError("Finish and review this recording before saving it")
        if body.get("reviewed") is not True:
            raise ValueError("Explicit review confirmation is required")
        if type(body.get("revision")) is not int or body["revision"] != self.settings["revision"]:
            raise ValueError("Profiles changed in another view; reload before saving")
        summary = self.preview(identity, body)
        if not summary["complete"]:
            raise ValueError("Recording contains missing measurements; trim to complete coverage or record again")
        if recording["interrupted"]:
            raise ValueError("Recording was interrupted; record a complete cycle before selecting a profile")
        recording.update(status="saved", summary=summary, saved_at=self.app.now().isoformat())
        self._save(recording, select=True)
        return recording

    def select(self, identity: str, body: dict[str, Any]) -> None:
        recording = self.get(identity)
        if recording["status"] != "saved":
            raise ValueError("Only reviewed saved recordings can be selected")
        if type(body.get("revision")) is not int or body["revision"] != self.settings["revision"]:
            raise ValueError("Profiles changed in another view; reload before selecting")
        key = f"{recording['machine']}/{recording['program']}"
        settings = {**self.settings, "selected": {**self.settings["selected"], key: identity}}
        self._persist_settings(settings)

    async def _sample(self, recording: dict[str, Any]) -> None:
        if self.app.demo or self.app.ha is None:
            return
        try:
            reading = await self.app.ha.entity_state(recording["entity_id"])
            power, error = power_reading(reading), None
        except (aiohttp.ClientError, TimeoutError, ValueError, RuntimeError) as exc:
            power, error = None, f"Power read failed: {type(exc).__name__}: {str(exc)[:160]}"
        self.ingest(recording["id"], self.app.now(), power, error)

    async def _loop(self) -> None:
        while True:
            await asyncio.gather(*(self._sample(recording) for recording in
                                   self._rows("status IN ('armed','recording')")))
            await asyncio.sleep(SAMPLE_SECONDS)
