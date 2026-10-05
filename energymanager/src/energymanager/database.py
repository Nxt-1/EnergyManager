"""InfluxDB 3 persistence for Energy Manager time-series history."""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import aiohttp

from .load_forecast import MODEL_VERSION, BackgroundLoadForecast, LoadSample
from .open_meteo import FORECAST_MODEL
from .pv_forecast import CALIBRATION_VERSION, PvForecast

_LOGGER = logging.getLogger(__name__)
_LEGACY_PV_ARCHIVE = Path("/data/pv_forecast_revisions.jsonl")
_LEGACY_LOAD_HISTORY = Path("/data/background_load_history.jsonl")
_LEGACY_LOAD_ARCHIVE = Path("/data/background_load_forecast_revisions.jsonl")


class InfluxDatabaseError(RuntimeError):
    """Raised when the Energy Manager InfluxDB store cannot complete an operation."""


class InfluxDatabaseClient:
    """Small HTTP client for the InfluxDB 3 write and SQL query APIs."""

    def __init__(self, url: str, database: str, token: str) -> None:
        self._url = url.rstrip("/")
        self.database = database
        self._token = token
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> InfluxDatabaseClient:
        timeout = aiohttp.ClientTimeout(total=30)
        self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def ping(self) -> None:
        """Verify authentication and access to the configured database."""
        rows = await self.query_sql("SELECT 1 AS ok")
        if not rows or int(rows[0].get("ok", 0)) != 1:
            raise InfluxDatabaseError("InfluxDB connection test returned an unexpected result")

    async def write_lines(self, lines: list[str]) -> None:
        """Write line-protocol points with explicit nanosecond timestamps."""
        if not lines:
            return
        session = self._require_session()
        endpoint = f"{self._url}/api/v3/write_lp"
        params = {
            "db": self.database,
            "precision": "nanosecond",
            "accept_partial": "false",
            "no_sync": "false",
        }
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "text/plain; charset=utf-8",
        }
        try:
            async with session.post(endpoint, params=params, headers=headers, data="\n".join(lines)) as response:
                body = await response.text()
                if response.status not in (200, 204):
                    raise InfluxDatabaseError(
                        f"InfluxDB write failed with HTTP {response.status}: {_short_error(body)}"
                    )
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise InfluxDatabaseError(f"InfluxDB write failed: {exc}") from exc

    async def query_sql(self, query: str) -> list[dict[str, str]]:
        """Execute SQL and return rows as dictionaries using the CSV response format."""
        session = self._require_session()
        endpoint = f"{self._url}/api/v3/query_sql"
        headers = {"Authorization": f"Bearer {self._token}"}
        params = {"db": self.database, "q": query, "format": "csv"}
        try:
            async with session.get(endpoint, params=params, headers=headers) as response:
                body = await response.text()
                if response.status != 200:
                    raise InfluxDatabaseError(
                        f"InfluxDB query failed with HTTP {response.status}: {_short_error(body)}"
                    )
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise InfluxDatabaseError(f"InfluxDB query failed: {exc}") from exc
        return list(csv.DictReader(io.StringIO(body)))

    def _require_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise InfluxDatabaseError("InfluxDB client is not open")
        return self._session


