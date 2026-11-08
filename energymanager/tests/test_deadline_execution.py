"""Cautious activation and fake mobile lifecycle, isolated from installation services."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

from deadline_fixtures import example
from energymanager.control import FastControl
from energymanager.deadline_guard import deadline_certificate
from energymanager.deadline_warnings import retain_checked_fallback
from energymanager.domain import instant
from energymanager.notifications import Notifications, NotificationTarget
from energymanager.optimization import JointModel
from energymanager.publication import admit
from energymanager.service import Application
from energymanager.store import Store
from test_planning_attention import FakePhone
from test_publication_closed_loop import result_for


def guarded_plan(name="tight_after_pv"):
    s = example(name)
    result = JointModel(s).run(2)
    assert result["feasible"]
    plan = result_for(s, result["flows"])
    plan["deadline_guard"] = deadline_certificate(s, result["flows"], 7)
    return s, plan


def test_cautious_progress_activates_precomputed_work_and_stops_at_its_own_target():
    s, plan = guarded_plan()
    guard = plan["deadline_guard"]
    assert guard["status"] == "certified"
    at = instant(guard["activation_at"])
    t = next(t for t, i in enumerate(guard["context"]["intervals"]) if instant(i["start"]) >= at
             and guard["flows"]["grid_ev"][t] > 1e-6)
    at = instant(guard["context"]["intervals"][t]["start"])
    o = replace(s.observation, at=at, ev_kwh=guard["progress_kwh"][t],
                house_kw=guard["context"]["intervals"][t]["house_kw"],
                pv_ac_kw=guard["context"]["intervals"][t]["pv_ac_kw"])
    control = FastControl(s.capabilities, s.policy)
    command = control.tick(o, at, plan, 1)
    assert command.current_a > 0 and control.deadline_execution.active
    assert command.peak_limit_kw == 3.5
    assert control.deadline_execution.activation_key
    completed = replace(o, at=at + timedelta(seconds=1), ev_kwh=guard["scope"]["target_kwh"])
    control.tick(completed, completed.at, plan, 1)
    assert not control.deadline_execution.active
    assert control.tick(o, at, plan, 1, ev_valid=False).current_a == 0


async def test_margin_warning_survives_restart_retries_without_forecast_spam_and_clears(tmp_path):
    s, plan = guarded_plan("margin_only_shortfall")
    assert plan["deadline_guard"]["status"] == "margin_shortfall"
    path = tmp_path / "synthetic.sqlite"
    store = Store(path)
    app = Application(store, snapshot=s, demo=False)
    app.now = lambda: s.observation.at
    phone = FakePhone()
    phone.fail = True
    app.notifications = Notifications(store, phone, NotificationTarget("notify.synthetic_phone", "action"))
    app.deadline_warnings.update(plan)
    await app.deadline_warnings.deliver()
    assert app.state()["issues"][0]["notification"] == "retrying"
    store.close()
    store = Store(path)
    app = Application(store, snapshot=s, demo=False)
    app.now = lambda: s.observation.at
    phone.fail = False
    import asyncio
    original_service = phone.service

    async def delayed_service(*args, **kwargs):
        await asyncio.sleep(.01)
        return await original_service(*args, **kwargs)

    phone.service = delayed_service
    app.notifications = Notifications(store, phone, NotificationTarget("notify.synthetic_phone", "action"))
    await asyncio.gather(*(app.deadline_warnings.deliver() for _ in range(4)))
    for n in range(3):
        plan["id"] = f"new-synthetic-plan-{n}"
        plan["forecast_id"] = str(n)
        app.deadline_warnings.update(plan)
        await app.deadline_warnings.deliver()
    assert len(phone.calls) == 1
    issue = app.state()["issues"][0]
    assert issue["kind"] == "deadline_margin" and "proposed_peak_kw" not in issue
    app.deadline_warnings.update({"deadline_guard": {**plan["deadline_guard"], "status": "certified"}})
    assert app.deadline_warnings.view() == []
    app.deadline_warnings.update(plan)
    await app.deadline_warnings.deliver()
    assert len(phone.calls) == 1
    app.observation = replace(s.observation, ev_kwh=plan["deadline_guard"]["scope"]["target_kwh"])
    assert app.deadline_warnings.view() == []
    app.observation = s.observation
    app.deadline_warnings.update(plan)
    app.goals = ()
    assert app.deadline_warnings.view() == []
    store.close()


def test_valid_checked_fallback_is_retained_on_timeout_and_corruption_is_rejected():
    s, previous = guarded_plan()
    new = deepcopy(previous)
    new["deadline_guard"] = {"status": "unverified"}
    retain_checked_fallback(new, previous, s)
    assert new["deadline_guard"]["retained_on_timeout"]
    bad = deepcopy(new)
    bad["deadline_guard"]["flows"]["guard_house_stock"][0] = 1
    _, errors = admit(s, bad, s.observation, s.observation.at)
    assert any("Protected" in error for error in errors)

    bad = deepcopy(new)
    bad["deadline_guard"].pop("scope")
    _, errors = admit(s, bad, s.observation, s.observation.at)
    assert any("authority" in error for error in errors)
