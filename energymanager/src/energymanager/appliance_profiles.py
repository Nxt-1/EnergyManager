"""Manual and Bosch-feedback captures with reviewed per-capture profile averages."""

from __future__ import annotations

import asyncio
import math
import json
import re
from datetime import datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import aiohttp

from .domain import instant, encode
from .appliance_average import average_recordings
from .appliance_migration import consolidate_captures
from .bosch import BoschDishwasher, FIELDS

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
    """Persist explicit manual captures and mapped Bosch runs; never recognize other loads."""

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
        self.settings = consolidate_captures(self.store, self.mode, self.key, self.settings)
        # A stopped service cannot establish what happened in its absence.
        for row in self._rows("status='recording'"):
            row.update(status="review", interrupted=True, error="Service restarted during recording")
            self._save(row)
        for row in self._rows("status='armed'"):
            row.update(idle_seen=False, idle_since=None, last_at=None,
                       error="Service restarted while armed; waiting for idle again")
            self._save(row)

        self.bosch = BoschDishwasher(self)

    def programs(self) -> dict[str, dict[str, str]]:
        return {**PROGRAMS, "dishwasher": {**PROGRAMS["dishwasher"], **self.settings.get("bosch_programs", {})}}

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

    def _save(self, recording: dict[str, Any], *, select: bool = False, edit: bool = False) -> None:
        settings = None
        if select:
            key = f"{recording['machine']}/{recording['program']}"
            members = self._include_recording(key, recording)
            settings = {**self.settings, "revision": self.settings["revision"] + 1,
                        "selected": {**self.settings["selected"], key: recording["id"]},
                        "members": {**self.settings.get("members", {}), key: members}}
        if edit:
            settings = {**self.settings, "revision": self.settings["revision"] + 1}
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
        membership = {key: self.members(key) for key in self.settings["selected"]}
        selected = {key: self.profile_summary(key, identities) for key, identities in membership.items()}
        included = {identity for identities in membership.values() for identity in identities}
        sampler_error = None
        if self.task and self.task.done() and not self.task.cancelled() and self.task.exception():
            sampler_error = f"Recorder stopped: {self.task.exception()}"
        return {"mode": self.mode, "programs": self.programs(), **self.settings, "profiles": selected, "bosch": self.bosch.state(),
                "sampler_error": sampler_error,
                "managed": self.app.appliance_runs.view() if hasattr(self.app,"appliance_runs") else None,
                "now": self.app.now().isoformat(), "timezone": getattr(getattr(self.app,"policy",None),"timezone","Europe/Brussels"),
                "members": membership,
                "recordings": [{**row, "included": row["id"] in included}
                               for row in self._rows("status != 'discarded'")],
                "sample_seconds": SAMPLE_SECONDS, "maximum_gap_seconds": MAX_GAP_SECONDS}

    def members(self, key: str) -> list[str]:
        """An older single selection remains its sole contributor until explicitly changed."""
        values = self.settings.get("members", {}).get(key)
        if values is None:
            identity = self.settings["selected"].get(key)
            return [identity] if identity else []
        return list(values)

    def _include_recording(self, key: str, recording: dict[str, Any]) -> list[str]:
        """Include each physical capture once."""
        capture = recording.get("capture_id", recording["id"])
        members: list[str] = []
        replaced = False
        for identity in self.members(key):
            previous = self.get(identity)
            if previous.get("capture_id", identity) == capture:
                if not replaced:
                    members.append(recording["id"])
                    replaced = True
            else:
                members.append(identity)
        if not replaced:
            members.append(recording["id"])
        return members

    def profile_summary(self, key: str, identities: list[str]) -> dict[str, Any]:
        recordings = [self.get(identity) for identity in identities]
        summaries = [row["summary"] for row in recordings]
        duration = max(row["duration_seconds"] for row in summaries)
        energy = math.fsum(row["energy_kwh"] for row in summaries) / len(summaries)
        machine, program = key.split("/", 1)
        return {"id": self.settings["selected"][key], "machine": machine, "program": program,
                "averaged": True, "recording_ids": identities, "recording_count": len(identities),
                "selection_signature": sha256(encode([(row["id"], row["summary"], row.get("saved_at"))
                                                    for row in recordings]).encode()).hexdigest(),
                "summary": {"start_seconds": 0, "end_seconds": duration, "duration_seconds": duration,
                            "mean_duration_seconds": math.fsum(row["duration_seconds"] for row in summaries) / len(summaries),
                            "energy_kwh": energy, "average_w": energy * 3600000 / duration,
                            "complete": True, "peak_w": None}}

    async def profile_detail(self, machine: str, program: str) -> dict[str, Any]:
        key = f"{machine}/{program}"
        identities = self.members(key)
        if not identities:
            raise ValueError("No reviewed recordings are included in this profile")
        revision = self.settings["revision"]
        # The read-only worker has its own SQLite connection; large curves cannot block control.
        detail = await asyncio.to_thread(average_recordings, self.store.path, self.mode,
                                         machine, program, identities)
        if revision != self.settings["revision"]:
            raise ValueError("Profiles changed while loading; inspect the profile again")
        return {**self.profile_summary(key, identities), **detail, "revision": revision,
                "maximum_gap_seconds": MAX_CAPTURE_SECONDS}

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

    def configure_bosch(self, body: dict[str, Any]) -> dict[str, Any]:
        if type(body.get("revision")) is not int or body["revision"] != self.settings["revision"]:
            raise ValueError("Profiles changed in another view; reload before saving")
        if any(row["machine"] == "dishwasher" for row in self._rows("status IN ('armed','recording')")):
            raise ValueError("Finish this dishwasher recording before changing Bosch mappings")
        values = body.get("entities")
        if not isinstance(values, dict) or set(values) != set(FIELDS):
            raise ValueError("Supply every Bosch mapping, leaving unavailable optional entities blank")
        entities: dict[str, str] = {}
        for key, (_, domains) in FIELDS.items():
            entity = values[key]
            if not isinstance(entity, str) or (entity and (not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", entity)
                                                          or entity.split(".")[0] not in domains)):
                raise ValueError(f"Invalid Bosch {key} entity")
            entities[key] = entity
        mapped = [entity for entity in entities.values() if entity]
        if len(mapped) != len(set(mapped)):
            raise ValueError("Bosch controls/readings must use distinct entities; selected and active program are different controls")
        self._persist_settings({**self.settings, "bosch": entities})
        self.bosch.readings, self.bosch.at, self.bosch.previous = {}, None, None
        self.bosch.seen_run = False
        return self.library()

    def begin_automatic(self, program: str, observed_start: bool) -> str:
        recording = self._arm({"machine": "dishwasher", "program": program,
                               "notes": "Automatic Bosch capture; review modifiers and cycle before inclusion"}, automatic=True)
        modifiers = {key: self.bosch.value(key) for key in ("extra_dry", "half_load", "vario_speed")}
        recording.update(status="recording", source="bosch", started_at=self.app.now().isoformat(),
                         modifiers=modifiers, start_observed=observed_start, interrupted=not observed_start,
                         error=None if observed_start else "Cycle already running when observation began; start not observed")
        self._save(recording)
        return recording["id"]

    def interrupt(self, identity: str, reason: str) -> None:
        rows = self._rows("id=?", (identity,))
        if rows and rows[0]["status"] == "recording":
            recording = rows[0]
            recording.update(interrupted=True, interruption_reason=reason)
            self._save(recording)

    def end_automatic(self, identity: str, reason: str | None) -> None:
        rows = self._rows("id=?", (identity,))
        if not rows or rows[0]["status"] != "recording":
            return
        recording = rows[0]
        recording.update(status="review", finished_at=self.app.now().isoformat())
        if reason:
            recording.update(interrupted=True, interruption_reason=reason, error=reason)
        self._save(recording)

    def delete(self, identity: str, body: dict[str, Any]) -> None:
        """Permanently remove exactly one recording and its membership, in one transaction."""
        identity = self.get(identity)["id"]
        if body.get("confirmed") is not True:
            raise ValueError("Confirm permanent deletion of the recording and all its samples")
        if type(body.get("revision")) is not int or body["revision"] != self.settings["revision"]:
            raise ValueError("Profiles changed in another view; reload before deleting")
        selected = dict(self.settings["selected"])
        membership = dict(self.settings.get("members", {}))
        for key in set(selected) | set(membership):
            members = [item for item in self.members(key) if item != identity]
            membership[key] = members
            if selected.get(key) == identity:
                if members:
                    selected[key] = members[-1]
                else:
                    selected.pop(key)
        settings = {**self.settings, "revision": self.settings["revision"] + 1,
                    "selected": selected, "members": membership,
                    "recording_aliases": {old: target for old, target in self.settings.get("recording_aliases", {}).items()
                                          if target != identity}}
        with self.store.connection:
            self.store.connection.execute("DELETE FROM appliance_samples WHERE recording_id=?", (identity,))
            self.store.connection.execute("DELETE FROM appliance_recordings WHERE id=? AND mode=?", (identity, self.mode))
            self.store.connection.execute("INSERT OR REPLACE INTO state VALUES (?,?)",
                                          (self.key, json.dumps(settings, allow_nan=False)))
        self.settings = settings

    def get(self, identity: str) -> dict[str, Any]:
        identity = self.settings.get("recording_aliases", {}).get(identity, identity)
        rows = self._rows("id=?", (identity,))
        if not rows:
            raise ValueError("Unknown recording")
        return rows[0]

    def arm(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._arm(body)

    def _arm(self, body: dict[str, Any], *, automatic: bool = False) -> dict[str, Any]:
        machine, program = body.get("machine"), body.get("program")
        if machine not in self.programs() or program not in self.programs()[machine]:
            raise ValueError("Choose a supported appliance program")
        if self.app.demo or self.app.ha is None:
            raise ValueError("Recording requires configured mode and a mapped HA power sensor")
        if machine == "dishwasher" and self.bosch.enabled and not automatic:
            raise ValueError("Bosch captures actual runs automatically; no per-cycle arming is needed")
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
        rows = self._rows("id=?", (identity,))
        if not rows:
            return  # A deletion during an HA read cannot resurrect samples.
        recording = rows[0]
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
            if recording.get("source") == "bosch":
                self._save(recording)
                return  # Bosch completion is feedback-driven, including quiet drying phases.
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
        if recording.get("source") == "bosch":
            recording.update(interrupted=True, interruption_reason="Recording stopped before Bosch finished feedback")
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
        identity = recording["id"]
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

    def _review_summary(self, recording: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        if body.get("reviewed") is not True:
            raise ValueError("Explicit review confirmation is required")
        if type(body.get("revision")) is not int or body["revision"] != self.settings["revision"]:
            raise ValueError("Profiles changed in another view; reload before saving")
        summary = self.preview(recording["id"], body)
        if not summary["complete"]:
            raise ValueError("Recording contains missing measurements; trim to complete coverage or record again")
        if recording["interrupted"]:
            raise ValueError("Recording was interrupted; record a complete cycle before selecting a profile")
        return summary

    def accept(self, identity: str, body: dict[str, Any]) -> dict[str, Any]:
        recording = self.get(identity)
        if recording["status"] != "review":
            raise ValueError("Finish and review this recording before saving it")
        summary = self._review_summary(recording, body)
        recording.update(status="saved", summary=summary, saved_at=self.app.now().isoformat())
        self._save(recording, select=True)
        return recording

    def revise(self, identity: str, body: dict[str, Any]) -> dict[str, Any]:
        """Update the reviewed selection atomically, retaining identity, raw samples and inclusion."""
        recording = self.get(identity)
        if recording["status"] != "saved":
            raise ValueError("Only saved recordings can have a revised trim")
        summary = self._review_summary(recording, body)
        recording.update(summary=summary, saved_at=self.app.now().isoformat())
        self._save(recording, edit=True)
        return recording

    def select(self, identity: str, body: dict[str, Any]) -> None:
        recording = self.get(identity)
        identity = recording["id"]
        if recording["status"] != "saved":
            raise ValueError("Only reviewed saved recordings can be selected")
        if type(body.get("revision")) is not int or body["revision"] != self.settings["revision"]:
            raise ValueError("Profiles changed in another view; reload before selecting")
        key = f"{recording['machine']}/{recording['program']}"
        included = body.get("included", True)
        if type(included) is not bool:
            raise ValueError("Profile inclusion must be true or false")
        members = self.members(key)
        if included:
            members = self._include_recording(key, recording)
        if not included and identity in members:
            members.remove(identity)
        selected = dict(self.settings["selected"])
        if members:
            selected[key] = identity if included else members[-1]
        else:
            selected.pop(key, None)
        settings = {**self.settings, "selected": selected,
                    "members": {**self.settings.get("members", {}), key: members}}
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
            await asyncio.gather(self.bosch.poll(), *(self._sample(recording) for recording in
                                   self._rows("status IN ('armed','recording')")
                                   if recording.get("source") != "bosch"))
            await asyncio.sleep(SAMPLE_SECONDS)
