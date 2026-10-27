"""Synthetic forecast and energy evidence; no installation data or actuator endpoints."""

from dataclasses import replace
from datetime import timedelta
import asyncio

import pytest

from energymanager.control import FastControl
from energymanager.domain import PeakPermission, json_data
from energymanager.optimization import JointModel
from energymanager.replanning import ReplanningEvidence
from energymanager.service import Application
from energymanager.store import Store
from test_first_slice import tiny


def sample(evidence, snapshot, seconds, **values):
    observation = replace(snapshot.observation, at=snapshot.observation.at + timedelta(seconds=seconds), **values)
    return evidence.forecast(observation, snapshot)


def flat_plan(snapshot):
    n = len(snapshot.intervals) + 1
    return {"id": "synthetic-flat", "intervals": json_data(snapshot.intervals), "flows": {
        "ev_energy": [snapshot.observation.ev_kwh] * n,
        "ess_solar": [snapshot.observation.ess_kwh - snapshot.capabilities.ess_min_kwh] * n,
        "ess_grid": [0.0] * n,
    }}


@pytest.mark.parametrize("channel", ["house_kw", "pv_ac_kw", "pv_dc_kw"])
def test_sustained_bias_changes_assumptions_once_even_when_mismatch_persists(channel):
    s = tiny(hours=3, house=2, pv=2, dc=2)
    evidence = ReplanningEvidence()
    events = [reply for t in range(0, 7201, 5)
              if (reply := sample(evidence, s, t, **{channel: 3}))]
    assert len(events) == 1
    assert events[0][channel] == pytest.approx(1)
    assert events[0]["changed_energy_kwh"] == pytest.approx(0.25)


def test_appliance_spikes_and_opposing_errors_do_not_request_full_solves():
    s = tiny(hours=2, house=1, pv=1)
    evidence = ReplanningEvidence()
    assert not any(sample(evidence, s, t, house_kw=4 if t % 60 == 0 else 1)
                   for t in range(0, 3601, 5))
    evidence = ReplanningEvidence()
    assert not any(sample(evidence, s, t, house_kw=2, pv_ac_kw=2)
                   for t in range(0, 3601, 5))
    evidence = ReplanningEvidence()
    assert not any(sample(evidence, s, t, house_kw=6 if t < 600 else 1)
                   for t in range(0, 1801, 5))  # A completed ten-minute appliance run.


def test_new_issuances_do_not_rediscover_the_same_uncorrected_load_bias():
    s = tiny(hours=3)
    evidence = ReplanningEvidence()
    events = []
    for t in range(0, 7201, 5):
        current = replace(s, forecast_id=f"synthetic-issuance-{t // 1800}")
        if reply := sample(evidence, current, t, house_kw=1.4):
            events.append(reply)
    assert len(events) == 1 and evidence.bias[0] == pytest.approx(1)


@pytest.mark.parametrize("interruption", ["gap", "unknown", "settling", "repeated"])
def test_invalid_or_duplicate_observations_cannot_manufacture_coverage(interruption):
    s = tiny(hours=2)
    evidence = ReplanningEvidence()
    for t in range(0, 601, 5):
        assert sample(evidence, s, t, house_kw=2) is None
    if interruption == "gap":
        resume = 660
    elif interruption == "repeated":
        assert all(sample(evidence, s, 600, house_kw=2) is None for _ in range(200))
        return
    else:
        sample(evidence, s, 605, house_kw=2, quality=interruption)
        resume = 610
    assert all(sample(evidence, s, t, house_kw=2) is None for t in range(resume, resume + 900, 5))
    assert sample(evidence, s, resume + 900, house_kw=2)


def test_material_new_bias_is_rate_limited_and_new_forecast_clears_old_correction():
    s = tiny(hours=3)
    evidence = ReplanningEvidence()
    assert sample(evidence, s, 0, house_kw=1.4) is None
    for t in range(5, 901, 5):
        first = sample(evidence, s, t, house_kw=1.4)
    assert first and evidence.bias[0] == pytest.approx(1)
    for t in range(905, 1800, 5):
        assert sample(evidence, s, t, house_kw=3.4) is None
    assert sample(evidence, s, 1800, house_kw=3.4)
    revised = replace(s, forecast_id="new-synthetic", intervals=tuple(replace(i, house_kw=3.4) for i in s.intervals))
    assert not any(sample(evidence, revised, t, house_kw=3.4) for t in range(1805, 3601, 5))
    assert evidence.bias == pytest.approx((0, 0, 0), abs=.02)


