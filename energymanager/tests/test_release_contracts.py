from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from energymanager.domain import Goal
from energymanager.domain import daily_goals
from zoneinfo import ZoneInfo
from energymanager.notifications import Notifications, NotificationTarget
from energymanager.adapters import HomeAssistantAdapter
from energymanager.optimization import JointModel
from energymanager.planner import Planner
from energymanager.store import Store
from energymanager.validation import accounting, validate
from test_first_slice import tiny


def test_winter_starts_early_and_useful_later_pv_justifies_waiting():
    s = tiny(hours=2, ev=24, house=0.4, planning_budget_seconds=12)
    s = replace(s, goals=(Goal("ready", "Readiness", s.intervals[-1].end, 45),))
    winter = Planner().plan(s)
    assert winter["valid"]
    ev = [r for r in winter["sessions"] if r["resource"] == "ev"]
    assert datetime.fromisoformat(ev[0]["start"]) <= s.observation.at + timedelta(minutes=15)
    assert winter["goals"][0]["desired_margin_met"]
    for key in ("comparison_eur", "predicted_bill_eur"):
        assert (
            winter["summary"][key]
            <= winter["polish_reference_summary"][key] + s.policy.polish_tolerance_eur + 2e-5
        )
    sunny = replace(
        s,
        intervals=tuple(
            replace(i, pv_ac_kw=4 if i.start >= s.observation.at + timedelta(hours=1) else 0)
            for i in s.intervals
        ),
    )
    waiting = Planner().plan(sunny)
    assert waiting["valid"]
    assert sum(waiting["flows"]["grid_ev"]) == pytest.approx(0)
    assert sum(
        waiting["flows"]["pv_ev"][t]
        for t, i in enumerate(sunny.intervals)
        if i.start < s.observation.at + timedelta(hours=1)
    ) == pytest.approx(0)


def test_month_boundary_does_not_carry_incurred_allowance_into_next_month():
    s = tiny(hours=0.5, house=6)
    shift = datetime(2026, 10, 31, 22, 50, tzinfo=UTC) - s.observation.at
    s = replace(
        s,
        observation=replace(
            s.observation, at=s.observation.at + shift, monthly_peak_kw=7, quarter_import_kwh=0.5
        ),
        intervals=tuple(replace(i, start=i.start + shift, end=i.end + shift) for i in s.intervals),
    )
    result = JointModel(s).run(5)
    assert result["feasible"]
    assert not validate(s, result["flows"])
    assert accounting(s, result["flows"])["capacity_cost_eur"] == pytest.approx(
        3.5 * s.policy.capacity_eur_kw_month
    )


async def test_peak_notice_is_deduplicated_through_real_local_ha_notify_action(tmp_path):
    delivered = []

    async def receive(request):
        delivered.append(await request.json())
        return web.json_response({"received": True})

    fake = web.Application()
    fake.router.add_post("/services/notify/mobile_app_phone", receive)
    store = Store(tmp_path / "notices.sqlite")
    async with TestServer(fake) as server:
        ha = HomeAssistantAdapter(str(server.make_url("")), {})
        await ha.__aenter__()
        notices = Notifications(store, ha, NotificationTarget("notify.mobile_app_phone", "action"))
        body = {"kind": "peak_precharge", "peak_kw": 3.1, "avoided_peak_kw": 5.0, "day": "2026-10-23"}
        await notices.inform("peak-precharge", body)
        await notices.inform("peak-precharge", {**body, "peak_kw": 3.104, "forecast_id": "new-issue"})
        assert len(delivered) == 1
        await notices.inform("peak-precharge", {**body, "peak_kw": 3.5})
        assert len(delivered) == 2
        assert delivered[0]["message"].startswith("Battery charging")
        await ha.__aexit__()
        assert sum(e["kind"] == "notification_delivered" for e in store.events()) == 2
    store.close()


def test_decision_replay_detects_snapshot_corruption(tmp_path):
    s = tiny()
    store = Store(tmp_path / "evidence.sqlite")
    store.record(s, {"id": "decision", "summary": {}}, "rejected")
    assert store.decision("decision")["snapshot"]["id"] == s.id
    store.connection.execute("UPDATE decisions SET snapshot='{}' WHERE id='decision'")
    with pytest.raises(ValueError, match="checksum"):
        store.decision("decision")
    store.close()


