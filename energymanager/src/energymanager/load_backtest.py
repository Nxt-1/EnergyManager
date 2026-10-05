"""Historical evaluation for the background-load predictor."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from statistics import median

from .load_forecast import (
    FORECAST_INTERVAL_MINUTES,
    LOCAL_TIMEZONE,
    BackgroundLoadModel,
    LoadSample,
)

BACKTEST_VERSION = "2026-10-05-evaluator-v1"
HORIZON_HOURS = (1, 3, 6, 12, 24)
MODEL_NAMES = ("energy_manager", "persistence", "yesterday", "last_week")
_EVALUATION_DAYS = 21
_MINIMUM_HISTORY_DAYS = 8
_ISSUE_HOURS = (0, 12)
_MIN_ENERGY_COVERAGE = 0.75


@dataclass(frozen=True, slots=True)
class BacktestMetric:
    """Accuracy summary for one candidate model and forecast horizon."""

    model: str
    horizon_hours: int
    mae_w: float
    bias_w: float
    p90_abs_error_w: float
    energy_mae_kwh: float | None
    points: int
    issue_count: int
    coverage: float


@dataclass(frozen=True, slots=True)
class ErrorBreakdown:
    """Current-model error summary for one contextual subset."""

    mae_w: float
    bias_w: float
    p90_abs_error_w: float
    points: int


@dataclass(frozen=True, slots=True)
class BackgroundLoadBacktest:
    """Rolling-origin evaluation of the current model and simple baselines."""

    generated_at_utc: datetime
    evaluation_start_local: datetime
    evaluation_end_local: datetime
    issue_count: int
    metrics: tuple[BacktestMetric, ...]
    best_by_horizon: dict[int, str]
    daypart_breakdown: dict[str, ErrorBreakdown]
    daytype_breakdown: dict[str, ErrorBreakdown]

    def metric(self, model: str, horizon_hours: int) -> BacktestMetric | None:
        """Return one metric tuple when present."""
        return next(
            (
                metric
                for metric in self.metrics
                if metric.model == model and metric.horizon_hours == horizon_hours
            ),
            None,
        )


@dataclass(slots=True)
class _Accumulator:
    errors_w: list[float]
    energy_errors_kwh: list[float]
    possible_points: int = 0
    issue_count: int = 0

    def add_point(self, predicted_w: float, actual_w: float) -> None:
        self.errors_w.append(predicted_w - actual_w)

    def add_energy_error(self, predicted_kwh: float, actual_kwh: float) -> None:
        self.energy_errors_kwh.append(predicted_kwh - actual_kwh)
        self.issue_count += 1


class BackgroundLoadBacktester:
    """Evaluate model structure without changing or fitting production parameters."""

    def __init__(self, model: BackgroundLoadModel | None = None) -> None:
        self._model = model or BackgroundLoadModel()

    def evaluate(
        self,
        samples: tuple[LoadSample, ...],
        *,
        now_local: datetime,
        generated_at_utc: datetime | None = None,
    ) -> BackgroundLoadBacktest | None:
        if now_local.tzinfo is None:
            raise ValueError("now_local must be timezone-aware")
        if not samples:
            return None

        ordered = tuple(sorted(samples, key=lambda item: item.observed_at_utc))
        first = ordered[0].observed_at_utc
        last = ordered[-1].observed_at_utc
        if (last - first) < timedelta(days=_MINIMUM_HISTORY_DAYS):
            return None

        actual = _aggregate_actual_buckets(ordered)
        evaluation_end_local = last.astimezone(now_local.tzinfo) - timedelta(hours=24)
        evaluation_start_local = max(
            first.astimezone(now_local.tzinfo) + timedelta(days=7),
            evaluation_end_local - timedelta(days=_EVALUATION_DAYS),
        )
        issues = _issue_times(evaluation_start_local, evaluation_end_local)
        if not issues:
            return None

        metrics: dict[tuple[str, int], _Accumulator] = {
            (model, horizon): _Accumulator([], [])
            for model in MODEL_NAMES
            for horizon in HORIZON_HOURS
        }
        daypart_errors: dict[str, list[float]] = defaultdict(list)
        daytype_errors: dict[str, list[float]] = defaultdict(list)
        evaluated_issues = 0

        for issue_local in issues:
            issue_utc = issue_local.astimezone(UTC)
            training = tuple(sample for sample in ordered if sample.observed_at_utc < issue_utc)
            if not training:
                continue
            forecast = self._model.build(
                training,
                now_local=issue_local,
                generated_at_utc=issue_utc,
            )
            points = forecast.points[: max(HORIZON_HOURS) * 4]
            if not points:
                continue
            persistence_w = _recent_baseline(training)
            issue_used = False

            for horizon in HORIZON_HOURS:
                target_points = points[: horizon * 4]
                current_predictions = {
                    _bucket_key(point.period_start_local): point.power_w
                    for point in target_points
                }
                predictions = {
                    "energy_manager": current_predictions,
                    "persistence": {
                        _bucket_key(point.period_start_local): persistence_w
                        for point in target_points
                    },
                    "yesterday": _offset_predictions(target_points, actual, days=1),
                    "last_week": _offset_predictions(target_points, actual, days=7),
                }

                for model_name, model_predictions in predictions.items():
                    accumulator = metrics[(model_name, horizon)]
                    accumulator.possible_points += len(target_points)
                    predicted_energy_wh = 0.0
                    actual_energy_wh = 0.0
                    energy_points = 0

                    for point in target_points:
                        key = _bucket_key(point.period_start_local)
                        actual_w = actual.get(key)
                        predicted_w = model_predictions.get(key)
                        if actual_w is None or predicted_w is None:
                            continue
                        accumulator.add_point(predicted_w, actual_w)
                        predicted_energy_wh += predicted_w * FORECAST_INTERVAL_MINUTES / 60.0
                        actual_energy_wh += actual_w * FORECAST_INTERVAL_MINUTES / 60.0
                        energy_points += 1

                        if model_name == "energy_manager" and horizon == 24:
                            error = predicted_w - actual_w
                            daypart_errors[_daypart(point.period_start_local)].append(error)
                            daytype_errors[_daytype(point.period_start_local)].append(error)
                            issue_used = True

                    minimum_points = max(1, int(len(target_points) * _MIN_ENERGY_COVERAGE))
                    if energy_points >= minimum_points:
                        accumulator.add_energy_error(
                            predicted_energy_wh / 1000.0,
                            actual_energy_wh / 1000.0,
                        )
            if issue_used:
                evaluated_issues += 1

        metric_rows = tuple(
            _metric_from_accumulator(model, horizon, accumulator)
            for (model, horizon), accumulator in sorted(metrics.items())
            if accumulator.errors_w
        )
        if not metric_rows:
            return None

        best_by_horizon: dict[int, str] = {}
        for horizon in HORIZON_HOURS:
            candidates = [
                metric
                for metric in metric_rows
                if metric.horizon_hours == horizon
                and metric.coverage >= 0.50
                and metric.points >= horizon * 4
            ]
            if candidates:
                best_by_horizon[horizon] = min(candidates, key=lambda item: item.mae_w).model

        return BackgroundLoadBacktest(
            generated_at_utc=generated_at_utc or datetime.now(UTC),
            evaluation_start_local=issues[0],
            evaluation_end_local=issues[-1],
            issue_count=evaluated_issues,
            metrics=metric_rows,
            best_by_horizon=best_by_horizon,
            daypart_breakdown={
                name: _breakdown(errors)
                for name, errors in sorted(daypart_errors.items())
                if errors
            },
            daytype_breakdown={
                name: _breakdown(errors)
                for name, errors in sorted(daytype_errors.items())
                if errors
            },
        )


def _aggregate_actual_buckets(samples: tuple[LoadSample, ...]) -> dict[tuple[date, int], float]:
    grouped: dict[tuple[date, int], list[float]] = defaultdict(list)
    for sample in samples:
        local = sample.observed_at_utc.astimezone(LOCAL_TIMEZONE)
        grouped[_bucket_key(local)].append(max(0.0, sample.power_w))
    return {key: float(median(values)) for key, values in grouped.items()}


def _issue_times(start_local: datetime, end_local: datetime) -> tuple[datetime, ...]:
    start_date = start_local.date()
    end_date = end_local.date()
    issues: list[datetime] = []
    current = start_date
    while current <= end_date:
        for hour in _ISSUE_HOURS:
            issue = datetime.combine(current, time(hour=hour), tzinfo=start_local.tzinfo)
            if start_local <= issue <= end_local:
                issues.append(issue)
        current += timedelta(days=1)
    return tuple(issues)


def _offset_predictions(
    points: tuple | list,
    actual: dict[tuple[date, int], float],
    *,
    days: int,
) -> dict[tuple[date, int], float]:
    predictions: dict[tuple[date, int], float] = {}
    for point in points:
        key = _bucket_key(point.period_start_local)
        source_key = (key[0] - timedelta(days=days), key[1])
        source = actual.get(source_key)
        if source is not None:
            predictions[key] = source
    return predictions


def _recent_baseline(samples: tuple[LoadSample, ...]) -> float:
    latest = max(sample.observed_at_utc for sample in samples)
    recent = [
        max(0.0, sample.power_w)
        for sample in samples
        if latest - sample.observed_at_utc <= timedelta(hours=3)
    ]
    values = recent if recent else [max(0.0, sample.power_w) for sample in samples]
    return float(median(values))


def _metric_from_accumulator(model: str, horizon: int, accumulator: _Accumulator) -> BacktestMetric:
    errors = accumulator.errors_w
    absolute = [abs(error) for error in errors]
    energy_absolute = [abs(error) for error in accumulator.energy_errors_kwh]
    coverage = len(errors) / accumulator.possible_points if accumulator.possible_points else 0.0
    return BacktestMetric(
        model=model,
        horizon_hours=horizon,
        mae_w=sum(absolute) / len(absolute),
        bias_w=sum(errors) / len(errors),
        p90_abs_error_w=_percentile(absolute, 0.90),
        energy_mae_kwh=(sum(energy_absolute) / len(energy_absolute)) if energy_absolute else None,
        points=len(errors),
        issue_count=accumulator.issue_count,
        coverage=coverage,
    )


def _breakdown(errors: list[float]) -> ErrorBreakdown:
    absolute = [abs(error) for error in errors]
    return ErrorBreakdown(
        mae_w=sum(absolute) / len(absolute),
        bias_w=sum(errors) / len(errors),
        p90_abs_error_w=_percentile(absolute, 0.90),
        points=len(errors),
    )


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def _bucket_key(local: datetime) -> tuple[date, int]:
    slot = local.hour * 4 + local.minute // FORECAST_INTERVAL_MINUTES
    return local.date(), slot


def _daypart(local: datetime) -> str:
    if local.hour < 6:
        return "night"
    if local.hour < 12:
        return "morning"
    if local.hour < 18:
        return "afternoon"
    return "evening"


def _daytype(local: datetime) -> str:
    return "weekend" if local.weekday() >= 5 else "weekday"
