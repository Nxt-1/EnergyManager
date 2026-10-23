from dataclasses import replace

import pytest

from energymanager.planner import Planner
from energymanager.validation import validate
from test_first_slice import tiny


def test_ess_precharge_reproduces_independent_smaller_peak_arithmetic():
    s = tiny(hours=0.5, house=1, ess=2.8, planning_budget_seconds=10)
    s = replace(
        s,
        intervals=tuple(
            replace(i, house_kw=5) if (i.start - s.observation.at).total_seconds() >= 900 else i
            for i in s.intervals
        ),
    )
    result = Planner().plan(s)
    assert result["valid"], result
    assert any(r["kind"] == "peak_precharge" for r in result["reasons"]), result["stages"]
    assert sum(result["flows"]["grid_store"][:4]) > 0
    expected = (5 + (0.95 * 0.95) * 1) / (1 + 0.95 * 0.95)
    assert result["summary"]["peak_kw"] == pytest.approx(expected, abs=0.01)
    assert result["summary"]["comparison_eur"] < result["reference_summary"]["comparison_eur"]
    assert validate(s, result["flows"]) == []


def test_no_grid_arbitrage_below_incurred_peak():
    s = tiny(hours=0.5, house=1, ess=2.8, planning_budget_seconds=8)
    s = replace(
        s,
        observation=replace(s.observation, monthly_peak_kw=7),
        intervals=tuple(
            replace(i, house_kw=5) if (i.start - s.observation.at).total_seconds() >= 900 else i
            for i in s.intervals
        ),
    )
    result = Planner().plan(s)
    assert result["valid"]
    assert sum(result["flows"]["grid_store"]) == pytest.approx(0)


def test_scarce_solar_can_exceed_normal_ceiling_without_grid():
    s = tiny(hours=3, ev=47, ess=14, house=0, planning_budget_seconds=12)
    s = replace(
        s, intervals=tuple(replace(i, pv_ac_kw=4) if t < 12 else i for t, i in enumerate(s.intervals))
    )
    result = Planner().plan(s)
    assert result["valid"], result
    assert result["flows"]["ev_energy"][-1] > 48.05, result["reasons"]
    assert sum(result["flows"]["grid_ev"]) == pytest.approx(0)
    assert any(r["kind"] == "scarce_solar" for r in result["reasons"])


def test_plentiful_later_solar_keeps_current_opportunity_at_80_percent():
    s = tiny(hours=6, ev=47, ess=14, house=0, planning_budget_seconds=20)
    s = replace(
        s,
        intervals=tuple(
            replace(i, pv_ac_kw=4 if t < 12 else 8 if t >= 24 else 0) for t, i in enumerate(s.intervals)
        ),
    )
    result = Planner().plan(s)
    assert result["valid"], result
    assert max(result["flows"]["ev_energy"][:13]) <= 48.0001, result["reasons"]
