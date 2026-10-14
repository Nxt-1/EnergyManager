"""Versioned, bounded, atomic local decision archive. No network or hardware access."""

from __future__ import annotations

import dataclasses
import gzip
import hashlib
import json
import os
import re
import tempfile
import time
import zlib
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 1
MODEL_VERSION = "3.0-preview.2"
_ID = re.compile(r"^[a-f0-9]{32}$")


def encode(value):
    if dataclasses.is_dataclass(value):
        return {
            "$type": type(value).__name__,
            **{f.name: encode(getattr(value, f.name)) for f in dataclasses.fields(value)},
        }
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("archive timestamps must be timezone-aware")
        return {"$datetime": value.isoformat(), "zone": getattr(value.tzinfo, "key", None)}
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    if isinstance(value, (tuple, list)):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    return value


def canonical(value) -> str:
    return json.dumps(encode(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def decode(value):
    """Closed schema; never dynamically import a type from archived user input."""
    from . import actuators, config, economics, hierarchy, load_forecast, planner, pv_forecast, requirements, tasks

    modules = (actuators, config, economics, hierarchy, planner, requirements, tasks, load_forecast, pv_forecast)
    allowed = {
        name: cls
        for module in modules
        for name, cls in vars(module).items()
        if isinstance(cls, type) and dataclasses.is_dataclass(cls)
    }
    if isinstance(value, list):
        return tuple(decode(v) for v in value)
    if not isinstance(value, dict):
        return value
    if "$date" in value:
        return date.fromisoformat(value["$date"])
    if "$datetime" in value:
        dt = datetime.fromisoformat(value["$datetime"])
        if dt.tzinfo is None:
            raise ValueError("naive timestamp")
        return dt.astimezone(ZoneInfo(value["zone"])) if value.get("zone") else dt
    if "$type" in value:
        name = value["$type"]
        if name not in allowed:
            raise ValueError(f"unknown archive type: {name}")
        return allowed[name](**{k: decode(v) for k, v in value.items() if k != "$type"})
    return {k: decode(v) for k, v in value.items()}


@dataclasses.dataclass(frozen=True, slots=True)
class PlanningSnapshot:
    snapshot_id: str
    payload: str  # immutable canonical JSON, not a mutable dict in a frozen wrapper

    @classmethod
    def create(
        cls,
        frame,
        profile,
        capacity_state,
        policy,
        *,
        previous_plan=None,
        observations=(),
        forecast_revisions=(),
        ev_settings=None,
        forecasts=(),
    ):
        payload = canonical(
            {
                "schema_version": SCHEMA_VERSION,
                "model_version": MODEL_VERSION,
                "frame": frame,
                "profile": profile,
                "capacity_state": capacity_state,
                "policy": policy,
                "previous_plan": previous_plan,
                "observations": observations,
                "forecast_revisions": forecast_revisions,
                "ev_settings": ev_settings,
                "forecasts": forecasts,
                "solver_settings": {"threads": 1, "random_seed": 0, "import_weight_half_life_days": 3},
            }
        )
        return cls(hashlib.sha256(payload.encode()).hexdigest()[:32], payload)

    def inputs(self):
        raw = json.loads(self.payload)
        if (raw.get("schema_version") != SCHEMA_VERSION
                or raw.get("model_version") not in ("3.0-preview.1", MODEL_VERSION)):
            raise ValueError("unsupported snapshot schema/model; replay with the matching release")
        if hashlib.sha256(self.payload.encode()).hexdigest()[:32] != self.snapshot_id:
            raise ValueError("snapshot checksum mismatch")
        return decode(raw)

    def solve(self, *, restrictions=()):
        from .milp_planner import evaluate_plan_milp

        data = self.inputs()
        return evaluate_plan_milp(
            data["frame"],
            data["profile"],
            data["capacity_state"],
            policy=data["policy"],
            previous_plan=data["previous_plan"],
            restrictions=restrictions,
        )

    def regenerate(self):
        from .tasks import TaskRegistry

        data = self.inputs()
        if data["ev_settings"] is None:
            raise ValueError("snapshot has no generator configuration")
        frame = data["frame"]
        return TaskRegistry(data["ev_settings"]).snapshots(
            frame.actuator_snapshots,
            now_utc=frame.generated_at_utc,
            local_tz=frame.intervals[0].period_start_local.tzinfo,
        )


class DecisionStore:
    def __init__(self, root: Path, *, max_bytes: int = 1024 * 1024 * 1024, keep: int = 10000, days: int = 30):
        self.root, self.max_bytes, self.keep, self.days = root, max_bytes, keep, days
        if max_bytes < 1024 or keep < 1 or days < 1:
            raise ValueError("invalid archive bounds")

    def _path(self, identity: str) -> Path:
        if not _ID.fullmatch(identity):
            raise ValueError("invalid snapshot ID")
        return self.root / f"{identity}.json"

    def save(self, snapshot: PlanningSnapshot, evaluation, *, disposition: str, changes=()) -> None:
        snapshot.inputs()
        document = {
            "schema_version": SCHEMA_VERSION,
            "snapshot_id": snapshot.snapshot_id,
            "snapshot": json.loads(snapshot.payload),
            "evaluation": encode(evaluation),
            "disposition": disposition,
            "changes": encode(changes),
            "attribution": "Stage comparisons are facts; individual causal attribution is indeterminate "
            "without a counterfactual. Near-equivalent schedules may exist.",
        }
        document["decision_schema_version"] = 2
        document["decision_checksum"] = hashlib.sha256(canonical(document).encode()).hexdigest()
        raw = canonical(document).encode()
        body = gzip.compress(raw, compresslevel=6, mtime=0)
        if len(raw) > 32 * 1024 * 1024 or len(body) > self.max_bytes:
            raise ValueError("decision exceeds archive byte limit")
        self.root.mkdir(parents=True, exist_ok=True)
        target = self._path(snapshot.snapshot_id).with_suffix(".json.gz")
        descriptor, temp = tempfile.mkstemp(prefix=".pending-", dir=self.root)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, target)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        # Incomplete atomic writes are never replayed. Clean only stale files we own.
        for path in self.root.glob(".pending-*"):
            if path.is_file() and time.time() - path.stat().st_mtime > 86400:
                path.unlink()

        legacy = self._path(snapshot.snapshot_id)
        if legacy.exists():
            legacy.unlink()
        files = self._files()
        total = 0
        for index, path in enumerate(files):
            total += path.stat().st_size
            if index >= self.keep or total > self.max_bytes or time.time() - path.stat().st_mtime > self.days * 86400:
                path.unlink()

    def read(self, identity: str):
        path = self._path(identity)
        compressed = path.with_suffix(".json.gz")
        if compressed.exists():
            path = compressed
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("oversized decision")
        try:
            opener = gzip.open if path.suffix == ".gz" else open
            with opener(path, "rb") as handle:
                raw = handle.read(32 * 1024 * 1024 + 1)
            if len(raw) > 32 * 1024 * 1024:
                raise ValueError("oversized decompressed decision")
            document = json.loads(raw)
        except (OSError, EOFError, zlib.error, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("corrupt decision archive") from exc
        if document.get("decision_schema_version", 1) not in (1, 2):
            raise ValueError("unsupported decision schema")
        if document.get("decision_schema_version") == 2:
            expected = document.pop("decision_checksum", None)
            actual = hashlib.sha256(canonical(document).encode()).hexdigest()
            document["decision_checksum"] = expected
            if expected != actual:
                raise ValueError("decision checksum mismatch")
        if document.get("snapshot_id") != identity:
            raise ValueError("decision identity mismatch")
        if document.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported decision schema")
        snapshot = PlanningSnapshot(identity, canonical(document["snapshot"]))
        snapshot.inputs()
        return snapshot, document

    def _files(self):
        return sorted(
            (p for p in self.root.iterdir()
             if p.is_file() and (p.name.endswith(".json") or p.name.endswith(".json.gz"))
             and _ID.fullmatch(p.name.removesuffix(".gz").removesuffix(".json"))),
            key=lambda p: p.stat().st_mtime, reverse=True,
        ) if self.root.exists() else []

    def list_ids(self):
        return tuple(dict.fromkeys(p.name.split(".")[0] for p in self._files()))