def test_correction_is_local_fades_preserves_inputs_and_expires_when_reads_stop():
    s = tiny(hours=3, house=1, pv=2)
    evidence = ReplanningEvidence()
    for t in range(0, 901, 5):
        sample(evidence, s, t, house_kw=2, pv_ac_kw=0)
    start = s.observation.at + timedelta(seconds=900)
    current = replace(s, intervals=tuple(i for i in s.intervals if i.start >= start))
    adjusted = evidence.adjusted(current)
    assert adjusted.intervals[0].house_kw == 2
    assert adjusted.intervals[0].pv_ac_kw == 0
    assert adjusted.forecast_id != current.forecast_id
    assert evidence.adjusted(adjusted) is adjusted  # Never double-correct an accepted snapshot.
    assert adjusted.intervals[0].end == current.intervals[0].end
    assert all(i == old for i, old in zip(adjusted.intervals, current.intervals)
               if i.start >= start + timedelta(hours=1))
    middle = next(i for i in adjusted.intervals if i.start == start + timedelta(minutes=45))
    assert 1 < middle.house_kw < 2 and 0 < middle.pv_ac_kw < 2
    assert s.intervals[0].house_kw == 1 and s.intervals[0].pv_ac_kw == 2
    stale = replace(current, intervals=current.intervals[1:])
    assert evidence.adjusted(stale) is stale


def test_corrected_forecast_cannot_reuse_an_ess_peak_grant_for_old_assumptions():
    s = tiny(hours=3)
    evidence = ReplanningEvidence()
    for t in range(0, 901, 5):
        sample(evidence, s, t, house_kw=1.4)
    grant = PeakPermission("synthetic-grant", s.forecast_id, s.intervals[-1].end, 6, "granted")
    at = s.observation.at + timedelta(seconds=900)
    current = replace(s, intervals=tuple(i for i in s.intervals if i.start >= at), peak_permissions=(grant,))
    original = JointModel(current, grid_ess=True)
    corrected = JointModel(evidence.adjusted(current), grid_ess=True)
    assert any(name.endswith("synthetic-grant") for name in original.linear.variables)
    assert not any(name.endswith("synthetic-grant") for name in corrected.linear.variables)


def test_ordinary_resource_progress_does_not_invalidate_control_or_replan(tmp_path):
    s = tiny(hours=2, ess=5)
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=s)
    app.accepted = flat_plan(s)
    app.ev_valid = app.ess_valid = True
    # Increments exceed the retired per-read0.2kWh trigger; inventories are above plan.
    app.observe(replace(s.observation, at=s.observation.at + timedelta(seconds=5), ev_kwh=25, ess_kwh=5.5))
    assert app.revision == 1 and not app.requested.is_set()
    assert app.ev_valid and app.ess_valid
    store.close()


def test_expected_ess_discharge_is_not_a_resource_shortfall(tmp_path):
    s = tiny(hours=2, ess=5)
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=s)
    app.accepted = flat_plan(s)
    app.accepted["flows"]["ess_solar"] = [5 - s.capabilities.ess_min_kwh
                                         - (i - s.intervals[0].start).total_seconds() / 3600
                                         for i in [s.intervals[0].start] + [i.end for i in s.intervals]]
    app.ev_valid = app.ess_valid = True
    app.observe(replace(s.observation, at=s.observation.at + timedelta(hours=1), ess_kwh=4))
    assert app.revision == 1 and not app.requested.is_set() and app.ess_valid
    store.close()


