"""Read-only native-dashboard discovery; the add-on owns the versioned UI bundle."""

from __future__ import annotations

from typing import Any

from . import __version__
from .service import Application
from .control import GuardedActuator


def dashboard_manifest(application: Application) -> dict[str, Any]:
    entities = dict(application.ha.entities) if application.ha and not application.demo else {}
    if not application.demo and isinstance(application.actuator, GuardedActuator):
        actuator = application.actuator
        entities.update({key: entity for key in ("force", "current", "phase")
                         if (entity := actuator.entities.get(key))})
        if actuator.charger:
            entities.update({key: entity for key in ("ev_status", "charger_status", "charger_error",
                                                    "charge_allowed", "heartbeat", "vehicle_charging")
                             if (entity := actuator.charger.entities.get(key))})
    return {
        "protocol": 1,
        "version": __version__,
        "demo": application.demo,
        "entities": entities,
        "phase_selector": (application.actuator.entities.get("phase")
                           if not application.demo and isinstance(application.actuator, GuardedActuator) else None),
    }
