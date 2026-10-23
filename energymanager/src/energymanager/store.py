"""Append-only decision evidence and transactional current household state."""

from __future__ import annotations

import json
import sqlite3
import zlib
from hashlib import sha256
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .domain import encode
from .load_forecast import LoadSample


def archive_json(value: Any) -> bytes:
    return zlib.compress(encode(value).encode(), level=6)


def read_archive(value: str | bytes) -> str:
    return zlib.decompress(value).decode() if isinstance(value, bytes) else value


class Store:
    def __init__(self, path: str | Path) -> None:
        self.connection = sqlite3.connect(str(path))
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY, at TEXT NOT NULL, disposition TEXT NOT NULL,
                digest TEXT NOT NULL, snapshot TEXT NOT NULL, result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS load_samples (at REAL PRIMARY KEY, power_w REAL NOT NULL);
        """)

    def close(self) -> None:
        self.connection.close()

    def record_load(self, sample: LoadSample) -> None:
        with self.connection:
            self.connection.execute("INSERT OR IGNORE INTO load_samples VALUES (?,?)",
                                    (sample.observed_at_utc.timestamp(), sample.power_w))

    def load_samples(self, since: datetime) -> tuple[LoadSample, ...]:
        rows = self.connection.execute("SELECT at,power_w FROM load_samples WHERE at>=? ORDER BY at",
                                       (since.timestamp(),))
        return tuple(LoadSample(datetime.fromtimestamp(at, UTC), power) for at, power in rows)

    def get(self, key: str, default: Any = None) -> Any:
        row = self.connection.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key: str, value: Any) -> None:
        with self.connection:
            self.connection.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, encode(value)))

    def event(self, kind: str, body: Any) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO events(at,kind,body) VALUES (?,?,?)",
                (datetime.now(UTC).isoformat(), kind, encode(body)),
            )

    def events(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT at,kind,body FROM events ORDER BY sequence DESC LIMIT ?", (min(1000, max(1, limit)),)
        )
        return [{"at": row[0], "kind": row[1], "body": json.loads(row[2])} for row in rows]

    def record(self, snapshot: Any, result: dict[str, Any], disposition: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO decisions VALUES (?,?,?,?,?,?)",
                (
                    result["id"],
                    datetime.now(UTC).isoformat(),
                    disposition,
                    snapshot.digest,
                    archive_json(snapshot),
                    archive_json(result),
                ),
            )
            if disposition == "accepted":
                self.connection.execute(
                    "INSERT OR REPLACE INTO state VALUES ('accepted',?)", (encode(result),)
                )

    def decisions(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id,at,disposition,digest,result FROM decisions ORDER BY at DESC LIMIT ?",
            (min(100, max(1, limit)),),
        )
        return [
            {
                "id": r[0],
                "at": r[1],
                "disposition": r[2],
                "digest": r[3],
                "summary": json.loads(read_archive(r[4])).get("summary", {}),
            }
            for r in rows
        ]

    def decision(self, identity: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT digest,snapshot,result,disposition FROM decisions WHERE id=?", (identity,)
        ).fetchone()
        if not row:
            return None
        snapshot_text = read_archive(row[1])
        if sha256(snapshot_text.encode()).hexdigest() != row[0]:
            raise ValueError("Decision snapshot checksum mismatch")
        return {
            "digest": row[0],
            "snapshot": json.loads(snapshot_text),
            "result": json.loads(read_archive(row[2])),
            "disposition": row[3],
        }