@pytest.mark.parametrize("resource", ["ev", "ess"])
def test_new_inventory_shortfall_requests_work_once_until_additional_evidence(tmp_path, resource):
    s = tiny(hours=2, ess=5)
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=s)
    app.accepted = flat_plan(s)
    app.ev_valid = app.ess_valid = True
    values = {f"{resource}_kwh": getattr(s.observation, f"{resource}_kwh") - 0.7}
    app.observe(replace(s.observation, at=s.observation.at + timedelta(seconds=5), **values))
    assert app.planning_activity["reason"] == "resource_shortfall"
    assert app.revision == 2
    app.requested.clear()
    for t in range(10, 1800, 5):
        app.observe(replace(s.observation, at=s.observation.at + timedelta(seconds=t), **values))
    assert app.revision == 2 and not app.requested.is_set()
    values[f"{resource}_kwh"] -= 0.7
    app.observe(replace(s.observation, at=s.observation.at + timedelta(seconds=1800), **values))
    assert app.revision == 3 and app.requested.is_set()
    store.close()


def test_peak_protection_remains_immediate_without_continuous_solver_requests():
    s = tiny(hours=2, ess=2.8)
    control = FastControl(s.capabilities, s.policy)
    for t in range(0, 600, 5):
        at = s.observation.at + timedelta(seconds=t)
        observation = replace(s.observation, at=at, house_kw=8, quarter_import_kwh=.62)
        command = control.tick(observation, at, None, 1)
        assert command.ev_kw == 0 and command.ess_kw == 0
        assert command.reason == "Quarter-hour peak protection"
        assert not command.replan


async def test_real_input_loop_requests_corrected_forecast_once_and_snapshot_uses_it(tmp_path, monkeypatch):
    s = tiny(hours=169)
    store = Store(tmp_path / "synthetic.sqlite")
    clock = [s.observation.at + timedelta(seconds=895)]
    data = {"issued_at": s.forecast_at.isoformat(), "revision": s.forecast_id,
            "provenance": "SYNTHETIC", "intervals": json_data(s.intervals)}

    class SyntheticHA:
        async def observe(self, capabilities):
            return replace(s.observation, at=clock[0], house_kw=1.4)

    class SyntheticForecast:
        async def read(self, observation, at):
            return data

    app = Application(store, snapshot=s, ha=SyntheticHA(), forecast=SyntheticForecast(), demo=False)
    app.forecast_data = data
    for t in range(0, 895, 5):
        sample(app.replanning, s, t, house_kw=1.4)
    monkeypatch.setattr(app, "now", lambda: clock[0])
    real_sleep = asyncio.sleep

    async def advance(seconds):
        clock[0] += timedelta(seconds=5)
        if clock[0] >= s.observation.at + timedelta(seconds=930):
            app.shutdown = True
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", advance)
    await app.input_loop()
    events = [event for event in store.events() if event["kind"] == "forecast_bias"]
    assert len(events) == 1 and app.planning_activity["reason"] == "forecast_bias"
    prepared = app.build_snapshot()
    assert prepared.intervals[0].house_kw == pytest.approx(1.4)
    assert data["intervals"][0]["house_kw"] == .4
    assert "measured near-term forecast correction" in prepared.provenance
    assert prepared.forecast_id == app.snapshot.forecast_id != s.forecast_id
    assert not any(event["kind"] == "input_error" for event in store.events())
    await asyncio.gather(*app.protective_tasks)
    store.close()


async def test_expired_control_instruction_requests_once_without_a_retry_loop(tmp_path, monkeypatch):
    s = tiny()
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=s, demo=False)
    app.accepted = flat_plan(s)
    clock = [s.intervals[-1].end + timedelta(seconds=1)]
    app.observation = replace(s.observation, at=clock[0])
    monkeypatch.setattr(app, "now", lambda: clock[0])
    ticks = []

    async def advance(seconds):
        ticks.append(clock[0])
        clock[0] += timedelta(seconds=1)
        app.observation = replace(app.observation, at=clock[0])
        app.requested.clear()  # Pretend the request was consumed, with the same expired plan retained.
        if len(ticks) == 10:
            app.shutdown = True

    monkeypatch.setattr(asyncio, "sleep", advance)
    await app.control_loop()
    assert len([event for event in store.events() if event["kind"] == "planning_requested"]) == 1
    assert app.planning_activity["reason"] == "control_unavailable"
    store.close()
