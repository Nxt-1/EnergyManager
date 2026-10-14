"""Focused V3 corrections: real solver regressions and archive/control boundaries."""
import asyncio
import gzip
import json
import os
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from test_milp_planner import _reference_plan, _task
from test_v3 import NOW, frame, snapshot

from energymanager.config import ConfigurationError, EssSettings, EvSettings, Settings
from energymanager.counterfactual import confidence
from energymanager.decision_store import DecisionStore, canonical
from energymanager.ess_control import EssHardwareController
from energymanager.ev_control import EvHardwareController
from energymanager.hierarchy import StageRecord
from energymanager.requirements import Provenance, Requirement, StorageResource


@pytest.mark.parametrize("minute", [0, 5, 10, 15])
def test_trip_departure_constraint_and_energy_conservation(minute):
    start = datetime(2026, 10, 8, 6, tzinfo=UTC)
    departure = start + timedelta(hours=1, minutes=minute)
    first = replace(_task(start), latest_end_local=departure, minimum_soc_percent=55,
                    target_soc_percent=55, expected_trip_energy_kwh=3,
                    expected_return_local=departure + timedelta(minutes=20))
    second = replace(first, task_id="second", latest_end_local=start + timedelta(minutes=105),
                     minimum_soc_percent=48, target_soc_percent=48, expected_trip_energy_kwh=2,
                     expected_return_local=start + timedelta(hours=2))
    result = snapshot(_reference_plan(start, tasks=(first, second))).solve()
    assert result.adoption_ready, result.reason
    intervals = result.plan.intervals
    boundary = (60 + minute) // 15
    assert intervals[boundary - 1].projected_ev_soc_percent >= 55 - 1e-5
    stored = 46.8 * .5
    withdrawn = 0
    for interval in intervals:
        at = interval.period_start_local.astimezone(UTC)
        draw = sum(t.expected_trip_energy_kwh for t in (first, second)
                   if at <= t.latest_end_local < at + timedelta(minutes=15))
        withdrawn += draw
        stored += interval.scheduled_load_w / 1000 * .25 * .9 - draw
        assert interval.projected_ev_soc_percent * 46.8 / 100 == pytest.approx(stored, abs=1e-5)
        if any(at < t.expected_return_local and at + timedelta(minutes=15) > t.latest_end_local
               for t in (first, second)):
            assert interval.scheduled_load_w == pytest.approx(0, abs=1e-5)
    assert withdrawn == 5


@pytest.mark.parametrize("fold", [0, 1])
def test_trip_withdrawal_dst_repeated_local_hour(fold):
    from energymanager.milp_planner import _ev_trip_energy_at_start
    zone = ZoneInfo("Europe/Brussels")
    departure = datetime(2026, 10, 25, 2, 5, tzinfo=zone, fold=fold)
    start = datetime(2026, 10, 24, 23, tzinfo=UTC)
    task = replace(_task(start), latest_end_local=departure, expected_trip_energy_kwh=4)
    draws = [_ev_trip_energy_at_start(start + timedelta(minutes=15 * i), (task,)) for i in range(16)]
    assert sum(draws) == 4
    assert draws[4 + 4 * fold] == 4


@pytest.mark.parametrize("windows, feasible", [(None, True), ((), False), ("early", True), ("late", False)])
def test_storage_resource_windows_are_separate_from_state_requirements(windows, feasible):
    if windows == "early":
        windows = ((NOW, NOW + timedelta(minutes=30)),)
    elif windows == "late":
        windows = ((NOW + timedelta(hours=1), NOW + timedelta(hours=2)),)
    resource = StorageResource("water", 4, 0, 0, .8, max_input_kw=4, charging_windows=windows)
    provenance = Provenance("test", "1", NOW, (), "valid", "state deadline", ())
    requirement = Requirement("water-ready", "water", "state_by_deadline", True, 1.6, "kWh",
                              NOW + timedelta(minutes=45), NOW + timedelta(hours=1), True, provenance)
    result = snapshot(replace(frame(), resources=(resource,), requirements=(requirement,))).solve()
    assert result.adoption_ready is feasible
    if feasible:
        assert dict(result.plan.intervals[3].resource_energy_kwh)["water"] >= 1.6 - 1e-5
        previous = 0
        for interval in result.plan.intervals:
            power = dict(interval.job_power_w)["water"] / 1000
            energy = dict(interval.resource_energy_kwh)["water"]
            assert energy == pytest.approx(previous + power * .25 * .8)
            previous = energy
            if windows and interval.period_start_local >= NOW + timedelta(minutes=30):
                assert power == pytest.approx(0, abs=1e-5)


