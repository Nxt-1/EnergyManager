"""Persisted EV delivery incidents, bounded recovery and read-only diagnostic exports."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import aiohttp

from .control import Command, GuardedActuator
from .domain import Observation, instant, json_data

if TYPE_CHECKING:
    from .service import Application

CLOSED = ("recovered", "acknowledged")


class EVFaults:
    def __init__(self, application: Application, reboot_entity: str = "",
                 diagnostics: dict[str, str] | None = None) -> None:
        self.app = application
        self.reboot_entity = reboot_entity or ""
        self.diagnostics = diagnostics or {}
        self.current: dict[str, Any] | None = application.store.get("ev_incident")
        self.tasks: list[asyncio.Task[None]] = []
        self.next_notification: datetime | None = None
        self.power_since: datetime | None = None
        actuator = application.actuator
        if not isinstance(actuator, GuardedActuator):
            raise ValueError("EV recovery requires the guarded actuator")
        self.actuator = actuator
        self.actuator.on_delivery_fault = self.capture
        if self.current and self.current["status"] not in CLOSED:
            self.actuator.delivery_fault = True
            self.actuator.delivery_fault_at = instant(self.current["detected_at"])
            if self.current["status"] == "verifying":
                self.unresolved("Application restarted during charging verification; inspect before acknowledging")

    def start(self) -> None:
        self.tasks = [asyncio.create_task(self.loop()), asyncio.create_task(self.sample_loop())]

    async def close(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    def save(self) -> None:
        assert self.current is not None
        self.app.store.save_ev_incident(self.current)

    def capture(self, command: Command, observation: Observation, since: datetime) -> None:
        if self.current and self.current["status"] not in CLOSED:
            if self.current["status"] == "verifying":
                self.unresolved("Charging did not resume after the single reboot attempt")
            return
        self.current = {"id": uuid4().hex, "started_at": since.isoformat(),
                        "detected_at": command.at.isoformat(), "status": "pending",
                        "reason": self.actuator.delivery_reason,
                        "reboot_allowed": self.actuator.delivery_reboot_allowed,
                        "charger": self.actuator.charger.view(command.at) if self.actuator.charger else None,
                        "reboot_attempts": 0, "attempted_at": None, "resolved_at": None,
                        "notification": "pending", "command": json_data(command),
                        "observation": json_data(observation)}
        self.next_notification = None
        self.save()

    def fresh(self) -> bool:
        o = self.app.observation
        age = (self.app.now() - o.at).total_seconds()
        return ((self.actuator.charger is None or self.actuator.charger.issue(self.app.now()) is None)
                and o.quality == "measured" and -5 <= age <= self.app.policy.measurement_max_age_seconds
                and o.connected and o.ev_phase_known and o.ev_state_known)

    def permitted(self) -> bool:
        charger = self.actuator.charger
        return (self.actuator.enabled and self.fresh() and self.app.observation.ev_power_kw < .1
                and (charger is None or charger.reboot_issue(self.app.now()) is None and charger.code("force") == 1))

    def unresolved(self, reason: str) -> None:
        assert self.current is not None
        self.actuator.delivery_fault = True
        self.current.update(status="unresolved", reason=reason)
        self.save()

    async def loop(self) -> None:
        while not self.app.shutdown:
            try:
                await self.step()
            except (RuntimeError, OSError, ValueError, aiohttp.ClientError, TimeoutError) as exc:
                if self.current and self.current["status"] not in CLOSED:
                    self.unresolved(f"Recovery could not complete ({type(exc).__name__})")
            await asyncio.sleep(1)

    async def step(self) -> None:
        self.check_disabled_stop()
        incident = self.current
        if not incident or incident["status"] in CLOSED:
            return
        at = self.app.now()
        if incident["status"] == "pending":
            charger = self.actuator.charger
            if not incident.get("reboot_allowed", False):
                self.unresolved(incident["reason"] + "; automatic reboot is not eligible")
            elif charger and charger.reboot_issue(at):
                self.unresolved(charger.reboot_issue(at) or "Charger recovery unavailable")
            elif not self.reboot_entity:
                self.unresolved("No charger reboot button is configured")
            elif not self.actuator.enabled:
                self.unresolved("Hardware control is off; no reboot was attempted")
            elif not self.permitted():
                if (at - instant(incident["detected_at"])).total_seconds() >= 120:
                    self.unresolved("Fresh connected EV inputs and zero charging power could not be confirmed")
            else:
                last_reboot = self.app.store.get("ev_last_reboot")
                if last_reboot and (at - instant(last_reboot)).total_seconds() < 1800:
                    self.unresolved("A reboot was already attempted within the last 30 minutes")
                    return
                assert self.app.ha is not None
                button = await self.app.ha.entity_state(self.reboot_entity)
                if str(button.get("state", "unavailable")) == "unavailable":
                    self.unresolved("The configured charger reboot button is unavailable")
                    return

                def before_press() -> None:
                    attempted_at = self.app.now().isoformat()
                    incident.update(status="rebooting", reboot_attempts=1, attempted_at=attempted_at,
                                    reason="One reboot requested; waiting for fresh charger inputs")
                    self.save()  # A crash or HTTP timeout must never replay the reboot.
                    self.app.store.put("ev_last_reboot", attempted_at)

                await self.actuator.reboot_ev(self.reboot_entity, self.permitted, before_press)
                return
        elif incident["status"] == "rebooting":
            attempted = instant(incident["attempted_at"])
            if at < attempted + timedelta(seconds=60):
                return
            if not self.actuator.enabled:
                self.unresolved("Hardware control was disabled during recovery")
            elif (self.fresh() and self.app.observation.at >= attempted + timedelta(seconds=60)
                  and (self.actuator.charger is None or self.actuator.charger.device_at is not None
                       and self.actuator.charger.device_at >= attempted + timedelta(seconds=60))):
                incident.update(status="verifying", verification_started_at=at.isoformat(),
                                reason="Reboot wait completed; verifying actual charging")
                self.actuator.delivery_fault = False
                self.actuator.delivery_fault_at = None
                self.actuator.charging_since = None
                self.actuator.last = self.actuator.phase = None
                if self.actuator.goe_control:
                    self.actuator.goe_control.reset()
                self.power_since = None
                self.save()
            elif at >= attempted + timedelta(seconds=180):
                self.unresolved("Fresh connected charger inputs did not return after reboot")
        elif incident["status"] == "verifying":
            command = self.app.current_command
            charger = self.actuator.charger
            power_ok = (self.actuator.enabled and self.fresh() and self.app.observation.ev_power_kw >= .1
                        and command is not None and command.ev_kw > .1 and command.current_a > 0
                        and (charger is None or charger.error() is None and charger.code("force") == 2
                             and charger.number("current") == command.current_a and charger.waiting() is None))
            if power_ok:
                sample_at = charger.device_at if charger else self.app.observation.at
                assert sample_at is not None
                self.power_since = self.power_since or sample_at
                if (sample_at - self.power_since).total_seconds() >= 10:
                    incident.update(status="recovered", reason="Charging delivery verified after reboot",
                                    resolved_at=at.isoformat(), notification="not needed")
                    self.save()
                    return
            else:
                self.power_since = None
            if not self.actuator.enabled or at >= instant(incident["verification_started_at"]) + timedelta(minutes=5):
                self.unresolved("Charging recovery could not be verified; EV remains stopped")
        if incident["status"] == "unresolved" and (self.next_notification is None or at >= self.next_notification):
            self.next_notification = at + timedelta(seconds=60)
            detected = instant(incident["detected_at"]).astimezone(ZoneInfo(self.app.policy.timezone))
            message = (f"EV charging stopped. Fault detected {detected:%d %b %H:%M:%S %Z}. {incident['reason']}. "
                       f"Incident {incident['id']}; open EnergyManager for the five-minute diagnostic report.")
            delivered = await self.app.notifications.inform("ev-delivery:" + incident["id"],
                {"kind": "ev_delivery_fault", "message": message, "incident_id": incident["id"]})
            notification = ("delivered" if delivered else "retrying") if self.app.notifications.target else "phone not configured"
            if incident["notification"] != notification:
                incident["notification"] = notification
                self.save()

    def check_disabled_stop(self) -> None:
        control, charger = self.actuator.goe_control, self.actuator.charger
        if control is None or charger is None or control.disabled_stop_at is None or self.actuator.enabled:
            return
        at, sent = self.app.now(), control.disabled_stop_at
        if (charger.issue(at) is None and charger.device_at is not None and charger.device_at > sent
                and charger.code("force") == 1 and self.app.observation.ev_power_kw < .1
                and self.app.observation.at > sent):
            control.disabled_stop_at = None
        elif (at - sent).total_seconds() >= 30:
            control.disabled_stop_at = None
            command = Command(self.app.revision, None, at, 0, 0, self.app.observation.ev_phases, 0, 0,
                              "Hardware control disabled")
            control.fault(command, self.app.observation, "EV stop after disabling hardware could not be verified")

    def acknowledge(self, identity: str) -> None:
        if not self.current or self.current["id"] != identity or self.current["status"] != "unresolved":
            raise ValueError("Only the current unresolved EV incident can be acknowledged")
        if not self.fresh():
            raise ValueError("Fresh connected EV inputs are required before acknowledging recovery")
        if self.actuator.charger and self.actuator.charger.error():
            raise ValueError("The go-e fault must clear before acknowledging recovery")
        self.current.update(status="acknowledged", resolved_at=self.app.now().isoformat(),
                            reason="Acknowledged by user; normal planning and input guards still apply")
        self.save()
        self.actuator.delivery_fault = False
        self.actuator.delivery_fault_at = self.actuator.charging_since = None
        self.actuator.last = None
        if self.actuator.goe_control:
            self.actuator.goe_control.reset()
        self.app.changed("ev_fault_acknowledged", ev=True)

    async def sample_loop(self) -> None:
        while not self.app.shutdown:
            await self.sample()
            await asyncio.sleep(5)

    async def sample(self) -> None:
        ha = self.app.ha
        if ha is None:
            return
        entities = {ha.entities.get(key) for key in ("ev_soc", "connected", "ev_kw", "ev_phases")}
        entities.update(self.actuator.entities.get(key) for key in ("force", "phase", "current"))
        entities.update(self.diagnostics.values())
        if self.actuator.charger:
            entities.update(self.actuator.charger.entities.values())
        readings = {}
        raw_rows = {}

        async def read(entity: str) -> None:
            try:
                row = await ha.entity_state(entity)
                raw_rows[entity] = row
                state = str(row.get("state", "unknown"))
                readings[entity] = {"state": state[:256], "truncated": len(state) > 256,
                                    "reported_at": row.get("last_reported") or row.get("last_updated"),
                                    "unit": row.get("attributes", {}).get("unit_of_measurement")}
                if entity == self.actuator.entities.get("current"):
                    readings[entity]["limits"] = {key: row.get("attributes", {}).get(key) for key in ("min", "max")}
            except (aiohttp.ClientError, TimeoutError, RuntimeError, ValueError, TypeError, KeyError, AttributeError) as exc:
                readings[entity] = {"state": None, "error": type(exc).__name__}

        await asyncio.gather(*(read(entity) for entity in entities if entity))
        if self.actuator.charger:
            self.actuator.charger.update(raw_rows, self.app.now())
            self.update_limits()
        self.app.store.event("ev_diagnostics", {"at": self.app.now().isoformat(), "entities": readings})

    def update_limits(self) -> None:
        """Replan against the intersection; never increase the configured installation maximum."""
        charger = self.actuator.charger
        if charger is None or charger.issue(self.app.now()):
            return
        minimum, maximum = charger.limits(self.actuator.c.minimum_current_a, self.actuator.c.maximum_current_a)
        if minimum > maximum:
            return  # The EV dispatch guard reports a disjoint range without inventing capabilities.
        current = self.app.snapshot.capabilities
        if (minimum, maximum) != (current.minimum_current_a, current.maximum_current_a):
            effective = replace(current, minimum_current_a=minimum, maximum_current_a=maximum)
            self.app.snapshot = replace(self.app.snapshot, capabilities=effective)
            self.app.controller.c = effective
            self.app.changed("goe_current_limits", ev=True)


def incident_report(path: Path, incident: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Read a bounded T−5min to T+10min trace on a separate SQLite worker connection."""
    detected = instant(incident["detected_at"])
    start, end = detected - timedelta(minutes=5), min(now, detected + timedelta(minutes=10))
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    deadline = monotonic() + 5
    connection.set_progress_handler(lambda: int(monotonic() > deadline), 1000)
    try:
        rows = connection.execute("SELECT at,kind,body FROM events WHERE julianday(at) BETWEEN julianday(?) "
            "AND julianday(?) AND kind IN ('measurement','command_intent','commanded_dry_run',"
            "'actuator_service','actuator_error','ev_diagnostics','ev_incident') ORDER BY julianday(at),sequence LIMIT 10001",
            (start.isoformat(), end.isoformat()))
        events = []
        for at, kind, body in rows:
            if monotonic() > deadline:
                raise TimeoutError("EV incident archive read exceeded five seconds")
            events.append({"at": at, "kind": kind, "body": json.loads(body)})
        return {"incident": incident, "window_start": start.isoformat(), "window_end": end.isoformat(),
                "events": events[:10000], "truncated": len(events) > 10000,
                "note": "Only actually recorded data is included. Additional go-e states are available only after diagnostic collection was installed/configured."}
    except sqlite3.OperationalError as exc:
        if monotonic() > deadline:
            raise TimeoutError("EV incident archive read exceeded five seconds") from exc
        raise
    finally:
        connection.close()
