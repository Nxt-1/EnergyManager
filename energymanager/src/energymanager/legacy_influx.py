"""Incremental backfill from the legacy Home Assistant InfluxDB 1.x database."""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp

from .config import LegacyInfluxSettings, Settings
from .database import EnergyManagerStore

_LOGGER = logging.getLogger(__name__)
_DERIVATION_ID = "house_background_v4_ev_idle_fallback"
_SOURCE_NORMALIZATION_VERSION = "power_w_v1"
_BUCKET = timedelta(minutes=5)
_CHUNK = timedelta(days=14)
_EV_NOISE_FLOOR_W = 100.0
_ACTIVE_SAMPLE_MAX_AGE = timedelta(minutes=15)
_STALE_NEAR_ZERO_THRESHOLD_W = 50.0


class LegacyInfluxError(RuntimeError):
    """Raised when the legacy InfluxDB source cannot be queried safely."""


@dataclass(frozen=True, slots=True)
class LegacySeries:
    """One discovered Home Assistant power series in InfluxDB 1.x."""

    entity_id: str
    entity_tag: str
    measurement: str
    scale_to_w: float
    first_at_utc: datetime
    last_at_utc: datetime


@dataclass(frozen=True, slots=True)
class LegacySourceDefinition:
    """Configured logical source that EnergyManager wants to retain historically."""

    key: str
    entity_id: str
    normalization_version: str


@dataclass(frozen=True, slots=True)
class LegacyBackfillResult:
    """Summary of one incremental legacy-history synchronization."""

    status: str
    source_start_utc: datetime | None = None
    source_end_utc: datetime | None = None
    source_rows: int = 0
    sources_updated: int = 0
    house_rows: int = 0
    background_rows: int = 0
    skipped_rows: int = 0


