"""Explicit commissioning configuration; synthetic defaults cannot silently enable commands."""

from __future__ import annotations

import json
from dataclasses import fields, replace
from importlib.resources import files
from pathlib import Path
from typing import Any

from .adapters import HomeAssistantAdapter
from .control import GuardedActuator
from .domain import Capabilities, Policy
from .forecasts import demo_snapshot
from .service import Application
from .store import Store
from .notifications import Notifications, NotificationTarget
from .connections import HomeAssistantConnection
from .measurements import MeasurementOptions, installation_configuration
from .forecast_service import InstallationForecast
from .open_meteo import FORECAST_URL
from .calendars import calendar_sources
from .ev_faults import EVFaults
from .goe import GoEReadings


def create_configuration_if_missing(path: Path) -> bool:
    """Create the packaged starter configuration without replacing any existing path."""
    if path.exists():
        return False
    template = files("energymanager").joinpath("defaults", "configuration.example.json").read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as destination:
            destination.write(template)
    except FileExistsError:
        return False  # Another startup may have created it after the existence check.
    return True


def configured_application(path: Path, store: Store, *, weather_url: str = FORECAST_URL,
                           addon: bool = False) -> Application:
    data: dict[str, Any] = installation_configuration(json.loads(path.read_text(encoding="utf-8")))
    required_capabilities = {f.name for f in fields(Capabilities)}
    if required_capabilities - set(data.get("capabilities", {})):
        return pending_configuration(store,
            "All physical capabilities must be explicitly configured; no synthetic commissioning defaults"
        )
    required_policy = {
        "import_eur_kwh",
        "export_eur_kwh",
        "capacity_eur_kw_month",
        "billing_floor_kw",
        "automatic_peak_kw",
        "ev_value_eur_kwh",
        "ess_value_eur_kwh",
        "timezone",
    }
    if required_policy - set(data.get("policy", {})):
        return pending_configuration(store, "Tariffs, valuations, timezone and permission limits must be explicit")
    try:
        c = Capabilities(**data["capabilities"])
        # The Overview switch is the sole authority; old commissioning flags cannot activate it.
        p = Policy(**{**data["policy"], "control_enabled": False})
        connection = HomeAssistantConnection.resolve(data, addon=addon)
        target = NotificationTarget.from_data(data.get("notification_target"))
        calendar_sources(data.get("calendars"))
    except (ValueError, TypeError) as exc:
        return pending_configuration(store, str(exc))
    if not data.get("actuators", {}).get("phase"):
        return pending_configuration(store, "Select the charger phase selector")
    ha = HomeAssistantAdapter(
        connection.url,
        data["measurements"],
        connection.token,
        allow_remote=connection.allow_remote,
        measurement_options=MeasurementOptions.installation(),
        phase_entity=data.get("actuators", {}).get("phase"),
        measurement_max_age_seconds=p.measurement_max_age_seconds,
    )
    forecast = InstallationForecast(ha, store, allow_remote=connection.allow_remote, weather_url=weather_url,
                                    max_age_seconds=p.forecast_max_age_seconds,
                                    measurement_max_age_seconds=p.measurement_max_age_seconds)
    placeholder = demo_snapshot(policy=p, goals=())
    placeholder = replace(
        placeholder,
        capabilities=c,
        observation=replace(
            placeholder.observation, ev_kwh=c.ev_capacity_kwh * 0.5, ess_kwh=c.ess_min_kwh, quality="unknown"
        ),
        provenance="Inputs pending · placeholder has no measurement or command authority",
    )
    application = Application(store, policy=p, snapshot=placeholder, demo=False, ha=ha, forecast=forecast)
    application.notifications = Notifications(store, ha, target)
    application.actuator = GuardedActuator(
        ha, data.get("actuators", {}), c, enabled=False,
        generation=lambda: application.revision,
        on_write=lambda body: store.event("actuator_service", body),
        charger=GoEReadings(data.get("actuators", {}), data.get("ev_diagnostics", {}), p.measurement_max_age_seconds),
    )
    application.ev_faults = EVFaults(application, data.get("actuators", {}).get("ev_reboot", ""),
                                     data.get("ev_diagnostics", {}))
    return application


def pending_configuration(store: Store, reason: str) -> Application:
    """Keep the editor available for incomplete files, without a live input or actuator adapter."""
    placeholder = demo_snapshot(goals=())
    placeholder = replace(placeholder, observation=replace(placeholder.observation, quality="unknown"),
                          provenance="Installation settings incomplete · no live measurements")
    application = Application(store, snapshot=placeholder, demo=False)
    application.accepted = None  # Stored decision evidence remains available through history.
    application.configuration_error = reason
    application.status, application.error = "settings_incomplete", "Complete the highlighted settings"
    store.event("configuration_incomplete", {"reason": reason})
    return application
