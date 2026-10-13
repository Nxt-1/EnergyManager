"""Regression tests for grid-import-aware tie-break, accounting and solver configuration."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from energymanager.config import ConfigurationError, Settings
from energymanager.milp_planner import (
    MILP_EV_CHARGE_DELAY_WEIGHT,
    MILP_EV_SESSION_START_WEIGHT,
    MILP_GRID_IMPORT_DELAY_WEIGHT,
    _accounting_delta,
    _economic_objective_value,
    _economic_stage_accounting,
)


def test_grid_purchase_uncertainty_outweighs_three_session_savings() -> None:
    """Observed v0.31.11 pathological trade-off must not be preferred purely by tie-break weights."""
    economic_score = (8 * MILP_EV_SESSION_START_WEIGHT + 14.49471 * MILP_GRID_IMPORT_DELAY_WEIGHT
                      + 237.5121 * MILP_EV_CHARGE_DELAY_WEIGHT)
    aggressive_score = (5 * MILP_EV_SESSION_START_WEIGHT + 19.37491 * MILP_GRID_IMPORT_DELAY_WEIGHT
                        + 213.5933 * MILP_EV_CHARGE_DELAY_WEIGHT)
    assert economic_score < aggressive_score
    assert 5 * MILP_EV_SESSION_START_WEIGHT < 8 * MILP_EV_SESSION_START_WEIGHT


def test_stage_accounting_matches_monetary_objective_and_delta() -> None:
    def var(index: int) -> SimpleNamespace:
        return SimpleNamespace(index=index)

    variables = SimpleNamespace(
        grid_import_kw=[var(0)],
        grid_export_kw=[var(1)],
        stored_energy_kwh=[var(3)],
        ev_preferred_shortfall_kwh=var(4),
        capacity_peak_kw={"2026-10": var(5)},
    )
    ess = SimpleNamespace(capabilities=SimpleNamespace(discharge_efficiency=0.9))
    ev = SimpleNamespace(capabilities=SimpleNamespace(charge_efficiency=0.9))
    price = SimpleNamespace(
        import_energy_eur_per_kwh=0.3,
        export_energy_eur_per_kwh=0.04,
        capacity_tariff_eur_per_kw_month=4.0,
    )
    early = [4.0, 1.0, 0.0, 10.0, 0.5, 3.0]
    late = [8.0, 1.0, 0.0, 10.0, 0.5, 3.0]
    before = _economic_stage_accounting(ess, ev, price, variables, early)
    after = _economic_stage_accounting(ess, ev, price, variables, late)
    delta = _accounting_delta(before, after)
    assert before["economic_objective_eur"] == pytest.approx(
        _economic_objective_value(ess, ev, price, variables, early), abs=0.00001
    )
    assert delta["grid_import_kwh"] == 1.0
    assert delta["grid_import_cost_eur"] == pytest.approx(0.3)
    assert delta["economic_objective_eur"] == pytest.approx(0.3)


def test_planner_defaults_and_optional_thread_benchmark(tmp_path) -> None:
    path = tmp_path / "options.json"
    defaults = Settings.load(path)
    assert defaults.planner.tie_break_seconds == 30
    assert defaults.planner.solver_threads == 1
    assert defaults.benchmark_milp_threads_once is False
    assert defaults.as_options()["planner"] == {"tie_break_seconds": 30, "solver_threads": 1}

    path.write_text(json.dumps({
        "planner": {"tie_break_seconds": 60, "solver_threads": 4},
        "benchmark_milp_threads_once": True,
    }))
    settings = Settings.load(path)
    assert (settings.planner.tie_break_seconds, settings.planner.solver_threads) == (60, 4)
    assert settings.as_options()["benchmark_milp_threads_once"] is True


@pytest.mark.parametrize("planner", [
    {"tie_break_seconds": 0},
    {"tie_break_seconds": 121},
    {"solver_threads": 3},
    {"solver_threads": 0},
])
def test_invalid_planner_limits_rejected(tmp_path, planner) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"planner": planner}))
    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_benchmark_modes_cannot_be_enabled_together(tmp_path) -> None:
    path = tmp_path / "options.json"
    path.write_text('{"benchmark_milp_once":true,"benchmark_milp_threads_once":true}')
    with pytest.raises(ConfigurationError, match="one MILP benchmark"):
        Settings.load(path)