class LegacyInfluxClient:
    """Minimal InfluxDB 1.x HTTP client for Home Assistant history."""

    def __init__(self, settings: LegacyInfluxSettings) -> None:
        if settings.url is None:
            raise LegacyInfluxError("legacy_influx.url is required for backfill")
        self._url = settings.url.rstrip("/")
        self._database = settings.database
        self._retention_policy = settings.retention_policy
        self._username = settings.username
        self._password = settings.password
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> LegacyInfluxClient:
        auth = None
        if self._username is not None and self._password is not None:
            auth = aiohttp.BasicAuth(self._username, self._password)
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            auth=auth,
        )
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def ping(self) -> None:
        session = self._require_session()
        try:
            async with session.get(f"{self._url}/ping") as response:
                if response.status != 204:
                    body = await response.text()
                    raise LegacyInfluxError(
                        f"Legacy InfluxDB ping failed with HTTP {response.status}: {_short_error(body)}"
                    )
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise LegacyInfluxError(f"Legacy InfluxDB ping failed: {exc}") from exc

    async def discover_power_series(self, entity_id: str) -> LegacySeries:
        """Find the legacy measurement for one configured Home Assistant power entity."""
        candidates = _legacy_entity_candidates(entity_id)
        for entity_tag in candidates:
            keys = await self._show_series(entity_tag)
            for key in keys:
                measurement = _series_measurement(key)
                scale = _power_scale(measurement)
                if scale is None:
                    continue
                bounds = await self._series_bounds(measurement, entity_tag)
                if bounds is None:
                    continue
                first_at, last_at = bounds
                return LegacySeries(
                    entity_id=entity_id,
                    entity_tag=entity_tag,
                    measurement=measurement,
                    scale_to_w=scale,
                    first_at_utc=first_at,
                    last_at_utc=last_at,
                )
        raise LegacyInfluxError(
            f"No numeric W/kW power series found in legacy InfluxDB for configured entity {entity_id}"
        )

    async def read_five_minute_power(
        self,
        series: LegacySeries,
        start_utc: datetime,
        end_utc: datetime,
    ) -> dict[datetime, float]:
        """Read five-minute mean power values for a UTC range."""
        measurement = self._measurement_source(series.measurement)
        entity = _quote_string(series.entity_tag)
        start = _rfc3339(start_utc)
        end = _rfc3339(end_utc)
        query = (
            f'SELECT mean("value") AS "value" FROM {measurement} '
            f'WHERE "entity_id" = \'{entity}\' AND time >= \'{start}\' AND time < \'{end}\' '
            "GROUP BY time(5m) fill(none)"
        )
        payload = await self.query(query)
        points: dict[datetime, float] = {}
        for columns, values in _series_rows(payload):
            try:
                time_index = columns.index("time")
                value_index = columns.index("value")
            except ValueError:
                continue
            for row in values:
                if len(row) <= max(time_index, value_index) or row[value_index] is None:
                    continue
                try:
                    observed = _parse_timestamp(str(row[time_index]))
                    value_w = float(row[value_index]) * series.scale_to_w
                except (TypeError, ValueError):
                    continue
                points[observed] = value_w
        return points

    async def query(self, query: str) -> dict[str, Any]:
        session = self._require_session()
        params = {"db": self._database, "q": query}
        try:
            async with session.get(f"{self._url}/query", params=params) as response:
                body = await response.text()
                if response.status != 200:
                    raise LegacyInfluxError(
                        f"Legacy InfluxDB query failed with HTTP {response.status}: {_short_error(body)}"
                    )
                try:
                    payload = await response.json(content_type=None)
                except ValueError as exc:
                    raise LegacyInfluxError("Legacy InfluxDB returned invalid JSON") from exc
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise LegacyInfluxError(f"Legacy InfluxDB query failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise LegacyInfluxError("Legacy InfluxDB returned an unexpected response")
        for result in payload.get("results", []):
            if isinstance(result, dict) and result.get("error"):
                raise LegacyInfluxError(f"Legacy InfluxDB query failed: {result['error']}")
        return payload

    async def _show_series(self, entity_tag: str) -> list[str]:
        query = f'SHOW SERIES WHERE "entity_id" = \'{_quote_string(entity_tag)}\''
        payload = await self.query(query)
        keys: list[str] = []
        for columns, values in _series_rows(payload):
            try:
                key_index = columns.index("key")
            except ValueError:
                continue
            for row in values:
                if len(row) > key_index and row[key_index] is not None:
                    keys.append(str(row[key_index]))
        return keys

    async def _series_bounds(self, measurement: str, entity_tag: str) -> tuple[datetime, datetime] | None:
        measurement_name = self._measurement_source(measurement)
        entity = _quote_string(entity_tag)
        first_payload = await self.query(
            f'SELECT first("value") AS "value" FROM {measurement_name} WHERE "entity_id" = \'{entity}\''
        )
        last_payload = await self.query(
            f'SELECT last("value") AS "value" FROM {measurement_name} WHERE "entity_id" = \'{entity}\''
        )
        first = _single_row_time(first_payload)
        last = _single_row_time(last_payload)
        if first is None or last is None:
            return None
        return first, last

    def _measurement_source(self, measurement: str) -> str:
        return f"{_quote_identifier(self._retention_policy)}.{_quote_identifier(measurement)}"

    def _require_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise LegacyInfluxError("Legacy InfluxDB client is not open")
        return self._session


class LegacyInfluxBackfill:
    """Incrementally archive selected HA signals and reconstruct canonical load history."""

    def __init__(self, settings: Settings, source: LegacyInfluxClient, target: EnergyManagerStore) -> None:
        self._settings = settings
        self._source = source
        self._target = target

    async def run(self) -> LegacyBackfillResult:
        """Synchronize only configured EnergyManager sources that are new or have extended coverage."""
        await self._source.ping()
        definitions = self._configured_sources()
        discovered = {
            key: await self._source.discover_power_series(definition.entity_id)
            for key, definition in definitions.items()
        }

        source_rows = 0
        sources_updated = 0
        for key, definition in definitions.items():
            imported = await self._sync_source(definition, discovered[key])
            source_rows += imported
            if imported:
                sources_updated += 1

        start = max(_ceil_bucket(item.first_at_utc) for item in discovered.values())
        end = min(_floor_bucket(item.last_at_utc) for item in discovered.values())
        if end <= start:
            raise LegacyInfluxError("Configured legacy power series have no overlapping complete five-minute history")

        fingerprint = _derivation_fingerprint(definitions, self._settings.ess.power_positive_means)
        derivation = await self._target.load_legacy_derivation_state(_DERIVATION_ID, fingerprint)
        ranges = _missing_coverage_ranges(derivation, start, end)

        house_rows = 0
        background_rows = 0
        skipped_rows = 0
        for range_start, range_end in ranges:
            cursor = range_start
            while cursor < range_end:
                chunk_end = min(cursor + _CHUNK, range_end)
                values: dict[str, dict[datetime, float]] = {}
                for key, definition in definitions.items():
                    source_values = await self._target.load_legacy_power_source(
                        signal=key,
                        entity_id=definition.entity_id,
                        start_utc=cursor,
                        end_utc=chunk_end,
                    )
                    seed = await self._target.load_legacy_power_source_seed(
                        signal=key,
                        entity_id=definition.entity_id,
                        before_utc=cursor,
                    )
                    if seed is not None:
                        seed_time, seed_value = seed
                        source_values.setdefault(seed_time, seed_value)
                    values[key] = source_values

                rows, chunk_house, chunk_background, chunk_skipped = _reconstruct_rows(
                    values,
                    start_utc=cursor,
                    end_utc=chunk_end,
                    ev_configured="ev" in definitions,
                )
                await self._target.record_legacy_house_load_batch(rows)
                house_rows += chunk_house
                background_rows += chunk_background
                skipped_rows += chunk_skipped
                cursor = chunk_end

        if ranges:
            previous_house = _optional_int(derivation.get("house_rows")) if derivation else 0
            previous_background = _optional_int(derivation.get("background_rows")) if derivation else 0
            previous_skipped = _optional_int(derivation.get("skipped_rows")) if derivation else 0
            await self._target.record_legacy_derivation_state(
                derivation_id=_DERIVATION_ID,
                fingerprint=fingerprint,
                source_start_utc=start,
                source_end_utc=end,
                house_rows=previous_house + house_rows,
                background_rows=previous_background + background_rows,
                skipped_rows=previous_skipped + skipped_rows,
            )

        status = "updated" if source_rows or ranges else "up_to_date"
        _LOGGER.info(
            "Legacy InfluxDB sync %s: sources_updated=%d source_rows=%d house=%d background=%d skipped=%d",
            status,
            sources_updated,
            source_rows,
            house_rows,
            background_rows,
            skipped_rows,
        )
        return LegacyBackfillResult(
            status=status,
            source_start_utc=start,
            source_end_utc=end,
            source_rows=source_rows,
            sources_updated=sources_updated,
            house_rows=house_rows,
            background_rows=background_rows,
            skipped_rows=skipped_rows,
        )

    async def _sync_source(self, definition: LegacySourceDefinition, series: LegacySeries) -> int:
        start = _ceil_bucket(series.first_at_utc)
        end = _floor_bucket(series.last_at_utc)
        if end <= start:
            return 0

        state = await self._target.load_legacy_source_state(
            signal=definition.key,
            entity_id=definition.entity_id,
            normalization_version=definition.normalization_version,
        )
        ranges = _missing_coverage_ranges(state, start, end)
        imported = 0
        for range_start, range_end in ranges:
            cursor = range_start
            while cursor < range_end:
                chunk_end = min(cursor + _CHUNK, range_end)
                raw = await self._source.read_five_minute_power(series, cursor, chunk_end)
                normalized = _normalize_source_values(definition.key, raw, self._settings.ess.power_positive_means)
                await self._target.record_legacy_power_source_batch(
                    signal=definition.key,
                    entity_id=definition.entity_id,
                    rows=normalized,
                )
                imported += len(normalized)
                cursor = chunk_end

        if ranges:
            previous_rows = _optional_int(state.get("rows")) if state else 0
            await self._target.record_legacy_source_state(
                signal=definition.key,
                entity_id=definition.entity_id,
                normalization_version=definition.normalization_version,
                source_start_utc=start,
                source_end_utc=end,
                rows=previous_rows + imported,
            )
            _LOGGER.info(
                "Legacy source synced: %s <- %s, imported=%d, coverage=%s..%s",
                definition.key,
                definition.entity_id,
                imported,
                start.isoformat(),
                end.isoformat(),
            )
        return imported

    def _configured_sources(self) -> dict[str, LegacySourceDefinition]:
        required = {
            "grid_import": self._settings.grid.import_power_entity,
            "grid_export": self._settings.grid.export_power_entity,
            "ess": self._settings.ess.power_entity,
            "solax": self._settings.pv.solax_power_entity,
        }
        missing = [name for name, entity_id in required.items() if entity_id is None]
        if missing:
            raise LegacyInfluxError(
                "Cannot backfill house load without configured current entity mappings: " + ", ".join(missing)
            )

        sources = {
            key: LegacySourceDefinition(key, entity_id, _source_normalization_version(key, self._settings))
            for key, entity_id in required.items()
            if entity_id is not None
        }
        if self._settings.ev.charging_power_entity is not None:
            entity_id = self._settings.ev.charging_power_entity
            sources["ev"] = LegacySourceDefinition(
                "ev",
                entity_id,
                _source_normalization_version("ev", self._settings),
            )
        return sources


def _normalize_source_values(
    key: str,
    values: dict[datetime, float],
    ess_positive_means: str,
) -> list[tuple[datetime, float]]:
    normalized: list[tuple[datetime, float]] = []
    ess_sign = -1.0 if ess_positive_means == "charge" else 1.0
    for observed, value in sorted(values.items()):
        if not math.isfinite(value):
            continue
        if key == "ess":
            normalized.append((observed, value * ess_sign))
            continue
        if key == "ev" and -_EV_NOISE_FLOOR_W <= value < 0:
            value = 0.0
        if value < 0:
            continue
        normalized.append((observed, value))
    return normalized


def _source_normalization_version(key: str, settings: Settings) -> str:
    if key == "ess":
        return f"{_SOURCE_NORMALIZATION_VERSION}:ess_{settings.ess.power_positive_means}"
    if key == "ev":
        return f"{_SOURCE_NORMALIZATION_VERSION}:ev_noise_{int(_EV_NOISE_FLOOR_W)}w"
    return _SOURCE_NORMALIZATION_VERSION


def _derivation_fingerprint(definitions: dict[str, LegacySourceDefinition], ess_positive_means: str) -> str:
    parts = [f"recipe={_DERIVATION_ID}", f"ess={ess_positive_means}"]
    parts.extend(
        f"{key}={definition.entity_id}:{definition.normalization_version}"
        for key, definition in sorted(definitions.items())
    )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]


