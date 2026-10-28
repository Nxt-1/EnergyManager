"""Restore compatible accepted instructions after fresh startup checks, without a solve."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import sqlite3
import zlib
from typing import TYPE_CHECKING, Any

from .control import GuardedActuator
from .domain import Snapshot, encode, json_data

if TYPE_CHECKING:
    from .service import Application


class PlanRecovery:
    """One startup candidate; a live invalidation can never reactivate it later."""

    FORMAT = 1

    def __init__(self, application: Application) -> None:
        self.app = application
        self.plan = application.accepted
        self.pending = bool(not application.demo and self.plan and application.store.get("hardware_control_enabled") is True)
        self.state = "waiting" if self.pending else "not_requested"
        self.reason = "Waiting for startup checks" if self.pending else ""
        self.source: Snapshot | None = None

    @staticmethod
    def digest(value: Any) -> str:
        return sha256(encode(value).encode()).hexdigest()

    def configuration_identity(self) -> str | None:
        if self.app.hardware is None:
            return None
        # These are active typed settings; secret values are already masked by the editor.
        return self.digest(self.app.hardware.configuration.started_values)

    def requirements_identity(self) -> str:
        return self.digest({"goals": sorted(json_data(self.app.goals), key=lambda g: g["id"]),
                            "daily_approvals": self.app.store.get("daily_approvals", {}),
                            "peak_permissions": self.app.store.get("peak_permissions", {})})

    def stamp(self, result: dict[str, Any]) -> None:
        """Persist identity with the accepted result in the existing adoption transaction."""
        identity = self.configuration_identity()
        if not self.app.demo and identity:
            result["execution_context"] = {"format": self.FORMAT, "configuration": identity,
                                           "requirements": self.requirements_identity(),
                                           "result_digest": self.digest({k: v for k, v in result.items() if k != "execution_context"})}
        self.plan, self.source = result, None
        self.pending = False
        self.state, self.reason = "new_plan", "A new calculation was accepted"

    def cancel(self, reason: str) -> None:
        if self.pending:
            self.finish("incompatible", reason)

    def finish(self, state: str, reason: str) -> None:
        self.pending = False
        self.state, self.reason = state, reason
        self.app.store.event("plan_recovery", self.view())

    def load(self) -> Snapshot:
        assert self.plan is not None
        context = self.plan.get("execution_context", {})
        if not isinstance(context, dict) or context.get("format") != self.FORMAT:
            raise ValueError("Saved plan predates compatible startup recovery metadata")
        if context.get("configuration") != self.configuration_identity():
            raise ValueError("Active installation settings differ from the saved plan")
        if context.get("requirements") != self.requirements_identity():
            raise ValueError("Goals or permissions differ from the saved plan")
        payload = {key: value for key, value in self.plan.items() if key != "execution_context"}
        if context.get("result_digest") != self.digest(payload):
            raise ValueError("Saved plan execution checksum mismatch")
        decision = self.app.store.decision(self.plan["id"])
        if not decision or decision["disposition"] != "accepted" or decision["result"] != self.plan:
            raise ValueError("Saved plan does not match its accepted archive")
        if not self.plan.get("valid") or not self.plan.get("admission", {}).get("passed"):
            raise ValueError("Saved plan lacks successful calculation and admission evidence")
        if self.plan.get("input_digest") != decision["digest"]:
            raise ValueError("Saved plan does not match its original input snapshot")
        original = Snapshot.from_dict(decision["snapshot"])
        return Snapshot.from_dict(self.plan["effective_snapshot"]) if self.plan.get("effective_snapshot") else original

    def attempt(self) -> bool:
        app = self.app
        if not self.pending or app.demo or not app.hardware or not app.hardware.requested:
            return False
        if self.plan is not app.accepted:
            self.cancel("A different plan replaced the startup candidate")
            return False
        at, o = app.now(), app.observation
        if (o.quality != "measured" or not -5 <= (at - o.at).total_seconds() <= app.policy.measurement_max_age_seconds
                or app.house_mismatch_since is not None or not o.ev_phase_known or not o.ev_state_known):
            self.reason = "Waiting for fresh usable measurements and known EV state"
            return False
        if not isinstance(app.actuator, GuardedActuator) or not app.actuator.enabled:
            self.reason = "Waiting for the persisted hardware-control request to resume"
            return False
        charger = app.actuator.charger
        if charger is None or charger.issue(at):
            self.reason = "Waiting for fresh validated charger readbacks"
            return False
        if app.actuator.delivery_fault or charger.error() or charger.vehicle.fault(at):
            self.cancel("EV fault or recovery requires attention before resuming")
            return False
        try:
            source = self.source or self.load()
            self.source = source
            assert self.plan is not None
            context = self.plan["execution_context"]
            if context["requirements"] != self.requirements_identity():
                raise ValueError("Goals or permissions changed during startup")
            if context["configuration"] != self.configuration_identity():
                raise ValueError("Installation settings changed during startup")
            if (source.capabilities != app.snapshot.capabilities
                    or replace(source.policy, control_enabled=False) != replace(app.policy, control_enabled=False)):
                raise ValueError("Capabilities or policy differ from the saved calculation")
            if (o.connected != source.observation.connected or o.ev_state_known != source.observation.ev_state_known):
                raise ValueError("EV connection or state availability changed since calculation")
            if (at - source.forecast_at).total_seconds() > app.policy.forecast_max_age_seconds:
                raise ValueError("Saved planning forecast is stale")
            if at < source.intervals[0].start or at >= source.intervals[-1].end:
                raise ValueError("Saved schedule does not cover the current time")
            if any(i.start < at and (i.withdrawal_kwh > 0 or not i.available) for i in source.intervals):
                raise ValueError("Travel or an away interval requires a new calculation")
            # Restore runtime context, never the archived calculation or its original flows.
            runtime = replace(source, observation=o, revision=app.revision, policy=app.policy)
        except (ValueError, TypeError, KeyError, IndexError, sqlite3.Error, zlib.error) as exc:
            self.cancel(str(exc))
            return False
        app.snapshot = runtime
        app.ev_valid = o.connected and o.ev_state_known
        app.ess_valid = app.conditional_valid = True
        command = app.controller.tick(o, at, self.plan, app.revision, app.ev_valid, app.ess_valid, app.conditional_valid)
        app.current_command = command
        # Forecast command continuity from the recovered request, never the startup dry-run zero.
        held = command if command.phases == o.ev_phases else replace(command, ev_kw=0, current_a=0, phases=o.ev_phases)
        app.last_command = json_data(held)
        self.finish("restored", "Saved schedule resumed after fresh startup checks; recalculation continues independently")
        return True

    def view(self) -> dict[str, Any]:
        return {"state": self.state, "reason": self.reason,
                "plan_id": self.plan.get("id") if self.plan else None, "revision": self.app.revision}
