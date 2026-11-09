"""Deterministic charger totals and explicit vehicle sample times; no installation reads."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from energymanager.domain import Capabilities, Goal, Observation, Policy, Snapshot
from energymanager.ev_progress import EVProgress
from energymanager.live_inputs import Reading
from energymanager.store import Store


AT = datetime(2026, 11, 8, 20, tzinfo=UTC)
C = Capabilities(ev_capacity_kwh=46.8)
P = Policy()


def sample(seconds=0, *, soc=22.932, vehicle_at=None, connected=True):
    return Observation(AT + timedelta(seconds=seconds), soc, 7, connected, 1, 0, 0,
                       ev_observed_at=vehicle_at)


def meter(seconds, value, unit="kWh", entity="sensor.synthetic_eto"):
    return Reading.parse(entity, {"state": str(value), "attributes": {"unit_of_measurement": unit}},
                         AT + timedelta(seconds=seconds), "kWh", 30, nonnegative=True)


def update(progress, seconds, value, *, unit="kWh", entity="sensor.synthetic_eto", **kwargs):
    return progress.update(sample(seconds, **kwargs), meter(seconds, value, unit, entity)
                           if value is not None else None, entity, C, P)


def test_unchanged_soc_replans_reconnections_and_restart_keep_each_increment_once(tmp_path):
    store = Store(tmp_path / "progress.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    for seconds, total in ((5, 100.1), (10, 100.2), (15, 100.2)):
        o = update(progress, seconds, total, connected=seconds != 10)
    assert o.ev_kwh == pytest.approx(23.112)
    assert o.ev_progress["reported_kwh"] == 22.932
    assert o.ev_observed_at is None
    store.close()
    store = Store(tmp_path / "progress.sqlite")
    o = update(EVProgress(store), 20, 100.3)
    assert o.ev_kwh == pytest.approx(23.202)
    assert o.ev_progress["credited_kwh"] == pytest.approx(.27)
    store.close()


def test_declared_wh_kwh_and_gaps_recover_continuous_delivery(tmp_path):
    store = Store(tmp_path / "progress.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100000, unit="Wh")
    assert update(progress, 20, None).ev_progress["usable"]
    assert not update(progress, 31, None).ev_progress["usable"]
    o = update(progress, 40, 100.4)
    assert o.ev_kwh == pytest.approx(23.292)
    assert o.ev_progress["usable"]
    store.close()


def test_resets_source_changes_and_bad_units_preserve_credit_without_inventing_gap(tmp_path):
    store = Store(tmp_path / "progress.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    update(progress, 5, 101)
    for seconds, total, entity in ((10, 0, "sensor.synthetic_eto"), (15, 900, "sensor.synthetic_replacement")):
        o = update(progress, seconds, total, entity=entity)
        assert o.ev_kwh == pytest.approx(23.832)
    o = update(progress, 20, 900.1, entity="sensor.synthetic_replacement")
    assert o.ev_kwh == pytest.approx(23.922)
    assert o.ev_progress["segments"] == 2 and o.ev_progress["uncertain"]
    assert update(progress, 51, 900.2, unit="W").ev_kwh == pytest.approx(23.922)
    assert not update(progress, 52, -1).ev_progress["usable"]
    store.close()


def test_vehicle_reconciliation_requires_real_time_and_counter_alignment(tmp_path):
    store = Store(tmp_path / "progress.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    update(progress, 5, 100.2)
    # A new sample bracketed by a stationary counter replaces the old stock baseline.
    o = update(progress, 10, 100.2, soc=23.2, vehicle_at=AT + timedelta(seconds=7))
    assert o.ev_kwh == pytest.approx(23.2)
    assert not o.ev_progress["uncertain"]
    o = update(progress, 15, 100.3, soc=23.2, vehicle_at=AT + timedelta(seconds=7))
    assert o.ev_kwh == pytest.approx(23.29)
    # Do not add that increment to a repeated SoC, or align a sample across delivery.
    o = update(progress, 20, 100.4, soc=23.3, vehicle_at=AT + timedelta(seconds=17))
    assert o.ev_kwh == pytest.approx(23.38) and o.ev_progress["uncertain"]
    store.close()


def test_fresh_vehicle_fallback_never_uses_ha_read_time_as_vehicle_time(tmp_path):
    store = Store(tmp_path / "progress.sqlite")
    progress = EVProgress(store)
    assert not update(progress, 0, None).ev_progress["usable"]
    o = update(progress, 5, None, soc=23.0, vehicle_at=AT)
    assert o.ev_kwh == 23.0 and o.ev_progress["source"] == "vehicle SoC"
    assert not update(progress, 31, None, soc=23.0, vehicle_at=AT).ev_progress["usable"]
    store.close()


def test_legacy_supplied_snapshot_digest_is_unchanged():
    from test_first_slice import tiny
    from energymanager.domain import json_data
    snapshot = tiny()
    original = json_data(snapshot)
    assert "ev_progress" not in original["observation"]
    assert Snapshot.from_dict(original).digest == snapshot.digest
    assert replace(snapshot.observation, ev_progress={"usable": True}).ev_progress["usable"]


def test_new_vehicle_timestamp_with_unchanged_rounded_soc_does_not_erase_delivery(tmp_path):
    store = Store(tmp_path / "progress.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    for second in range(5, 30, 5):
        o = update(progress, second, 100 + second / 100, vehicle_at=AT + timedelta(seconds=second))
    assert o.ev_kwh == pytest.approx(22.932 + .25 * .9)
    assert o.ev_progress["credited_kwh"] == pytest.approx(.225)
    store.close()


def test_counter_before_first_soc_baseline_is_not_credited_again(tmp_path):
    store = Store(tmp_path / "progress.sqlite")
    progress = EVProgress(store)
    unknown = replace(sample(), ev_state_known=False)
    progress.update(unknown, meter(0, 100), "sensor.synthetic_eto", C, P)
    assert update(progress, 5, 100.1).ev_kwh == 22.932
    assert update(progress, 10, 100.2).ev_kwh == pytest.approx(23.022)
    store.close()


def test_fresh_soc_during_counter_gap_does_not_double_credit_overlapping_delivery(tmp_path):
    store = Store(tmp_path / "progress.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    update(progress, 5, 100.2)
    o = update(progress, 40, None, soc=23.4, vehicle_at=AT + timedelta(seconds=40))
    assert o.ev_kwh == 23.4
    o = update(progress, 45, 100.4, soc=23.4, vehicle_at=AT + timedelta(seconds=40))
    assert o.ev_kwh == 23.4 and o.ev_progress["uncertain"]
    assert update(progress, 50, 100.5, soc=23.4).ev_kwh == pytest.approx(23.49)
    store.close()


def test_known_trip_return_requires_new_vehicle_information_even_with_counter(tmp_path):
    store = Store(tmp_path / "progress.sqlite")
    progress = EVProgress(store)
    goal = Goal("trip", "SYNTHETIC away", AT + timedelta(seconds=10), kind="trip",
                return_at=AT + timedelta(seconds=15), distance_km=20)
    progress.update(sample(), meter(0, 100), "sensor.synthetic_eto", C, P, (goal,))
    progress.update(sample(5, connected=False), meter(5, 100), "sensor.synthetic_eto", C, P, (goal,))
    old = progress.update(sample(20, vehicle_at=AT), meter(20, 100), "sensor.synthetic_eto", C, P, (goal,))
    assert not old.ev_state_known and not old.ev_progress["usable"]
    new = progress.update(sample(25, soc=20, vehicle_at=AT + timedelta(seconds=25)),
                          meter(25, 100), "sensor.synthetic_eto", C, P, (goal,))
    assert new.ev_state_known and new.ev_kwh == 20
    assert update(progress, 30, 100.1, soc=20).ev_kwh == pytest.approx(20.09)
    store.close()


def test_progress_watchdog_stops_only_ev_and_keeps_the_task_for_recovery(tmp_path):
    from energymanager.control import FastControl
    from test_ev_live_protection import example
    s, plan = example(house=1)
    store = Store(tmp_path / "progress.sqlite")
    progress = EVProgress(store)
    o = progress.update(s.observation, Reading.parse("sensor.synthetic_eto",
        {"state": "100", "attributes": {"unit_of_measurement": "kWh"}}, s.observation.at, "kWh", 30),
        "sensor.synthetic_eto", s.capabilities, s.policy)
    control = FastControl(s.capabilities, s.policy)
    assert control.tick(o, o.at, plan, 1).current_a > 0
    target = control.ev_task["target"]
    at = o.at + timedelta(seconds=31)
    stopped = control.tick(replace(o, at=at, ess_kwh=7), at, plan, 1)
    assert stopped.current_a == 0 and stopped.ess_kw > 0
    assert control.ev_task["target"] == target
    reading = Reading.parse("sensor.synthetic_eto", {"state": "100.1", "attributes": {
        "unit_of_measurement": "kWh"}}, at, "kWh", 30)
    recovered = progress.update(replace(s.observation, at=at, ess_kwh=7), reading,
                                "sensor.synthetic_eto", s.capabilities, s.policy)
    assert control.tick(recovered, at, plan, 1).current_a > 0
    store.close()


def test_stationary_total_is_valid_at_rest_but_stalled_delivery_requires_real_recovery(tmp_path):
    store = Store(tmp_path / "progress.sqlite")
    progress = EVProgress(store)
    update(progress, 0, 100)
    assert update(progress, 60, 100).ev_progress["usable"]
    powered = replace(sample(65), ev_power_kw=1.38)
    progress.update(powered, meter(65, 100), "sensor.synthetic_eto", C, P)
    stalled = progress.update(replace(powered, at=AT + timedelta(seconds=96)), meter(96, 100),
                              "sensor.synthetic_eto", C, P)
    assert not stalled.ev_progress["usable"]
    assert "not advancing" in stalled.ev_progress["issue"]
    assert not update(progress, 100, 100).ev_progress["usable"]  # Stopping alone is not recovery.
    recovered = update(progress, 105, 100.1)
    assert recovered.ev_progress["usable"] and recovered.ev_kwh == pytest.approx(23.022)
    store.close()