class EnergyManagerStore:
    """Domain-specific persistent store backed by InfluxDB 3."""

    def __init__(self, client: InfluxDatabaseClient) -> None:
        self._client = client

    @property
    def database(self) -> str:
        return self._client.database

    async def initialize(self) -> tuple[int, int, int]:
        """Test connectivity, import legacy JSONL data, and return imported record counts."""
        await self._client.ping()
        pv_count = await self._migrate_legacy_pv_revisions()
        load_count = await self._migrate_legacy_load_history()
        forecast_count = await self._migrate_legacy_load_revisions()
        return pv_count, load_count, forecast_count

    async def load_background_samples(self, *, days: int = 35) -> tuple[LoadSample, ...]:
        """Load the active in-memory training window; database retention remains unlimited."""
        days = max(1, int(days))
        query = (
            'SELECT time, background_load_power_w FROM "house_load" '
            f"WHERE time >= now() - INTERVAL '{days} days' "
            "AND background_load_power_w IS NOT NULL ORDER BY time ASC"
        )
        rows = await self._client.query_sql(query)
        samples: list[LoadSample] = []
        for row in rows:
            try:
                observed = _parse_timestamp(row["time"])
                samples.append(LoadSample(observed, max(0.0, float(row["background_load_power_w"]))))
            except (KeyError, TypeError, ValueError):
                _LOGGER.warning("Ignoring invalid background-load row returned by InfluxDB")
        return tuple(samples)

    async def record_house_load(
        self,
        *,
        observed_at_utc: datetime,
        house_load_power_w: float | None,
        known_controllable_load_power_w: float | None,
        background_load_power_w: float,
    ) -> None:
        """Persist the canonical derived load signals at the predictor's five-minute sample cadence."""
        await self.record_house_load_batch(
            [(observed_at_utc, house_load_power_w, known_controllable_load_power_w, background_load_power_w)]
        )

    async def record_house_load_batch(
        self,
        rows: list[tuple[datetime, float | None, float | None, float | None]],
    ) -> None:
        """Persist canonical house-load rows, including historical backfill batches."""
        lines: list[str] = []
        for observed_at_utc, house_load, known_load, background_load in rows:
            fields: list[str] = []
            if background_load is not None:
                fields.append(f"background_load_power_w={max(0.0, background_load):.6f}")
            if house_load is not None:
                fields.append(f"house_load_power_w={max(0.0, house_load):.6f}")
            if known_load is not None:
                fields.append(f"known_controllable_load_power_w={max(0.0, known_load):.6f}")
            if fields:
                lines.append(f"house_load {','.join(fields)} {_timestamp_ns(observed_at_utc)}")
        await _write_in_batches(self._client, lines)

    async def load_legacy_source_state(
        self,
        *,
        signal: str,
        entity_id: str,
        normalization_version: str,
    ) -> dict[str, str] | None:
        """Return the latest coverage marker for one logical legacy source mapping."""
        if not await self._table_exists("legacy_source_state"):
            return None
        signal_sql = _escape_sql_string(signal)
        entity_sql = _escape_sql_string(entity_id)
        version_sql = _escape_sql_string(normalization_version)
        query = (
            'SELECT source_start_utc, source_end_utc, rows FROM "legacy_source_state" '
            f"WHERE signal = '{signal_sql}' AND entity_id = '{entity_sql}' "
            f"AND normalization_version = '{version_sql}' ORDER BY time DESC LIMIT 1"
        )
        rows = await self._client.query_sql(query)
        return rows[0] if rows else None

    async def record_legacy_source_state(
        self,
        *,
        signal: str,
        entity_id: str,
        normalization_version: str,
        source_start_utc: datetime,
        source_end_utc: datetime,
        rows: int,
    ) -> None:
        """Persist imported coverage for one selected legacy Home Assistant source."""
        tags = (
            f"signal={_escape_tag(signal)},entity_id={_escape_tag(entity_id)},"
            f"normalization_version={_escape_tag(normalization_version)}"
        )
        fields = (
            f'source_start_utc="{_escape_string(source_start_utc.isoformat())}",'
            f'source_end_utc="{_escape_string(source_end_utc.isoformat())}",'
            f"rows={rows}i"
        )
        line = f"legacy_source_state,{tags} {fields} {_timestamp_ns(datetime.now(UTC))}"
        await self._client.write_lines([line])

    async def record_legacy_power_source_batch(
        self,
        *,
        signal: str,
        entity_id: str,
        rows: list[tuple[datetime, float]],
    ) -> None:
        """Archive normalized five-minute history for a selected legacy power source."""
        tags = f"signal={_escape_tag(signal)},entity_id={_escape_tag(entity_id)}"
        lines = [
            f"legacy_power_source,{tags} power_w={value:.6f} {_timestamp_ns(observed)}"
            for observed, value in rows
        ]
        await _write_in_batches(self._client, lines)

    async def load_legacy_power_source(
        self,
        *,
        signal: str,
        entity_id: str,
        start_utc: datetime,
        end_utc: datetime,
    ) -> dict[datetime, float]:
        """Load archived normalized source power for a UTC range."""
        if not await self._table_exists("legacy_power_source"):
            return {}
        signal_sql = _escape_sql_string(signal)
        entity_sql = _escape_sql_string(entity_id)
        start_sql = _escape_sql_string(start_utc.astimezone(UTC).isoformat())
        end_sql = _escape_sql_string(end_utc.astimezone(UTC).isoformat())
        query = (
            'SELECT time, power_w FROM "legacy_power_source" '
            f"WHERE signal = '{signal_sql}' AND entity_id = '{entity_sql}' "
            f"AND time >= '{start_sql}' AND time < '{end_sql}' ORDER BY time ASC"
        )
        rows = await self._client.query_sql(query)
        values: dict[datetime, float] = {}
        for row in rows:
            try:
                values[_parse_timestamp(row["time"])] = float(row["power_w"])
            except (KeyError, TypeError, ValueError):
                _LOGGER.warning("Ignoring invalid archived legacy power-source row")
        return values

    async def load_legacy_derivation_state(
        self,
        derivation_id: str,
        fingerprint: str,
    ) -> dict[str, str] | None:
        """Return coverage for one derived-history recipe and configured source set."""
        if not await self._table_exists("legacy_derivation_state"):
            return None
        derivation_sql = _escape_sql_string(derivation_id)
        fingerprint_sql = _escape_sql_string(fingerprint)
        query = (
            'SELECT source_start_utc, source_end_utc, house_rows, background_rows, skipped_rows '
            'FROM "legacy_derivation_state" '
            f"WHERE derivation_id = '{derivation_sql}' AND fingerprint = '{fingerprint_sql}' "
            "ORDER BY time DESC LIMIT 1"
        )
        rows = await self._client.query_sql(query)
        return rows[0] if rows else None

    async def record_legacy_derivation_state(
        self,
        *,
        derivation_id: str,
        fingerprint: str,
        source_start_utc: datetime,
        source_end_utc: datetime,
        house_rows: int,
        background_rows: int,
        skipped_rows: int,
    ) -> None:
        """Persist coverage for derived history without globally closing future backfill."""
        tags = f"derivation_id={_escape_tag(derivation_id)},fingerprint={_escape_tag(fingerprint)}"
        fields = (
            f'source_start_utc="{_escape_string(source_start_utc.isoformat())}",'
            f'source_end_utc="{_escape_string(source_end_utc.isoformat())}",'
            f"house_rows={house_rows}i,background_rows={background_rows}i,skipped_rows={skipped_rows}i"
        )
        line = f"legacy_derivation_state,{tags} {fields} {_timestamp_ns(datetime.now(UTC))}"
        await self._client.write_lines([line])

    async def _table_exists(self, table_name: str) -> bool:
        table_sql = _escape_sql_string(table_name)
        rows = await self._client.query_sql(
            "SELECT table_name FROM information_schema.tables "
            f"WHERE table_name = '{table_sql}' LIMIT 1"
        )
        return bool(rows)

    async def record_pv_forecast(self, forecast: PvForecast, now_local: datetime) -> None:
        """Persist one row per forecast target day for a rolling PV forecast revision."""
        issued_at = forecast.generated_at_utc.astimezone(UTC)
        lines = []
        for item in forecast.daily_energies():
            tags = f"target_date={_escape_tag(item.target_date.isoformat())}"
            fields = (
                f"front_kwh={item.front_kwh:.6f},rear_kwh={item.rear_kwh:.6f},"
                f"shed_kwh={item.shed_kwh:.6f},total_kwh={item.total_kwh:.6f},"
                f'model="{_escape_string(FORECAST_MODEL)}",'
                f'calibration_version="{_escape_string(CALIBRATION_VERSION)}",'
                f'issued_at_local="{_escape_string(now_local.isoformat())}"'
            )
            lines.append(f"pv_forecast_revision,{tags} {fields} {_timestamp_ns(issued_at)}")
        await self._client.write_lines(lines)

    async def record_background_forecast(
        self,
        forecast: BackgroundLoadForecast,
        now_local: datetime,
    ) -> None:
        """Persist daily summaries of one rolling background-load forecast revision."""
        lines = []
        for offset in range(1, 8):
            target = now_local.date() + timedelta(days=offset)
            item = forecast.daily_energy(target)
            if item is None:
                continue
            tags = f"target_date={_escape_tag(target.isoformat())}"
            fields = (
                f"energy_kwh={item.energy_kwh:.6f},"
                f"history_sample_count={forecast.history_sample_count}i,"
                f"history_days={forecast.history_days:.6f},"
                f'model_version="{_escape_string(MODEL_VERSION)}",'
                f'issued_at_local="{_escape_string(now_local.isoformat())}"'
            )
            lines.append(
                f"background_load_forecast_revision,{tags} {fields} "
                f"{_timestamp_ns(forecast.generated_at_utc)}"
            )
        await self._client.write_lines(lines)

    async def _migrate_legacy_pv_revisions(self) -> int:
        records = _read_jsonl(_LEGACY_PV_ARCHIVE)
        lines: list[str] = []
        count = 0
        for record in records:
            try:
                issued_at = _parse_timestamp(str(record["issued_at_utc"]))
                issued_local = str(record.get("issued_at_local", ""))
                model = str(record.get("model", FORECAST_MODEL))
                calibration = str(record.get("calibration_version", CALIBRATION_VERSION))
                for item in record.get("daily", []):
                    target = str(item["target_date"])
                    tags = f"target_date={_escape_tag(target)}"
                    fields = (
                        f"front_kwh={float(item['front_kwh']):.6f},"
                        f"rear_kwh={float(item['rear_kwh']):.6f},"
                        f"shed_kwh={float(item['shed_kwh']):.6f},"
                        f"total_kwh={float(item['total_kwh']):.6f},"
                        f'model="{_escape_string(model)}",'
                        f'calibration_version="{_escape_string(calibration)}",'
                        f'issued_at_local="{_escape_string(issued_local)}"'
                    )
                    lines.append(f"pv_forecast_revision,{tags} {fields} {_timestamp_ns(issued_at)}")
                    count += 1
            except (KeyError, TypeError, ValueError):
                _LOGGER.warning("Ignoring invalid legacy PV forecast revision during migration")
        await _write_in_batches(self._client, lines)
        _mark_migrated(_LEGACY_PV_ARCHIVE)
        return count

    async def _migrate_legacy_load_history(self) -> int:
        records = _read_jsonl(_LEGACY_LOAD_HISTORY)
        lines: list[str] = []
        for record in records:
            try:
                observed = _parse_timestamp(str(record["observed_at_utc"]))
                power = max(0.0, float(record["power_w"]))
                lines.append(f"house_load background_load_power_w={power:.6f} {_timestamp_ns(observed)}")
            except (KeyError, TypeError, ValueError):
                _LOGGER.warning("Ignoring invalid legacy background-load sample during migration")
        await _write_in_batches(self._client, lines)
        _mark_migrated(_LEGACY_LOAD_HISTORY)
        return len(lines)

    async def _migrate_legacy_load_revisions(self) -> int:
        records = _read_jsonl(_LEGACY_LOAD_ARCHIVE)
        lines: list[str] = []
        count = 0
        for record in records:
            try:
                issued_at = _parse_timestamp(str(record["issued_at_utc"]))
                issued_local = str(record.get("issued_at_local", ""))
                model_version = str(record.get("model_version", MODEL_VERSION))
                sample_count = int(record.get("history_sample_count", 0))
                history_days = float(record.get("history_days", 0.0))
                for item in record.get("daily", []):
                    target = str(item["target_date"])
                    tags = f"target_date={_escape_tag(target)}"
                    fields = (
                        f"energy_kwh={float(item['energy_kwh']):.6f},"
                        f"history_sample_count={sample_count}i,history_days={history_days:.6f},"
                        f'model_version="{_escape_string(model_version)}",'
                        f'issued_at_local="{_escape_string(issued_local)}"'
                    )
                    lines.append(
                        f"background_load_forecast_revision,{tags} {fields} {_timestamp_ns(issued_at)}"
                    )
                    count += 1
            except (KeyError, TypeError, ValueError):
                _LOGGER.warning("Ignoring invalid legacy background-load forecast revision during migration")
        await _write_in_batches(self._client, lines)
        _mark_migrated(_LEGACY_LOAD_ARCHIVE)
        return count