def _missing_coverage_ranges(
    state: dict[str, str] | None,
    source_start: datetime,
    source_end: datetime,
) -> list[tuple[datetime, datetime]]:
    if state is None:
        return [(source_start, source_end)]
    covered_start = _optional_timestamp(state.get("source_start_utc"))
    covered_end = _optional_timestamp(state.get("source_end_utc"))
    if covered_start is None or covered_end is None:
        return [(source_start, source_end)]

    ranges: list[tuple[datetime, datetime]] = []
    if source_start < covered_start:
        ranges.append((source_start, min(covered_start, source_end)))
    if covered_end < source_end:
        ranges.append((max(covered_end, source_start), source_end))
    return [(start, end) for start, end in ranges if end > start]


def _reconstruct_rows(
    values: dict[str, dict[datetime, float]],
    *,
    start_utc: datetime,
    end_utc: datetime,
    ev_configured: bool,
) -> tuple[list[tuple[datetime, float, float | None, float | None]], int, int, int]:
    """Rebuild a regular five-minute load timeline from sparse historical state updates.

    Home Assistant's legacy InfluxDB history may omit buckets when an entity value did not
    change. Recent non-zero values are therefore carried forward briefly, while stale values
    close to zero decay to zero and may be held indefinitely. Stale material non-zero values
    are rejected so a sensor outage is not silently stretched across history.
    """
    required = ("grid_import", "grid_export", "ess", "solax")
    keys = (*required, "ev") if ev_configured else required
    states: dict[str, tuple[datetime, float] | None] = {
        key: _latest_before(values.get(key, {}), start_utc) for key in keys
    }

    rows: list[tuple[datetime, float, float | None, float | None]] = []
    house_rows = 0
    background_rows = 0
    skipped_rows = 0

    observed = start_utc
    while observed < end_utc:
        for key in keys:
            if observed in values.get(key, {}):
                states[key] = (observed, values[key][observed])

        resolved = {
            key: _resolve_historical_state(
                states[key],
                observed,
                stale_to_zero=key == "ev",
            )
            for key in keys
        }
        if any(resolved[key] is None for key in required):
            skipped_rows += 1
            observed += _BUCKET
            continue

        grid_import = resolved["grid_import"]
        grid_export = resolved["grid_export"]
        ess = resolved["ess"]
        solax = resolved["solax"]
        assert grid_import is not None
        assert grid_export is not None
        assert ess is not None
        assert solax is not None

        if min(grid_import, grid_export, solax) < 0:
            skipped_rows += 1
            observed += _BUCKET
            continue

        house = max(0.0, grid_import - grid_export + solax + ess)
        house_rows += 1

        known: float | None = None
        background: float | None = None
        if not ev_configured:
            known = 0.0
            background = house
        else:
            ev = resolved.get("ev")
            if ev is not None and ev >= 0:
                known = ev
                background = max(0.0, house - ev)

        if background is not None:
            background_rows += 1
        rows.append((observed, house, known, background))
        observed += _BUCKET

    return rows, house_rows, background_rows, skipped_rows


