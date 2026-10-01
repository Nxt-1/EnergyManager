"""Energy Manager application package."""

from __future__ import annotations

__all__ = ["__version__"]

import os

__version__ = os.environ.get("ENERGY_MANAGER_VERSION", "dev")
