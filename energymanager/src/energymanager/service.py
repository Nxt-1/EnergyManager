"""Event-loop owner of state, isolated planning, approval revisions and atomic adoption."""

from __future__ import annotations

import asyncio
import aiohttp
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from multiprocessing import get_context
from time import monotonic
from typing import Any
from uuid import uuid4

from . import __version__
from .control import Actuator, Command, FakeActuator, FastControl
from .adapters import HomeAssistantAdapter, JsonForecastAdapter
from .domain import Goal, Observation, PeakPermission, Policy, Snapshot, json_data
from .publication import rebase
from .demo_plant import DemoPlant
from .forecasts import demo_snapshot
from .planner import plan_snapshot
from .store import Store
from .notifications import Notifications
from .validation import validate
from .worker import watch_parent


class Application:
    def __init__(
        self,
        store: Store,
        *,
        policy: Policy | None = None,
        snapshot: Snapshot | None = None,
        demo: bool = True,
        ha: HomeAssistantAdapter | None = None,
        forecast: JsonForecastAdapter | None = None,
    ) -> None:
        self.store, self.demo = store, demo
        self.ha, self.forecast = ha, forecast
        self.forecast_data: dict[str, Any] | None = None
        self.input_task: asyncio.Task[None] | None = None
        self.policy = policy or Policy()
        self.revision = int(store.get("revision", 1))
        self.goals = tuple(Goal.from_dict(g) for g in store.get("goals", []))
        self.snapshot = snapshot or demo_snapshot(
            policy=self.policy, goals=self.goals or None, revision=self.revision
        )
        if not self.goals:
            self.goals = tuple(g for g in self.snapshot.goals if g.kind != "daily")
        self.observation = self.snapshot.observation
        self.demo_season = "winter" if "winter" in self.snapshot.forecast_id else "mixed"
        self.demo_plant = DemoPlant(self.snapshot)
        self.current_command: Command | None = None
        self.accepted: dict[str, Any] | None = store.get("accepted")
        self.ev_valid = False  # Restart must reconcile measured state before using recorded commands.
        self.ess_valid = False
        self.conditional_valid = False
        self.protective_tasks: set[asyncio.Task[None]] = set()
        self.status = "starting"
        self.error: str | None = None
        self.controller = FastControl(self.snapshot.capabilities, self.snapshot.policy)
        self.actuator: Actuator = FakeActuator()
        self.worker: ProcessPoolExecutor | None = None
        self.planning: asyncio.Task[None] | None = None
        self.control_task: asyncio.Task[None] | None = None
        self.requested = asyncio.Event()
        self.shutdown = False
        self.last_command: dict[str, Any] | None = None
        self.response_seconds: list[float] = []
        self.observed: list[dict[str, Any]] = store.get("observed", [])
        self.started = monotonic()
        self.demo_origin = self.observation.at
        self.last_control_replan: datetime | None = None
        self.notifications = Notifications(store)

    def now(self) -> datetime:
        return (
            self.demo_origin + timedelta(seconds=monotonic() - self.started)
            if self.demo
            else datetime.now(UTC)
        )

    async def start(self) -> None:
        self.worker = ProcessPoolExecutor(
            max_workers=1, mp_context=get_context("spawn"), initializer=watch_parent
        )
        self.control_task = asyncio.create_task(self.control_loop())
        self.planning = asyncio.create_task(self.planning_loop())
        if self.ha and self.forecast:
            await self.ha.__aenter__()
            self.observation = replace(self.observation, quality="unknown")
            self.input_task = asyncio.create_task(self.input_loop())
        else:
            self.requested.set()

    async def close(self) -> None:
        self.shutdown = True
        self.revision += 1
        at = self.now()
        await self.actuator.apply(
            Command(
                self.revision,
                None,
                at,
                0,
                0,
                self.observation.ev_phases,
                0,
                self.policy.billing_floor_kw,
                "Application shutdown",
            ),
            self.revision,
            self.observation,
        )
        for task in (self.control_task, self.planning, self.input_task, *self.protective_tasks):
            if task:
                task.cancel()
        await asyncio.gather(
            *(t for t in (self.control_task, self.planning, self.input_task, *self.protective_tasks) if t),
            return_exceptions=True,
        )
        if self.ha:
            await self.ha.__aexit__()
        self.store.put("observed", self.observed)
        if self.worker:
            self.worker.shutdown(wait=False, cancel_futures=True)

    def invalidate(self, kind: str, *, ev: bool, ess: bool) -> None:
        if ev:
            self.ev_valid = False
        if ess:
            self.ess_valid = False
        self.store.event("invalidation", {"reason": kind, "ev": ev, "ess": ess, "revision": self.revision})

    def changed(self, kind: str, *, ev: bool = False, ess: bool = False) -> None:
        self.revision += 1
        self.store.put("revision", self.revision)
        self.invalidate(kind, ev=ev, ess=ess)
        self.requested.set()
        if ev or ess:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return  # Synchronous goal editing before the service is started.
            task = loop.create_task(self.protect(kind))
            self.protective_tasks.add(task)
            task.add_done_callback(self.protective_tasks.discard)

    async def protect(self, reason: str) -> None:
        at = self.now()
        command = self.controller.tick(
            self.observation,
            at,
            self.accepted,
            self.revision,
            self.ev_valid,
            self.ess_valid,
            self.conditional_valid,
        )
        command = replace(command, reason=f"Affected instruction revoked: {reason}")
        try:
            await self.actuator.apply(command, self.revision, self.observation)
        except (OSError, RuntimeError) as exc:
            self.store.event("protective_dispatch_error", {"reason": str(exc)})
        if command.generation == self.revision:
            self.current_command = command
            self.last_command = json_data(command)
            self.store.event("protective_command", command)

    def build_snapshot(self) -> Snapshot:
        if self.forecast_data is not None:
            prepared = JsonForecastAdapter.snapshot(
                self.forecast_data,
                self.observation,
                self.snapshot.capabilities,
                self.policy,
                self.goals,
                self.revision,
                self.now(),
            )
        elif self.demo:
            prepared = demo_snapshot(
                season=self.demo_season,
                start=self.now(),
                goals=self.goals,
                revision=self.revision,
                policy=self.policy,
            )
        else:
            prepared = replace(
                self.snapshot, id=uuid4().hex, revision=self.revision, observation=self.observation
            )
        daily_approvals = self.store.get("daily_approvals", {})
        goals = tuple(
            Goal.from_dict(daily_approvals[g.id])
            if g.id in daily_approvals and daily_approvals[g.id]["revision"] == g.revision
            else g
            for g in prepared.goals
        )
        hold_until = prepared.intervals[0].start + timedelta(seconds=self.policy.planning_budget_seconds + 15)
        intervals = []
        for interval in prepared.intervals:
            if interval.start < hold_until < interval.end:
                intervals += [
                    replace(interval, end=hold_until),
                    replace(interval, start=hold_until, withdrawal_kwh=0.0),
                ]
            else:
                intervals.append(interval)
        return replace(
            prepared,
            observation=self.observation,
            goals=goals,
            intervals=tuple(intervals),
            hold_until=hold_until,
            hold_ev_kw=self.last_command["ev_kw"] if self.ev_valid and self.last_command else 0,
            hold_phases=self.observation.ev_phases,
            hold_plan_id=self.accepted["id"] if self.accepted else None,
            peak_permissions=tuple(
                PeakPermission.from_dict(g) for g in self.store.get("peak_permissions", {}).values()
            ),
        )

    async def input_loop(self) -> None:
        assert self.ha and self.forecast
        last_forecast = None
        while not self.shutdown:
            try:
                observation = await self.ha.observe(self.snapshot.capabilities)
                initial = self.observation.quality == "unknown"
                self.observe(observation)
                try:
                    data = await self.forecast.read()
                except (
                    ValueError,
                    KeyError,
                    OSError,
                    RuntimeError,
                    aiohttp.ClientError,
                    TimeoutError,
                ) as exc:
                    self.error = f"Forecast unavailable: {type(exc).__name__}: {exc}"
                    self.status = "forecast_unavailable"
                    self.store.event("forecast_error", {"reason": self.error})
                    await asyncio.sleep(5)
                    continue
                try:
                    prepared = JsonForecastAdapter.snapshot(
                        data,
                        observation,
                        self.snapshot.capabilities,
                        self.policy,
                        self.goals,
                        self.revision,
                        self.now(),
                    )
                except (ValueError, KeyError, TypeError) as exc:
                    self.error = f"Forecast rejected: {exc}"
                    self.status = "forecast_unavailable"
                    self.store.event("forecast_error", {"reason": self.error})
                    await asyncio.sleep(5)
                    continue
                self.forecast_data = data
                self.snapshot = prepared
                if data["revision"] != last_forecast or initial:
                    self.conditional_valid = False
                    last_forecast = data["revision"]
                    self.changed("inputs_ready" if initial else "forecast_revision", ess=not initial)
            except (ValueError, KeyError, OSError, RuntimeError, aiohttp.ClientError, TimeoutError) as exc:
                self.error = f"Inputs unavailable: {type(exc).__name__}: {exc}"
                self.status = "inputs_unavailable"
                was_unknown = self.observation.quality == "unknown"
                self.observation = replace(self.observation, quality="unknown")
                if not was_unknown:
                    self.changed("critical_input_unavailable", ev=True, ess=True)
                self.store.event("input_error", {"reason": self.error})
            await asyncio.sleep(5)

    async def planning_loop(self) -> None:
        while not self.shutdown:
            try:
                await asyncio.wait_for(self.requested.wait(), timeout=300)
            except TimeoutError:
                self.requested.set()
            self.requested.clear()
            await asyncio.sleep(0.05)  # Coalesce event bursts, never queue independent full solves.
            try:
                snapshot = self.build_snapshot()
            except (ValueError, KeyError) as exc:
                self.status, self.error = "inputs_unavailable", str(exc)
                self.store.event("snapshot_error", {"reason": self.error})
                continue
            self.status = "planning"
            try:
                result = await asyncio.get_running_loop().run_in_executor(
                    self.worker, plan_snapshot, json_data(snapshot)
                )
            except BrokenProcessPool as exc:
                self.status, self.error = "solver_error", str(exc)
                self.store.event("worker_restarted", {"reason": str(exc)})
                if self.worker:
                    self.worker.shutdown(wait=False, cancel_futures=True)
                self.worker = ProcessPoolExecutor(
                    max_workers=1, mp_context=get_context("spawn"), initializer=watch_parent
                )
                await asyncio.sleep(1)
                self.requested.set()
                continue
            except (RuntimeError, ValueError, OSError) as exc:
                self.status, self.error = "solver_error", str(exc)
                self.store.event("solver_error", {"type": type(exc).__name__, "reason": str(exc)})
                continue
            # All changes are conservatively revalidated by a fresh solve; accepted unaffected work continues.
            if snapshot.revision != self.revision:
                self.store.record(snapshot, result, "rejected_stale")
                self.status = "superseded"
                self.requested.set()
                continue
            effective = (
                Snapshot.from_dict(result["effective_snapshot"])
                if result.get("effective_snapshot")
                else snapshot
            )
            errors = (
                validate(effective, result["flows"], result.get("service"))
                if result.get("valid")
                else [result.get("reason", "No incumbent")]
            )
            if not errors:
                effective, result, errors = rebase(effective, result, self.observation, self.now())
            if errors:
                result["publication_errors"] = errors
                self.store.record(snapshot, result, "rejected")
                self.status, self.error = (
                    "publication_rejected" if result.get("valid") else result["status"],
                    errors[0],
                )
                continue
            self.store.record(snapshot, result, "accepted")
            self.accepted, self.snapshot = result, snapshot
            if self.demo:
                self.demo_plant.snapshot = effective
            self.ev_valid = self.observation.connected
            self.ess_valid = True
            self.conditional_valid = True
            self.status, self.error = "ready", None
            self.update_issues(result)
            for reason in result["reasons"]:
                if reason["kind"] == "peak_precharge":
                    await self.notifications.inform(
                        "peak-precharge",
                        {
                            **reason,
                            "peak_kw": result["summary"]["peak_kw"],
                            "avoided_peak_kw": reason.get(
                                "counterfactual_peak_kw", result["reference_summary"]["peak_kw"]
                            ),
                            "day": result["intervals"][0]["start"][:10],
                        },
                    )

    def update_issues(self, plan: dict[str, Any]) -> None:
        issues = self.store.get("issues", {})
        proposals = {p["goal_id"]: p for p in plan.get("permission_proposals", [])}
        for goal in plan["goals"]:
            key = f"{goal['id']}:{goal['revision']}"
            if goal["shortfall_kwh"] is None:
                issues[key] = {
                    "goal_id": goal["id"],
                    "revision": goal["revision"],
                    "state": "reconciliation_required",
                    "shortfall_kwh": None,
                    "proposed_peak_kw": None,
                    "text": "Post-trip battery state is unknown. Reconnection measurement is required before dependent charging can execute.",
                }
            elif goal["shortfall_kwh"] > 2e-5:
                issues[key] = {
                    "goal_id": goal["id"],
                    "revision": goal["revision"],
                    "state": goal["approval_state"],
                    "shortfall_kwh": goal["shortfall_kwh"],
                    "text": "Forecast shortfall. No higher-permission plan has been demonstrated to meet this goal; useful permitted work continues.",
                    "proposed_peak_kw": None,
                }
                if goal["id"] in proposals:
                    issues[key] = proposals[goal["id"]]
            elif key in issues:
                del issues[key]
        active = {f"{g['id']}:{g['revision']}" for g in plan["goals"]}
        for proposal in plan.get("permission_proposals", []):
            if proposal.get("kind") == "ess_peak":
                key = f"{proposal['goal_id']}:{proposal['revision']}"
                issues[key] = proposal
                active.add(key)
        self.store.put("issues", {key: value for key, value in issues.items() if key in active})

    async def control_loop(self) -> None:
        while not self.shutdown:
            before = monotonic()
            at = self.now()
            if self.demo:
                # Explicitly synthetic device feed; never presented as measured installation history.
                observation = self.demo_plant.step(at, self.current_command)
                if (
                    observation.connected != self.observation.connected
                    or observation.monthly_peak_kw > self.observation.monthly_peak_kw + 0.05
                ):
                    self.observe(observation)
                else:
                    self.observation = observation
            command = self.controller.tick(
                self.observation,
                at,
                self.accepted,
                self.revision,
                self.ev_valid,
                self.ess_valid,
                self.conditional_valid,
            )
            try:
                await self.actuator.apply(command, self.revision, self.observation)
            except (OSError, RuntimeError) as exc:
                self.error = f"Actuator unavailable: {type(exc).__name__}: {exc}"
                self.store.event("actuator_error", {"reason": self.error, "generation": self.revision})
            if command.replan and (
                self.last_control_replan is None or (at - self.last_control_replan).total_seconds() >= 60
            ):
                self.last_control_replan = at
                self.requested.set()
            self.last_command = json_data(command)
            self.current_command = command
            self.store.event(
                "command_intent" if getattr(self.actuator, "enabled", False) else "commanded_dry_run",
                self.last_command,
            )
            self.response_seconds.append(monotonic() - before)
            if len(self.response_seconds) > 10000:
                self.response_seconds = self.response_seconds[-10000:]
            self.observed.append({**json_data(self.observation), "provenance": self.snapshot.provenance})
            self.store.event(
                "measurement", {**json_data(self.observation), "provenance": self.snapshot.provenance}
            )
            # No retention policy: records remain in events. This is only a bounded GUI projection.
            if len(self.observed) > 2000:
                self.observed = self.observed[-2000:]
            await asyncio.sleep(self.policy.control_period_seconds)

    def upsert_goal(self, data: dict[str, Any]) -> Goal:
        old = next((g for g in self.goals if g.id == data.get("id")), None)
        allowed = {
            "id",
            "title",
            "deadline",
            "target_soc_percent",
            "kind",
            "priority",
            "distance_km",
            "return_at",
            "earliest",
        }
        if set(data) - allowed:
            raise ValueError("Goal fields do not include authority or approval settings")
        new = Goal.from_dict(
            {**data, "id": old.id if old else uuid4().hex, "revision": old.revision + 1 if old else 1}
        )
        if new.deadline <= self.now():
            raise ValueError("Deadline must be in the future")
        self.goals = tuple(g for g in self.goals if g.id != new.id) + (new,)
        self.store.event("goal_revised" if old else "goal_created", new)
        self.store.put("goals", self.goals)
        self.clear_goal_issues(new.id)
        self.changed("goal_changed", ev=old is not None)
        return new

    def delete_goal(self, identity: str) -> None:
        if not any(g.id == identity for g in self.goals):
            raise KeyError(identity)
        self.store.event("goal_cancelled", next(g for g in self.goals if g.id == identity))
        self.goals = tuple(g for g in self.goals if g.id != identity)
        self.store.put("goals", self.goals)
        self.clear_goal_issues(identity)
        self.changed("goal_cancelled", ev=True)

    def clear_goal_issues(self, identity: str) -> None:
        self.store.put(
            "issues",
            {
                key: value
                for key, value in self.store.get("issues", {}).items()
                if value["goal_id"] != identity
            },
        )

    def approval_issue_state(self, identity: str, state: str) -> None:
        issues = self.store.get("issues", {})
        for issue in issues.values():
            if issue["goal_id"] == identity:
                issue["state"] = state
        self.store.put("issues", issues)

    def approve(self, identity: str, state: str, peak: float | None, revision: int) -> Goal | PeakPermission:
        if state not in ("granted", "rejected"):
            raise ValueError("Unknown approval action")
        if identity.startswith("ess-peak-"):
            issue = next((i for i in self.store.get("issues", {}).values() if i["goal_id"] == identity), None)
            if issue is None:
                raise KeyError(identity)
            if revision != issue["revision"] or issue["forecast_id"] != self.snapshot.forecast_id:
                raise ValueError("ESS permission belongs to an obsolete forecast")
            if peak is None or not 0 < peak <= self.snapshot.capabilities.grid_connection_kw:
                raise ValueError("Invalid ESS approved ceiling")
            permission = PeakPermission.from_dict(
                {
                    "id": identity,
                    "forecast_id": issue["forecast_id"],
                    "deadline": issue["deadline"],
                    "peak_kw": peak,
                    "state": state,
                    "revision": revision,
                }
            )
            permissions = self.store.get("peak_permissions", {})
            permissions[identity] = json_data(permission)
            self.store.put("peak_permissions", permissions)
            self.store.event("ess_approval", permission)
            self.approval_issue_state(identity, state)
            self.changed("ess_approval_changed", ess=state == "rejected")
            return permission
        old = next((g for g in self.goals + self.snapshot.goals if g.id == identity), None)
        if old is None:
            raise KeyError(identity)
        if old.revision != revision:
            raise ValueError("Approval belongs to an obsolete goal revision")
        if state == "granted" and (
            peak is None or not 0 < peak <= self.snapshot.capabilities.grid_connection_kw
        ):
            raise ValueError("Invalid approved peak")
        new = replace(
            old,
            approval_state=state if state == "granted" or old.approval_state != "granted" else "granted",
            approved_peak_kw=peak if state == "granted" else old.approved_peak_kw,
            rejected_peak_kw=peak if state == "rejected" else None,
            approval_revision=old.revision,
        )
        self.goals = tuple(new if g.id == identity else g for g in self.goals)
        if old.kind == "daily":
            approvals = self.store.get("daily_approvals", {})
            approvals[identity] = json_data(new)
            self.store.put("daily_approvals", approvals)
        self.store.put("goals", self.goals)
        self.store.event("approval", new)
        self.approval_issue_state(identity, state)
        self.changed("approval_changed", ev=state == "rejected")
        return new

    def observe(self, observation: Observation) -> None:
        previous = self.observation
        self.observation = observation
        if self.demo:
            self.demo_plant.observation = observation
            if observation.connected and not previous.connected:
                self.demo_plant.unknown_return = False
        self.store.event("observed", observation)
        if previous.connected != observation.connected:
            self.changed(
                "reconnected" if observation.connected else "disconnected",
                ev=True,
                ess=previous.ess_kwh > observation.ess_kwh + 0.1,
            )
        elif previous.ev_state_known != observation.ev_state_known:
            self.changed("ev_state_reconciled" if observation.ev_state_known else "ev_state_unknown", ev=True)
        elif observation.monthly_peak_kw > previous.monthly_peak_kw + 0.05:
            self.changed("actual_peak_increased")
        elif (
            abs(previous.ev_kwh - observation.ev_kwh) > 0.2
            or abs(previous.ess_kwh - observation.ess_kwh) > 0.2
        ):
            self.changed("resource_progress", ess=observation.ess_kwh < previous.ess_kwh - 0.2)

    def state(self) -> dict[str, Any]:
        return {
            "version": __version__,
            "status": self.status,
            "error": self.error,
            "revision": self.revision,
            "now": self.now().isoformat(),
            "demo": self.demo,
            "control_enabled": bool(getattr(self.actuator, "enabled", False)),
            "actuator_health": {
                "delivery_fault": bool(getattr(self.actuator, "delivery_fault", False)),
                "write_failures": getattr(self.actuator, "failures", 0),
                "preparing_phase": getattr(self.actuator, "target_phase", None),
            },
            "provenance": self.snapshot.provenance,
            "observation": json_data(self.observation),
            "capabilities": json_data(self.snapshot.capabilities),
            "policy": json_data(self.policy),
            "goals": json_data(self.goals),
            "accepted": self.accepted,
            "issues": list(self.store.get("issues", {}).values()),
            "command": self.last_command,
            "observed": self.observed,
            "control_max_seconds": max(self.response_seconds, default=0),
        }
