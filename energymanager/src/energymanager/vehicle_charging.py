"""Optional reported vehicle charging status; cloud telemetry is not a power measurement."""

from datetime import datetime
from typing import Any
import math


STATES = {"NOT_READY", "SCHEDULED", "PAUSED", "IN_PROGRESS", "STOPPED", "FAULT", "STATION_NOT_DETECTED"}
ATTRIBUTES = ("plugStatus", "chargingStationStatus", "chargingStatus", "chargingType", "stateOfCharge",
              "chargingkW", "globalAcTargetSoc", "globalDcTargetSoc", "estimatedEndTime")


class VehicleCharging:
    def __init__(self, entity: str = "", maximum_age: float = 30) -> None:
        self.entity, self.maximum_age = entity, maximum_age
        self.row: dict[str, Any] = {}
        self.at: datetime | None = None

    def update(self, row: dict[str, Any], at: datetime) -> None:
        self.row, self.at = row, at

    @property
    def state(self) -> str:
        return str(self.row.get("state", "unknown")).strip().upper()

    def issue(self, at: datetime) -> str | None:
        if not self.entity:
            return "Vehicle charging status is not configured"
        if self.at is None or not -5 <= (at - self.at).total_seconds() <= self.maximum_age:
            return "Vehicle charging status read is stale"
        if self.state not in STATES:
            return "Vehicle charging status is unavailable or unrecognized"
        return None

    def fault(self, at: datetime) -> str | None:
        if self.issue(at) is None and self.state == "FAULT":
            return "Vehicle reports charging FAULT; inspect the car before restarting"
        return None

    def reboot_issue(self, at: datetime) -> str | None:
        if not self.entity:
            return None
        if issue := self.issue(at):
            return issue + "; automatic charger reboot is not permitted"
        if self.state != "IN_PROGRESS":
            return f"Vehicle reports {self.state}; automatic charger reboot is not permitted"
        return None

    def view(self, at: datetime) -> dict[str, Any]:
        attributes = self.row.get("attributes", {})
        attributes = attributes if isinstance(attributes, dict) else {}
        selected = {}
        for key in ATTRIBUTES:
            value = attributes.get(key)
            if key not in attributes or not isinstance(value, (str, int, float, bool, type(None))):
                continue
            if isinstance(value, float) and not math.isfinite(value):
                continue
            selected[key] = value[:256] if isinstance(value, str) else value
        return {"configured": bool(self.entity), "entity_id": self.entity,
                "state": str(self.row.get("state", "unknown"))[:256],
                "read_at": self.at.isoformat() if self.at else None,
                "reported_at": self.row.get("last_reported") or self.row.get("last_updated"),
                # A successful HA/cloud read does not establish the vehicle measurement time.
                "vehicle_observed_at": None, "attributes": selected,
                "issue": self.issue(at), "error": self.fault(at)}