def economic_result(status="Optimal", objective=2, bound=2, gap=0, valid=True):
    stage = StageRecord("economics", "EUR", status, objective, bound, gap, 1, .01, valid)
    return SimpleNamespace(stages=(stage,), adoption_ready=valid, milp_objective_eur=objective)


def test_counterfactual_confidence_uses_bounds_not_status_labels():
    exact = economic_result()
    proven = confidence(exact, economic_result(objective=3, bound=3))
    assert proven["conclusion"] == "alternative_more_expensive_proven_by_bounds"
    assert proven["optimal_difference_bounds_eur"] == {"lower": 1, "upper": 1}
    uncertain = confidence(economic_result(objective=2, bound=1, gap=.5),
                           economic_result("Time limit reached", 3, 1.5, .5))
    assert uncertain["conclusion"] == "feasible_incumbents_only"
    assert uncertain["optimal_difference_bounds_eur"] == {"lower": -.5, "upper": 2}
    assert uncertain["alternative"]["mip_gap"] == .5
    assert not uncertain["alternative"]["hierarchy_complete"]


@pytest.mark.parametrize("status", ["Infeasible", "Time limit reached", "Error"])
def test_counterfactual_incomplete_economics_never_claims_price_proof(status):
    incomplete = economic_result(status, None, None, None, False)
    evidence = confidence(economic_result(), incomplete)
    assert evidence["conclusion"] == "incomplete"
    assert evidence["optimal_difference_bounds_eur"] == {"lower": None, "upper": None}
    incomplete.stages = ()
    assert confidence(incomplete, economic_result())["baseline"]["status"] == "not_run"


@pytest.mark.parametrize("ess_enabled, ev_enabled", [(False, False), (True, False), (False, True), (True, True)])
def test_final_hardware_permissions_are_independent(ess_enabled, ev_enabled):
    class Client:
        def __init__(self):
            self.calls = []

        async def call_service(self, *args):
            self.calls.append(args)

    client = Client()
    ess = EssHardwareController(client, EssSettings(control_enabled=ess_enabled, setpoint_entity="number.ess"))
    ev = EvHardwareController(client, EvSettings(control_enabled=ev_enabled, current_entity="number.ev",
                                                phase_mode_entity="select.phase", force_state_entity="select.force"))

    async def run():
        await ess._client.call_service("number", "set_value", {"entity_id": "number.ess"})
        for entity in ("number.ev", "select.phase", "select.force", "button.reset"):
            await ev._client.call_service(entity.split(".")[0], "test", {"entity_id": entity})
    asyncio.run(run())
    ids = [call[2]["entity_id"] for call in client.calls]
    assert ("number.ess" in ids) is ess_enabled
    assert len(ids) == int(ess_enabled) + 4 * int(ev_enabled)


def test_migration_defaults_disabled_and_obsolete_permission_requires_review(tmp_path):
    path = tmp_path / "options.json"
    path.write_text("{}")
    settings = Settings.load(path)
    assert not settings.ess.control_enabled and not settings.ev.control_enabled
    for old_value in (True, False):
        path.write_text(json.dumps({"planner": {"shadow_mode": old_value},
                                    "ess": {"control_enabled": True, "setpoint_entity": "number.ess"}}))
        with pytest.raises(ConfigurationError, match="reviewing ess.control_enabled"):
            Settings.load(path)


