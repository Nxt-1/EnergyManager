"""Deterministic synthetic accounting cases; no installation or actuator access."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.domain import Goal
from energymanager.forecasts import apply_requirements
from energymanager.planner import Planner
from energymanager.session_attribution import attribute_ev_sessions
from test_first_slice import tiny


def goal(identity, index, energy, kind="trip"):
    s = tiny()
    return Goal(
        identity,
        "SYNTHETIC " + identity,
        s.observation.at + timedelta(minutes=5 * index),
        target_soc_percent=energy / s.capabilities.ev_capacity_kwh * 100,
        kind=kind,
        distance_km=energy / s.policy.consumption_kwh_per_100km * 100,
    )


def fixture(charges, goals, initial=0):
    s = tiny(ev=initial, arrival_reserve_km=0)
    intervals = tuple(
        replace(
            s.intervals[-1],
            start=s.observation.at + timedelta(minutes=5 * t),
            end=s.observation.at + timedelta(minutes=5 * (t + 1)),
        )
        for t in range(len(charges))
    )
    intervals = apply_requirements(intervals, tuple(goals), s.observation, s.capabilities, s.policy)
    s = replace(s, intervals=intervals, goals=tuple(goals))
    flows = {"ev_energy": [initial], "pv_ev": [], "grid_ev": [], "solar_dis_ev": []}
    sessions = []
    left = None
    for t, charge in enumerate(charges + [0]):
        if charge and left is None:
            left = t
        if not charge and left is not None:
            sessions.append(
                {
                    "id": f"session-{left}",
                    "resource": "ev",
                    "energy_kwh": sum(charges[left:t]),
                    "start": intervals[left].start.isoformat(),
                    "end": intervals[t - 1].end.isoformat(),
                    "goal_ids": [g.id for g in goals],
                }
            )
            left = None
        if t < len(charges):
            flows["grid_ev"].append(charge / intervals[t].hours / s.capabilities.ev_efficiency)
            flows["pv_ev"].append(0)
            flows["solar_dis_ev"].append(0)
            flows["ev_energy"].append(flows["ev_energy"][-1] + charge - intervals[t].withdrawal_kwh)
    return s, flows, sessions


def rows(session, category):
    return {r["goal_id"]: r["energy_kwh"] for r in session["energy_attribution"][category]}


def conserved(sessions):
    for session in sessions:
        a = session["energy_attribution"]
        assert sum(row["energy_kwh"] for row in a["driving"]) + a["stored_kwh"] + a[
            "unresolved_kwh"
        ] == pytest.approx(session["energy_kwh"])
        assert sum(row["energy_kwh"] for row in a["targets"]) <= session["energy_kwh"] + 1e-8


def test_eight_kwh_is_assigned_to_two_actual_trips_not_every_later_goal():
    goals = [goal("first", 1, 6), goal("second", 3, 2), goal("later", 5, 8, "daily")]
    s, flows, sessions = fixture([8, 0, 0, 0, 0, 0], goals)
    original = deepcopy(flows)
    attribute_ev_sessions(s, flows, sessions)
    assert rows(sessions[0], "driving") == pytest.approx({"first": 6, "second": 2})
    assert sessions[0]["goal_ids"] == ["first", "second"]
    assert flows == original
    conserved(sessions)


def test_existing_stock_supplies_the_first_trip_before_new_charge_is_used():
    s, flows, sessions = fixture([6, 0, 0, 0, 0], [goal("first", 1, 6), goal("second", 3, 6)], initial=6)
    attribute_ev_sessions(s, flows, sessions)
    assert rows(sessions[0], "driving") == pytest.approx({"second": 6})
    assert sessions[0]["goal_ids"] == ["second"]
    conserved(sessions)


def test_multiple_sessions_share_only_the_energy_needed_by_each_trip():
    s, flows, sessions = fixture([4, 0, 4, 0, 0, 0], [goal("first", 3, 6), goal("second", 5, 2)])
    attribute_ev_sessions(s, flows, sessions)
    assert rows(sessions[0], "driving") == pytest.approx({"first": 4})
    assert rows(sessions[1], "driving") == pytest.approx({"first": 2, "second": 2})
    conserved(sessions)


def test_repeated_morning_minima_do_not_claim_the_same_stored_energy():
    goals = [goal(f"morning-{t}", t, 8, "daily") for t in range(1, 5)]
    s, flows, sessions = fixture([8, 0, 0, 0, 0], goals)
    attribute_ev_sessions(s, flows, sessions)
    assert rows(sessions[0], "targets") == pytest.approx({"morning-1": 8})
    assert rows(sessions[0], "driving") == pytest.approx({})
    assert sessions[0]["energy_attribution"]["stored_kwh"] == pytest.approx(8)
    assert sessions[0]["goal_ids"] == ["morning-1"]
    conserved(sessions)


def test_only_an_additional_target_increase_claims_more_of_the_session():
    goals = [goal("lower", 1, 8, "daily"), goal("higher", 2, 10, "manual"), goal("repeat", 3, 10, "daily")]
    s, flows, sessions = fixture([10, 0, 0, 0], goals)
    attribute_ev_sessions(s, flows, sessions)
    assert rows(sessions[0], "targets") == pytest.approx({"lower": 8, "higher": 2})
    conserved(sessions)


def test_strongest_simultaneous_target_explains_the_shared_requirement_once():
    goals = [goal("morning", 1, 4, "daily"), goal("explicit", 1, 8, "manual")]
    s, flows, sessions = fixture([8, 0, 0], goals)
    attribute_ev_sessions(s, flows, sessions)
    assert rows(sessions[0], "targets") == pytest.approx({"explicit": 8})
    conserved(sessions)


def test_charge_after_a_deadline_cannot_be_credited_backwards():
    s, flows, sessions = fixture([0, 8, 0, 0], [goal("past", 1, 8, "manual"), goal("future", 3, 8, "manual")])
    attribute_ev_sessions(s, flows, sessions)
    assert sessions[0]["goal_ids"] == ["future"]
    conserved(sessions)


def test_session_crossing_a_checkpoint_credits_only_energy_delivered_by_that_time():
    s, flows, sessions = fixture([2, 2, 0], [goal("first", 1, 4, "manual"), goal("second", 2, 4, "daily")])
    attribute_ev_sessions(s, flows, sessions)
    assert rows(sessions[0], "targets") == pytest.approx({"first": 2, "second": 2})
    conserved(sessions)


def test_unknown_battery_barrier_does_not_assign_future_consumption_or_stored_energy():
    s, flows, sessions = fixture([8, 0, 0, 0, 0], [goal("trip", 1, 2), goal("after", 4, 8, "daily")])
    s = replace(
        s,
        intervals=tuple(replace(i, ev_state_known=False) if t >= 2 else i for t, i in enumerate(s.intervals)),
    )
    attribute_ev_sessions(s, flows, sessions)
    assert rows(sessions[0], "driving") == pytest.approx({"trip": 2})
    assert sessions[0]["energy_attribution"]["unresolved_kwh"] == pytest.approx(6)
    assert sessions[0]["energy_attribution"]["stored_kwh"] == pytest.approx(0)
    assert "after" not in sessions[0]["goal_ids"]
    conserved(sessions)


def test_trip_reserve_is_retained_stock_with_separate_target_support():
    s, flows, sessions = fixture([8, 0, 0], [goal("trip", 1, 6)])
    s = replace(s, policy=replace(s.policy, arrival_reserve_km=2 / s.policy.consumption_kwh_per_100km * 100))
    attribute_ev_sessions(s, flows, sessions)
    assert rows(sessions[0], "driving") == pytest.approx({"trip": 6})
    assert rows(sessions[0], "targets") == pytest.approx({"trip": 8})
    assert sessions[0]["energy_attribution"]["stored_kwh"] == pytest.approx(2)
    conserved(sessions)


def test_remaining_charge_is_explicit_and_ess_sessions_are_untouched():
    s, flows, sessions = fixture([8, 0, 0], [])
    ess = {"id": "ess", "resource": "ess", "goal_ids": [], "energy_kwh": 3}
    sessions.append(ess)
    attribute_ev_sessions(s, flows, sessions)
    assert sessions[0]["goal_ids"] == []
    assert sessions[0]["energy_attribution"]["stored_kwh"] == pytest.approx(8)
    assert ess == {"id": "ess", "resource": "ess", "goal_ids": [], "energy_kwh": 3}
    conserved(sessions[:1])


def test_real_planner_attaches_conserved_explanations_without_repeated_later_goals():
    s = tiny(hours=2, planning_budget_seconds=12)
    goals = (
        Goal("first", "SYNTHETIC first target", s.observation.at + timedelta(hours=1), 45),
        Goal("later", "SYNTHETIC repeated target", s.intervals[-1].end, 45, "daily"),
    )
    result = Planner().plan(replace(s, goals=goals))
    assert result["valid"], result
    sessions = [item for item in result["sessions"] if item["resource"] == "ev"]
    assert sessions
    assert all("later" not in item["goal_ids"] for item in sessions)
    assert any("first" in item["goal_ids"] for item in sessions)
    conserved(sessions)


def test_trip_target_that_adds_no_information_is_not_repeated_below_driving():
    s, flows, sessions = fixture([6, 0, 0], [goal("trip", 1, 6)])
    attribute_ev_sessions(s, flows, sessions)
    assert rows(sessions[0], "driving") == pytest.approx({"trip": 6})
    assert rows(sessions[0], "targets") == {}
    conserved(sessions)


def test_simultaneous_trips_partition_the_actual_withdrawal():
    s, flows, sessions = fixture([10, 0, 0], [goal("a", 1, 6), goal("b", 1, 4)])
    attribute_ev_sessions(s, flows, sessions)
    assert rows(sessions[0], "driving") == pytest.approx({"a": 6, "b": 4})
    conserved(sessions)
