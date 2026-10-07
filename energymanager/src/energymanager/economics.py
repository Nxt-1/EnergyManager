"""Versioned planner economics inputs and tariff history."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .config import EconomicsSettings
from .ha_client import HomeAssistantClient

COST_MODEL_VERSION = "2026-10-07-cost-v1"
ECONOMICS_STATUS_ENTITY = "sensor.energy_manager_economics_status"
_LOCAL_HISTORY_PATH = Path("/data/tariff_profile_history.jsonl")
_LOGGER = logging.getLogger(__name__)


class _InfluxClient(Protocol):
    async def query_sql(self, query: str) -> list[dict[str, str]]: ...

    async def write_lines(self, lines: list[str]) -> None: ...


@dataclass(frozen=True, slots=True)
class TariffProfile:
    """Immutable planner-relevant tariff snapshot."""

    profile_id: str
    valid_from_utc: datetime
    import_energy_eur_per_kwh: float
    export_energy_eur_per_kwh: float
    capacity_tariff_eur_per_kw_month: float
    capacity_tariff_floor_kw: float

    def energy_cost_eur(self, import_kwh: float, export_kwh: float) -> float:
        """Return marginal energy cost excluding the capacity-tariff contribution."""
        return (
            max(0.0, import_kwh) * self.import_energy_eur_per_kwh
            - max(0.0, export_kwh) * self.export_energy_eur_per_kwh
        )


class TariffProfileHistory:
    """Activate immutable tariff snapshots without rewriting prior history."""

    def __init__(
        self,
        settings: EconomicsSettings,
        *,
        influx_client: _InfluxClient | None = None,
        local_path: Path = _LOCAL_HISTORY_PATH,
    ) -> None:
        self._settings = settings
        self._influx_client = influx_client
        self._local_path = local_path
        self.backend = "influxdb" if influx_client is not None else "local_jsonl"

    async def activate(self, *, now_utc: datetime | None = None) -> TariffProfile | None:
        """Return the active profile and append a revision only when the configured tariff changed."""
        if not self._settings.configured:
            return None
        observed = (now_utc or datetime.now(UTC)).astimezone(UTC)
        profile_id = _profile_id(self._settings)
        if self._influx_client is not None:
            try:
                latest = await self._latest_influx_profile()
                if latest is not None and latest.profile_id == profile_id:
                    return latest
                profile = _profile_from_settings(self._settings, profile_id, observed)
                await self._write_influx_profile(profile)
                return profile
            except Exception as exc:  # noqa: BLE001 - economics history must not stop the controller.
                _LOGGER.warning("Tariff history InfluxDB persistence failed; using local fallback: %s", exc)
                self.backend = "local_jsonl"
        return self._activate_local(profile_id, observed)

    async def _latest_influx_profile(self) -> TariffProfile | None:
        assert self._influx_client is not None
        tables = await self._influx_client.query_sql(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'tariff_profile' LIMIT 1"
        )
        if not tables:
            return None
        rows = await self._influx_client.query_sql(
            'SELECT time, profile_id, import_energy_eur_per_kwh, export_energy_eur_per_kwh, '
            'capacity_tariff_eur_per_kw_month, capacity_tariff_floor_kw FROM "tariff_profile" '
            "ORDER BY time DESC LIMIT 1"
        )
        if not rows:
            return None
        return _profile_from_record(rows[0])

    async def _write_influx_profile(self, profile: TariffProfile) -> None:
        assert self._influx_client is not None
        fields = (
            f'import_energy_eur_per_kwh={profile.import_energy_eur_per_kwh:.9f},'
            f'export_energy_eur_per_kwh={profile.export_energy_eur_per_kwh:.9f},'
            f'capacity_tariff_eur_per_kw_month={profile.capacity_tariff_eur_per_kw_month:.9f},'
            f'capacity_tariff_floor_kw={profile.capacity_tariff_floor_kw:.6f},'
            f'cost_model_version="{COST_MODEL_VERSION}"'
        )
        line = (
            f"tariff_profile,profile_id={profile.profile_id} {fields} "
            f"{_timestamp_ns(profile.valid_from_utc)}"
        )
        await self._influx_client.write_lines([line])

    def _activate_local(self, profile_id: str, observed: datetime) -> TariffProfile:
        records = _read_local_records(self._local_path)
        if records:
            try:
                latest = _profile_from_record(records[-1])
            except (KeyError, TypeError, ValueError):
                latest = None
            if latest is not None and latest.profile_id == profile_id:
                return latest
        profile = _profile_from_settings(self._settings, profile_id, observed)
        self._local_path.parent.mkdir(parents=True, exist_ok=True)
        with self._local_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_profile_record(profile), sort_keys=True) + "\n")
        return profile


class EconomicsService:
    """Publish the active versioned economic inputs for inspection by Home Assistant."""

    def __init__(
        self,
        settings: EconomicsSettings,
        client: HomeAssistantClient,
        *,
        influx_client: _InfluxClient | None = None,
        local_path: Path = _LOCAL_HISTORY_PATH,
    ) -> None:
        self._settings = settings
        self._client = client
        self._history = TariffProfileHistory(settings, influx_client=influx_client, local_path=local_path)
        self.current_profile: TariffProfile | None = None

    async def initialize(self) -> TariffProfile | None:
        """Activate the configured tariff revision and publish its diagnostic state."""
        self.current_profile = await self._history.activate()
        if not self._settings.enabled:
            await self._client.set_state(
                ECONOMICS_STATUS_ENTITY,
                "disabled",
                {
                    "friendly_name": "Energy Manager Economics Status",
                    "cost_model_version": COST_MODEL_VERSION,
                    "history_backend": self._history.backend,
                    "last_update_utc": datetime.now(UTC).isoformat(),
                },
            )
            return None
        if self.current_profile is None:
            await self._client.set_state(
                ECONOMICS_STATUS_ENTITY,
                "not_configured",
                {
                    "friendly_name": "Energy Manager Economics Status",
                    "cost_model_version": COST_MODEL_VERSION,
                    "history_backend": self._history.backend,
                    "last_update_utc": datetime.now(UTC).isoformat(),
                },
            )
            return None
        profile = self.current_profile
        await self._client.set_state(
            ECONOMICS_STATUS_ENTITY,
            "ready",
            {
                "friendly_name": "Energy Manager Economics Status",
                "cost_model_version": COST_MODEL_VERSION,
                "profile_id": profile.profile_id,
                "valid_from_utc": profile.valid_from_utc.isoformat(),
                "history_backend": self._history.backend,
                "import_energy_eur_per_kwh": profile.import_energy_eur_per_kwh,
                "export_energy_eur_per_kwh": profile.export_energy_eur_per_kwh,
                "capacity_tariff_eur_per_kw_month": profile.capacity_tariff_eur_per_kw_month,
                "capacity_tariff_floor_kw": profile.capacity_tariff_floor_kw,
                "last_update_utc": datetime.now(UTC).isoformat(),
            },
        )
        _LOGGER.info(
            "Economic profile active: id=%s, import=%.5f EUR/kWh, export=%.5f EUR/kWh, "
            "capacity=%.5f EUR/kW/month, floor=%.2f kW, history=%s",
            profile.profile_id,
            profile.import_energy_eur_per_kwh,
            profile.export_energy_eur_per_kwh,
            profile.capacity_tariff_eur_per_kw_month,
            profile.capacity_tariff_floor_kw,
            self._history.backend,
        )
        return profile


def _profile_id(settings: EconomicsSettings) -> str:
    payload = {
        "cost_model_version": COST_MODEL_VERSION,
        "capacity_tariff_eur_per_kw_month": settings.capacity_tariff_eur_per_kw_month,
        "capacity_tariff_floor_kw": settings.capacity_tariff_floor_kw,
        "export_energy_eur_per_kwh": settings.export_energy_eur_per_kwh,
        "import_energy_eur_per_kwh": settings.import_energy_eur_per_kwh,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _profile_from_settings(settings: EconomicsSettings, profile_id: str, valid_from: datetime) -> TariffProfile:
    assert settings.import_energy_eur_per_kwh is not None
    assert settings.export_energy_eur_per_kwh is not None
    assert settings.capacity_tariff_eur_per_kw_month is not None
    return TariffProfile(
        profile_id=profile_id,
        valid_from_utc=valid_from.astimezone(UTC),
        import_energy_eur_per_kwh=settings.import_energy_eur_per_kwh,
        export_energy_eur_per_kwh=settings.export_energy_eur_per_kwh,
        capacity_tariff_eur_per_kw_month=settings.capacity_tariff_eur_per_kw_month,
        capacity_tariff_floor_kw=settings.capacity_tariff_floor_kw,
    )


def _profile_record(profile: TariffProfile) -> dict[str, str | float]:
    return {
        "profile_id": profile.profile_id,
        "valid_from_utc": profile.valid_from_utc.isoformat(),
        "import_energy_eur_per_kwh": profile.import_energy_eur_per_kwh,
        "export_energy_eur_per_kwh": profile.export_energy_eur_per_kwh,
        "capacity_tariff_eur_per_kw_month": profile.capacity_tariff_eur_per_kw_month,
        "capacity_tariff_floor_kw": profile.capacity_tariff_floor_kw,
        "cost_model_version": COST_MODEL_VERSION,
    }


def _profile_from_record(record: dict[str, str | float]) -> TariffProfile:
    valid_from = record.get("valid_from_utc", record.get("time"))
    if valid_from is None:
        raise KeyError("valid_from_utc")
    return TariffProfile(
        profile_id=str(record["profile_id"]),
        valid_from_utc=_parse_timestamp(str(valid_from)),
        import_energy_eur_per_kwh=float(record["import_energy_eur_per_kwh"]),
        export_energy_eur_per_kwh=float(record["export_energy_eur_per_kwh"]),
        capacity_tariff_eur_per_kw_month=float(record["capacity_tariff_eur_per_kw_month"]),
        capacity_tariff_floor_kw=float(record["capacity_tariff_floor_kw"]),
    )


def _read_local_records(path: Path) -> list[dict[str, str | float]]:
    if not path.exists():
        return []
    records: list[dict[str, str | float]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _LOGGER.warning("Could not read tariff profile history %s: %s", path, exc)
        return []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            _LOGGER.warning("Ignoring invalid tariff profile history row")
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _parse_timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _timestamp_ns(value: datetime) -> int:
    utc = value.astimezone(UTC)
    return int(utc.timestamp()) * 1_000_000_000 + utc.microsecond * 1000