async def _write_in_batches(client: InfluxDatabaseClient, lines: list[str], batch_size: int = 1000) -> None:
    for index in range(0, len(lines), batch_size):
        await client.write_lines(lines[index : index + batch_size])


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _LOGGER.warning("Could not read legacy persistence file %s: %s", path, exc)
        return []
    records: list[dict[str, Any]] = []
    for line in raw_lines:
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                records.append(value)
        except json.JSONDecodeError:
            _LOGGER.warning("Ignoring invalid JSON line in legacy persistence file %s", path)
    return records


def _mark_migrated(path: Path) -> None:
    """Keep a one-time backup of legacy JSONL after a successful database migration."""
    if not path.exists():
        return
    migrated_path = path.with_name(f"{path.name}.migrated")
    try:
        if migrated_path.exists():
            migrated_path.unlink()
        path.replace(migrated_path)
    except OSError as exc:
        _LOGGER.warning("Could not mark legacy persistence file %s as migrated: %s", path, exc)


def _parse_timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _timestamp_ns(value: datetime) -> int:
    utc = value.astimezone(UTC)
    return int(utc.timestamp()) * 1_000_000_000 + utc.microsecond * 1000


def _escape_tag(value: str) -> str:
    return value.replace("\\", "\\\\").replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def _escape_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape_sql_string(value: str) -> str:
    return value.replace("'", "''")


def _short_error(value: str, limit: int = 300) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= limit else f"{compact[:limit]}..."