def _latest_before(
    values: dict[datetime, float],
    before_utc: datetime,
) -> tuple[datetime, float] | None:
    candidates = ((observed, value) for observed, value in values.items() if observed < before_utc)
    return max(candidates, default=None, key=lambda item: item[0])


def _resolve_historical_state(
    state: tuple[datetime, float] | None,
    observed_at_utc: datetime,
    *,
    stale_to_zero: bool = False,
) -> float | None:
    if state is None:
        return None
    state_time, value = state
    age = observed_at_utc - state_time
    if age < timedelta(0):
        return None
    if age <= _ACTIVE_SAMPLE_MAX_AGE:
        return value
    if stale_to_zero:
        return 0.0
    if abs(value) <= _STALE_NEAR_ZERO_THRESHOLD_W:
        return 0.0
    return None


def _series_rows(payload: dict[str, Any]) -> list[tuple[list[str], list[list[Any]]]]:
    rows: list[tuple[list[str], list[list[Any]]]] = []
    for result in payload.get("results", []):
        if not isinstance(result, dict):
            continue
        for series in result.get("series", []):
            if not isinstance(series, dict):
                continue
            columns = series.get("columns", [])
            values = series.get("values", [])
            if isinstance(columns, list) and isinstance(values, list):
                rows.append(([str(item) for item in columns], values))
    return rows


