"""Persistent deadline-margin warnings with goal/deadline-scoped mobile deduplication."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from .deadline_audit import validate_certificate
from .domain import Snapshot, daily_goals, encode, instant, json_data

if TYPE_CHECKING:
    from .service import Application


def retain_checked_fallback(result: dict[str, Any], previous: dict[str, Any] | None,
                            snapshot: Snapshot) -> None:
    guard = result.get("deadline_guard", {})
    prior = (previous or {}).get("deadline_guard", {})
    if guard.get("status") != "unverified" or prior.get("status") != "certified":
        return
    scope = prior["scope"]
    goal = next((g for g in result["goals"] if g["id"] == scope["goal_id"] and g["revision"] == scope["revision"]
                 and g["deadline"] == scope["deadline"] and abs(g["target_kwh"] - scope["target_kwh"]) < 1e-6), None)
    context = prior["nominal_context"]
    if (goal is None or context["capabilities"] != json_data(snapshot.capabilities)
            or context["policy"] != json_data(snapshot.policy)
            or result.get("appliance") != (previous or {}).get("appliance")
            or (snapshot.observation.at - instant(context["forecast_at"])).total_seconds() > snapshot.policy.forecast_max_age_seconds
            or validate_certificate(prior)):
        return
    result["deadline_guard"] = {**prior, "retained_on_timeout": True, "new_assessment": guard}


class DeadlineWarnings:
    def __init__(self, app: Application) -> None:
        self.app = app
        self.task: asyncio.Task[None] | None = None
        self.delivery_lock = asyncio.Lock()

    def start(self) -> None:
        self.task = asyncio.create_task(self.loop())

    async def close(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    def update(self, plan: dict[str, Any]) -> None:
        guard = plan.get("deadline_guard", {})
        scope = guard.get("scope")
        if not scope:
            self.prune()
            return
        key = f"{scope['goal_id']}:{scope['deadline']}"
        issues = self.app.store.get("deadline_margin_issues", {})
        if guard["status"] == "margin_shortfall":
            existing = issues.get(key, {})
            issues[key] = {**existing, **scope, "kind": "deadline_margin", "state": "margin_unavailable",
                           "notification": existing.get("notification", "retrying"),
                           "text": "The EV deadline is feasible on the normal forecast, but the 20% PV safety margin "
                                   "cannot be met within the permitted peak. That limit is retained.",
                           "withdrawals": guard.get("withdrawals", [])}
        elif guard["status"] == "certified":
            issues.pop(key, None)
        self.app.store.put("deadline_margin_issues", issues)
        self.prune()

    def prune(self) -> None:
        now = self.app.now()
        goals = {g.id: g for g in (*self.app.goals, *daily_goals(now, now + timedelta(days=7),
                                                              self.app.policy, self.app.goals))}
        issues = self.app.store.get("deadline_margin_issues", {})
        remaining = {}
        for key, issue in issues.items():
            goal = goals.get(issue["goal_id"])
            if (goal is None or goal.revision != issue["revision"] or goal.deadline != instant(issue["deadline"])
                    or goal.deadline <= now or abs(goal.target(self.app.snapshot.capabilities, self.app.policy)
                                                   - issue["target_kwh"]) > 1e-6):
                continue
            required = issue["target_kwh"] + sum(row["kwh"] for row in issue.get("withdrawals", [])
                                                  if now <= instant(row["at"]) < goal.deadline)
            if self.app.observation.ev_state_known and self.app.observation.ev_kwh >= required - 1e-6:
                continue
            remaining[key] = issue
        if remaining != issues:
            self.app.store.put("deadline_margin_issues", remaining)

    def view(self) -> list[dict[str, Any]]:
        self.prune()
        return list(self.app.store.get("deadline_margin_issues", {}).values())

    async def deliver(self) -> None:
        async with self.delivery_lock:
            self.prune()
            destination = encode(asdict(self.app.notifications.target) if self.app.notifications.target else None)
            for key, issue in self.app.store.get("deadline_margin_issues", {}).items():
                delivered = self.app.store.get("deadline_margin_delivered", {})
                if delivered.get(key) == destination:
                    continue
                local = instant(issue["deadline"]).astimezone(ZoneInfo(self.app.policy.timezone))
                success = await self.app.notifications.inform("deadline-margin:" + key, {
                    "kind": "deadline_margin", "goal_id": issue["goal_id"], "deadline": issue["deadline"],
                    "message": f"{issue['title']} ({local:%d %b %H:%M}): the 20% PV safety margin cannot be met "
                               "within the permitted peak. The normal forecast meets the deadline; the peak limit is retained."})
                current = self.app.store.get("deadline_margin_issues", {})
                if success:
                    delivered = self.app.store.get("deadline_margin_delivered", {})
                    delivered[key] = destination
                    self.app.store.put("deadline_margin_delivered", delivered)
                if key in current:
                    current[key]["notification"] = ("delivered" if self.app.notifications.target else "local_only") if success else "retrying"
                    self.app.store.put("deadline_margin_issues", current)

    async def loop(self) -> None:
        while True:
            await self.deliver()
            await asyncio.sleep(5)
