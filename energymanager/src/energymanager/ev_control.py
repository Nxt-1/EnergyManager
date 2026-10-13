"""Guarded Home Assistant hardware writer for the go-e EV charger."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import EvSettings
from .ha_client import HomeAssistantError

_LOGGER = logging.getLogger(__name__)
EV_CONTROL_VERSION = "2026-10-13-ev-control-v5"
EV_CONTROL_STATUS_ENTITY = "sensor.energy_manager_ev_control_status"
_PHASE_SWITCH_DELAY_SECONDS = 10.0
_PHASE_ZERO_CONFIRM_SECONDS = 3.0
_PHASE_MIN_INTERVAL_SECONDS = 600.0
_FORCE_DONT_CHARGE = "1"
_FORCE_CHARGE = "2"
_PHASE_SINGLE = "1"
_PHASE_THREE = "2"
_CURRENT_TOLERANCE_A = 0.1
_MAX_COMMAND_ATTEMPTS = 3
_MAX_WRITE_ERRORS = 3
_FAULT_COOLDOWN_SECONDS = 10.0
_CHARGE_START_CONFIRM_SECONDS = 90.0
_CHARGING_POWER_MIN_W = 100.0
_RESET_RESTART_WAIT_SECONDS = 30.0
_RESET_RESTART_TIMEOUT_SECONDS = 150.0
_RECOVERY_SUCCESS_CONFIRM_SECONDS = 20.0


class EvHardwareController:
    """Translate generic EV power commands into safe go-e Home Assistant writes."""

    def __init__(
        self,
        client,
        settings: EvSettings,
        *,
        phase_switch_delay_seconds: float = _PHASE_SWITCH_DELAY_SECONDS,
    ) -> None:
        self._client = client
        self._settings = settings
        self._phase_switch_delay_seconds = max(0.0, float(phase_switch_delay_seconds))
        self._phase_switch_target: str | None = None
        self._phase_switch_until_utc: datetime | None = None
        self._phase_switch_stopped_at_utc: datetime | None = None
        self._last_phase_switch_utc: datetime | None = None
        self._service_write_count = 0
        self._phase_switch_count = 0
        self._last_write_utc: datetime | None = None
        self._last_action: str | None = None
        self._last_command_key: tuple[str, str] | None = None
        self._command_attempts = 0
        self._write_errors = 0
        self._fault_until_utc: datetime | None = None
        self._last_error: str | None = None
        self._requested_charge_power_w = 0.0
        self._charge_enable_requested = False
        self._charge_wait_since: datetime | None = None
        self._delivery_error: str | None = None
        self._recovery_state: str | None = None
        self._recovery_started_utc: datetime | None = None
        self._reset_issued_utc: datetime | None = None
        self._reset_attempts = 0
        self._reset_total_count = 0
        self._last_reset_utc: datetime | None = None
        self._last_reset_outcome: str | None = None
        self._test_charging_since: datetime | None = None
        self._charge_confirm_since: datetime | None = None
        self._connected_observed = False
        self._power_observed_w: float | None = None

    @property
    def enabled(self) -> bool:
        return self._settings.control_enabled and all(
            (
                self._settings.current_entity,
                self._settings.phase_mode_entity,
                self._settings.force_state_entity,
            )
        )

    @property
    def fault_active(self) -> bool:
        return self._fault_until_utc is not None and datetime.now(UTC) < self._fault_until_utc

    @property
    def consecutive_failures(self) -> int:
        return max(max(0, self._command_attempts - 1), self._write_errors)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    async def initialize(self) -> None:
        """Keep the charger stopped until the first authoritative plan is available."""
        if not self.enabled:
            await self._publish_status("disabled", reason="control_disabled")
            return
        _LOGGER.warning(
            "EV hardware control ENABLED: current=%s, phase=%s, force=%s, limits=%.0f-%.0f A",
            self._settings.current_entity,
            self._settings.phase_mode_entity,
            self._settings.force_state_entity,
            self._settings.min_charge_current_a,
            self._settings.max_charge_current_a,
        )
        if self._settings.charging_power_entity is None:
            _LOGGER.warning("EV phase changes require a configured ev.charging_power_entity")
        await self.safe_stop("startup_safe_stop", force=True)

    async def shutdown(self) -> None:
        """Leave the charger stopped on a clean Energy Manager shutdown."""
        if self.enabled:
            await self.safe_stop("shutdown_safe_stop", force=True)

    def observe_charging(self, house_state, *, now_utc: datetime | None = None) -> None:
        """Track actual power and retain a confirmed charge failure across planner idling."""
        now = now_utc or datetime.now(UTC)
        connected = house_state.value("ev.connected")
        measured = house_state.value("ev.charging_power")
        self._connected_observed = connected is True
        self._power_observed_w = (
            float(measured) if isinstance(measured, (int, float)) and math.isfinite(measured) else None
        )
        if self._recovery_state == "manual_intervention":
            return
        charge_commanded = (
            self._charge_enable_requested
            and self._requested_charge_power_w >= 500
            and self._phase_switch_target is None
        )
        if self._recovery_state == "test_charging":
            if connected is not True or not charge_commanded or self._power_observed_w is None:
                self._test_charging_since = None
                self._charge_confirm_since = None
                return
            if connected is True and charge_commanded and self._power_observed_w is not None:
                if self._power_observed_w >= _CHARGING_POWER_MIN_W:
                    if self._charge_confirm_since is None:
                        self._charge_confirm_since = now
                    if (now - self._charge_confirm_since).total_seconds() >= _RECOVERY_SUCCESS_CONFIRM_SECONDS:
                        _LOGGER.info("EV charging confirmed after go-e reset; recovery attempt succeeded")
                        self._last_reset_outcome = "verified_charging"
                        self._clear_delivery_recovery()
                else:
                    self._charge_confirm_since = None
                    if self._test_charging_since is None:
                        self._test_charging_since = now
                    elif (now - self._test_charging_since).total_seconds() >= _CHARGE_START_CONFIRM_SECONDS:
                        self._latch_delivery_fault("charging_failed_after_reset")
            return
        if self._recovery_state is not None:
            return
        if connected is not True or not charge_commanded or self.fault_active or self._power_observed_w is None:
            self._charge_wait_since = None
            self._delivery_error = None
            return
        if self._power_observed_w >= _CHARGING_POWER_MIN_W:
            self._charge_wait_since = None
            self._delivery_error = None
            return
        if self._charge_wait_since is None:
            self._charge_wait_since = now
        if (now - self._charge_wait_since).total_seconds() >= _CHARGE_START_CONFIRM_SECONDS:
            self._delivery_error = "connected_not_charging"
            self._recovery_started_utc = now
            self._recovery_state = "waiting_reset" if self._settings.automatic_fault_reset else "manual_intervention"
            if self._recovery_state == "manual_intervention":
                self._latch_delivery_fault("charging_fault_manual_intervention")
            else:
                _LOGGER.warning("EV charging not detected for 90 seconds; waiting to reset go-e once")

    def _clear_delivery_recovery(self) -> None:
        self._delivery_error = None
        self._recovery_state = None
        self._recovery_started_utc = None
        self._charge_wait_since = None
        self._test_charging_since = None
        self._charge_confirm_since = None
        self._reset_issued_utc = None
        self._reset_attempts = 0

    def _latch_delivery_fault(self, reason: str) -> None:
        self._recovery_state = "manual_intervention"
        self._delivery_error = "charging_fault_latched"
        self._charge_confirm_since = None
        self._last_error = reason
        if self._reset_attempts:
            self._last_reset_outcome = reason
        _LOGGER.error("EV charging fault latched: %s; automatic charging stopped", reason)

    async def _handle_delivery_recovery(self, now: datetime) -> bool:
        """Return True if the recovery state prevents normal charging dispatch."""
        if self._recovery_state is None:
            return False
        if self._recovery_state == "manual_intervention":
            await self.safe_stop("charging_fault_latched")
            return True
        if self._recovery_state == "waiting_reset":
            await self.safe_stop("charging_fault_waiting_reset")
            if not self._connected_observed or self._recovery_started_utc is None:
                return True
            if (now - self._recovery_started_utc).total_seconds() < self._settings.fault_reset_delay_seconds:
                return True
            if (
                self._settings.reset_button_entity is None
                or self._reset_attempts >= self._settings.max_reset_attempts
            ):
                self._latch_delivery_fault("automatic_reset_unavailable")
                return True
            observed = await self._read_control_state()
            if observed[3] is not None or not _force_is_off(observed[2]):
                return True
            if not await self._charging_power_is_zero():
                return True
            self._reset_attempts += 1  # Count before the write; never repeatedly press on errors.
            self._reset_total_count += 1
            self._last_reset_utc = now
            self._last_reset_outcome = "requested"
            try:
                await self._client.call_service(
                    "button", "press", {"entity_id": self._settings.reset_button_entity},
                )
            except (HomeAssistantError, OSError, TimeoutError) as exc:
                self._latch_delivery_fault(f"charger_reset_failed:{exc}")
                return True
            self._service_write_count += 1
            self._last_write_utc = now
            self._last_action = "charger_fault_reset"
            self._reset_issued_utc = now
            self._recovery_state = "waiting_restart"
            _LOGGER.warning("EV go-e reset button pressed once; waiting for charger restart")
            await self._publish_status("reset_sent", reason="charger_fault_reset")
            return True
        if self._recovery_state == "waiting_restart":
            await self._publish_status("reset_wait", reason="await_charger_restart")
            if self._reset_issued_utc is None:
                self._latch_delivery_fault("charger_reset_timing_missing")
                return True
            elapsed = (now - self._reset_issued_utc).total_seconds()
            if elapsed > _RESET_RESTART_TIMEOUT_SECONDS:
                self._latch_delivery_fault("charger_unavailable_after_reset")
                return True
            if elapsed < _RESET_RESTART_WAIT_SECONDS:
                return True
            observed = await self._read_control_state()
            if observed[3] is not None:
                return True
            if not _force_is_off(observed[2]):
                await self.safe_stop("reset_restart_hold_off")
                return True
            self._recovery_state = "test_charging"
            self._test_charging_since = None
            self._charge_confirm_since = None
            _LOGGER.info("EV go-e responsive after reset; verifying actual charging before clearing fault")
            return False
        return False  # test_charging: allow one controlled charging attempt.

    @property
    def delivery_error(self) -> str | None:
        return self._delivery_error

    async def apply_dispatch(self, result) -> None:
        """Apply the EV command generated by the current planner interval."""
        self._clear_expired_fault()
        if self.fault_active:
            await self._publish_fault_fallback("write_retry_cooldown")
            return
        ev_result = next((item for item in result.command_results if item.actuator_id == "ev"), None)
        if not self.enabled:
            await self._publish_status(
                "disabled",
                reason="control_disabled",
                requested_power_w=None if ev_result is None else ev_result.requested_power_w,
                accepted_power_w=None if ev_result is None else ev_result.accepted_power_w,
            )
            return
        if await self._handle_delivery_recovery(datetime.now(UTC)):
            return
        self._requested_charge_power_w = 0.0 if ev_result is None else max(0.0, ev_result.accepted_power_w)
        if ev_result is None:
            await self.safe_stop("ev_command_unavailable")
            return
        if (
            ev_result.accepted_power_w <= 0.0
            or ev_result.phase_count not in {1, 3}
            or ev_result.current_a is None
            or ev_result.current_a <= 0.0
        ):
            await self.safe_stop(
                ev_result.reason or "planner_idle",
                requested_power_w=ev_result.requested_power_w,
                accepted_power_w=ev_result.accepted_power_w,
            )
            return

        target_current = int(round(float(ev_result.current_a)))
        minimum_current = math.ceil(self._settings.min_charge_current_a)
        maximum_current = math.floor(self._settings.max_charge_current_a)
        if not minimum_current <= target_current <= maximum_current:
            await self.safe_stop(
                "current_outside_configured_limits",
                requested_power_w=ev_result.requested_power_w,
                accepted_power_w=ev_result.accepted_power_w,
            )
            return

        target_phase = _PHASE_SINGLE if ev_result.phase_count == 1 else _PHASE_THREE
        await self._apply_charge_target(
            target_phase,
            target_current,
            requested_power_w=ev_result.requested_power_w,
            accepted_power_w=ev_result.accepted_power_w,
        )

    async def safe_stop(
        self,
        reason: str,
        *,
        requested_power_w: float | None = None,
        accepted_power_w: float | None = None,
        force: bool = False,
    ) -> None:
        """Force the charger into Don't charge and cancel any phase transition."""
        self._clear_expired_fault()
        self._phase_switch_target = None
        self._phase_switch_until_utc = None
        self._phase_switch_stopped_at_utc = None
        self._requested_charge_power_w = 0.0
        self._charge_enable_requested = False
        if not self.enabled:
            await self._publish_status("disabled", reason="control_disabled")
            return

        observed = await self._read_control_state()
        force_state = observed[2]
        error = observed[3]
        if error is not None and not force:
            await self._trip_fault(f"control_state_unavailable:{error}")
            await self._publish_status(
                "safe_fallback",
                reason=reason,
                requested_power_w=requested_power_w,
                accepted_power_w=accepted_power_w,
                desired_phase_count=0,
                desired_current_a=0,
                observed_current_a=observed[0],
                observed_phase_mode=observed[1],
                observed_force_state=force_state,
                acknowledged=False,
                error=self._last_error,
            )
            return
        write_performed = False
        if force or not _force_is_off(force_state):
            write_error = await self._write_select(self._settings.force_state_entity, _FORCE_DONT_CHARGE, "force_off")
            if write_error is not None:
                await self._publish_status(
                    "write_error",
                    reason=reason,
                    requested_power_w=requested_power_w,
                    accepted_power_w=accepted_power_w,
                    observed_current_a=observed[0],
                    observed_phase_mode=observed[1],
                    observed_force_state=force_state,
                    error=write_error,
                )
                return
            write_performed = True

        if _force_is_off(force_state) and not write_performed and self._recovery_state is None:
            self._reset_failure_tracking()
        await self._publish_status(
            "fault_latched" if self._recovery_state == "manual_intervention" else "stopped",
            reason=reason,
            requested_power_w=requested_power_w,
            accepted_power_w=accepted_power_w,
            desired_phase_count=0,
            desired_current_a=0,
            observed_current_a=observed[0],
            observed_phase_mode=observed[1],
            observed_force_state=force_state,
            write_performed=write_performed,
            acknowledged=_force_is_off(force_state) and not write_performed,
            error=error,
        )

    async def _apply_charge_target(
        self,
        target_phase: str,
        target_current: int,
        *,
        requested_power_w: float,
        accepted_power_w: float,
    ) -> None:
        observed_current, observed_phase, observed_force, read_error = await self._read_control_state()
        desired_phase_count = 1 if target_phase == _PHASE_SINGLE else 3
        now = datetime.now(UTC)

        if read_error is not None:
            await self._trip_fault(f"control_state_unavailable:{read_error}")
            await self._publish_status(
                "safe_fallback",
                reason="control_state_unavailable",
                requested_power_w=requested_power_w,
                accepted_power_w=accepted_power_w,
                desired_phase_count=desired_phase_count,
                desired_current_a=target_current,
                observed_current_a=observed_current,
                observed_phase_mode=observed_phase,
                observed_force_state=observed_force,
                error=read_error,
            )
            return

        # Finish a physical transition before accepting another phase-mode request.
        # New planner outputs must not reverse the phase switch while the charger is paused.
        tracking_reason = "planner_command"
        if self._phase_switch_target is not None:
            pending = self._phase_switch_target
            pending_phase_count = 1 if pending == _PHASE_SINGLE else 3
            if self._phase_switch_until_utc is None:
                # The EVSE is stopped. Require a pause and zero-power feedback.
                # Never change phase mode just because Home Assistant acknowledged Force Off.
                stopped_at = self._phase_switch_stopped_at_utc or now
                if (
                    (now - stopped_at).total_seconds() < _PHASE_ZERO_CONFIRM_SECONDS
                    or not _force_is_off(observed_force)
                ):
                    await self._publish_status(
                        "phase_switch_wait", reason="await_stop_before_phase_change",
                        requested_power_w=requested_power_w, accepted_power_w=accepted_power_w,
                        desired_phase_count=pending_phase_count, desired_current_a=target_current,
                        observed_current_a=observed_current, observed_phase_mode=observed_phase,
                        observed_force_state=observed_force, acknowledged=False,
                    )
                    return
                if not await self._charging_power_is_zero():
                    await self._publish_status(
                        "phase_switch_wait", reason="await_zero_charging_power",
                        requested_power_w=requested_power_w, accepted_power_w=accepted_power_w,
                        desired_phase_count=pending_phase_count, desired_current_a=target_current,
                        observed_current_a=observed_current, observed_phase_mode=observed_phase,
                        observed_force_state=observed_force, acknowledged=False,
                    )
                    return
                error = await self._write_select(self._settings.phase_mode_entity, pending, "phase_switch")
                if error is not None:
                    await self._publish_write_error(
                        "phase_switch", error, requested_power_w, accepted_power_w,
                        pending_phase_count, target_current, observed_current, observed_phase, observed_force,
                    )
                    return
                self._last_phase_switch_utc = now
                self._phase_switch_count += 1
                self._phase_switch_until_utc = now + timedelta(seconds=self._phase_switch_delay_seconds)
                await self._publish_status(
                    "phase_switch_wait", reason="phase_change_settle",
                    requested_power_w=requested_power_w, accepted_power_w=accepted_power_w,
                    desired_phase_count=pending_phase_count, desired_current_a=target_current,
                    observed_current_a=observed_current, observed_phase_mode=observed_phase,
                    observed_force_state=observed_force, write_performed=True, acknowledged=False,
                )
                return
            if now < self._phase_switch_until_utc:
                await self._publish_status(
                    "phase_switch_wait", reason="phase_change_settle",
                    requested_power_w=requested_power_w, accepted_power_w=accepted_power_w,
                    desired_phase_count=pending_phase_count, desired_current_a=target_current,
                    observed_current_a=observed_current, observed_phase_mode=observed_phase,
                    observed_force_state=observed_force, acknowledged=False,
                )
                return
            if not _phase_matches(observed_phase, pending):
                # HA has not acknowledged the requested phase. Never spam phase writes.
                await self.safe_stop("phase_mode_not_acknowledged")
                return
            self._phase_switch_target = None
            self._phase_switch_until_utc = None
            self._phase_switch_stopped_at_utc = None
            # If the planner changed its mind, the new physical phase must remain
            # in place until its ten-minute dwell expires.
            observed_phase = pending

        if not _phase_matches(observed_phase, target_phase):
            if self._last_phase_switch_utc is not None and (
                now - self._last_phase_switch_utc
            ).total_seconds() < _PHASE_MIN_INTERVAL_SECONDS:
                # Avoid phase reversal. Keep charging in the existing mode when the
                # requested power can be delivered without exceeding it.
                if not any(_phase_matches(observed_phase, mode) for mode in (_PHASE_SINGLE, _PHASE_THREE)):
                    await self.safe_stop("phase_mode_unrecognized_during_dwell")
                    return
                held_phase_count = 1 if _phase_matches(observed_phase, _PHASE_SINGLE) else 3
                held_current = min(
                    math.floor(self._settings.max_charge_current_a),
                    math.floor(accepted_power_w / (self._settings.nominal_voltage_v * held_phase_count)),
                )
                if held_current < math.ceil(self._settings.min_charge_current_a):
                    await self.safe_stop("phase_change_dwell_insufficient_power")
                    return
                _LOGGER.debug("EV phase dwell active: retaining %s phases at %s A", held_phase_count, held_current)
                target_phase = observed_phase if observed_phase is not None else target_phase
                target_current = held_current
                desired_phase_count = held_phase_count
                tracking_reason = "phase_change_dwell_hold"
            else:
                await self._start_phase_switch(
                    target_phase, desired_phase_count, target_current, requested_power_w,
                    accepted_power_w, observed_current, observed_phase, observed_force, now,
                )
                return

        write_performed = False
        if observed_current is None or not math.isclose(
            observed_current,
            float(target_current),
            abs_tol=_CURRENT_TOLERANCE_A,
        ):
            error = await self._write_number(self._settings.current_entity, target_current, "set_current")
            if error is not None:
                await self._best_effort_force_off()
                await self._publish_write_error(
                    "set_current",
                    error,
                    requested_power_w,
                    accepted_power_w,
                    desired_phase_count,
                    target_current,
                    observed_current,
                    observed_phase,
                    observed_force,
                )
                return
            write_performed = True

        if not _force_is_on(observed_force):
            error = await self._write_select(self._settings.force_state_entity, _FORCE_CHARGE, "force_charge")
            if error is not None:
                await self._best_effort_force_off()
                await self._publish_write_error(
                    "force_charge",
                    error,
                    requested_power_w,
                    accepted_power_w,
                    desired_phase_count,
                    target_current,
                    observed_current,
                    observed_phase,
                    observed_force,
                )
                return
            write_performed = True

        acknowledged = (
            not write_performed
            and _phase_matches(observed_phase, target_phase)
            and observed_current is not None
            and math.isclose(observed_current, float(target_current), abs_tol=_CURRENT_TOLERANCE_A)
            and _force_is_on(observed_force)
        )
        self._charge_enable_requested = True
        if acknowledged:
            self._reset_failure_tracking()
        await self._publish_status(
            "tracking" if acknowledged else "write_sent",
            reason=tracking_reason,
            requested_power_w=requested_power_w,
            accepted_power_w=accepted_power_w,
            desired_phase_count=desired_phase_count,
            desired_current_a=target_current,
            observed_current_a=observed_current,
            observed_phase_mode=observed_phase,
            observed_force_state=observed_force,
            write_performed=write_performed,
            acknowledged=acknowledged,
        )

    async def _start_phase_switch(
        self,
        target_phase: str,
        desired_phase_count: int,
        target_current: int,
        requested_power_w: float,
        accepted_power_w: float,
        observed_current: float | None,
        observed_phase: str | None,
        observed_force: str | None,
        now: datetime,
    ) -> None:
        """Stop charging first; a later dispatch verifies zero power and changes phase."""
        self._charge_enable_requested = False
        if not _force_is_off(observed_force):
            error = await self._write_select(
                self._settings.force_state_entity, _FORCE_DONT_CHARGE, "phase_switch_force_off",
            )
            if error is not None:
                await self._publish_write_error(
                    "phase_switch_force_off", error, requested_power_w, accepted_power_w,
                    desired_phase_count, target_current, observed_current, observed_phase, observed_force,
                )
                return
        self._phase_switch_target = target_phase
        self._phase_switch_stopped_at_utc = now
        self._phase_switch_until_utc = None
        await self._publish_status(
            "phase_switch_wait", reason="await_zero_charging_power",
            requested_power_w=requested_power_w, accepted_power_w=accepted_power_w,
            desired_phase_count=desired_phase_count, desired_current_a=target_current,
            observed_current_a=observed_current, observed_phase_mode=observed_phase,
            observed_force_state=observed_force, write_performed=not _force_is_off(observed_force),
            acknowledged=False,
        )

    async def _charging_power_is_zero(self) -> bool:
        """Fail closed when the charger power reading is missing or not numeric."""
        if self._settings.charging_power_entity is None:
            return False
        try:
            state = await self._client.get_state(self._settings.charging_power_entity)
            watts = float(state.get("state"))
        except (HomeAssistantError, OSError, TimeoutError, ValueError, TypeError):
            return False
        return math.isfinite(watts) and 0 <= watts < _CHARGING_POWER_MIN_W

    async def _read_control_state(self) -> tuple[float | None, str | None, str | None, str | None]:
        current_entity = self._settings.current_entity
        phase_entity = self._settings.phase_mode_entity
        force_entity = self._settings.force_state_entity
        assert current_entity is not None
        assert phase_entity is not None
        assert force_entity is not None

        errors: list[str] = []
        current: float | None = None
        phase: str | None = None
        force: str | None = None
        for name, entity_id in (
            ("current", current_entity),
            ("phase", phase_entity),
            ("force", force_entity),
        ):
            try:
                state = await self._client.get_state(entity_id)
            except (HomeAssistantError, OSError, TimeoutError) as exc:
                errors.append(f"{name}:{exc}")
                continue
            raw = state.get("state")
            if name == "current":
                try:
                    parsed = float(raw)
                except (TypeError, ValueError):
                    errors.append(f"current:non_numeric:{raw!r}")
                    continue
                if not math.isfinite(parsed):
                    errors.append(f"current:non_finite:{raw!r}")
                    continue
                current = parsed
            elif name == "phase":
                phase = None if raw is None else str(raw).strip()
                if phase is None or phase.lower() in {"", "unknown", "unavailable"}:
                    errors.append(f"phase:unavailable:{raw!r}")
                    phase = None
            else:
                force = None if raw is None else str(raw).strip()
                if force is None or force.lower() in {"", "unknown", "unavailable"}:
                    errors.append(f"force:unavailable:{raw!r}")
                    force = None
        return current, phase, force, "; ".join(errors) or None

    async def _best_effort_force_off(self) -> None:
        self._charge_enable_requested = False
        if self.fault_active:
            return
        await self._write_select(self._settings.force_state_entity, _FORCE_DONT_CHARGE, "fail_safe_force_off")

    async def _write_number(self, entity_id: str | None, value: int, action: str) -> str | None:
        assert entity_id is not None
        key = (entity_id, str(value))
        guard_error = await self._guard_repeated_command(key)
        if guard_error is not None:
            return guard_error
        try:
            await self._client.call_service("number", "set_value", {"entity_id": entity_id, "value": value})
        except (HomeAssistantError, OSError, TimeoutError) as exc:
            return await self._record_write_error(action, exc)
        self._record_write(action, key)
        return None

    async def _write_select(self, entity_id: str | None, option: str, action: str) -> str | None:
        assert entity_id is not None
        key = (entity_id, option)
        guard_error = await self._guard_repeated_command(key)
        if guard_error is not None:
            return guard_error
        try:
            await self._client.call_service(
                "select",
                "select_option",
                {"entity_id": entity_id, "option": option},
            )
        except (HomeAssistantError, OSError, TimeoutError) as exc:
            return await self._record_write_error(action, exc)
        self._record_write(action, key)
        return None

    async def _guard_repeated_command(self, key: tuple[str, str]) -> str | None:
        self._clear_expired_fault()
        if self.fault_active:
            return "write_retry_cooldown"
        if self._last_command_key == key and self._command_attempts >= _MAX_COMMAND_ATTEMPTS:
            error = f"command_not_acknowledged:{key[0]}={key[1]}"
            await self._trip_fault(error)
            return error
        return None

    async def _record_write_error(self, action: str, exc: Exception) -> str:
        self._write_errors += 1
        self._last_error = str(exc)
        _LOGGER.error("EV %s write failed (%d/%d): %s", action, self._write_errors, _MAX_WRITE_ERRORS, exc)
        if self._write_errors >= _MAX_WRITE_ERRORS:
            await self._trip_fault(f"{action}_write_failed:{exc}")
        return str(exc)

    def _record_write(self, action: str, key: tuple[str, str]) -> None:
        self._service_write_count += 1
        self._last_write_utc = datetime.now(UTC)
        self._last_action = action
        self._write_errors = 0
        if self._last_command_key == key:
            self._command_attempts += 1
        else:
            self._last_command_key = key
            self._command_attempts = 1

    async def _trip_fault(self, error: str) -> None:
        self._charge_enable_requested = False
        self._last_error = error
        self._fault_until_utc = datetime.now(UTC) + timedelta(seconds=_FAULT_COOLDOWN_SECONDS)
        force_entity = self._settings.force_state_entity
        if force_entity is None:
            return
        try:
            await self._client.call_service(
                "select",
                "select_option",
                {"entity_id": force_entity, "option": _FORCE_DONT_CHARGE},
            )
        except (HomeAssistantError, OSError, TimeoutError) as exc:
            _LOGGER.error("EV fail-safe stop write failed: %s", exc)
            self._last_error = f"{error}; safe_stop_failed:{exc}"
            return
        self._service_write_count += 1
        self._last_write_utc = datetime.now(UTC)
        self._last_action = "fault_safe_stop"

    async def _publish_fault_fallback(self, reason: str) -> None:
        observed = await self._read_control_state()
        await self._publish_status(
            "safe_fallback",
            reason=reason,
            observed_current_a=observed[0],
            observed_phase_mode=observed[1],
            observed_force_state=observed[2],
            acknowledged=_force_is_off(observed[2]),
            error=self._last_error or observed[3],
        )

    def _clear_expired_fault(self) -> None:
        if self._fault_until_utc is not None and datetime.now(UTC) >= self._fault_until_utc:
            self._fault_until_utc = None
            self._command_attempts = 0
            self._write_errors = 0
            self._last_command_key = None

    def _reset_failure_tracking(self) -> None:
        self._command_attempts = 0
        self._write_errors = 0
        self._last_command_key = None
        self._fault_until_utc = None
        self._last_error = None

    async def _publish_write_error(
        self,
        action: str,
        error: str,
        requested_power_w: float,
        accepted_power_w: float,
        desired_phase_count: int,
        desired_current_a: int,
        observed_current_a: float | None,
        observed_phase_mode: str | None,
        observed_force_state: str | None,
    ) -> None:
        await self._publish_status(
            "write_error",
            reason=action,
            requested_power_w=requested_power_w,
            accepted_power_w=accepted_power_w,
            desired_phase_count=desired_phase_count,
            desired_current_a=desired_current_a,
            observed_current_a=observed_current_a,
            observed_phase_mode=observed_phase_mode,
            observed_force_state=observed_force_state,
            error=error,
        )

    async def _publish_status(
        self,
        status: str,
        *,
        reason: str,
        requested_power_w: float | None = None,
        accepted_power_w: float | None = None,
        desired_phase_count: int | None = None,
        desired_current_a: int | None = None,
        observed_current_a: float | None = None,
        observed_phase_mode: str | None = None,
        observed_force_state: str | None = None,
        write_performed: bool = False,
        acknowledged: bool | None = None,
        error: str | None = None,
    ) -> None:
        attributes: dict[str, Any] = {
            "friendly_name": "Energy Manager EV Control Status",
            "ev_control_version": EV_CONTROL_VERSION,
            "control_enabled": self.enabled,
            "hardware_writes": self.enabled,
            "current_entity": self._settings.current_entity,
            "phase_mode_entity": self._settings.phase_mode_entity,
            "force_state_entity": self._settings.force_state_entity,
            "min_charge_current_a": self._settings.min_charge_current_a,
            "max_charge_current_a": self._settings.max_charge_current_a,
            "phase_switch_delay_seconds": self._phase_switch_delay_seconds,
            "phase_quiet_seconds": _PHASE_ZERO_CONFIRM_SECONDS,
            "phase_min_interval_seconds": _PHASE_MIN_INTERVAL_SECONDS,
            "last_phase_switch_utc": (
                self._last_phase_switch_utc.isoformat() if self._last_phase_switch_utc else None
            ),
            "phase_switch_stopped_at_utc": (
                self._phase_switch_stopped_at_utc.isoformat() if self._phase_switch_stopped_at_utc else None
            ),
            "reason": reason,
            "requested_power_w": _round_optional(requested_power_w),
            "accepted_power_w": _round_optional(accepted_power_w),
            "desired_phase_count": desired_phase_count,
            "desired_current_a": desired_current_a,
            "observed_current_a": _round_optional(observed_current_a),
            "observed_phase_mode": observed_phase_mode,
            "observed_force_state": observed_force_state,
            "phase_transition_active": self._phase_switch_target is not None,
            "phase_transition_target": self._phase_switch_target,
            "phase_transition_until_utc": (
                self._phase_switch_until_utc.isoformat() if self._phase_switch_until_utc else None
            ),
            "write_performed": write_performed,
            "acknowledged": acknowledged,
            "service_write_count": self._service_write_count,
            "phase_switch_count": self._phase_switch_count,
            "last_write_utc": self._last_write_utc.isoformat() if self._last_write_utc else None,
            "last_action": self._last_action,
            "command_attempts": self._command_attempts,
            "write_error_count": self._write_errors,
            "max_retry_attempts": max(_MAX_COMMAND_ATTEMPTS, _MAX_WRITE_ERRORS),
            "fault_active": self.fault_active,
            "fault_until_utc": self._fault_until_utc.isoformat() if self._fault_until_utc else None,
            "last_error": self._last_error,
            "delivery_error": self._delivery_error,
            "charge_enable_requested": self._charge_enable_requested,
            "reset_button_entity": self._settings.reset_button_entity,
            "automatic_fault_reset": self._settings.automatic_fault_reset,
            "fault_reset_delay_seconds": self._settings.fault_reset_delay_seconds,
            "max_reset_attempts": self._settings.max_reset_attempts,
            "recovery_state": self._recovery_state,
            "reset_attempts": self._reset_attempts,
            "reset_total_count": self._reset_total_count,
            "last_reset_utc": self._last_reset_utc.isoformat() if self._last_reset_utc else None,
            "last_reset_outcome": self._last_reset_outcome,
            "reset_issued_utc": self._reset_issued_utc.isoformat() if self._reset_issued_utc else None,
            "charge_wait_seconds": (
                round((datetime.now(UTC) - self._charge_wait_since).total_seconds(), 1)
                if self._charge_wait_since is not None else 0
            ),
            "last_update_utc": datetime.now(UTC).isoformat(),
        }
        if error is not None:
            attributes["error"] = error
        await self._client.set_state(EV_CONTROL_STATUS_ENTITY, status, attributes)


def _phase_matches(observed: str | None, target: str) -> bool:
    if observed is None:
        return False
    normalized = observed.strip().lower()
    if target == _PHASE_SINGLE:
        return normalized in {"1", "1-phase", "1 phase", "single phase", "single-phase"}
    return normalized in {"2", "3-phase", "3 phase", "three phase", "three-phase"}


def _force_is_off(observed: str | None) -> bool:
    if observed is None:
        return False
    return observed.strip().lower() in {"1", "don't charge", "dont charge", "off"}


def _force_is_on(observed: str | None) -> bool:
    if observed is None:
        return False
    return observed.strip().lower() in {"2", "charge", "on"}


def _round_optional(value: float | None) -> float | None:
    return None if value is None else round(float(value), 1)
