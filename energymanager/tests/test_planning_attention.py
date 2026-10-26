"""Synthetic rejection recovery and phone notices; no installation endpoint is used."""

import asyncio
from copy import deepcopy

from energymanager.notifications import Notifications, NotificationTarget
from energymanager.service import Application
from energymanager.planner import Planner
from energymanager.publication import rebase
from energymanager.store import Store
from test_first_slice import tiny


class FakePhone:
    def __init__(self):
        self.calls = []
        self.fail = False

    async def service(self, domain, service, data):
        if self.fail:
            raise RuntimeError("SYNTHETIC phone unavailable")
        self.calls.append((domain, service, data))


async def test_rejected_plan_retries_once_then_escalates_without_inventing_permission(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=tiny())
    phone = FakePhone()
    app.notifications = Notifications(store, phone, NotificationTarget("notify.synthetic_phone", "action"))
    app.accepted = {"id": "previous-accepted"}
    app.ev_valid = True
    errors = ["Unapproved EV peak SYNTHETIC: 5532 W exceeds 5490 W allowance"]
    await app.reject_plan({"id": "candidate-one"}, errors)
    issue = app.state()["issues"][0]
    assert issue["state"] == "retrying" and app.requested.is_set()
    assert not phone.calls
    assert "first_at" in issue and issue["decision_id"] == "candidate-one"
    assert not issue.get("proposed_peak_kw")
    app.requested.clear()
    await app.reject_plan({"id": "candidate-two"}, errors)
    assert not app.requested.is_set()
    issue = app.state()["issues"][0]
    assert issue["state"] == "attention_required" and issue["notification"] == "delivered"
    assert len(phone.calls) == 1
    assert "after an automatic retry" in phone.calls[0][2]["message"]
    app.revision += 1  # Ordinary measurement progress must not reset the retry budget.
    await app.reject_plan({"id": "candidate-three"}, ["Unapproved EV peak SYNTHETIC changed quarter"])
    assert len(phone.calls) == 1  # Changing solver IDs/quarters do not spam this incident.
    assert not app.requested.is_set()
    assert app.state()["issues"][0]["attempts"] == 3
    assert app.accepted["id"] == "previous-accepted" and app.ev_valid
    assert not store.get("issues", {})  # No fictional approval request.
    restarted = Application(store, snapshot=tiny())
    assert restarted.state()["issues"][0]["id"] == issue["id"]
    app.resolve_planning_issue("accepted-recovery")
    assert app.state()["issues"] == []
    assert any(e["kind"] == "planning_recovered" for e in store.events())
    store.close()


async def test_failed_phone_delivery_remains_retryable_and_local_only_is_honest(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=tiny())
    phone = FakePhone()
    phone.fail = True
    app.notifications = Notifications(store, phone, NotificationTarget("notify.synthetic_phone", "action"))
    await app.planning_retry_failed("SYNTHETIC startup inputs unavailable")
    assert not app.state()["issues"]
    await app.reject_plan({"id": "first"}, ["SYNTHETIC validation failure"])
    await app.planning_retry_failed("SYNTHETIC retry inputs unavailable")
    assert app.state()["issues"][0]["notification"] == "retrying"
    phone.fail = False
    await app.reject_plan({"id": "later"}, ["SYNTHETIC validation failure"])
    assert app.state()["issues"][0]["notification"] == "delivered"
    assert len(phone.calls) == 1
    app.resolve_planning_issue("recovered")
    app.notifications = Notifications(store)
    for identity in ("local-first", "local-retry"):
        await app.reject_plan({"id": identity}, ["SYNTHETIC local-only failure"])
    assert app.state()["issues"][0]["notification"] == "local_only"
    store.close()


async def test_real_permission_proposals_get_materially_deduplicated_phone_notices(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=tiny())
    phone = FakePhone()
    app.notifications = Notifications(store, phone, NotificationTarget("notify.synthetic_phone", "action"))
    issue = {"goal_id": "synthetic-morning", "revision": 1, "state": "pending",
             "proposed_peak_kw": 6.1, "shortfall_kwh": 1, "text": "SYNTHETIC proven diagnostic"}
    store.put("issues", {"synthetic-morning:1": issue})
    await app.notify_permission_issues()
    await app.notify_permission_issues()
    assert len(phone.calls) == 1 and "6100 W" in phone.calls[0][2]["message"]
    assert store.get("issues")["synthetic-morning:1"]["notification"] == "delivered"
    store.put("issues", {"synthetic-morning:1": {**issue, "proposed_peak_kw": 6.104}})
    await app.notify_permission_issues()
    assert len(phone.calls) == 1
    store.put("issues", {"synthetic-morning:1": {**issue, "proposed_peak_kw": 6.4}})
    await app.notify_permission_issues()
    assert len(phone.calls) == 2
    store.close()


async def test_publication_loop_recovers_once_and_clears_attention_without_phone_alert(tmp_path, monkeypatch):
    s = tiny(planning_budget_seconds=3)
    valid = Planner().plan(s)
    assert valid["valid"]
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=s, policy=s.policy)
    phone = FakePhone()
    app.notifications = Notifications(store, phone, NotificationTarget("notify.synthetic_phone", "action"))
    monkeypatch.setattr(app, "build_snapshot", lambda: s)
    monkeypatch.setattr(app, "now", lambda: s.observation.at)
    attempts = []

    def calculate(_):
        attempts.append(len(attempts))
        return {**deepcopy(valid), "id": f"synthetic-{len(attempts)}"}

    def reconcile(snapshot, result, observation, at):
        if len(attempts) == 1:
            return snapshot, result, ["SYNTHETIC changed-state peak rejection"]
        return rebase(snapshot, result, observation, at)

    async def accepted():
        app.shutdown = True

    monkeypatch.setattr("energymanager.service.plan_snapshot", calculate)
    monkeypatch.setattr("energymanager.service.rebase", reconcile)
    monkeypatch.setattr(app, "notify_permission_issues", accepted)
    app.requested.set()
    await asyncio.wait_for(app.planning_loop(), 5)
    assert len(attempts) == 2 and app.status == "ready"
    assert app.accepted["id"] == "synthetic-2"
    assert store.get("planning_issue") is None
    assert not phone.calls
    assert {row["disposition"] for row in store.decisions()} == {"accepted", "rejected"}
    store.close()
