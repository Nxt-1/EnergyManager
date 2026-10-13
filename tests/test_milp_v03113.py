"""Regression tests for grid-import-aware tie-break, accounting and solver configuration."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from energymanager.config import ConfigurationError, Settings
from energymanager.milp_planner import (
    _accounting_delta,
    _economic_objective_value,
    _economic_stage_accounting,
)


def test_grid_purchase_uncertainty_is_a_bound_not_a_session_weight() -> None:
    import highspy

    from energymanager.hierarchy import refine

    model = highspy.Highs()
    model.setOptionValue("output_flag", False)
    model.setOptionValue("threads", 1)
    choice = model.addVariable(lb=0, ub=1, type=highspy.HighsVarType.kInteger)
    model.setObjective(choice)
    model.run()
    values, _, _, stages, _ = refine(
        model, highspy,
        (("robustness", "weighted_kWh", 14.49471 + (19.37491 - 14.49471) * choice, .05),
         ("operations", "events", 8 - 3 * choice, 0)),
        [0.0], seconds=1, describe=lambda values: (None, {}),
    )
    assert values[0] == 0  # Three fewer sessions cannot consume another 4.88 weighted kWh.
    assert stages[-1].objective == 8


def test_stage_accounting_matches_monetary_objective_and_delta() -> None:
    def var(index: int) -> SimpleNamespace:
        return SimpleNamespace(index=index)

    variables = SimpleNamespace(
        generic_penalty=0.0,
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


def test_planner_defaults_and_custom_time_limit(tmp_path) -> None:
    path = tmp_path / "options.json"
    defaults = Settings.load(path)
    assert defaults.planner.tie_break_seconds == 30
    assert defaults.as_options()["planner"]["tie_break_seconds"] == 30

    path.write_text(json.dumps({"planner": {"tie_break_seconds": 60}}))
    settings = Settings.load(path)
    assert settings.planner.tie_break_seconds == 60
    assert settings.as_options()["planner"]["tie_break_seconds"] == 60


@pytest.mark.parametrize("planner", [
    {"tie_break_seconds": 0},
    {"tie_break_seconds": 121},
])
def test_invalid_planner_limits_rejected(tmp_path, planner) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"planner": planner}))
    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_removed_benchmark_settings_are_ignored_for_older_saved_options(tmp_path) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({
        "benchmark_milp_once": True,
        "benchmark_milp_threads_once": True,
        "planner": {"tie_break_seconds": 45, "solver_threads": 4},
    }))
    settings = Settings.load(path)
    assert settings.planner.tie_break_seconds == 45
    assert settings.as_options()["planner"]["tie_break_seconds"] == 45
    assert "benchmark_milp_once" not in settings.as_options()
    assert "benchmark_milp_threads_once" not in settings.as_options()
