from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from energymanager.load_backtest import BackgroundLoadBacktester
from energymanager.load_forecast import LoadSample

LOCAL_TZ = ZoneInfo("Europe/Brussels")


def _weekly_samples(days: int = 40) -> tuple[LoadSample, ...]:
    start = datetime(2026, 9, 1, 0, 0, tzinfo=LOCAL_TZ)
    rows: list[LoadSample] = []
    for index in range(days * 24 * 12):
        local = start + timedelta(minutes=5 * index)
        power = 450.0
        if local.weekday() < 5:
            power += 100.0
        if 6 <= local.hour < 9:
            power += 250.0
        if 18 <= local.hour < 21:
            power += 700.0
        rows.append(LoadSample(local.astimezone(UTC), power))
    return tuple(rows)


def test_backtest_requires_enough_history() -> None:
    start = datetime(2026, 10, 1, 0, 0, tzinfo=LOCAL_TZ)
    samples = tuple(
        LoadSample((start + timedelta(hours=index)).astimezone(UTC), 500.0)
        for index in range(7 * 24)
    )

    result = BackgroundLoadBacktester().evaluate(
        samples,
        now_local=datetime(2026, 10, 8, 12, 0, tzinfo=LOCAL_TZ),
    )

    assert result is None


def test_backtest_evaluates_current_model_and_baselines_without_lookahead() -> None:
    samples = _weekly_samples()

    result = BackgroundLoadBacktester().evaluate(
        samples,
        now_local=datetime(2026, 10, 10, 12, 0, tzinfo=LOCAL_TZ),
    )

    assert result is not None
    assert result.issue_count > 0
    current_24h = result.metric("energy_manager", 24)
    assert current_24h is not None
    assert current_24h.coverage == 1.0
    assert current_24h.issue_coverage == 1.0
    assert current_24h.total_energy_mae_kwh == 0.0
    assert current_24h.energy_bias_kwh == 0.0
    assert current_24h.timing_mismatch_kwh == 0.0
    assert current_24h.peak_underprediction_w == 0.0
    assert current_24h.p90_peak_underprediction_w == 0.0
    assert current_24h.mae_w == 0.0
    assert result.best_by_horizon[24] == "energy_manager"
    assert result.best_power_by_horizon[24] == "energy_manager"
    assert set(result.daypart_breakdown) == {"night", "morning", "afternoon", "evening"}
    assert set(result.daytype_breakdown) == {"weekday", "weekend"}


def test_backtest_reports_baseline_coverage_and_energy_error() -> None:
    samples = _weekly_samples()

    result = BackgroundLoadBacktester().evaluate(
        samples,
        now_local=datetime(2026, 10, 10, 12, 0, tzinfo=LOCAL_TZ),
    )

    assert result is not None
    persistence = result.metric("persistence", 6)
    yesterday = result.metric("yesterday", 6)
    last_week = result.metric("last_week", 6)
    assert persistence is not None
    assert yesterday is not None
    assert last_week is not None
    assert persistence.total_energy_mae_kwh is not None
    assert persistence.energy_bias_kwh is not None
    assert persistence.timing_mismatch_kwh is not None
    assert persistence.peak_underprediction_w is not None
    assert persistence.p90_peak_underprediction_w is not None
    assert yesterday.coverage > 0.9
    assert last_week.coverage > 0.9
    assert last_week.mae_w == 0.0


def test_backtest_scores_models_on_same_common_intervals() -> None:
    samples = _weekly_samples()
    hole_start = datetime(2026, 10, 1, 12, 0, tzinfo=LOCAL_TZ)
    hole_end = hole_start + timedelta(hours=6)
    samples = tuple(
        sample
        for sample in samples
        if not hole_start <= sample.observed_at_utc.astimezone(LOCAL_TZ) < hole_end
    )

    result = BackgroundLoadBacktester().evaluate(
        samples,
        now_local=datetime(2026, 10, 10, 12, 0, tzinfo=LOCAL_TZ),
    )

    assert result is not None
    metrics = [metric for metric in result.metrics if metric.horizon_hours == 24]
    assert len(metrics) == 4
    assert len({metric.points for metric in metrics}) == 1
    assert len({metric.issue_count for metric in metrics}) == 1

    current = result.metric("energy_manager", 24)
    last_week = result.metric("last_week", 24)
    assert current is not None
    assert last_week is not None
    assert last_week.coverage < current.coverage
    assert last_week.issue_coverage <= current.issue_coverage
