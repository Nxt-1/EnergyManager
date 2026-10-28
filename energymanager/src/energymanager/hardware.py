"""One persisted, immediate hardware switch; planning and measurement continue while off."""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from .control import GuardedActuator
from .settings import ConfigurationFile, SETTING_FIELDS

if TYPE_CHECKING:
    from .service import Application


class HardwareControl:
    def __init__(self, application: Application, configuration: ConfigurationFile) -> None:
        self.application, self.configuration = application, configuration
        self.requested = application.store.get("hardware_control_enabled", False) is True
        self.lock = asyncio.Lock()
        self.epoch = 0
        self.error: str | None = None
        self.task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self.task = asyncio.create_task(self.resume())

    async def close(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    def readiness_reason(self) -> str | None:
        app = self.application
        if app.demo:
            return "Demo mode: select configured mode in the HA app"
        try:
            settings = self.configuration.read()
        except (OSError, ValueError, TypeError, KeyError):
            return "Settings could not be read"
        if settings["issues"]:
            return "Complete the highlighted settings"
        if settings["restart_required"]:
            return "Restart EnergyManager to apply saved settings"
        if app.ha is None or not isinstance(app.actuator, GuardedActuator):
            return "Home Assistant is not connected"
        observation = app.observation
        age = (app.now() - observation.at).total_seconds()
        if observation.quality != "measured" or not -5 <= age <= app.policy.measurement_max_age_seconds:
            return "Waiting for valid live measurements"
        return None

    def state(self) -> dict[str, Any]:
        enabled = bool(getattr(self.application.actuator, "enabled", False))
        reason = self.readiness_reason()
        return {"requested": self.requested, "enabled": enabled, "can_enable": reason is None,
                "reason": self.error or reason, "changing": self.lock.locked()}

    def update_policy(self, enabled: bool) -> None:
        app = self.application
        app.policy = replace(app.policy, control_enabled=enabled)
        app.snapshot = replace(app.snapshot, policy=app.policy)
        app.controller.p = app.policy
        app.changed("hardware_control_enabled" if enabled else "hardware_control_disabled", ev=True, ess=True)
        if enabled:
            app.plan_recovery.attempt()

    async def set_requested(self, enabled: bool) -> dict[str, Any]:
        self.epoch += 1
        epoch = self.epoch
        app = self.application
        actuator = app.actuator
        if not enabled:
            # Revoke synchronously, including a queued enable or an in-flight multi-write dispatch.
            was_enabled = isinstance(actuator, GuardedActuator) and actuator.enabled
            self.requested = False
            if isinstance(actuator, GuardedActuator):
                actuator.enabled = False
            self.update_policy(False)
            persistence_error = None
            try:
                app.store.put("hardware_control_enabled", False)
            except (OSError, sqlite3.Error) as exc:
                persistence_error = exc
            async with self.lock:
                self.error = None
                try:
                    if was_enabled and isinstance(actuator, GuardedActuator):
                        await actuator.stop(app.revision, at=app.now())
                    if persistence_error:
                        raise RuntimeError("Hardware control is off; its saved state could not be updated")
                except RuntimeError as exc:
                    self.error = str(exc)
                    raise
            app.store.event("hardware_control", {"enabled": False})
            return self.state()

        async with self.lock:
            reason = self.readiness_reason()
            if reason:
                raise ValueError(reason)
            inventory = await self.configuration.entities()
            available = {entity["entity_id"]: entity for entity in inventory["entities"]}
            settings = self.configuration.read()
            for field in SETTING_FIELDS:
                if field.kind != "entity" or not field.required:
                    continue
                entity = available.get(settings["values"][field.path])
                if entity is None:
                    raise ValueError(f"{field.label}: entity not found")
                if field.path.startswith("actuators.") and entity["state"] in ("unknown", "unavailable"):
                    raise ValueError(f"{field.label}: unavailable")
                if field.units and entity["unit"] and entity["unit"] not in field.units:
                    raise ValueError(f"{field.label}: incompatible unit")
            if epoch != self.epoch:
                raise ValueError("Hardware control request was superseded")
            reason = self.readiness_reason()
            if reason:
                raise ValueError(reason)
            if not isinstance(actuator, GuardedActuator):
                raise ValueError("No hardware adapter is available")
            app.store.put("hardware_control_enabled", True)
            self.requested, self.error = True, None
            actuator.last, actuator.phase = None, None
            if actuator.goe_control:
                actuator.goe_control.reset()
            actuator.enabled = True
            self.update_policy(True)
            app.store.event("hardware_control", {"enabled": True})
            return self.state()

    async def resume(self) -> None:
        while not self.application.shutdown:
            if (self.requested and not getattr(self.application.actuator, "enabled", False)
                    and self.readiness_reason() is None):
                try:
                    await self.set_requested(True)
                except (ValueError, RuntimeError, OSError, sqlite3.Error) as exc:
                    self.error = str(exc)
            await asyncio.sleep(5)
