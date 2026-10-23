"""Explicit commissioning configuration; synthetic defaults cannot silently enable commands."""

from __future__ import annotations

import json
import os
from dataclasses import fields, replace
from importlib.resources import files
from pathlib import Path
from typing import Any

from .adapters import HomeAssistantAdapter, JsonForecastAdapter
from .control import GuardedActuator
from .domain import Capabilities, Policy
from .forecasts import demo_snapshot
from .service import Application
from .store import Store
from .notifications import Notifications


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


def configured_application(path: Path, store: Store) -> Application:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    required_capabilities = {f.name for f in fields(Capabilities)}
    if required_capabilities - set(data.get("capabilities", {})):
        raise ValueError(
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
        raise ValueError("Tariffs, valuations, timezone and permission limits must be explicit")
    c = Capabilities(**data["capabilities"])
    p = Policy(**data["policy"])
    allow_remote = bool(data.get("allow_remote", False))
    ha = HomeAssistantAdapter(
        data["home_assistant_url"],
        data["measurements"],
        os.environ.get(data.get("token_environment", "ENERGY_MANAGER_HA_TOKEN"), ""),
        allow_remote=allow_remote,
    )
    forecast = JsonForecastAdapter(data["forecast_url"], allow_remote=allow_remote)
    placeholder = demo_snapshot(policy=p)
    placeholder = replace(
        placeholder,
        capabilities=c,
        observation=replace(
            placeholder.observation, ev_kwh=c.ev_capacity_kwh * 0.5, ess_kwh=c.ess_min_kwh, quality="unknown"
        ),
        provenance="Inputs pending · placeholder has no measurement or command authority",
    )
    application = Application(store, policy=p, snapshot=placeholder, demo=False, ha=ha, forecast=forecast)
    if data.get("notification_webhook"):
        application.notifications = Notifications(
            store, data["notification_webhook"], allow_remote=allow_remote
        )
    if p.control_enabled:
        if not all(
            isinstance(data.get("actuators", {}).get(key), str) and data["actuators"][key]
            for key in ("force", "phase", "current", "ess_setpoint")
        ):
            raise ValueError("Complete explicit actuator mapping is required before enabling control")
        if (
            data.get("exclusive_controller_confirmed") is not True
            or data.get("commissioning_reviewed") is not True
        ):
            raise ValueError("Control requires explicit commissioning and exclusive-controller confirmation")
        application.actuator = GuardedActuator(
            ha,
            data["actuators"],
            c,
            enabled=True,
            generation=lambda: application.revision,
            on_write=lambda body: store.event("actuator_service", body),
        )
    return application
