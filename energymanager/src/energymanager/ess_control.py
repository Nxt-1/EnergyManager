"""Guarded Home Assistant hardware writer for the Victron ESS setpoint."""

from __future__ import annotations

import logging
import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from .actuators import (
    ACTUATOR_COMMAND_VERSION,
    ActuatorCommandResult,
    ActuatorRegistry,
    EssActuatorSnapshot,
    EvActuatorSnapshot,
)
from .config import EssSettings, Settings
from .ha_client import HomeAssistantError

_LOGGER = logging.getLogger(__name__)
ESS_CONTROL_VERSION = "2026-10-10-ess-control-v2"
ESS_CONTROL_STATUS_ENTITY = "sensor.energy_manager_ess_control_status"
ACTUATOR_COMMAND_STATUS_ENTITY = "sensor.energy_manager_actuator_command_status"
_SETPOINT_STEP_W = 10.0
_ACK_TOLERANCE_W = 10.0
_ACK_GRACE_SECONDS = 2.0
_MAX_ACK_ATTEMPTS = 3
_MAX_WRITE_ERRORS = 3
_FAULT_COOLDOWN = timedelta(seconds=10)


class ControlAwareActuatorRegistry(ActuatorRegistry):
    """Expose real control ownership while retaining existing actuator translation."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._ess_control_enabled = settings.ess.control_enabled
        self._ev_control_enabled = settings.ev.control_enabled

    def snapshots(self, house_state):
        snapshots = super().snapshots(house_state)
        result = []
        for item in snapshots:
            if isinstance(item, EssActuatorSnapshot):
                item = replace(item, control_enabled=self._ess_control_enabled)
            elif isinstance(item, EvActuatorSnapshot):
                item = replace(item, control_enabled=self._ev_control_enabled)
            result.append(item)
        return tuple(result)


class EssHardwareController:
    """Translate canonical ESS power requests into Victron HA number writes."""

    def __init__(self, client, settings: EssSettings) -> None:
        self._client = client
        self._settings = settings
        self._write_count = 0
        self._last_write_utc: datetime | None = None
        self._last_commanded_setpoint_w: float | None = None
        self._ack_attempts = 0
        self._write_errors = 0
        self._fault_until_utc: datetime | None = None
        self._last_error: str | None = None

    @property
    def enabled(self) -> bool:
        return self._settings.control_enabled and self._settings.setpoint_entity is not None

    @property
    def fault_active(self) -> bool:
        return self._fault_until_utc is not None and datetime.now(UTC) < self._fault_until_utc

    @property
    def consecutive_failures(self) -> int:
        return max(max(0, self._ack_attempts - 1), self._write_errors)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    async def initialize(self) -> None:
        """Neutralize the Victron setpoint before the first live plan is available."""
        if not self.enabled:
            await self._publish_status("disabled", reason="control_disabled")
            return
        _LOGGER.warning(
            "ESS hardware control ENABLED: setpoint=%s, limits=-%.0f/+%.0f W",
            self._settings.setpoint_entity,
            self._settings.max_discharge_power_w,
            self._settings.max_charge_power_w,
        )
        await self.safe_zero("startup_safe_zero", force=True)

    async def shutdown(self) -> None:
        """Attempt to leave the external ESS setpoint neutral on a clean shutdown."""
        if self.enabled:
            await self.safe_zero("shutdown_safe_zero", force=True)

    async def apply_dispatch(self, result) -> None:
        """Write the accepted ESS command from one fast-dispatch cycle."""
        if not self.enabled:
            await self._publish_status(
                "disabled",
                reason="control_disabled",
                requested_ess_power_w=result.requested_ess_power_w,
                accepted_ess_power_w=result.accepted_ess_power_w,
            )
            return

        ess_result = next((item for item in result.command_results if item.actuator_id == "ess"), None)
        if ess_result is None or result.accepted_ess_power_w is None:
            await self.safe_zero("fast_dispatch_unavailable")
            return

        desired_setpoint = -float(ess_result.accepted_power_w)
        await self._apply_target(
            desired_setpoint,
            reason="fast_dispatch",
            requested_ess_power_w=ess_result.requested_power_w,
            accepted_ess_power_w=ess_result.accepted_power_w,
        )

    async def safe_zero(self, reason: str, *, force: bool = False) -> None:
        """Command zero when live control has no safe non-zero target."""
        if not self.enabled:
            await self._publish_status("disabled", reason="control_disabled")
            return
        await self._apply_target(
            0.0,
            reason=reason,
            requested_ess_power_w=0.0,
            accepted_ess_power_w=0.0,
            force=force,
        )

    async def publish_command_status(
        self,
        results: tuple[ActuatorCommandResult, ...],
        *,
        ev_control_enabled: bool = False,
    ) -> None:
        """Publish command translation with explicit real/shadow ownership per actuator."""
        hardware_actuators = []
        if self.enabled:
            hardware_actuators.append("ess")
        if ev_control_enabled:
            hardware_actuators.append("ev")
        commands = []
        for item in results:
            command: dict[str, Any] = {
                "id": item.actuator_id,
                "kind": item.kind,
                "requested_power_w": round(item.requested_power_w, 1),
                "accepted_power_w": round(item.accepted_power_w, 1),
                "status": item.status,
                "limited": item.limited,
                "reason": item.reason,
                "hardware_write_enabled": item.actuator_id in hardware_actuators,
            }
            if item.phase_count is not None:
                command["phase_count"] = item.phase_count
            if item.current_a is not None:
                command["current_a"] = round(item.current_a, 3)
            commands.append(command)

        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager Actuator Command Status",
            "command_version": ACTUATOR_COMMAND_VERSION,
            "shadow_mode": not hardware_actuators,
            "control_enabled": bool(hardware_actuators),
            "hardware_writes": bool(hardware_actuators),
            "hardware_write_actuators": hardware_actuators,
            "shadow_only_actuators": [
                item.actuator_id for item in results if item.actuator_id not in hardware_actuators
            ],
            "command_count": len(results),
            "commands": commands,
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if not results:
            state = "idle"
        elif any(item.status == "rejected" for item in results):
            state = "rejected"
        elif any(item.status == "limited" for item in results):
            state = "limited"
        else:
            state = "accepted"
        await self._client.set_state(ACTUATOR_COMMAND_STATUS_ENTITY, state, attributes)

    async def _apply_target(
        self,
        setpoint_w: float,
        *,
        reason: str,
        requested_ess_power_w: float,
        accepted_ess_power_w: float,
        force: bool = False,
    ) -> None:
        entity_id = self._settings.setpoint_entity
        assert entity_id is not None
        target = self._normalize_setpoint(setpoint_w)
        now = datetime.now(UTC)
        if self._fault_until_utc is not None and now >= self._fault_until_utc:
            self._fault_until_utc = None
            self._ack_attempts = 0
            self._write_errors = 0

        if self.fault_active and target != 0.0 and not force:
            await self._publish_status(
                "safe_fallback",
                reason="write_retry_cooldown",
                requested_ess_power_w=requested_ess_power_w,
                accepted_ess_power_w=accepted_ess_power_w,
                desired_setpoint_w=0.0,
                acknowledged=False,
                error=self._last_error or "write_retry_cooldown",
            )
            return

        observed, read_error = await self._read_setpoint()
        if observed is None and target != 0.0 and not force:
            await self._trip_fault(read_error or "setpoint_state_unavailable")
            await self._publish_status(
                "safe_fallback",
                reason="setpoint_state_unavailable",
                requested_ess_power_w=requested_ess_power_w,
                accepted_ess_power_w=accepted_ess_power_w,
                desired_setpoint_w=0.0,
                observed_setpoint_w=None,
                acknowledged=False,
                error=self._last_error,
            )
            return

        acknowledged = observed is not None and math.isclose(observed, target, abs_tol=_ACK_TOLERANCE_W)
        if acknowledged and not force:
            self._reset_failure_tracking()
            await self._publish_status(
                "safe_zero" if target == 0.0 else "tracking",
                reason=reason,
                requested_ess_power_w=requested_ess_power_w,
                accepted_ess_power_w=accepted_ess_power_w,
                desired_setpoint_w=target,
                observed_setpoint_w=observed,
                acknowledged=True,
            )
            return

        same_target = (
            self._last_commanded_setpoint_w is not None
            and math.isclose(self._last_commanded_setpoint_w, target, abs_tol=1e-6)
        )
        awaiting_ack = (
            not force
            and same_target
            and self._last_write_utc is not None
            and (now - self._last_write_utc).total_seconds() < _ACK_GRACE_SECONDS
        )
        if awaiting_ack:
            await self._publish_status(
                "awaiting_ack",
                reason=reason,
                requested_ess_power_w=requested_ess_power_w,
                accepted_ess_power_w=accepted_ess_power_w,
                desired_setpoint_w=target,
                observed_setpoint_w=observed,
                acknowledged=False,
                error=read_error if observed is None else None,
            )
            return

        if same_target and self._ack_attempts >= _MAX_ACK_ATTEMPTS and not force:
            await self._trip_fault("setpoint_not_acknowledged")
            await self._publish_status(
                "safe_fallback",
                reason="setpoint_not_acknowledged",
                requested_ess_power_w=requested_ess_power_w,
                accepted_ess_power_w=accepted_ess_power_w,
                desired_setpoint_w=0.0,
                observed_setpoint_w=observed,
                acknowledged=False,
                error=self._last_error,
            )
            return

        try:
            await self._client.call_service(
                "number",
                "set_value",
                {"entity_id": entity_id, "value": target},
            )
        except (HomeAssistantError, OSError, TimeoutError) as exc:
            self._write_errors += 1
            self._last_error = str(exc)
            _LOGGER.error("ESS setpoint write failed (%d/%d): %s", self._write_errors, _MAX_WRITE_ERRORS, exc)
            if self._write_errors >= _MAX_WRITE_ERRORS:
                await self._trip_fault(f"setpoint_write_failed:{exc}")
            await self._publish_status(
                "safe_fallback" if self.fault_active else "write_error",
                reason=reason,
                requested_ess_power_w=requested_ess_power_w,
                accepted_ess_power_w=accepted_ess_power_w,
                desired_setpoint_w=0.0 if self.fault_active else target,
                observed_setpoint_w=observed,
                error=self._last_error,
            )
            return

        self._write_errors = 0
        self._write_count += 1
        self._last_write_utc = now
        self._ack_attempts = self._ack_attempts + 1 if same_target else 1
        self._last_commanded_setpoint_w = target
        await self._publish_status(
            "write_sent",
            reason=reason,
            requested_ess_power_w=requested_ess_power_w,
            accepted_ess_power_w=accepted_ess_power_w,
            desired_setpoint_w=target,
            observed_setpoint_w=observed,
            write_performed=True,
            acknowledged=False,
            error=read_error if observed is None else None,
        )

    async def _trip_fault(self, error: str) -> None:
        self._last_error = error
        self._fault_until_utc = datetime.now(UTC) + _FAULT_COOLDOWN
        entity_id = self._settings.setpoint_entity
        assert entity_id is not None
        try:
            await self._client.call_service(
                "number",
                "set_value",
                {"entity_id": entity_id, "value": 0.0},
            )
        except (HomeAssistantError, OSError, TimeoutError) as exc:
            _LOGGER.error("ESS fail-safe zero write failed: %s", exc)
            self._last_error = f"{error}; safe_zero_failed:{exc}"
            return
        self._write_count += 1
        self._last_write_utc = datetime.now(UTC)
        self._last_commanded_setpoint_w = 0.0

    def _reset_failure_tracking(self) -> None:
        self._ack_attempts = 0
        self._write_errors = 0
        self._fault_until_utc = None
        self._last_error = None

    async def _read_setpoint(self) -> tuple[float | None, str | None]:
        entity_id = self._settings.setpoint_entity
        assert entity_id is not None
        try:
            state = await self._client.get_state(entity_id)
        except (HomeAssistantError, OSError, TimeoutError) as exc:
            return None, str(exc)
        raw = state.get("state")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None, f"non_numeric_setpoint_state:{raw!r}"
        if not math.isfinite(value):
            return None, f"non_finite_setpoint_state:{raw!r}"
        return value, None

    def _normalize_setpoint(self, setpoint_w: float) -> float:
        minimum = -float(self._settings.max_discharge_power_w)
        maximum = float(self._settings.max_charge_power_w)
        limited = max(minimum, min(maximum, float(setpoint_w)))
        return round(limited / _SETPOINT_STEP_W) * _SETPOINT_STEP_W

    async def _publish_status(
        self,
        status: str,
        *,
        reason: str,
        requested_ess_power_w: float | None = None,
        accepted_ess_power_w: float | None = None,
        desired_setpoint_w: float | None = None,
        observed_setpoint_w: float | None = None,
        write_performed: bool = False,
        acknowledged: bool | None = None,
        error: str | None = None,
    ) -> None:
        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager ESS Control Status",
            "ess_control_version": ESS_CONTROL_VERSION,
            "control_enabled": self.enabled,
            "hardware_writes": self.enabled,
            "setpoint_entity": self._settings.setpoint_entity,
            "canonical_positive_means": "discharge",
            "victron_setpoint_positive_means": "charge",
            "setpoint_step_w": _SETPOINT_STEP_W,
            "max_charge_power_w": self._settings.max_charge_power_w,
            "max_discharge_power_w": self._settings.max_discharge_power_w,
            "reason": reason,
            "requested_ess_power_w": _round_optional(requested_ess_power_w),
            "accepted_ess_power_w": _round_optional(accepted_ess_power_w),
            "desired_setpoint_w": _round_optional(desired_setpoint_w),
            "observed_setpoint_w": _round_optional(observed_setpoint_w),
            "write_performed": write_performed,
            "acknowledged": acknowledged,
            "write_count": self._write_count,
            "last_write_utc": self._last_write_utc.isoformat() if self._last_write_utc else None,
            "last_commanded_setpoint_w": _round_optional(self._last_commanded_setpoint_w),
            "ack_attempts": self._ack_attempts,
            "write_error_count": self._write_errors,
            "max_retry_attempts": max(_MAX_ACK_ATTEMPTS, _MAX_WRITE_ERRORS),
            "fault_active": self.fault_active,
            "fault_until_utc": self._fault_until_utc.isoformat() if self._fault_until_utc else None,
            "last_error": self._last_error,
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if error is not None:
            attributes["error"] = error
        await self._client.set_state(ESS_CONTROL_STATUS_ENTITY, status, attributes)


def _round_optional(value: float | None) -> float | None:
    return None if value is None else round(float(value), 1)
