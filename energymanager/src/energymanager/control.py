"""Fast independent control, quarter-hour headroom and guarded actuator translation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol
from collections.abc import Callable
import asyncio

from .domain import Capabilities, Observation, Policy, instant


@dataclass(frozen=True)
class Command:
    generation: int
    plan_id: str | None
    at: datetime
    ev_kw: float
    ess_kw: float  # Positive supplies AC, negative charges from AC.
    phases: int
    current_a: int
    peak_limit_kw: float
    reason: str
    replan: bool = False


class FastControl:
    def __init__(self, capabilities: Capabilities, policy: Policy) -> None:
        self.c = capabilities
        self.p = policy
        self.deviation_since: datetime | None = None
        self.input_deviation_since: datetime | None = None
        self.last_ev_kw = 0.0
        self.last_tick: datetime | None = None
        self.last_meter_at: datetime | None = None
        self.estimated_quarter_kwh = 0.0
        self.last_import_kw = 0.0

    def tick(
        self,
        observation: Observation,
        at: datetime,
        plan: dict[str, Any] | None,
        generation: int,
        ev_valid: bool = True,
        ess_valid: bool = True,
        conditional_valid: bool = True,
    ) -> Command:
        c, p, o = self.c, self.p, observation
        baseline = max(o.monthly_peak_kw, p.billing_floor_kw)
        limit = baseline
        fresh = (at - o.at).total_seconds() <= p.measurement_max_age_seconds and o.quality not in (
            "unknown",
            "stale",
        )
        if not fresh:
            return Command(
                generation,
                None,
                at,
                0,
                0,
                o.ev_phases,
                0,
                baseline,
                "Measurements stale; new commands restricted",
                True,
            )
        position = (
            next(
                (t for t, i in enumerate(plan["intervals"]) if instant(i["start"]) <= at < instant(i["end"])),
                None,
            )
            if plan
            else None
        )
        planned_ev = planned_ess = 0.0
        floor = c.ess_min_kwh
        phases = o.ev_phases
        conditional = False
        dc_reserved = 0.0
        protected_solar = 0.0
        sustained_deviation = False
        if plan and position is not None:
            f = plan["flows"]
            eligible = [
                g
                for g in plan["goals"]
                if instant(g["deadline"]) > at
                and o.ev_kwh
                < g["target_kwh"]
                + sum(
                    i["withdrawal_kwh"]
                    for i in plan["intervals"]
                    if i["withdrawal_kwh"] > 0 and at <= instant(i["start"]) < instant(g["deadline"])
                )
                - 0.02
            ]
            planned_ev = (
                (f["pv_ev"][position] + f["grid_ev"][position] + f["solar_dis_ev"][position])
                if ev_valid
                else 0
            )
            planned_ess = (
                (
                    f["solar_dis_ev"][position]
                    + f["solar_dis_house"][position]
                    + f["grid_dis_house"][position]
                    - f["pv_store"][position]
                    - f["grid_store"][position]
                )
                if ess_valid
                else 0
            )
            if f["one"][position] + f["three"][position] > 0.5:
                phases = 3 if f["three"][position] > 0.5 else 1
            else:
                upcoming = next(
                    (
                        t
                        for t in range(position + 1, len(plan["intervals"]))
                        if instant(plan["intervals"][t]["start"]) <= at + timedelta(seconds=15)
                        and f["one"][t] + f["three"][t] > 0.5
                    ),
                    None,
                )
                if upcoming is not None:
                    phases = 3 if f["three"][upcoming] > 0.5 else 1
            allocations = plan.get("reservations", [])
            if allocations:
                after = allocations[position + 1]
                protected_solar = after["solar_house_kwh"] if ess_valid else 0
                if ev_valid and (conditional_valid or eligible):
                    protected_solar += after["solar_ev_kwh"]
                floor += protected_solar + (after["grid_house_kwh"] if ess_valid else 0)
            interval = plan["intervals"][position]
            net_deviation = (o.house_kw - o.pv_ac_kw) - (interval["house_kw"] - interval["pv_ac_kw"])
            if abs(net_deviation) > 0.5 or abs(o.pv_dc_kw - interval["pv_dc_kw"]) > 0.5:
                self.input_deviation_since = self.input_deviation_since or at
                sustained_deviation = (
                    at - self.input_deviation_since
                ).total_seconds() >= p.sustained_deviation_seconds
            else:
                self.input_deviation_since = None
            conditional = any(r["kind"] == "joint_capture" for r in plan["reasons"])
            dc_reserved = f["dc_store"][position]
            if o.ev_kwh >= f["ev_energy"][position + 1] + 0.02:
                planned_ev = 0.0
            forecast_fresh = (
                at - instant(plan.get("forecast_at", at.isoformat()))
            ).total_seconds() <= p.forecast_max_age_seconds
            if (not forecast_fresh or not conditional_valid) and not eligible:
                planned_ev = 0.0
            if f["grid_ev"][position] > 1e-5:
                limit = max(
                    [baseline, p.automatic_peak_kw]
                    + [
                        g["approved_peak_kw"] or baseline
                        for g in eligible
                        if g["approval_state"] == "granted" and g["approval_revision"] == g["revision"]
                    ]
                )
            if f["grid_store"][position] > 1e-5 and any(
                r["kind"] == "peak_precharge" for r in plan["reasons"]
            ):
                ess_limit = max(
                    [baseline, p.automatic_peak_kw]
                    + [
                        g["peak_kw"]
                        for g in plan.get("peak_permissions", [])
                        if g["state"] == "granted" and at < instant(g["deadline"]) <= at + timedelta(hours=24)
                    ]
                )
                limit = min(limit, ess_limit) if f["grid_ev"][position] > 1e-5 else ess_limit
        quarter_end = at.replace(minute=at.minute // 15 * 15, second=0, microsecond=0) + timedelta(minutes=15)
        period_h = max(p.control_period_seconds, 1) / 3600
        quarter_start = quarter_end - timedelta(minutes=15)
        if self.last_meter_at != o.at:
            self.estimated_quarter_kwh = o.quarter_import_kwh if o.at >= quarter_start else 0.0
            self.last_meter_at = o.at
        elif self.last_tick is not None:
            elapsed = max(0, (at - max(self.last_tick, quarter_start)).total_seconds()) / 3600
            if self.last_tick < quarter_start:
                self.estimated_quarter_kwh = 0.0
            self.estimated_quarter_kwh += self.last_import_kw * elapsed
        future_reservation = 0.0
        if plan and position is not None:
            after_response = at + timedelta(hours=period_h)
            for t in range(position, len(plan["intervals"])):
                interval = plan["intervals"][t]
                left, right = (
                    max(after_response, instant(interval["start"])),
                    min(quarter_end, instant(interval["end"])),
                )
                if left >= quarter_end:
                    break
                if right > left:
                    future_import = sum(plan["flows"][name][t] for name in ("grid_house", "grid_store"))
                    if ev_valid:
                        future_import += plan["flows"]["grid_ev"][t]
                    future_reservation += future_import * (right - left).total_seconds() / 3600
        else:
            future_reservation = max(0, o.house_kw - o.pv_ac_kw) * max(
                0, (quarter_end - at).total_seconds() / 3600 - period_h
            )
        # Budget energy over the billing quarter; a permitted short pulse is not an instantaneous violation.
        headroom = max(0, (limit * 0.25 - self.estimated_quarter_kwh - future_reservation) / period_h)
        direct_dc_ac = min(c.ac_discharge_kw, max(0, o.pv_dc_kw - dc_reserved) * c.ac_discharge_efficiency)
        available_discharge = min(
            c.ac_discharge_kw,
            direct_dc_ac + c.battery_discharge_kw * c.ac_discharge_efficiency,
            direct_dc_ac + max(0.0, o.ess_kwh - floor) * c.ac_discharge_efficiency / period_h,
        )
        net_house = o.house_kw - o.pv_ac_kw
        # Basic ESS mode remains useful without a plan; no forecast-driven grid precharge.
        ev = planned_ev if o.connected and ev_valid else 0.0
        if not o.ev_state_known:
            ev = 0.0
        if (
            plan
            and position is not None
            and ev_valid
            and conditional_valid
            and o.connected
            and o.ev_state_known
        ):
            # Only explicitly scheduled conditional work can advance, after ESS absorbs the surplus.
            if (
                at - instant(plan.get("forecast_at", at.isoformat()))
            ).total_seconds() <= p.forecast_max_age_seconds:
                charge_room_kw = min(
                    c.ac_charge_kw, max(0, c.ess_capacity_kwh - o.ess_kwh) / c.ac_charge_efficiency / period_h
                )
                residual_pv = max(0, o.pv_ac_kw - o.house_kw - charge_room_kw)
                task = next(
                    (
                        task
                        for task in plan.get("conditional_tasks", [])
                        if at < instant(task["deadline"]) <= at + timedelta(hours=24)
                        and task["target_ev_kwh"] > o.ev_kwh + 0.02
                        and plan["intervals"][position]["available"]
                    ),
                    None,
                )
                phase_preparation = any(
                    instant(plan["intervals"][t]["start"]) <= at + timedelta(seconds=15)
                    and (
                        (f["three"][t] > 0.5 and o.ev_phases != 3) or (f["one"][t] > 0.5 and o.ev_phases != 1)
                    )
                    for t in range(position, min(position + 3, len(plan["intervals"])))
                )
                worthwhile = task and (
                    self.last_ev_kw > 0
                    or (instant(task["deadline"]) - at).total_seconds() >= 300
                    and task["quantity_kwh"]
                    >= c.minimum_current_a * c.voltage * min(c.phases) / 1000 * c.ev_efficiency / 12
                )
                if task and worthwhile and not phase_preparation:
                    ev = max(
                        ev, min(residual_pv, (task["target_ev_kwh"] - o.ev_kwh) / c.ev_efficiency / period_h)
                    )
                    conditional = True
        desired_ess = net_house + o.ev_power_kw
        if desired_ess < 0:
            charge_headroom = min(
                c.ac_charge_kw,
                max(0, c.ess_capacity_kwh - o.ess_kwh) / c.ac_charge_efficiency / period_h,
                max(0, c.battery_charge_kw - o.pv_dc_kw * c.dc_efficiency) / c.ac_charge_efficiency,
            )
            ess = -min(-desired_ess, charge_headroom)
        else:
            ess = min(max(0.0, desired_ess), available_discharge)
        basic_ess = ess
        # Honour scheduled AC charging before considering EV advancement.
        if planned_ess < 0 and position is not None and ess_valid:
            permitted_grid_charge = bool(plan and plan["flows"]["grid_store"][position] > 1e-5)
            available_source = (
                max(0.0, -net_house - ev) if not permitted_grid_charge else max(0, headroom - net_house - ev)
            )
            ess = -min(
                -planned_ess,
                c.ac_charge_kw,
                available_source,
                max(0, c.ess_capacity_kwh - o.ess_kwh) / c.ac_charge_efficiency / period_h,
                max(0, c.battery_charge_kw - min(o.pv_dc_kw, c.dc_charge_kw) * c.dc_efficiency)
                / c.ac_charge_efficiency,
            )
        predicted_import = net_house + ev - ess
        emergency = predicted_import > headroom + 0.03
        if emergency:
            # Protective changes bypass smoothing and may stop immediately.
            ev = max(0, ev - (predicted_import - headroom))
            ess = min(max(0, net_house + ev - headroom), available_discharge)
        elif abs(ev - self.last_ev_kw) > 0.5 and self.last_ev_kw > 0:
            if self.deviation_since is None:
                self.deviation_since = at
            if (at - self.deviation_since).total_seconds() < p.sustained_deviation_seconds:
                ev = min(self.last_ev_kw, max(0, headroom - net_house + ess))
        else:
            self.deviation_since = None
        # An optional task cannot purchase direct grid energy during a sustained source loss.
        if plan and position is not None and plan["flows"]["grid_ev"][position] < 1e-5:
            eligible_discharge = min(
                available_discharge,
                max(0, o.ess_kwh - c.ess_min_kwh - o.ess_grid_kwh - protected_solar)
                * c.ac_discharge_efficiency
                / period_h,
            )
            solar_source = o.pv_ac_kw + direct_dc_ac + eligible_discharge
            ev = min(ev, max(0, solar_source - (0 if conditional else o.house_kw)))
        if not o.ev_phase_known:
            ev = 0.0
        amps = min(c.maximum_current_a, math.floor((ev + 1e-9) * 1000 / (c.voltage * phases)))
        if amps < c.minimum_current_a:
            amps = 0
        ev = amps * phases * c.voltage / 1000
        # Recompute ESS after EV reductions; never intentionally export stored energy.
        if ess > 0:
            ess = min(ess, max(0, net_house + o.ev_power_kw))
        if not ess_valid:
            ess = basic_ess
        self.last_ev_kw = ev
        self.last_tick = at
        self.last_import_kw = max(0, net_house + ev - ess)
        reason = (
            "Charger phase information unavailable; EV paused, ESS balancing continues"
            if not o.ev_phase_known
            else
            "Quarter-hour peak protection"
            if emergency
            else "Accepted schedule and measured balancing"
            if position is not None
            else "Basic ESS balancing; no EV instruction"
        )
        return Command(
            generation,
            plan["id"] if plan else None,
            at,
            ev,
            ess,
            phases,
            amps,
            limit,
            reason,
            emergency or sustained_deviation,
        )


class ServiceClient(Protocol):
    async def service(self, domain: str, service: str, data: dict[str, Any]) -> None: ...


class Actuator(Protocol):
    async def apply(self, command: Command, generation: int, observation: Observation) -> None: ...


class FakeActuator:
    def __init__(self) -> None:
        self.commands: list[Command] = []

    async def apply(self, command: Command, generation: int, observation: Observation) -> None:
        if command.generation == generation:
            self.commands.append(command)


class GuardedActuator:
    """go-e stop/confirm/dwell sequencing and Victron setpoint sign, verified on fake HA."""

    def __init__(
        self,
        client: ServiceClient,
        entities: dict[str, str],
        capabilities: Capabilities,
        enabled: bool = False,
        generation: Callable[[], int] | None = None,
        on_write: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.client, self.entities, self.c, self.enabled = client, entities, capabilities, enabled
        self.generation = generation
        self.on_write = on_write
        self.command_generation = 0
        self.command_plan: str | None = None
        self.lock = asyncio.Lock()
        self.phase: int | None = None
        self.target_phase: int | None = None
        self.awaiting_phase: int | None = None
        self.stopped_at: datetime | None = None
        self.zero_since: datetime | None = None
        self.switched_at: datetime | None = None
        self.failures = 0
        self.fault_until: datetime | None = None
        self.last: tuple[int, int, int] | None = None
        self.charging_since: datetime | None = None
        self.delivery_fault = False

    async def write(self, domain: str, service: str, key: str, value_key: str, value: Any) -> None:
        if not self.enabled or self.generation and self.generation() != self.command_generation:
            raise StaleDispatch()
        await self.client.service(domain, service, {"entity_id": self.entities[key], value_key: value})
        if self.on_write:
            self.on_write(
                {
                    "generation": self.command_generation,
                    "plan_id": self.command_plan,
                    "domain": domain,
                    "service": service,
                    "entity_id": self.entities[key],
                    value_key: value,
                }
            )

    async def stop(self, generation: int) -> None:
        """Stop EV charging and clear the ESS setpoint after ordinary writes are revoked."""
        self.enabled = False
        errors = []
        async with self.lock:
            for domain, service, key, value_key, value in (
                ("select", "select_option", "force", "option", "1"),
                ("number", "set_value", "ess_setpoint", "value", 0),
            ):
                try:
                    await self.client.service(domain, service, {"entity_id": self.entities[key], value_key: value})
                    if self.on_write:
                        self.on_write({"generation": generation, "reason": "Hardware control disabled",
                                       "entity_id": self.entities[key], value_key: value})
                except (OSError, RuntimeError, KeyError) as exc:
                    errors.append(str(exc))
            self.last = None
            self.target_phase = self.awaiting_phase = None
            self.stopped_at = self.zero_since = None
        if errors:
            raise RuntimeError("Hardware control is off, but a stop command failed: " + "; ".join(errors))

    async def apply(self, command: Command, generation: int, observation: Observation) -> None:
        async with self.lock:
            await self.apply_serial(command, generation, observation)

    async def apply_serial(self, command: Command, generation: int, observation: Observation) -> None:
        if not self.enabled or command.generation != generation:
            return
        self.command_generation, self.command_plan = command.generation, command.plan_id
        if not all(self.entities.get(name) for name in ("force", "phase", "current", "ess_setpoint")):
            raise ValueError("Incomplete actuator mapping")
        if self.fault_until and command.at < self.fault_until and command.current_a:
            return
        if not observation.ev_phase_known:
            self.phase = None
        elif self.phase is None:
            self.phase = observation.ev_phases
        try:
            # ESS remains responsive while EV phase changes or a delivery fault block charging.
            await self.write(
                "number", "set_value", "ess_setpoint", "value", round(-command.ess_kw * 1000 / 10) * 10
            )
            if self.awaiting_phase is not None:
                if (observation.ev_phase_known and observation.ev_phases == self.awaiting_phase
                        and self.switched_at is not None and observation.at > self.switched_at):
                    self.phase = self.awaiting_phase
                    self.awaiting_phase = None
                else:
                    await self.write("select", "select_option", "force", "option", "1")
                    return
            if (observation.ev_phase_known and observation.ev_phase_source == "goe_selector"
                    and observation.ev_phases != self.phase):
                self.phase = observation.ev_phases
                self.last = None
            if (
                command.ev_kw > 0.1
                and observation.connected
                and observation.ev_power_kw < 0.1
                and command.phases == self.phase
                and self.target_phase is None
            ):
                self.charging_since = self.charging_since or command.at
                if (command.at - self.charging_since).total_seconds() >= 90:
                    self.delivery_fault = True
            else:
                self.charging_since = None
            if self.delivery_fault:
                await self.write("select", "select_option", "force", "option", "1")
                return
            if command.phases != self.phase:
                if self.target_phase != command.phases:
                    self.target_phase = command.phases
                    self.stopped_at = self.zero_since = None
                self.last = None
                await self.write("select", "select_option", "force", "option", "1")
                self.stopped_at = self.stopped_at or command.at
                if observation.ev_power_kw < 0.1:
                    self.zero_since = self.zero_since or command.at
                else:
                    self.zero_since = None
                ready = (
                    (command.at - self.stopped_at).total_seconds() >= 10
                    and self.zero_since
                    and (command.at - self.zero_since).total_seconds() >= 3
                    and (
                        self.switched_at is None
                        or (command.at - self.switched_at).total_seconds() >= self.c.phase_dwell_seconds
                    )
                )
                if ready:
                    await self.write(
                        "select", "select_option", "phase", "option", "2" if command.phases == 3 else "1"
                    )
                    self.switched_at = command.at
                    self.awaiting_phase = command.phases
                    self.stopped_at = self.zero_since = None
                    self.target_phase = None
                    self.last = None
                return
            self.target_phase = None
            self.stopped_at = self.zero_since = None
            target = (command.current_a, command.phases, round(-command.ess_kw * 100))
            if target == self.last:
                return
            if command.current_a and observation.connected:
                await self.write("number", "set_value", "current", "value", command.current_a)
                await self.write("select", "select_option", "force", "option", "2")
            else:
                await self.write("select", "select_option", "force", "option", "1")
            self.last, self.failures = target, 0
        except StaleDispatch:
            self.last = None
            return
        except (OSError, RuntimeError):
            self.failures += 1
            if self.failures >= 3:
                self.fault_until = command.at + timedelta(seconds=10)
            raise


class StaleDispatch(RuntimeError):
    """An event revoked a command between asynchronous hardware writes."""