def test_residual_value_sensitivity_selects_zero_or_partial_optional_energy():
    s = tiny(hours=0.5, ev=24, ess=14, house=0.8, pv=2, planning_budget_seconds=4)
    valuable = Planner().plan(s)
    assert valuable["valid"] and 0 < valuable["summary"]["optional_ev_kwh"] < 24
    low = replace(s, policy=replace(s.policy, ev_value_eur_kwh=0.01, ess_value_eur_kwh=0.01))
    rejected = Planner().plan(low)
    assert rejected["valid"]
    assert rejected["summary"]["optional_ev_kwh"] == pytest.approx(0)
    assert sum(valuable["flows"]["grid_ev"]) == pytest.approx(0)


def test_ess_grid_purchase_is_rejected_without_economic_peak_benefit():
    s = tiny(hours=0.5, house=1, ess=2.8, capacity_eur_kw_month=0, planning_budget_seconds=4)
    s = replace(
        s, intervals=tuple(replace(i, house_kw=5) if t >= 4 else i for t, i in enumerate(s.intervals))
    )
    result = Planner().plan(s)
    assert result["valid"]
    assert sum(result["flows"]["grid_store"]) == pytest.approx(0)


def test_local_morning_goal_remains_07_during_the_dst_transition():
    s = tiny()
    start = datetime(2026, 10, 24, tzinfo=UTC)
    goals = daily_goals(start, start + timedelta(hours=72), s.policy, ())
    assert [g.deadline.astimezone(ZoneInfo(s.policy.timezone)).hour for g in goals] == [7, 7, 7]
    assert (goals[1].deadline - goals[0].deadline).total_seconds() == 25 * 3600


def test_invalidated_ess_balances_measured_ev_without_export_or_overfilling():
    from energymanager.control import FastControl

    s = tiny(ess=14, house=0.4, pv=5)
    command = FastControl(s.capabilities, s.policy).tick(
        s.observation, s.observation.at, None, 1, ess_valid=False
    )
    assert command.ess_kw == 0
    o = replace(s.observation, ess_kwh=7, pv_ac_kw=0)
    command = FastControl(s.capabilities, s.policy).tick(o, o.at, None, 2, ess_valid=False)
    assert command.ess_kw <= o.house_kw + o.ev_power_kw


def test_best_effort_service_retains_a_source_valid_incumbent_with_later_solar():
    s = tiny(hours=2, ev=24, house=0.4, planning_budget_seconds=10)
    urgent = Goal(
        "urgent", "Impossible original readiness", s.observation.at + timedelta(minutes=30), 90, priority=90
    )
    later = Goal("later", "Later feasible readiness", s.intervals[-1].end, 50)
    s = replace(
        s,
        goals=(urgent, later),
        intervals=tuple(
            replace(i, pv_ac_kw=4) if i.start >= s.observation.at + timedelta(hours=1) else i
            for i in s.intervals
        ),
    )
    result = Planner().plan(s)
    assert result["valid"], result
    assert result["goals"][0]["shortfall_kwh"] > 0
    assert result["goals"][1]["shortfall_kwh"] < 2e-5
    assert not validate(s, result["flows"], result["service"])


def test_full_horizon_urgent_goal_has_an_authorized_relaxed_starting_point():
    from energymanager.forecasts import demo_snapshot
    from energymanager.incumbent import seed
    from energymanager.optimization import JointModel

    initial = demo_snapshot(season="winter")
    urgent = Goal("urgent", "Synthetic urgent goal", initial.observation.at + timedelta(hours=1), 56)
    snapshot = demo_snapshot(start=initial.observation.at, season="winter", goals=(urgent,))
    model = JointModel(snapshot, relaxed_service=True)
    warm = seed(model)
    assert warm is not None, getattr(model, "seed_issue", None)
    result = model.run(3, objective={}, warm=warm)
    assert result["feasible"], result
    assert len(snapshot.intervals) == 2017
    service = {
        goal.id: min(
            goal.target(snapshot.capabilities, snapshot.policy),
            result["flows"]["ev_energy"][snapshot.checkpoint_index(goal.deadline)],
        )
        for goal in snapshot.goals
    }
    assert service[urgent.id] < urgent.target(snapshot.capabilities, snapshot.policy)
    assert not validate(snapshot, result["flows"], service)
