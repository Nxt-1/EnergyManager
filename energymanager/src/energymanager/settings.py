"""Validated configuration editing and read-only Home Assistant entity discovery."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import stat
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Any
from uuid import uuid4

import aiohttp

from .connections import HomeAssistantConnection
from .notifications import NotificationTarget
from .domain import Capabilities, Policy
from .measurements import installation_configuration
from .calendars import calendar_sources


@dataclass(frozen=True)
class SettingField:
    path: str
    label: str
    group: str
    kind: str = "number"
    help: str = ""
    minimum: float | None = 0
    maximum: float | None = None
    step: float = 0.01
    domains: tuple[str, ...] = ()
    units: tuple[str, ...] = ()
    required: bool = True


def setting_fields() -> tuple[SettingField, ...]:
    result = [SettingField("notification_target", "Phone notifications (optional)", "Notifications",
                           "notification", domains=("notify",), required=False)]
    result.append(SettingField("calendars", "Subscribed calendars", "EV calendars", "calendars", required=False,
                               help="Label each iCalendar link. Imported journeys use provisional 50 km total and four hours from event start. Save and restart to sync."))
    measurements = (
        ("ev_soc", "EV state of charge", ("%",)),
        ("ess_soc", "ESS state of charge", ("%",)),
        ("connected", "EV connected", ()),
        ("grid_import_kw", "Grid import power", ("W", "kW")),
        ("grid_export_kw", "Grid export power", ("W", "kW")),
        ("pv_ac_kw", "AC solar power", ("W", "kW")),
        ("pv_dc_kw", "DC solar power", ("W", "kW")),
        ("ev_kw", "EV charging power", ("W", "kW")),
        ("ess_kw", "ESS power · positive discharge", ("W", "kW")),
        ("quarter_import_kwh", "Current Quarter Average Demand", ("W", "kW")),
        ("monthly_peak_kw", "Measured monthly peak", ("W", "kW")),
    )
    for key, label, units in measurements:
        domains: tuple[str, ...] = ("sensor", "number", "input_number")
        if key == "connected":
            domains = ("binary_sensor", "sensor", "input_boolean", "switch")
        result.append(SettingField(f"measurements.{key}", label, "Measurements", "entity",
                                   domains=domains, units=units))
    for key, label, domain in (
        ("force", "Charger stop / charge selector", "select"),
        ("phase", "Charger phase selector", "select"),
        ("current", "Charger current limit", "number"),
        ("ess_setpoint", "ESS AC setpoint", "number"),
    ):
        units = ("A",) if key == "current" else ("W",) if key == "ess_setpoint" else ()
        result.append(SettingField(f"actuators.{key}", label, "Actuators", "entity",
                                   domains=(domain,), units=units))
    result.append(SettingField("actuators.ev_reboot", "Automatic charger reboot button (optional)",
                               "EV fault recovery", "entity", domains=("button",), required=False))
    for key, label in (("ev_status", "EV status"), ("charger_status", "Charger status"),
                       ("charger_error", "Charger error"), ("charge_allowed", "Charging allowed")):
        result.append(SettingField(f"ev_diagnostics.{key}", f"{label} (optional)", "EV fault recovery", "entity",
                                   domains=("sensor", "binary_sensor", "select", "switch", "input_boolean"),
                                   required=False))
    for key, label, group, minimum, maximum in (
        ("ev_capacity_kwh", "EV capacity (kWh)", "EV and charger", 0.01, None),
        ("voltage", "Phase voltage (V)", "EV and charger", 1, None),
        ("phase_dwell_seconds", "Minimum phase dwell (seconds)", "EV and charger", 0, None),
        ("ess_capacity_kwh", "ESS capacity (kWh)", "ESS and conversion", 0.01, None),
        ("ess_min_kwh", "ESS minimum stored energy (kWh)", "ESS and conversion", 0, None),
        ("ac_charge_kw", "AC charging limit (kW)", "ESS and conversion", 0, None),
        ("ac_discharge_kw", "AC discharge limit (kW)", "ESS and conversion", 0, None),
        ("dc_charge_kw", "DC charging limit (kW)", "ESS and conversion", 0, None),
        ("battery_charge_kw", "Total battery charging limit (kW)", "ESS and conversion", 0, None),
        ("battery_discharge_kw", "Total battery discharge limit (kW)", "ESS and conversion", 0, None),
        ("grid_connection_kw", "Grid connection limit (kW)", "Tariffs and peak policy", 0.01, None),
        ("ev_efficiency", "EV charging efficiency (0–1)", "EV and charger", 0.001, 1),
        ("ac_charge_efficiency", "AC charging efficiency (0–1)", "ESS and conversion", 0.001, 1),
        ("ac_discharge_efficiency", "AC discharge efficiency (0–1)", "ESS and conversion", 0.001, 1),
        ("dc_efficiency", "DC charging efficiency (0–1)", "ESS and conversion", 0.001, 1),
    ):
        result.append(SettingField(f"capabilities.{key}", label, group, minimum=minimum, maximum=maximum))
    result.extend((
        SettingField("capabilities.minimum_current_a", "Minimum charging current (A)", "EV and charger",
                     "integer", minimum=1, step=1),
        SettingField("capabilities.maximum_current_a", "Maximum charging current (A)", "EV and charger",
                     "integer", minimum=1, step=1),
        SettingField("capabilities.phases", "Supported charging phases", "EV and charger", "phases"),
        SettingField("policy.timezone", "Timezone", "EV and charger", "text"),
        SettingField("policy.daily_time", "Daily ready time", "EV and charger", "time"),
    ))
    for key, label, group, minimum, maximum, step in (
        ("daily_soc_percent", "Daily target (%)", "EV and charger", 0, 100, 0.1),
        ("normal_soc_percent", "Normal optional ceiling (%)", "EV and charger", 0, 100, 0.1),
        ("consumption_kwh_per_100km", "Journey consumption (kWh / 100 km)", "EV and charger", 0, None, 0.1),
        ("arrival_reserve_km", "Arrival reserve (km)", "EV and charger", 0, None, 1),
        ("import_eur_kwh", "Import tariff (€/kWh)", "Tariffs and peak policy", 0, None, 0.00001),
        ("export_eur_kwh", "Export tariff (€/kWh)", "Tariffs and peak policy", 0, None, 0.00001),
        ("capacity_eur_kw_month", "Capacity tariff (€/kW/month)", "Tariffs and peak policy", 0, None, 0.00001),
        ("billing_floor_kw", "Billing floor (kW)", "Tariffs and peak policy", 0, None, 0.01),
        ("automatic_peak_kw", "Automatic peak ceiling (kW)", "Tariffs and peak policy", 0, None, 0.01),
        ("ev_value_eur_kwh", "EV residual energy value (€/kWh)", "Tariffs and peak policy", 0, None, 0.000001),
        ("ess_value_eur_kwh", "ESS residual energy value (€/kWh)", "Tariffs and peak policy", 0, None, 0.000001),
        ("planning_budget_seconds", "Planning budget (seconds)", "Advanced", 1, 600, 1),
        ("polish_tolerance_eur", "Plan comparison tolerance (€)", "Advanced", 0, None, 0.01),
        ("completion_margin_minutes", "Completion margin (minutes)", "Advanced", 0, None, 1),
        ("measurement_max_age_seconds", "HA input-read watchdog (seconds)", "Advanced", 0.001, None, 1),
        ("forecast_max_age_seconds", "Maximum forecast age (seconds)", "Advanced", 0.001, None, 1),
        ("control_period_seconds", "Control period (seconds)", "Advanced", 0.001, None, 0.1),
        ("sustained_deviation_seconds", "Sustained deviation (seconds)", "Advanced", 0, None, 1),
    ):
        kind = "integer" if key == "completion_margin_minutes" else "number"
        result.append(SettingField(f"policy.{key}", label, group, kind, minimum=minimum,
                                   maximum=maximum, step=step))
    result.append(SettingField("_description", "Configuration notes", "Advanced", "text", required=False))
    return tuple(result)


SETTING_FIELDS = setting_fields()
ENTITY_ID = re.compile(r"[a-z_][a-z0-9_]*\.[a-z0-9_]+")


class ConfigurationConflict(ValueError):
    """The file changed since the editor loaded it."""


class SettingsValidationError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        super().__init__(next(iter(errors.values())))


def field_value(document: dict[str, Any], path: str) -> Any:
    value: Any = document
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


class ConfigurationFile:
    """Own versioned file edits; credentials and running control stay outside the editor."""

    def __init__(self, path: Path, *, addon: bool = False, mode: str = "demo") -> None:
        self.path, self.addon, self.mode = path, addon, mode
        self.lock = Lock()
        self.started_values = self.values(json.loads(path.read_bytes()))

    @staticmethod
    def values(document: dict[str, Any]) -> dict[str, Any]:
        prepared = installation_configuration(document)
        return {field.path: field_value(prepared, field.path) for field in SETTING_FIELDS}

    def read(self) -> dict[str, Any]:
        original = self.path.read_bytes()
        document = json.loads(original)
        if not isinstance(document, dict):
            raise ValueError("The configuration must be a JSON object")
        revision = sha256(original).hexdigest()
        prepared = installation_configuration(document)
        values = self.values(prepared)
        return {
            "path": str(self.path), "revision": revision, "values": values,
            "fields": [asdict(field) for field in SETTING_FIELDS],
            "addon": self.addon, "mode": self.mode,
            "restart_required": values != self.started_values,
            "issues": self.issues(prepared),
        }

    def validate(self, document: dict[str, Any]) -> None:
        errors = {}
        for field in SETTING_FIELDS:
            value = field_value(document, field.path)
            if field.kind == "calendars":
                try:
                    calendar_sources(value)
                except ValueError as exc:
                    errors[field.path] = str(exc)
                continue
            if not field.required and (value is None or value == ""):
                continue
            if field.kind == "notification":
                try:
                    NotificationTarget.from_data(value)
                except ValueError as exc:
                    errors[field.path] = str(exc)
                continue
            if field.kind == "boolean":
                valid = type(value) is bool
            elif field.kind in ("number", "integer"):
                valid = type(value) in (int, float) and math.isfinite(value)
                if valid:
                    valid = (field.minimum is None or value >= field.minimum) and (
                        field.maximum is None or value <= field.maximum)
                if valid and field.kind == "integer":
                    valid = int(value) == value
            elif field.kind == "phases":
                valid = isinstance(value, list) and bool(value) and all(type(p) is int and p in (1, 3)
                                                                      for p in value)
            else:
                valid = isinstance(value, str) and len(value) <= 2000
                if field.required:
                    valid = valid and bool(value.strip())
                if valid and field.kind == "entity":
                    valid = bool(ENTITY_ID.fullmatch(value)) and value.split(".")[0] in field.domains
                if valid and field.kind == "time":
                    valid = bool(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value))
            if not valid:
                errors[field.path] = f"Check {field.label.lower()}"
        if errors:
            raise SettingsValidationError(errors)
        try:
            for group, model in (("capabilities", Capabilities), ("policy", Policy)):
                missing = {field.name for field in fields(model) if field.name != "control_enabled"} - set(document.get(group, {}))
                if missing:
                    raise ValueError(f"Missing {group}: {', '.join(sorted(missing))}")
            Capabilities(**document["capabilities"])
            Policy(**document["policy"])
        except (ValueError, TypeError, KeyError) as exc:
            raise SettingsValidationError({"configuration": str(exc)}) from exc

    def issues(self, document: dict[str, Any]) -> dict[str, str]:
        try:
            self.validate(document)
        except SettingsValidationError as exc:
            errors = dict(exc.errors)
        else:
            errors = {}
        for field in SETTING_FIELDS:
            value = field_value(document, field.path)
            if field.kind == "entity" and isinstance(value, str) and value.split(".")[-1].startswith("replace_"):
                errors[field.path] = "Select an entity"
        return errors

    def save(self, revision: str, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {field.path for field in SETTING_FIELDS}
        if not isinstance(changes, dict) or set(changes) - allowed:
            raise ValueError("Unknown configuration fields")
        with self.lock:
            original = self.path.read_bytes()
            if sha256(original).hexdigest() != revision:
                raise ConfigurationConflict("Settings changed elsewhere. Reload before saving your edits.")
            document = json.loads(original)
            if not isinstance(document, dict):
                raise ValueError("The configuration must be a JSON object")
            document = installation_configuration(document)
            for key in ("forecast_url", "notification_webhook", "commissioning_reviewed", "exclusive_controller_confirmed"):
                document.pop(key, None)
            if self.addon:
                for key in ("home_assistant_url", "token_environment", "allow_remote"):
                    document.pop(key, None)
            document.get("policy", {}).pop("control_enabled", None)
            for path, value in changes.items():
                keys = path.split(".")
                parent = document
                for key in keys[:-1]:
                    parent = parent.setdefault(key, {})
                    if not isinstance(parent, dict):
                        raise ValueError(f"Configuration section {key} must be an object")
                parent[keys[-1]] = value
            if "calendars" in document:
                try:
                    document["calendars"] = calendar_sources(document["calendars"])
                except ValueError as exc:
                    raise SettingsValidationError({"calendars": str(exc)}) from exc
            self.validate(document)
            if document == json.loads(original):
                return {**self.read(), "backup": None}
            backup = self.path.with_name(
                f"{self.path.stem}.backup-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}.json")
            permissions = stat.S_IMODE(self.path.stat().st_mode)
            temporary_path = None
            try:
                with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as output:
                    temporary_path = Path(output.name)
                    json.dump(document, output, ensure_ascii=False, indent=2, allow_nan=False)
                    output.write("\n")
                    output.flush()
                    os.fsync(output.fileno())
                os.chmod(temporary_path, permissions)
                if self.path.read_bytes() != original:
                    raise ConfigurationConflict("Settings changed elsewhere. Reload before saving your edits.")
                with backup.open("xb") as output_backup:
                    output_backup.write(original)
                os.chmod(backup, permissions)
                os.replace(temporary_path, self.path)
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
            return {**self.read(), "backup": backup.name}

    async def entities(self) -> dict[str, Any]:
        document = await asyncio.to_thread(lambda: json.loads(self.path.read_bytes()))
        connection = HomeAssistantConnection.resolve(document, addon=self.addon)
        if self.addon and not connection.token:
            raise RuntimeError("Home Assistant did not supply its connection token")
        headers = {"Authorization": f"Bearer {connection.token}"} if connection.token else {}

        async def read_list(session: aiohttp.ClientSession, resource: str) -> list[dict[str, Any]]:
            async with session.get(f"{connection.url}/{resource}", allow_redirects=False) as response:
                if response.status != 200:
                    raise RuntimeError(f"Home Assistant {resource} returned HTTP {response.status}")
                result = await response.json()
            if not isinstance(result, list):
                raise RuntimeError(f"Home Assistant returned invalid {resource}")
            return result

        try:
            async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as session:
                states = await read_list(session, "states")
                notification_error = None
                try:
                    services = await read_list(session, "services")
                except (aiohttp.ClientError, TimeoutError, RuntimeError):
                    services = []
                    notification_error = "Phone notification actions could not be loaded"
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise RuntimeError("Home Assistant could not be reached") from exc
        entities = []
        for state in states:
            if not isinstance(state, dict) or not ENTITY_ID.fullmatch(str(state.get("entity_id", ""))):
                continue
            attributes = state.get("attributes") or {}
            if not isinstance(attributes, dict):
                continue
            entity_id = state["entity_id"]
            entities.append({
                "entity_id": entity_id, "name": str(attributes.get("friendly_name", entity_id))[:255],
                "state": str(state.get("state", "unknown"))[:120],
                "unit": str(attributes.get("unit_of_measurement") or "")[:30],
            })
        entities.sort(key=lambda entity: (entity["name"].casefold(), entity["entity_id"]))
        targets = [{**entity, "kind": "entity"} for entity in entities if entity["entity_id"].startswith("notify.")]
        known = {target["entity_id"] for target in targets}
        for domain in services:
            if not isinstance(domain, dict) or domain.get("domain") != "notify":
                continue
            actions = domain.get("services", {})
            if not isinstance(actions, dict):
                continue
            for key, metadata in actions.items():
                identifier = f"notify.{key}"
                if (not ENTITY_ID.fullmatch(identifier) or identifier in known
                        or key in ("notify", "send_message", "persistent_notification")):
                    continue
                name = metadata.get("name") if isinstance(metadata, dict) else None
                targets.append({"entity_id": identifier, "name": str(name or key.replace("_", " "))[:255],
                                "state": "", "unit": "", "kind": "action"})
        targets.sort(key=lambda target: (target["name"].casefold(), target["entity_id"]))
        return {"entities": entities, "notification_targets": targets, "notification_error": notification_error,
                "source": "Home Assistant", "synthetic": False}