def test_compressed_archive_replay_legacy_and_whole_record_integrity(tmp_path):
    frozen = snapshot()
    result = frozen.solve()
    store = DecisionStore(tmp_path)
    store.save(frozen, result, disposition="accepted")
    path = tmp_path / (frozen.snapshot_id + ".json.gz")
    raw = gzip.decompress(path.read_bytes())
    assert len(path.read_bytes()) < len(raw) / 3
    saved, document = store.read(frozen.snapshot_id)
    assert saved.solve().adoption_ready
    # Legacy preview documents remain readable; they only carry snapshot integrity.
    document.pop("decision_checksum")
    document.pop("decision_schema_version")
    legacy = path.with_suffix("")
    legacy.write_text(canonical(document))
    path.unlink()
    assert store.read(frozen.snapshot_id)[0] == frozen
    store.save(frozen, result, disposition="accepted")
    assert not legacy.exists()
    document = json.loads(gzip.decompress(path.read_bytes()))
    document["disposition"] = "tampered"
    path.write_bytes(gzip.compress(canonical(document).encode()))
    with pytest.raises(ValueError, match="checksum"):
        store.read(frozen.snapshot_id)
    path.write_bytes(b"broken gzip")
    with pytest.raises(ValueError, match="corrupt"):
        store.read(frozen.snapshot_id)


def test_archive_age_bytes_and_failed_writes(tmp_path):
    store = DecisionStore(tmp_path)
    first = snapshot()
    result = first.solve()
    store.save(first, result, disposition="accepted")
    path = tmp_path / (first.snapshot_id + ".json.gz")
    size = path.stat().st_size
    old = time.time() - 31 * 86400
    os.utime(path, (old, old))
    second = snapshot(replace(frame(), generated_at_utc=NOW + timedelta(seconds=1)))
    store.save(second, result, disposition="accepted")
    assert store.list_ids() == (second.snapshot_id,)
    assert not path.exists()
    bounded = DecisionStore(tmp_path, max_bytes=max(1024, size + 1024))
    bounded.save(first, result, disposition="accepted")
    assert sum(p.stat().st_size for p in tmp_path.glob("*.gz")) <= bounded.max_bytes
    with pytest.raises(ValueError, match="byte limit"):
        DecisionStore(tmp_path, max_bytes=1024).save(first, result, disposition="accepted")
    assert store.read(first.snapshot_id)[0] == first


def test_two_departures_inside_one_slot_respect_both_minima_and_withdrawals():
    first = replace(_task(NOW), latest_end_local=NOW + timedelta(minutes=60), minimum_soc_percent=50,
                    expected_trip_energy_kwh=3, expected_return_local=NOW + timedelta(minutes=64))
    second = replace(first, task_id="second", latest_end_local=NOW + timedelta(minutes=65),
                     expected_trip_energy_kwh=2, expected_return_local=NOW + timedelta(minutes=80))
    result = snapshot(replace(frame(), tasks=(first, second))).solve()
    assert result.adoption_ready, result.reason
    before = result.plan.intervals[3].projected_ev_soc_percent * 46.8 / 100
    after = result.plan.intervals[4].projected_ev_soc_percent * 46.8 / 100
    assert before - 3 >= .5 * 46.8 - 1e-5
    assert after == pytest.approx(before - 5)


def test_archive_constructor_and_reads_do_not_run_retention(tmp_path):
    pending = tmp_path / ".pending-test"
    pending.write_text("interrupted write")
    old = time.time() - 2 * 86400
    os.utime(pending, (old, old))
    store = DecisionStore(tmp_path)
    assert pending.exists()
    assert store.list_ids() == ()
    frozen = snapshot()
    store.save(frozen, frozen.solve(), disposition="accepted")
    assert not pending.exists()


def test_decompression_limit_rejects_oversized_archive(tmp_path):
    frozen = snapshot()
    path = tmp_path / (frozen.snapshot_id + ".json.gz")
    path.write_bytes(gzip.compress(b" " * (32 * 1024 * 1024 + 1)))
    with pytest.raises(ValueError, match="oversized decompressed"):
        DecisionStore(tmp_path).read(frozen.snapshot_id)
