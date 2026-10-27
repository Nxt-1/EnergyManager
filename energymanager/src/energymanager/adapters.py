"""Configured HA/forecast boundaries. Defaults permit local verification endpoints only."""

from __future__ import annotations

import math
import asyncio
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote, urlsplit
from uuid import uuid4

import aiohttp

from .domain import Capabilities, Goal, Interval, Observation, Policy, Snapshot, instant, time_grid
from .forecasts import apply_requirements, daily_goals
from .measurements import HousePowerMismatch, MeasurementOptions
from .live_inputs import LiveInputs


def checked_url(url: str, allow_remote: bool = False) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password or not parsed.hostname:
        raise ValueError("Configured endpoints require HTTP(S), without embedded credentials")
    if not allow_remote and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Remote integration access is disabled; use a local fake endpoint")
    return url.rstrip("/")


class HomeAssistantAdapter:
    def __init__(
        self, base_url: str, entities: dict[str, str], token: str = "", *, allow_remote: bool = False,
        measurement_options: MeasurementOptions | None = None, phase_entity: str | None = None,
        measurement_max_age_seconds: float = 30,
    ) -> None:
        self.url = checked_url(base_url, allow_remote)
        self.entities = dict(entities)
        self.options = measurement_options or MeasurementOptions()
        if self.options.phase_source == "goe_selector":
            if not phase_entity:
                raise ValueError("The go-e phase source requires the charger phase selector")
            self.entities["ev_phases"] = phase_entity
        self.measurement_max_age_seconds = measurement_max_age_seconds
        self.token = token
        self.session: aiohttp.ClientSession | None = None
        self.last_observation: Observation | None = None
        self.inputs = LiveInputs(self.entities, self.options, measurement_max_age_seconds)

    async def __aenter__(self) -> HomeAssistantAdapter:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        self.session = aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=5))
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.session:
            await self.session.close()

    async def state(self, key: str) -> dict[str, Any]:
        return await self.entity_state(self.entities[key])

    async def entity_state(self, entity: str) -> dict[str, Any]:
        if self.session is None:
            raise RuntimeError("Adapter is not open")
        async with self.session.get(
            f"{self.url}/states/{quote(entity, safe='._-')}", allow_redirects=False
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def service(self, domain: str, service: str, data: dict[str, Any]) -> None:
        if self.session is None:
            raise RuntimeError("Adapter is not open")
        try:
            async with self.session.post(
                f"{self.url}/services/{quote(domain, safe='_')}/{quote(service, safe='_')}",
                json=data,
                allow_redirects=False,
            ) as response:
                response.raise_for_status()
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise RuntimeError(f"HA service failed: {type(exc).__name__}") from exc

    async def observe(self, c: Capabilities, *, at: datetime | None = None) -> Observation:
        required = (
            "ev_soc",
            "ess_soc",
            "connected",
            "house_kw",
            "pv_ac_kw",
            "pv_dc_kw",
            "ev_kw",
            "ess_kw",
            "quarter_import_kwh",
            "monthly_peak_kw",
            "ev_phases",
        )
        shared = tuple(key for key in required if key not in ("ev_soc", "ev_phases"))
        if self.options.house_source == "separate_grid":
            shared = tuple(key for key in shared if key != "house_kw") + ("grid_import_kw", "grid_export_kw")
        keys = (*shared, "ev_soc", "ev_phases")

        async def read(key: str) -> dict[str, Any] | Exception:
            try:
                return await self.state(key)
            except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as exc:
                return exc

        responses = await asyncio.gather(*(read(key) for key in keys))
        polled_at = at or datetime.now(UTC)
        # Publish each read before validating the collection used by planning/control.
        self.inputs.options = self.options
        self.inputs.update(dict(zip(keys, responses)), polled_at)

        def number(key: str) -> float:
            return self.inputs.number(key, polled_at)

        connected = str(self.inputs.readings["connected"].require(polled_at)).lower()
        if connected not in ("on", "off", "true", "false", "connected", "disconnected"):
            raise ValueError(f"{self.entities['connected']}: unknown EV connection state {connected!r} "
                             f"({self.inputs.readings['connected'].context()})")
        # This is a validated view of HA's current available states, not their last change time.
        at = polled_at
        ev_kw, ess_kw = number("ev_kw"), number("ess_kw")
        pv_ac_kw = number("pv_ac_kw")
        house_keys: tuple[str, ...]
        if self.options.house_source == "separate_grid":
            imported, exported = number("grid_import_kw"), number("grid_export_kw")
            house_input_kw = imported - exported
            house_keys = ("grid_import_kw", "grid_export_kw")
        else:
            house_input_kw = number("house_kw")
            house_keys = ("house_kw",)
        try:
            house_kw = self.options.house_power(house_input_kw, ev_kw, pv_ac_kw, ess_kw)
        except ValueError as exc:
            if self.options.house_source == "total_consumption":
                house_keys += ("ev_kw",)
            elif self.options.house_source in ("signed_grid", "separate_grid"):
                house_keys += ("ev_kw", "pv_ac_kw", "ess_kw")
            context = "; ".join(f"{self.inputs.readings[key].entity_id} ({self.inputs.readings[key].context()})"
                                for key in house_keys)
            message = f"{exc}; contributing inputs: {context}"
            if isinstance(exc, HousePowerMismatch):
                raise HousePowerMismatch(message) from exc
            raise ValueError(message) from exc
        quarter_kwh = self.options.quarter_energy(number("quarter_import_kwh"), polled_at)
        try:
            phases = self.options.phase_count(str(self.inputs.readings["ev_phases"].require(polled_at)))
        except ValueError:
            phases = None
        ev_known = True
        ev_at = None
        try:
            ev_kwh = number("ev_soc") / 100 * c.ev_capacity_kwh
            ev_at = self.inputs.readings["ev_soc"].reported_at
            ev_known = 0 <= ev_kwh <= c.ev_capacity_kwh
        except (ValueError, KeyError, TypeError):
            ev_kwh = self.last_observation.ev_kwh if self.last_observation else 0
            ev_known = False
        ess_kwh = number("ess_soc") / 100 * c.ess_capacity_kwh
        usable = max(0, ess_kwh - c.ess_min_kwh)
        # Unknown initial inventory is conservatively restricted. New solar is proven only
        # across fresh, import-free observations; restart never invents an eligible stock.
        restricted = usable
        if self.last_observation:
            previous = self.last_observation
            elapsed = (at - previous.at).total_seconds()
            if 0 <= elapsed <= 30:
                net_import = max(
                    0,
                    house_kw + ev_kw - pv_ac_kw - ess_kw,
                )
                restricted = min(
                    usable, previous.ess_grid_kwh + net_import * elapsed / 3600 * c.ac_charge_efficiency
                )
        observation = Observation(
            at,
            min(c.ev_capacity_kwh, max(0, ev_kwh)),
            ess_kwh,
            connected in ("on", "true", "connected"),
            house_kw,
            pv_ac_kw,
            number("pv_dc_kw"),
            ev_kw,
            ess_kw,
            quarter_kwh,
            number("monthly_peak_kw"),
            phases or (self.last_observation.ev_phases if self.last_observation else c.phases[0]),
            ess_grid_kwh=restricted,
            ev_state_known=ev_known,
            ev_observed_at=ev_at,
            ev_phase_known=phases is not None,
            ev_phase_source=self.options.phase_source,
        )
        self.last_observation = observation
        return observation


class ForecastSource(Protocol):
    async def read(self, observation: Observation, at: datetime) -> dict[str, Any]: ...

    async def close(self) -> None: ...


class JsonForecastAdapter:
    """Energy-preserving resampling of issued AC/DC/background forecasts onto the planning grid."""

    def __init__(self, url: str, *, allow_remote: bool = False) -> None:
        self.url = checked_url(url, allow_remote)

    async def read(self, observation: Observation | None = None, at: datetime | None = None) -> dict[str, Any]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(self.url, allow_redirects=False) as response:
                response.raise_for_status()
                if response.content_length and response.content_length > 8 * 1024 * 1024:
                    raise ValueError("Forecast too large")
                return await response.json()

    async def close(self) -> None:
        pass

    @staticmethod
    def snapshot(
        data: dict[str, Any],
        observation: Observation,
        c: Capabilities,
        p: Policy,
        goals: tuple[Goal, ...],
        revision: int,
        at: datetime,
    ) -> Snapshot:
        issued = instant(data["issued_at"])
        if (at - issued).total_seconds() > p.forecast_max_age_seconds or issued > at:
            raise ValueError("Forecast issuance is stale or in the future")
        horizon = at.timestamp() + 168 * 3600
        end = datetime.fromtimestamp(horizon, at.tzinfo)
        all_goals = goals + daily_goals(at, end, p, goals)
        boundaries = tuple(t for g in all_goals for t in (g.deadline, g.return_at, g.earliest) if t)
        grid = time_grid(at, boundaries=boundaries)
        source = [(instant(i["start"]), instant(i["end"]), i) for i in data["intervals"]]
        source.sort(key=lambda item: item[0])
        for index, (left, right, row) in enumerate(source):
            if right <= left or index and left != source[index - 1][1]:
                raise ValueError("Forecast intervals must be consecutive without overlap")
            for key in ("house_kw", "pv_ac_kw", "pv_dc_kw"):
                value = float(row[key])
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f"Invalid {key}")
        intervals = []
        source_index = 0
        for left, right in zip(grid, grid[1:]):
            duration = (right - left).total_seconds()
            covered = 0.0
            values = {key: 0.0 for key in ("house_kw", "pv_ac_kw", "pv_dc_kw")}
            # Sweep overlapping source rows once, keeping five-second input polling responsive.
            while source_index < len(source) and source[source_index][1] <= left:
                source_index += 1
            position = source_index
            while position < len(source) and source[position][0] < right:
                a, b, row = source[position]
                seconds = max(0, (min(b, right) - max(a, left)).total_seconds())
                if seconds:
                    covered += seconds
                    for key in values:
                        values[key] += float(row[key]) * seconds / duration
                position += 1
            if abs(covered - duration) > 1e-5:
                raise ValueError("A complete seven-day forecast is required; missing data is not zero")
            intervals.append(
                Interval(left, right, values["house_kw"], values["pv_ac_kw"], values["pv_dc_kw"])
            )
        prepared = apply_requirements(tuple(intervals), all_goals, observation, c, p)
        return Snapshot(
            uuid4().hex,
            revision,
            observation,
            issued,
            str(data["revision"]),
            prepared,
            all_goals,
            c,
            p,
            str(data["provenance"]),
        )
