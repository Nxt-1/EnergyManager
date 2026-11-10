"""Synthetic vehicle values, counters and notices; no installation access."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

from energymanager.domain import Goal
from energymanager.ev_progress import EVProgress, progress_warning
from energymanager.notifications import Notifications, NotificationTarget
from energymanager.service import Application
from energymanager.store import Store
from test_ev_progress import AT, C, P, meter, sample, update
from test_first_slice import tiny


def goal(seconds=7200, target=50, revision=1):
    return Goal("synthetic-goal", "SYNTHETIC next charge", AT + timedelta(seconds=seconds), target, revision=revision)


def confirm(progress, seconds=0, total=100, soc=17, g=None):
    g = g or goal()
    raw = sample(seconds)
    progress.feedback.confirm(soc, g, progress.automatic_observation or raw, meter(seconds, total),
                              "sensor.synthetic_eto", C, P, raw.at)
    return g


def manual_update(progress, seconds, total, g, **kwargs):
    return progress.update(sample(seconds, **kwargs), meter(seconds, total) if total is not None else None,
                           "sensor.synthetic_eto", C, P, (g,))


@pytest.mark.parametrize("crossing", [10, 1800, 7200])
def test_three_points_then_fifteen_minutes_survives_pauses_polls_and_restart(tmp_path, crossing):
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    o = update(progress, crossing, 101.56)
    assert not o.ev_progress["feedback_incident"]
    threshold = o.ev_progress["feedback_threshold_at"]
    for t in (crossing + 100, crossing + 899):
        assert not update(progress, t, 101.56).ev_progress["feedback_incident"]
    store.close()
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    failed = update(progress, crossing + 900, 101.56)
    assert not failed.ev_state_known and not failed.ev_progress["usable"]
    assert failed.ev_progress["feedback_incident"]["cause"] == "stuck_soc"
    assert failed.ev_progress["feedback_threshold_at"] == threshold
    issue_id = failed.ev_progress["feedback_incident"]["id"]
    for t in (crossing + 901, crossing + 3600):
        assert update(progress, t, 101.56).ev_progress["feedback_incident"]["id"] == issue_id
    assert len(progress.feedback.state["notices"]) == 1
    store.close()


@pytest.mark.parametrize("soc,total", [(22.932, 100), (22.932, 100.52), (46.332, 110)])
def test_parked_small_topup_and_near_full_saturation_are_not_stuck_feedback(tmp_path, soc, total):
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100, soc=soc)
    for t in (60, 960, 7200):
        o = update(progress, t, total, soc=soc)
        assert o.ev_state_known and not o.ev_progress["feedback_incident"]
    store.close()


@pytest.mark.parametrize("recovered_soc", [7.956, 30.0])
def test_changed_report_corrects_any_disagreement_and_resets_grace_without_convergence(tmp_path, recovered_soc):
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    update(progress, 10, 101.56)
    # A delayed/rounded change just before grace expires is sufficient new evidence.
    o = update(progress, 909, 101.56, soc=recovered_soc)
    assert o.ev_state_known and o.ev_kwh == recovered_soc
    assert o.ev_observed_at is None
    assert o.ev_progress["feedback_threshold_at"] is None
    assert o.ev_progress["feedback_delivery_kwh"] == 0
    assert not update(progress, 1810, 101.56, soc=recovered_soc).ev_progress["feedback_incident"]
    store.close()


def test_counter_gaps_resets_and_source_changes_never_manufacture_threshold_energy(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    update(progress, 5, 101)
    update(progress, 10, None)
    o = update(progress, 15, 101.2)
    assert o.ev_progress["feedback_delivery_kwh"] == pytest.approx(1.08)
    o = update(progress, 20, 0)
    assert o.ev_progress["feedback_delivery_kwh"] == 0 and o.ev_progress["feedback_threshold_at"] is None
    o = update(progress, 25, 900, entity="sensor.synthetic_replacement")
    assert o.ev_progress["feedback_delivery_kwh"] == 0
    store.close()


def test_manual_reference_is_bounded_persistent_and_unchanged_vehicle_reads_are_not_recovery(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)  # Vehicle says49%; actual manual entry is17%.
    g = confirm(progress, g=goal(100000))
    o = manual_update(progress, 5, 100.1, g)
    assert o.ev_kwh == pytest.approx(8.046) and o.ev_state_known
    assert o.ev_progress["reported_kwh"] == 22.932 and o.ev_observed_at is None
    store.close()
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    # Waiting well beyond12hours never expires the already confirmed goal.
    o = manual_update(progress, 50000, 100.1, g)
    assert o.ev_progress["manual"]["status"] == "active" and o.ev_state_known
    assert o.ev_kwh == pytest.approx(8.046)
    assert not progress.feedback.state.get("refresh")
    o = manual_update(progress, 50005, 117.16, g)
    assert o.ev_progress["manual"]["status"] == "completed"
    assert o.ev_progress["manual"]["delivered_kwh"] == pytest.approx(15.444)
    assert o.ev_kwh == pytest.approx(23.4)
    assert o.ev_progress["manual"]["limit_kwh"] == 23.4
    store.close()


@pytest.mark.parametrize("recovered_soc", [6.0, 35.0])
def test_manual_recovers_once_to_next_changed_vehicle_value_not_to_manual_agreement(tmp_path, recovered_soc):
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    update(progress, 10, 101.56)
    update(progress, 910, 101.56)
    g = confirm(progress, 910, 101.56)
    manual_update(progress, 915, 101.66, g)
    o = manual_update(progress, 920, 101.76, g, soc=recovered_soc)
    assert o.ev_kwh == recovered_soc and o.ev_state_known
    assert not o.ev_progress["manual"]["enabled"]
    assert not o.ev_progress["feedback_incident"]
    later = manual_update(progress, 925, 101.86, g, soc=recovered_soc)
    assert later.ev_kwh == pytest.approx(recovered_soc + .09)
    assert len([key for key in progress.feedback.state["notices"] if "recovered" in key]) == 1
    store.close()


@pytest.mark.parametrize("change", ["unplug", "edit", "counter_reset", "source_change", "expired"])
def test_manual_scope_and_measurement_failures_require_confirmation_without_auto_renewal(tmp_path, change):
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    g = confirm(progress)
    if change == "unplug":
        o = manual_update(progress, 5, 100, g, connected=False)
    elif change == "edit":
        o = manual_update(progress, 5, 100, replace(g, revision=2, target_soc_percent=80))
    elif change == "expired":
        o = manual_update(progress, 7201, 100, goal(20000, 80))
    elif change == "counter_reset":
        o = manual_update(progress, 5, 0, g)
    else:
        o = progress.update(sample(5), meter(5, 900, entity="sensor.synthetic_other"),
                            "sensor.synthetic_other", C, P, (g,))
    assert not o.ev_state_known and not o.ev_progress["usable"]
    assert o.ev_progress["manual"]["quantity_kwh"] == pytest.approx(15.444)
    assert not o.ev_progress["manual"]["delivered_kwh"]
    assert not manual_update(progress, 7210, 100.1, goal(20000, 80)).ev_state_known
    store.close()


def test_manual_cannot_bypass_missing_counter_or_stall_and_continuous_gap_counts_once(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    with pytest.raises(ValueError, match="counter"):
        progress.feedback.confirm(17, goal(), sample(), None, "sensor.synthetic_eto", C, P, AT)
    g = confirm(progress)
    assert not manual_update(progress, 31, None, g).ev_state_known
    o = manual_update(progress, 40, 100.4, g)
    assert o.ev_state_known and o.ev_kwh == pytest.approx(8.316)
    o = manual_update(progress, 45, 100.4, g)
    assert o.ev_kwh == pytest.approx(8.316)
    powered = replace(sample(50), ev_power_kw=1.38)
    progress.update(powered, meter(50, 100.4), "sensor.synthetic_eto", C, P, (g,))
    stalled = progress.update(replace(powered, at=AT + timedelta(seconds=81)), meter(81, 100.4),
                              "sensor.synthetic_eto", C, P, (g,))
    assert not stalled.ev_state_known and stalled.ev_progress["manual"]["enabled"]
    store.close()


def test_manual_cloud_loss_keeps_counter_guard_and_one_shared_incident_without_resetting_authority(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    g = confirm(progress)
    raw = replace(sample(5), ev_state_known=False)
    o = progress.update(raw, meter(5, 100.1), "sensor.synthetic_eto", C, P, (g,))
    assert o.ev_state_known and o.ev_progress["manual"]["enabled"]
    warning = progress_warning(o, o.at, (g,))
    assert "confirmed manual goal" in warning["text"]
    assert len(progress.feedback.state["notices"]) == 1
    old = manual_update(progress, 10, 100.2, g)
    assert old.ev_progress["manual"]["enabled"]
    assert old.ev_progress["feedback_incident"]["id"] == o.ev_progress["feedback_incident"]["id"]
    progress.feedback.disable()
    assert not progress.feedback.apply(progress.automatic_observation, old.at, P).ev_state_known
    store.close()


def test_real_planner_and_controller_enforce_one_manual_goal_and_keep_ess_independent(tmp_path):
    from energymanager.control import FastControl
    from energymanager.domain import Snapshot
    from energymanager.planner import Planner
    from energymanager.validation import validate
    base = tiny(hours=2, ev=7.956, ess=7)
    shift = AT - base.observation.at
    g = goal(3600)
    later = replace(goal(7200, 80), id="synthetic-later")
    s = replace(base, observation=sample(soc=7.956), capabilities=C,
        policy=replace(P, planning_budget_seconds=2), forecast_at=AT, goals=(g, later),
        intervals=tuple(replace(i, start=i.start + shift, end=i.end + shift) for i in base.intervals))
    store = Store(tmp_path / "synthetic.sqlite")
    ha = SimpleNamespace(entities={"ev_total_kwh":"sensor.synthetic_eto"},
                         inputs=SimpleNamespace(readings={"ev_total_kwh":meter(0, 100)}))
    app = Application(store, snapshot=s, policy=s.policy, ha=ha, demo=False)
    app.now = lambda: AT
    app.observe(sample(soc=7.956))
    item = app.manual_view(AT)["next_goal"]
    app.manual_soc({"enabled":True, "confirmed":True, "soc_percent":49,
        "goal_id":g.id, "goal_revision":g.revision, "deadline":g.deadline.isoformat(), "target_kwh":item["target_kwh"]})
    prepared = app.build_snapshot()
    result = Planner().plan(prepared)
    assert result["valid"], result
    effective = Snapshot.from_dict(result["effective_snapshot"])
    assert validate(effective, result["flows"], result["service"]) == []
    assert result["input_digest"] == prepared.digest
    assert len(effective.intervals) >= len(prepared.intervals)
    assert max(result["flows"]["ev_energy"]) <= 23.4 + 1e-6
    assert next(row for row in result["goals"] if row["id"] == later.id)["status"] == "manual_reference_required"
    control = FastControl(C, P)
    total = 100.0
    energy = 0.0
    for seconds in range(3600):
        o = app.ev_progress.update(sample(seconds, soc=7.956), meter(seconds, total),
                                  "sensor.synthetic_eto", C, P, (g, later))
        command = control.tick(o, o.at, result, 1)
        total += command.ev_kw / 3600
        energy += command.ev_kw * C.ev_efficiency / 3600
    quantum = C.minimum_current_a * C.voltage / 1000 * C.ev_efficiency * P.control_period_seconds / 3600
    assert .468 - quantum - 1e-6 <= energy <= .468 + 1e-6
    assert o.ev_progress["manual"]["status"] == "completed"
    assert command.ev_kw == 0
    # A hostile/outdated extra instruction cannot expand the manual quantity.
    complete = app.ev_progress.update(sample(3601, soc=7.956), meter(3601, total),
                                     "sensor.synthetic_eto", C, P, (later,))
    extra = control.tick(complete, complete.at, result, 1)
    assert extra.ev_kw == 0
    assert complete.ev_progress["manual"]["enabled"]
    store.close()


async def test_feedback_alert_refresh_recovery_notifications_are_durable_and_deduplicated(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    update(progress, 5, 101.56)
    update(progress, 905, 101.56)
    calls = []
    class FakePhone:
        async def service(self, domain, service, data):
            calls.append((domain, service, data))
    app = Application(store, snapshot=tiny(), demo=False)
    app.notifications = Notifications(store, FakePhone(), NotificationTarget("notify.synthetic_phone", "action"))
    await app.notify_ev_feedback()
    await app.notify_ev_feedback()
    assert len(calls) == 1
    g = confirm(app.ev_progress, 905, 101.56)
    for t in (906, 1000, 5000):
        app.ev_progress.feedback.request_refresh(AT + timedelta(seconds=t),
            {"manual_id":app.ev_progress.feedback.state["manual"]["id"], "would_start":(AT+timedelta(seconds=906)).isoformat(), "source":"synthetic due instruction"})
        await app.notify_ev_feedback()
    assert len(calls) == 2
    manual_update(app.ev_progress, 1005, 101.56, g, soc=7)
    await app.notify_ev_feedback()
    await app.notify_ev_feedback()
    assert len(calls) == 3
    store.close()


def test_a_fresh_confirmation_or_changed_vehicle_report_cancels_an_unsent_refresh_request(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    g = confirm(progress)
    def request(seconds):
        progress.feedback.request_refresh(AT+timedelta(seconds=seconds),
            {"manual_id":progress.feedback.state["manual"]["id"],"would_start":AT.isoformat()})
    request(5)
    assert any(key.startswith("ev-manual-refresh:") for key in progress.feedback.state["notices"])
    confirm(progress, 5, 100, soc=18, g=g)
    assert not progress.feedback.state.get("refresh")
    assert not any(key.startswith("ev-manual-refresh:") for key in progress.feedback.state["notices"])
    request(10)
    manual_update(progress, 15, 100, g, soc=12)
    assert not progress.feedback.state.get("refresh")
    assert not any(key.startswith("ev-manual-refresh:") for key in progress.feedback.state["notices"])
    assert len([key for key in progress.feedback.state["notices"] if "recovered" in key]) == 1
    store.close()


def test_manual_api_requires_explicit_current_reference_and_current_goal_confirmation(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    s = replace(tiny(), observation=sample())
    ha = SimpleNamespace(entities={"ev_total_kwh":"sensor.synthetic_eto"},
                         inputs=SimpleNamespace(readings={"ev_total_kwh":meter(0, 100)}))
    app = Application(store, snapshot=s, ha=ha, demo=False)
    app.now = lambda: AT
    app.observe(sample())
    g = app.manual_view(AT)["next_goal"]
    body = {"enabled":True, "confirmed":True, "soc_percent":17, "goal_id":g["id"],
            "goal_revision":g["revision"], "deadline":g["deadline"], "target_kwh":g["target_kwh"]}
    for invalid in ({"enabled":True}, {**body,"confirmed":False}, {**body,"soc_percent":None},
                    {**body,"soc_percent":True}, {**body,"soc_percent":101}, {**body,"goal_revision":999}):
        with pytest.raises(ValueError):
            app.manual_soc(invalid)
    assert not app.ev_progress.feedback.state.get("manual")
    assert app.manual_soc(body)["reference"]["enabled"]
    assert app.observation.ev_kwh == pytest.approx(.17 * s.capabilities.ev_capacity_kwh)
    assert not app.ev_valid
    assert not app.manual_soc({"enabled":False})["reference"]["enabled"]
    assert not app.observation.ev_state_known  # An old vehicle value cannot acquire manual authority.
    zero = {**body,"soc_percent":100}
    assert app.manual_soc(zero)["reference"]["quantity_kwh"] == 0
    assert app.observation.ev_kwh == s.capabilities.ev_capacity_kwh
    store.close()


async def test_manual_http_boundary_validation_and_confirmed_state_use_local_fake_only(tmp_path, monkeypatch):
    from aiohttp.test_utils import TestClient, TestServer
    from energymanager.web import create_web
    store = Store(tmp_path / "synthetic.sqlite")
    s = replace(tiny(), observation=sample())
    ha = SimpleNamespace(entities={"ev_total_kwh":"sensor.synthetic_eto"},
                         inputs=SimpleNamespace(readings={"ev_total_kwh":meter(0, 100)}))
    app = Application(store, snapshot=s, ha=ha, demo=False)
    app.now = lambda: AT
    app.observe(sample())
    async def no_worker():
        pass
    monkeypatch.setattr(app, "start", no_worker)
    monkeypatch.setattr(app, "close", no_worker)
    g = app.manual_view(AT)["next_goal"]
    body = {"enabled":True, "confirmed":True, "soc_percent":17, "goal_id":g["id"],
            "goal_revision":g["revision"], "deadline":g["deadline"], "target_kwh":g["target_kwh"]}
    async with TestClient(TestServer(create_web(app))) as client:
        resource = await client.get("/manual-soc.js")
        assert resource.status == 200 and "class ManualSoC" in await resource.text()
        assert (await client.post("/api/ev/manual-soc", json=body)).status == 403
        headers = {"X-EnergyManager":"1"}
        assert (await client.post("/api/ev/manual-soc", json=body,
                                 headers={**headers,"Origin":"https://synthetic-other.invalid"})).status == 403
        assert (await client.post("/api/ev/manual-soc", json={"enabled":True}, headers=headers)).status == 400
        response = await client.post("/api/ev/manual-soc", json=body, headers=headers)
        assert response.status == 200
        assert (await response.json())["reference"]["soc_percent"] == 17
        off = await client.post("/api/ev/manual-soc", json={"enabled":False}, headers=headers)
        assert off.status == 200
    await asyncio.gather(*app.protective_tasks)
    store.close()
