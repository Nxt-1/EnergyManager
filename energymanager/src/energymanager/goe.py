"""go-e APIv2 status interpretation and asynchronous command confirmation."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from .vehicle_charging import VehicleCharging

if TYPE_CHECKING:
    from .control import Command, GuardedActuator
    from .domain import Observation


WAITING = {
    0: "No charge-controller data", 2: "Waiting for authorization", 5: "Charger schedule",
    6: "Charger energy limit", 16: "Charger tariff", 17: "Charger tariff",
    18: "Charger automatic stop", 22: "Simulated unplugging", 23: "Phase switching",
    24: "Minimum charging pause", 27: "Load management", 28: "OCPP control",
    29: "Reconnect delay", 30: "Adapter blocking", 31: "Frequency protection",
    32: "Unbalanced-load protection", 34: "Grid monitoring", 35: "OCPP fallback",
}
CHARGING = {3, 7, 8, 9, 10, 11, 12, 13, 14, 15, 19, 20, 33}
RESUME_DELAY_SECONDS = 30
WAITING_TIMEOUT_SECONDS = 120


class GoEReadings:
    """A validated sampler frame; HA read success alone is not a device heartbeat."""

    def __init__(self, actuators: dict[str, str], diagnostics: dict[str, str], maximum_age: float = 30) -> None:
        self.entities = {key: actuators.get(key, "") for key in ("force", "current", "phase")}
        self.entities.update({key: diagnostics.get(key, "") for key in
                              ("ev_status", "charger_status", "charger_error", "charge_allowed", "heartbeat", "vehicle_charging")})
        self.vehicle = VehicleCharging(diagnostics.get("vehicle_charging", ""), maximum_age)
        self.maximum_age = maximum_age
        self.rows: dict[str, dict[str, Any]] = {}
        self.at: datetime | None = None
        self.device_at: datetime | None = None
        self.heartbeat: float | None = None
        self.problem = "Waiting for go-e readings"

    def number(self, key: str) -> float:
        row = self.rows.get(key, {})
        try:
            value = float(row.get("state", "nan"))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{key}: numeric go-e [CODE] reading required") from exc
        if not math.isfinite(value):
            raise ValueError(f"{key}: numeric go-e [CODE] reading required")
        return value

    def code(self, key: str) -> int:
        value = self.number(key)
        if value != int(value) or not 0 <= value <= 255:
            raise ValueError(f"{key}: invalid go-e code")
        return int(value)

    def attributes(self, key: str) -> dict[str, Any]:
        attributes = self.rows.get(key, {}).get("attributes")
        return attributes if isinstance(attributes, dict) else {}

    def update(self, rows: dict[str, dict[str, Any]], at: datetime) -> None:
        self.rows = {key: row if isinstance(row := rows.get(entity), dict) else {}
                     for key, entity in self.entities.items()}
        self.at = at
        self.vehicle.update(self.rows.get("vehicle_charging", {}), at)
        try:
            for key, entity in self.entities.items():
                if key not in ("charge_allowed", "vehicle_charging") and not entity:
                    raise ValueError(f"Select go-e {key.replace('_', ' ')} for EV control")
            for key in ("ev_status", "charger_status", "charger_error"):
                self.code(key)
            if self.code("force") not in (0, 1, 2) or self.code("phase") not in (1, 2):
                raise ValueError("go-e force/phase selector is unknown or automatic")
            attrs = self.attributes("current")
            current, lower, upper = self.number("current"), float(attrs["min"]), float(attrs["max"])
            if (attrs.get("unit_of_measurement") != "A" or not all(math.isfinite(v) for v in (lower, upper))
                    or not 0 < lower <= current <= upper or current != int(current)):
                raise ValueError("Invalid go-e current readback or limits")
            heartbeat = self.number("heartbeat")
            if heartbeat < 0 or self.attributes("heartbeat").get("unit_of_measurement") != "s":
                raise ValueError("Use go-e last Status change age in seconds; uptime in whole hours is unsuitable")
            if self.heartbeat is not None and heartbeat != self.heartbeat:
                self.device_at = at
            self.heartbeat = heartbeat
            self.problem = ""
        except (ValueError, TypeError, KeyError) as exc:
            self.problem = str(exc)
            self.device_at = None
            self.heartbeat = None

    def issue(self, at: datetime) -> str | None:
        if self.problem:
            return self.problem
        if self.at is None or not -5 <= (at - self.at).total_seconds() <= self.maximum_age:
            return "go-e read watchdog expired"
        if self.device_at is None or not -5 <= (at - self.device_at).total_seconds() <= self.maximum_age:
            return "Waiting for advancing go-e status age; charger data may be cached"
        return None

    def waiting(self) -> str | None:
        car, model = self.code("ev_status"), self.code("charger_status")
        if car == 4:
            return "Car reports charging complete"
        if car == 1:
            return "Charger reports no car"
        if model == 4:
            return "Charger reports forced stop"
        if model in WAITING:
            return WAITING[model]
        if car == 3:
            return "Waiting for car"
        if car not in (1, 2) or model not in CHARGING | {4}:
            return "Unknown go-e charging state"
        return None

    def error(self) -> str | None:
        code = self.code("charger_error")
        if code or self.code("ev_status") == 5 or self.code("charger_status") in (1, 26):
            return f"go-e fault code {code}, car {self.code('ev_status')}, status {self.code('charger_status')}"
        return None

    def reboot_issue(self, at: datetime) -> str | None:
        if issue := self.issue(at):
            return issue
        if issue := self.vehicle.reboot_issue(at):
            return issue
        if issue := self.error():
            return issue + "; automatic reboot is not permitted"
        stopped_after_request = self.code("charger_status") == 4 and self.code("ev_status") == 3
        if (self.code("ev_status") != 2 and not stopped_after_request
                or self.code("charger_status") not in CHARGING | {4}):
            return "go-e is waiting, complete or unknown; automatic reboot is not permitted"
        return None

    def limits(self, configured_minimum: int, configured_maximum: int) -> tuple[int, int]:
        attrs = self.attributes("current")
        return max(configured_minimum, math.ceil(float(attrs["min"]))), min(configured_maximum, math.floor(float(attrs["max"])))

    def view(self, at: datetime) -> dict[str, Any]:
        issue = self.issue(at)
        return {"issue": issue, "at": self.at.isoformat() if self.at else None,
                "device_at": self.device_at.isoformat() if self.device_at else None,
                "states": {key: row.get("state") for key, row in self.rows.items()},
                "current_limits": {key: self.attributes("current").get(key)
                                   for key in ("min", "max")},
                "waiting": self.waiting() if not issue else None,
                "vehicle_charging": self.vehicle.view(at)}


class GoEControl:
    """Non-blocking EV sequencing; all waits span sampler frames, never control-loop sleeps."""

    def __init__(self, actuator: GuardedActuator, readings: GoEReadings) -> None:
        self.actuator, self.readings = actuator, readings
        self.pending: dict[str, tuple[int, datetime]] = {}
        self.phase_started: datetime | None = None
        self.waiting_since: datetime | None = None
        self.no_power_since: datetime | None = None
        self.unhealthy_since: datetime | None = None
        self.stop_sent: datetime | None = None
        self.stopping_since: datetime | None = None
        self.disabled_stop_at: datetime | None = None
        self.observed_phase: int | None = None
        self.status = "Waiting for charger inputs"

    def reset(self) -> None:
        self.pending.clear()
        self.phase_started = self.waiting_since = self.no_power_since = self.unhealthy_since = self.stop_sent = None
        self.stopping_since = self.disabled_stop_at = None
        self.observed_phase = None
        self.actuator.resume_after = None
        self.actuator.last = None

    def view(self, at: datetime, observation: Observation, command: Command | None) -> dict[str, Any]:
        """Read-only display of controller intent, separate from charger measurements."""
        a, r = self.actuator, self.readings

        def activity(stage: str, label: str, detail: str = "", *,
                     until: datetime | None = None, seconds: int = 0, timer: str = "") -> dict[str, Any]:
            return {"as_of": at.isoformat(), "stage": stage, "label": label, "detail": detail,
                    "until": until.isoformat() if until else None, "duration_seconds": seconds, "timer": timer}

        if not a.enabled:
            return activity("disabled", "Automatic EV control off")
        if a.delivery_fault:
            return activity("fault", "Stopped for attention", a.delivery_reason)
        if observation.connected and (error := r.vehicle.fault(at)):
            return activity("fault", "Stopping for vehicle fault", error)
        if issue := r.issue(at):
            return activity("blocked", "Waiting for charger inputs", issue)
        if error := r.error():
            return activity("fault", "Stopping for charger fault", error)
        if command is None or not -5 <= (at - command.at).total_seconds() <= r.maximum_age:
            return activity("blocked", "Waiting for current controller request")
        pending_force = self.pending.get("force")
        if pending_force:
            starting = pending_force[0] == 2
            return activity("starting" if starting else "stopping",
                            "Confirming start" if starting else "Confirming stop",
                            "Waiting for a newer charger readback; service acceptance is not confirmation.")
        if not command.current_a or not observation.connected:
            return activity("idle", "Stopped as requested", command.reason)
        if self.phase_started is not None:
            target = a.target_phase or command.phases
            if "phase" in self.pending:
                return activity("settings", f"Selecting {target}-phase mode", "Waiting for charger readback.")
            if a.awaiting_phase is not None:
                if a.resume_after is not None and at >= a.resume_after:
                    return activity("settings", "Waiting for charger phase transition",
                                    "Restart hold complete; the charger still reports a phase transition.")
                return activity("settings", "Waiting for charger phase transition",
                                "The charger still reports simulated unplugging or phase switching.",
                                until=a.resume_after, seconds=RESUME_DELAY_SECONDS, timer="Restart hold")
            if observation.ev_power_kw >= .1:
                return activity("stopping", "Waiting for EV power to stop", "Charging must stop before changing phases.")
            ready = a.stopped_at + timedelta(seconds=10) if a.stopped_at else None
            if ready and a.zero_since:
                ready = max(ready, a.zero_since + timedelta(seconds=3))
            if ready and at >= ready:
                ready = None
            return activity("stopping", "Preparing phase change", "Confirming stopped power before changing phases.",
                            until=ready, seconds=10, timer="Stop preparation")
        if self.stopping_since is not None:
            return activity("stopping", "Waiting for EV power to stop", "Confirming stopped power before the restart hold.")
        if a.resume_after is not None and at < a.resume_after:
            return activity("settling", "Settling before restart", "Charging is deliberately held off before starting.",
                            until=a.resume_after, seconds=RESUME_DELAY_SECONDS, timer="Restart hold")
        if "current" in self.pending:
            return activity("settings", f"Confirming {command.current_a} A limit", "Current changes do not require a restart hold.")
        if self.waiting_since is not None:
            return activity("waiting", "Waiting for car or charger", self.status,
                            until=self.waiting_since + timedelta(seconds=WAITING_TIMEOUT_SECONDS),
                            seconds=WAITING_TIMEOUT_SECONDS, timer="Charging wait")
        if observation.ev_power_kw >= .1:
            return activity("charging", "Charging", "Measured power is reaching the car.")
        if a.charging_since is not None:
            delivery_deadline = a.charging_since + timedelta(seconds=90)
            waiting_deadline = self.no_power_since + timedelta(seconds=WAITING_TIMEOUT_SECONDS) if self.no_power_since else delivery_deadline
            blocked_first = waiting_deadline < delivery_deadline
            return activity("power", "Waiting for charging power", "Start confirmed; checking measured delivery.",
                            until=min(delivery_deadline, waiting_deadline),
                            seconds=WAITING_TIMEOUT_SECONDS if blocked_first else 90,
                            timer="Charging wait" if blocked_first else "Delivery check")
        return activity("waiting", "Waiting to start", self.status)

    def observe_stopped(self, command: Command, observation: Observation, confirmed: bool) -> None:
        """Start one settling interval when force off and low power are confirmed."""
        a = self.actuator
        if not confirmed or observation.ev_power_kw >= .1:
            a.resume_after = None
        elif a.resume_after is None:
            a.resume_after = command.at + timedelta(seconds=RESUME_DELAY_SECONDS)
        self.waiting_since = self.no_power_since = None

    def fault(self, command: Command, observation: Observation, reason: str, *, reboot: bool = False) -> None:
        a = self.actuator
        a.delivery_fault, a.delivery_fault_at = True, command.at
        a.delivery_reason, a.delivery_reboot_allowed = reason, reboot
        if a.on_delivery_fault:
            since = (self.no_power_since or a.charging_since or self.phase_started or self.unhealthy_since
                     or self.waiting_since or self.stopping_since or command.at)
            a.on_delivery_fault(command, observation, since)

    async def stop(self, command: Command) -> None:
        self.no_power_since = None
        # A stop must still be attempted when the readbacks themselves are unavailable.
        if self.stop_sent is None or (command.at - self.stop_sent).total_seconds() >= 10:
            await self.actuator.write("select", "select_option", "force", "option", "1")
            self.stop_sent = command.at
            self.actuator.resume_after = None

    async def fail(self, command: Command, observation: Observation, reason: str, *, reboot: bool = False) -> None:
        try:
            self.fault(command, observation, reason, reboot=reboot)
        finally:
            await self.stop(command)  # Failed evidence storage must not prevent the stop attempt.

    async def confirm(self, key: str, value: int, command: Command, observation: Observation) -> bool:
        r, a = self.readings, self.actuator
        pending = self.pending.get(key)
        # A revision changes authority, not an already submitted identical device command.
        same_request = pending is not None and pending[0] == value
        matches = r.number(key) == value
        if matches and (pending is None or same_request and r.device_at is not None and r.device_at > pending[1]):
            self.pending.pop(key, None)
            return True
        a.charging_since = None
        if same_request:
            assert pending is not None
            if (command.at - pending[1]).total_seconds() >= 30:
                await self.fail(command, observation, f"go-e {key} command was not confirmed within 30 seconds")
            return False
        domain, service, value_key = ("number", "set_value", "value") if key == "current" else ("select", "select_option", "option")
        previous_resume, previous_stop = a.resume_after, self.stop_sent
        self.pending[key] = value, command.at
        if key == "force" and value == 1:
            a.resume_after = None
        if key == "force" and value == 2:
            self.stop_sent = None  # A newer start request revokes any earlier stop acknowledgement.
        # Import here because the actuator module also imports this sequencer.
        from .control import StaleDispatch

        try:
            await a.write(domain, service, key, value_key, value if key == "current" else str(value))
        except StaleDispatch:
            # A revoked write never reached the device; do not await a phantom acknowledgement.
            a.resume_after, self.stop_sent = previous_resume, previous_stop
            if pending is None:
                self.pending.pop(key, None)
            else:
                self.pending[key] = pending
            raise
        self.status = f"Confirming go-e {key}"
        return False

    async def apply(self, command: Command, observation: Observation) -> None:
        a, r = self.actuator, self.readings
        if a.delivery_fault:
            self.status = "EV fault; stopped"
            await self.stop(command)
            return
        if observation.connected and (error := r.vehicle.fault(command.at)):
            await self.fail(command, observation, error)
            return
        issue = r.issue(command.at)
        if issue:
            a.charging_since = None
            self.pending.clear()
            self.status = issue
            await self.stop(command)
            if command.current_a and observation.connected:
                self.unhealthy_since = self.unhealthy_since or command.at
                if (command.at - self.unhealthy_since).total_seconds() >= 30:
                    await self.fail(command, observation, issue)
            return
        self.unhealthy_since = None
        if error := r.error():
            await self.fail(command, observation, error + "; inspect before restart")
            return
        phase = r.code("phase")
        if self.observed_phase is not None and phase != self.observed_phase:
            a.resume_after = command.at + timedelta(seconds=RESUME_DELAY_SECONDS)
        self.observed_phase = phase
        if not command.current_a or not observation.connected:
            a.charging_since = None
            self.waiting_since = self.no_power_since = None
            self.phase_started = None
            self.pending.pop("phase", None)
            self.pending.pop("current", None)
            a.target_phase = a.awaiting_phase = None
            a.stopped_at = a.zero_since = None
            self.status = "EV stopped"
            confirmed = await self.confirm("force", 1, command, observation)
            self.observe_stopped(command, observation, confirmed)
            if observation.ev_power_kw >= .1:
                self.stopping_since = self.stopping_since or command.at
                if confirmed and (command.at - self.stopping_since).total_seconds() >= 30:
                    await self.fail(command, observation, "EV power did not stop after the confirmed stop request")
            else:
                self.stopping_since = None
            return
        minimum, maximum = r.limits(a.c.minimum_current_a, a.c.maximum_current_a)
        if not minimum <= command.current_a <= maximum:
            self.status = f"EV paused: requested {command.current_a} A outside charger limits {minimum}–{maximum} A"
            await self.fail(command, observation, self.status)
            return
        if command.phases != {1: 1, 2: 3}[r.code("phase")] or self.phase_started is not None:
            self.status = "Preparing charger phase change"
            self.no_power_since = None
            a.charging_since = None
            self.phase_started = self.phase_started or command.at
            a.target_phase = a.target_phase or command.phases
            phase_target = a.target_phase
            if (command.at - self.phase_started).total_seconds() >= 180:
                await self.fail(command, observation, "go-e phase change timed out; EV remains stopped")
                return
            if not await self.confirm("force", 1, command, observation):
                return
            a.stopped_at = a.stopped_at or command.at
            a.zero_since = (a.zero_since or observation.at) if observation.ev_power_kw < .1 else None
            if (a.zero_since is None or (observation.at - a.zero_since).total_seconds() < 3
                    or (command.at - a.stopped_at).total_seconds() < 10):
                return
            if not await self.confirm("phase", 2 if phase_target == 3 else 1, command, observation):
                return
            # Selector acknowledgement starts the same tested hold in either direction.
            if "phase" not in self.pending and a.awaiting_phase is None:
                a.resume_after = command.at + timedelta(seconds=RESUME_DELAY_SECONDS)
                a.awaiting_phase = phase_target
            if r.code("charger_status") in (22, 23):
                self.status = "Waiting for charger phase transition"
                return
            a.switched_at = command.at
            a.phase = phase_target
            a.target_phase = a.awaiting_phase = None
            a.stopped_at = a.zero_since = None
            self.phase_started = None
            if command.phases != phase_target:
                return
        if (self.no_power_since is not None and observation.ev_power_kw < .1
                and (command.at - self.no_power_since).total_seconds() >= WAITING_TIMEOUT_SECONDS):
            reason = r.waiting() or "Requested charging delivered less than 100 W across changing states"
            await self.fail(command, observation, reason + "; waiting exceeded 2 minutes")
            return
        # Current-only changes stay live. Every actual restart waits for a settled stop.
        pending_force = self.pending.get("force")
        starting = (pending_force is not None and pending_force[0] == 2
                    and (a.resume_after is None or command.at >= a.resume_after))
        needs_resume = a.resume_after is not None or r.code("force") != 2 or pending_force is not None
        if needs_resume and not starting:
            confirmed = await self.confirm("force", 1, command, observation)
            self.observe_stopped(command, observation, confirmed)
            if not confirmed:
                return
            if observation.ev_power_kw >= .1:
                self.status = "Waiting for EV power below 100 W before restart"
                self.stopping_since = self.stopping_since or command.at
                if (command.at - self.stopping_since).total_seconds() >= 30:
                    await self.fail(command, observation, "EV power did not stop after the confirmed stop request")
                return
            self.stopping_since = None
        if not await self.confirm("current", command.current_a, command, observation):
            return
        if not starting and a.resume_after is not None and command.at < a.resume_after:
            remaining = math.ceil((a.resume_after - command.at).total_seconds())
            self.status = f"EV restart settling: {remaining} seconds remaining"
            return
        if not await self.confirm("force", 2, command, observation):
            return
        a.resume_after = None
        self.stopping_since = None
        self.stop_sent = None
        self.no_power_since = (self.no_power_since or command.at) if observation.ev_power_kw < .1 else None
        waiting = r.waiting()
        if waiting or r.entities["charge_allowed"] and str(r.rows["charge_allowed"].get("state")).lower() not in ("on", "true"):
            a.charging_since = None
            self.status = waiting or "Charger does not allow charging"
            if observation.ev_power_kw >= .1:
                self.waiting_since = None  # Actual delivery ends a non-delivery wait, despite a lagging status.
                return
            self.waiting_since = self.no_power_since
            return
        self.waiting_since = None
        self.status = "Charging command confirmed"
        if observation.ev_power_kw < .1:
            a.charging_since = a.charging_since or command.at
            if (command.at - a.charging_since).total_seconds() >= 90:
                await self.fail(command, observation, "Confirmed charging request delivered less than 100 W for 90 seconds",
                                reboot=r.vehicle.reboot_issue(command.at) is None)
        else:
            a.charging_since = None
