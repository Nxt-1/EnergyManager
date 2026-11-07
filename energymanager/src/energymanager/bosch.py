"""Mapped Home Connect feedback, automatic measured captures and explicit manual actions."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import aiohttp

from .domain import instant

if TYPE_CHECKING:
    from .appliance_profiles import ApplianceProfiles

# All installation entities are supplied by the user. Active program is a START control.
FIELDS = {
    "selected_program": ("Selected program (selection only)", ("select",)),
    "active_program": ("Active program (starts a cycle)", ("select",)),
    "operation": ("Operation state", ("sensor",)),
    "power": ("Appliance power switch", ("switch",)),
    "remote_control": ("Remote control permission", ("binary_sensor",)),
    "remote_start": ("Remote start permission", ("binary_sensor",)),
    "door": ("Door", ("binary_sensor", "sensor")),
    "delay": ("Native start delay (seconds, read only)", ("number",)),
    "finish": ("Reported finish time", ("sensor",)),
    "progress": ("Reported progress", ("sensor",)),
    "extra_dry": ("Extra dry", ("switch",)),
    "half_load": ("Half load", ("switch",)),
    "vario_speed": ("Vario speed+", ("switch",)),
}
UNAVAILABLE = {"unknown", "unavailable", "none", "", "None"}
IDLE = {"ready", "inactive", "finished"}


class BoschDishwasher:
    """Observe without control authority; only a user action can submit one HA write."""

    def __init__(self, profiles: ApplianceProfiles) -> None:
        self.profiles = profiles
        self.app = profiles.app
        self.readings: dict[str, Any] = {}
        self.at: str | None = None
        self.previous: tuple[str, str] | None = None
        self.capture: str | None = None
        self.seen_run = False
        self.capture_error: str | None = None
        self.lock = asyncio.Lock()
        self.last_command: dict[str, Any] | None = self.app.store.get(f"bosch_command_{profiles.mode}")

    @property
    def config(self) -> dict[str, str]:
        return self.profiles.settings.get("bosch", {})

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("operation") and self.config.get("active_program") and
                    self.profiles.settings["machines"]["dishwasher"]["entity_id"])

    def state(self) -> dict[str, Any]:
        return {"config": self.config, "fields": {key: {"label": label, "domains": domains}
                for key, (label, domains) in FIELDS.items()}, "enabled": self.enabled,
                "at": self.at, "readings": self.readings, "capture_error": self.capture_error,
                "command": self.last_command, "control_error": self.authority_reason()}

    def authority_reason(self) -> str | None:
        if self.app.demo or self.app.ha is None:
            return "Manual control requires configured Home Assistant mode"
        hardware = getattr(self.app, "hardware", None)
        if hardware is None or not hardware.state()["enabled"] or not self.app.policy.control_enabled:
            return "Enable EnergyManager hardware control before sending appliance commands"
        if hardware.lock.locked():
            return "Hardware control is changing"
        return None

    def value(self, key: str) -> str | None:
        return self.readings.get(key, {}).get("state")

    async def read(self) -> None:
        from .appliance_profiles import power_reading

        ha = self.app.ha
        if ha is None or self.app.demo:
            return

        async def one(key: str, entity: str) -> tuple[str, dict[str, Any]]:
            if not entity:
                return key, {"state": None, "error": "Not mapped"}
            try:
                raw = await ha.entity_state(entity)
                if not isinstance(raw, dict):
                    raise ValueError("Invalid HA state")
                value = str(raw.get("state", ""))
                attrs = raw.get("attributes") or {}
                if not isinstance(attrs, dict):
                    raise ValueError("Invalid HA attributes")
                options = attrs.get("options", [])
                if key == "active_program":
                    if (not isinstance(options, list) or len(options) > 100
                            or any(not self.valid_program(option) for option in options)):
                        raise ValueError("Invalid active-program options")
                elif not isinstance(options, list):
                    options = []
                # Home Connect can list startable programs while no program is active.
                unknown_active = key == "active_program" and value == "unknown"
                if len(value) > 200 or (value in UNAVAILABLE and not unknown_active):
                    raise ValueError("Unavailable")
                power = {"power_w": power_reading(raw)} if key == "meter" else {}
                return key, {**power, "state": None if unknown_active else value, "entity_id": entity, "error": None,
                             "options": [item for item in options[:100] if self.valid_program(item)],
                             "unit": str(attrs.get("unit_of_measurement", ""))[:30]}
            except (aiohttp.ClientError, TimeoutError, ValueError, RuntimeError) as exc:
                return key, {"state": None, "entity_id": entity, "error": f"Read failed: {type(exc).__name__}"}
        config = dict(self.config)
        meter = self.profiles.settings["machines"]["dishwasher"]["entity_id"]
        entities = {**{key: config.get(key, "") for key in FIELDS}, "meter": meter}
        readings = dict(await asyncio.gather(*(one(key, entity) for key, entity in entities.items())))
        # Mapping edits during a read cannot adopt the old appliance's feedback.
        if config != self.config or meter != self.profiles.settings["machines"]["dishwasher"]["entity_id"]:
            return
        self.readings, self.at = readings, self.app.now().isoformat()
        programs = set(self.readings["selected_program"].get("options", []))
        actual = self.value("active_program")
        if actual and self.valid_program(actual):
            programs.add(actual)
        known = self.profiles.settings.get("bosch_programs", {})
        if programs - known.keys():
            self.profiles._persist_settings({**self.profiles.settings,
                                            "bosch_programs": {**known, **{item: item for item in sorted(programs)}}})
        self.confirm_command()

    @staticmethod
    def valid_program(value: Any) -> bool:
        return isinstance(value, str) and 0 < len(value) <= 200 and value not in UNAVAILABLE and "/" not in value

    async def poll(self) -> None:
        if self.app.demo or self.app.ha is None or not self.enabled:
            return
        await self.read()
        await self.capture_tick()

    async def capture_tick(self) -> None:
        from .appliance_profiles import MAX_GAP_SECONDS

        ha = self.app.ha
        if ha is None:
            return
        now = self.app.now()
        operation, program = self.value("operation"), self.value("active_program")
        prior = self.previous
        if operation is None:
            if self.capture:
                self.profiles.interrupt(self.capture, "Bosch operation feedback unavailable")
                self.profiles.ingest(self.capture, now, None, "Bosch operation feedback unavailable")
            self.previous = None
            return
        if self.capture:
            rows = self.profiles._rows("id=?", (self.capture,))
            if not rows or rows[0]["status"] != "recording":
                self.capture = None  # User finished/deleted it; do not recapture the same run.
            elif program and program != rows[0]["program"] and operation == "run":
                self.profiles.end_automatic(self.capture, "Program changed during execution")
                self.capture, self.seen_run = None, False
                prior = None
        if operation == "run" and not self.seen_run:
            if not program or not self.valid_program(program):
                self.capture_error = "Running program unavailable; cannot assign this capture"
            else:
                observed_start = bool(prior and prior[0] in IDLE | {"delayedstart"} and
                                      0 <= (now - instant(prior[1])).total_seconds() <= MAX_GAP_SECONDS)
                self.capture = self.profiles.begin_automatic(program, observed_start)
                self.seen_run = True
                self.capture_error = None
        if self.capture:
            meter = self.readings.get("meter", {})
            self.profiles.ingest(self.capture, self.app.now(), meter.get("power_w"), meter.get("error"))
            if operation != "run":
                self.profiles.end_automatic(self.capture, None if operation == "finished" else
                                            f"Execution ended in {operation}, not finished")
                self.capture = None
        if operation != "run":
            self.seen_run = False
        self.previous = operation, now.isoformat()

    def confirm_command(self) -> None:
        command = self.last_command
        if not command or command["outcome"] not in ("pending", "unconfirmed"):
            return
        key, expected = command["feedback"], command["expected"]
        confirmed = self.value(key) == expected
        if command["action"] == "start":
            confirmed = confirmed and self.value("active_program") == command["program"]
        if confirmed:
            command = {**command, "outcome": "confirmed", "message": "Confirmed by appliance feedback"}
        elif command["outcome"] == "pending" and (self.app.now() - instant(command["at"])).total_seconds() >= 30:
            command = {**command, "outcome": "unconfirmed", "message": "No confirming feedback within 30 seconds; check the appliance"}
        else:
            return
        self.save_command(command)

    def save_command(self, command: dict[str, Any]) -> None:
        self.app.store.put(f"bosch_command_{self.profiles.mode}", command)
        self.last_command = command

    async def command(self, body: dict[str, Any]) -> dict[str, Any]:
        from .appliance_profiles import number

        if self.lock.locked():
            raise ValueError("An appliance command is already in progress")
        async with self.lock:
            reason = self.authority_reason()
            if reason:
                raise ValueError(reason)
            hardware = self.app.hardware
            assert hardware is not None
            epoch = hardware.epoch
            config = dict(self.config)
            if not self.enabled:
                raise ValueError("Map Bosch operation, active program and dedicated recording power first")
            await self.read()
            action = body.get("command")
            if self.value("remote_control") != "on":
                raise ValueError("Remote control permission is unavailable or off")
            if self.last_command and self.last_command["outcome"] == "pending":
                raise ValueError("Await appliance feedback before another command")
            operation = self.value("operation")
            key, expected, service, domain = "", "", "", ""
            data: dict[str, Any] = {}
            if action == "power_on":
                if self.value("power") != "off":
                    raise ValueError("Power on requires confirmed off feedback")
                key, expected, domain, service = "power", "on", "switch", "turn_on"
            else:
                if operation not in IDLE or self.value("power") != "on":
                    raise ValueError("Appliance must be powered on and idle; delayed/running/unknown states are blocked")
                if action in ("select", "start"):
                    program = body.get("program")
                    options = self.readings.get("selected_program", {}).get("options", [])
                    if not self.valid_program(program) or program not in options:
                        raise ValueError("Choose an available HA program")
                    assert isinstance(program, str)
                    key, expected, domain, service = "selected_program", program, "select", "select_option"
                    data["option"] = program
                    if action == "start":
                        if self.readings.get("meter", {}).get("power_w") is None:
                            raise ValueError("Start now and record requires an available dedicated W/kW measurement")
                        if self.value("selected_program") != program:
                            raise ValueError("Select the program and wait for its feedback before starting")
                        if self.value("door") not in ("off", "closed") or self.value("remote_start") != "on":
                            raise ValueError("Start requires a confirmed closed door and remote start permission")
                        delay = self.value("delay")
                        try:
                            seconds = float(delay) if delay is not None else -1
                        except ValueError:
                            seconds = -1
                        number(seconds, "Native delay seconds", 0, 86400)
                        if seconds != 0 or self.readings["delay"].get("unit") not in ("s", "seconds"):
                            raise ValueError("Clear the native delay at the appliance; Start now requires a confirmed zero-second delay")
                        if program not in self.readings.get("active_program", {}).get("options", []):
                            raise ValueError("Program is not available on the HA active-program start control")
                        key, expected = "active_program", program
                elif action == "modifier":
                    modifier = body.get("modifier", "")
                    key = modifier if isinstance(modifier, str) else ""
                    if key not in ("extra_dry", "half_load", "vario_speed") or type(body.get("enabled")) is not bool:
                        raise ValueError("Choose a modifier and an explicit on/off value")
                    if self.value(key) not in ("on", "off"):
                        raise ValueError("Modifier unavailable")
                    expected = "on" if body["enabled"] else "off"
                    domain, service = "switch", "turn_" + expected
                else:
                    raise ValueError("Unknown Bosch command")
            entity = self.config.get(key)
            if not entity:
                raise ValueError("Command entity is not mapped")
            reason = self.authority_reason()
            if reason or hardware.epoch != epoch or config != self.config:
                raise ValueError(reason or "Hardware authority or Bosch mappings changed while reading the appliance")
            command = {"action": action, "at": self.app.now().isoformat(), "program": body.get("program"),
                       "feedback": "operation" if action == "start" else key,
                       "expected": "run" if action == "start" else expected,
                       "outcome": "pending", "message": "Submitted to HA; awaiting appliance feedback"}
            self.save_command(command)  # Durable before sending; never replay a request on restart.
            ha = self.app.ha
            assert ha is not None
            try:
                await ha.service(domain, service, {"entity_id": entity, **data})
            except (aiohttp.ClientError, TimeoutError, RuntimeError) as exc:
                self.save_command({**command, "outcome": "failed", "message": "Command failed or outcome unknown; check the appliance"})
                raise ValueError("Bosch command failed or its outcome is unknown; check the appliance") from exc
            return self.state()
