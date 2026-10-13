"""Regression tests for the opt-in, read-only solver time-limit benchmark."""

from __future__ import annotations

from types import SimpleNamespace

from energymanager import milp_benchmark
from energymanager.config import Settings


class FakeQueue:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []

    def put(self, item: dict[str, object]) -> None:
        self.items.append(item)


def test_benchmark_uses_four_limits_and_identical_input_objects(monkeypatch) -> None:
    observed: list[tuple[object, object, object, float]] = []
    reference = object()
    profile = object()
    capacity = object()

    def fake_solve(frame, price, capacity_state, *, tie_break_max_time_seconds):
        observed.append((frame, price, capacity_state, tie_break_max_time_seconds))
        return SimpleNamespace(
            plan=object(),
            economic_stage_summary={"ev_session_count": 10, "ev_charge_delay_score_kwh_days": 240.0},
            selected_stage_summary={"ev_session_count": 8, "ev_charge_delay_score_kwh_days": 235.0},
            economic_solve_time_seconds=2.5,
            tie_break_solve_time_seconds=tie_break_max_time_seconds,
            economic_stage_status="optimal",
            tie_break_status="feasible_time_limit",
            selected_solution_stage="tie_break",
            mip_gap=0.03,
            validation_status="passed",
            first_stage_objective_eur=1.0,
            milp_objective_eur=1.005,
        )

    monkeypatch.setattr(milp_benchmark, "evaluate_plan_milp", fake_solve)
    monkeypatch.setattr(milp_benchmark.os, "nice", lambda increment: 0)
    queue = FakeQueue()
    milp_benchmark._benchmark_worker(queue, reference, profile, capacity)

    assert [item[3] for item in observed] == [10.0, 30.0, 60.0, 120.0]
    assert all(item[:3] == (reference, profile, capacity) for item in observed)
    assert len(queue.items) == 5
    assert [item["selected_ev_sessions"] for item in queue.items[:4]] == [8, 8, 8, 8]
    assert queue.items[-1] == {"complete": True}


def test_benchmark_setting_disabled_by_default() -> None:
    settings = Settings()
    assert settings.benchmark_milp_once is False
    assert settings.as_options()["benchmark_milp_once"] is False


def test_thread_benchmark_uses_single_case_and_provides_thread_count(monkeypatch) -> None:
    reference = object()
    profile = object()
    capacity = object()
    calls = []

    def fake_solve(frame, price, capacity_state, *, tie_break_max_time_seconds, solver_threads):
        calls.append((frame, price, capacity_state, tie_break_max_time_seconds, solver_threads))
        return SimpleNamespace(
            plan=object(),
            economic_stage_summary={"ev_session_count": 9},
            selected_stage_summary={"ev_session_count": 6},
            economic_stage_accounting={"grid_import_kwh": 20.0},
            selected_stage_accounting={"grid_import_kwh": 20.0},
            economic_accounting_delta={"grid_import_kwh": 0.0},
            economic_solve_time_seconds=2.0,
            tie_break_solve_time_seconds=30.0,
            economic_stage_status="optimal",
            tie_break_status="feasible_time_limit",
            selected_solution_stage="tie_break",
            mip_gap=0.05,
            validation_status="passed",
            first_stage_objective_eur=1.0,
            milp_objective_eur=1.01,
        )

    monkeypatch.setattr(milp_benchmark, "evaluate_plan_milp", fake_solve)
    monkeypatch.setattr(milp_benchmark.os, "nice", lambda increment: 0)
    queue = FakeQueue()
    milp_benchmark._benchmark_worker(queue, reference, profile, capacity, solver_threads=4)
    assert calls == [(reference, profile, capacity, 30.0, 4)]
    assert queue.items[0]["threads"] == 4
    assert queue.items[0]["economic_accounting_delta"] == {"grid_import_kwh": 0.0}
    assert queue.items[-1] == {"complete": True}
