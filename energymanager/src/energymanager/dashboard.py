"""Read-only native-dashboard discovery; the add-on owns the versioned UI bundle."""

from __future__ import annotations

from typing import Any

from . import __version__
from .service import Application


def dashboard_manifest(application: Application) -> dict[str, Any]:
    return {
        "protocol": 1,
        "version": __version__,
        "demo": application.demo,
        "entities": dict(application.ha.entities) if application.ha and not application.demo else {},
    }
