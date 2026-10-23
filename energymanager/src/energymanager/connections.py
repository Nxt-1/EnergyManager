"""Automatic Supervisor access in HA; explicit endpoints remain available for local tools."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .adapters import checked_url


@dataclass(frozen=True)
class HomeAssistantConnection:
    url: str
    token: str
    allow_remote: bool

    @classmethod
    def resolve(cls, document: dict[str, Any], *, addon: bool = False) -> HomeAssistantConnection:
        if addon:
            return cls("http://supervisor/core/api", os.environ.get("SUPERVISOR_TOKEN", ""), True)
        url = os.environ.get("ENERGY_MANAGER_HA_URL", document.get("home_assistant_url", "http://127.0.0.1:8123/api"))
        allow_remote = os.environ.get("ENERGY_MANAGER_ALLOW_REMOTE", "").lower() == "true"
        allow_remote = allow_remote or document.get("allow_remote") is True
        token_name = document.get("token_environment", "ENERGY_MANAGER_HA_TOKEN")
        return cls(checked_url(url, allow_remote), os.environ.get(token_name, ""), allow_remote)