def _single_row_time(payload: dict[str, Any]) -> datetime | None:
    for columns, values in _series_rows(payload):
        try:
            time_index = columns.index("time")
        except ValueError:
            continue
        for row in values:
            if len(row) > time_index and row[time_index] is not None:
                try:
                    return _parse_timestamp(str(row[time_index]))
                except ValueError:
                    continue
    return None


def _legacy_entity_candidates(entity_id: str) -> tuple[str, ...]:
    short = entity_id.split(".", 1)[1] if "." in entity_id else entity_id
    return (short, entity_id) if short != entity_id else (entity_id,)


def _series_measurement(key: str) -> str:
    escaped = False
    result: list[str] = []
    for char in key:
        if escaped:
            result.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ",":
            break
        else:
            result.append(char)
    return "".join(result)


def _power_scale(measurement: str) -> float | None:
    normalized = measurement.strip().lower()
    return {"w": 1.0, "kw": 1000.0, "mw": 1_000_000.0}.get(normalized)


def _quote_identifier(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _quote_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _floor_bucket(value: datetime) -> datetime:
    utc = value.astimezone(UTC).replace(second=0, microsecond=0)
    minute = utc.minute - utc.minute % 5
    return utc.replace(minute=minute)


def _ceil_bucket(value: datetime) -> datetime:
    floor = _floor_bucket(value)
    return floor if floor == value.astimezone(UTC).replace(second=0, microsecond=0) else floor + _BUCKET


def _optional_timestamp(value: object) -> datetime | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return _parse_timestamp(str(value))
    except ValueError:
        return None


def _optional_int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _short_error(value: str, limit: int = 300) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= limit else f"{compact[:limit]}..."
