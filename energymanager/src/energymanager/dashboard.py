"""Read-only native-dashboard discovery; the add-on owns the versioned UI bundle."""

from __future__ import annotations

from typing import Any

from . import __version__
from .service import Application
from .control import GuardedActuator


def dashboard_manifest(application: Application) -> dict[str, Any]:
    return {
        "protocol": 1,
        "version": __version__,
        "demo": application.demo,
        "entities": dict(application.ha.entities) if application.ha and not application.demo else {},
        "phase_selector": (application.actuator.entities.get("phase")
                           if not application.demo and isinstance(application.actuator, GuardedActuator) else None),
    }
