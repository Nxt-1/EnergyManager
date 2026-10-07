from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from energymanager.load_forecast import BackgroundLoadModel, LoadSample

LOCAL_TZ = ZoneInfo("Europe/Brussels")


def _sample(local_time: datetime, power_w: float) -> LoadSample:
    return LoadSample(local_time.astimezone(UTC), power_w)


def test_model_uses_recent_baseline_with_little_history() -> None:
    now = datetime(2026, 10, 4, 12, 7, tzinfo=LOCAL_TZ)
    samples = tuple(
        _sample(now - timedelta(minutes=5 * index), value)
        for index, value in enumerate((600.0, 500.0, 400.0, 700.0))
    )

    forecast = BackgroundLoadModel().build(samples, now_local=now)

    assert forecast.model_stage == "learning"
    assert forecast.points[0].period_start_local.minute == 15
    assert forecast.points[0].method == "recent_baseline"
    assert forecast.points[0].power_w == 550.0
    assert forecast.next_hour_average_power_w() == 550.0
    assert forecast.next_24_hours_energy_kwh() == 13.2


def test_model_learns_same_weekday_slot_when_two_weeks_exist() -> None:
    now = datetime(2026, 10, 19, 12, 0, tzinfo=LOCAL_TZ)  # Monday
    samples = (
        _sample(datetime(2026, 10, 5, 12, 0, tzinfo=LOCAL_TZ), 900.0),
        _sample(datetime(2026, 10, 12, 12, 0, tzinfo=LOCAL_TZ), 1100.0),
        _sample(datetime(2026, 10, 18, 12, 0, tzinfo=LOCAL_TZ), 300.0),
        _sample(datetime(2026, 10, 19, 11, 55, tzinfo=LOCAL_TZ), 400.0),
    )

    forecast = BackgroundLoadModel().build(samples, now_local=now)

    assert forecast.model_stage == "connected"
    assert forecast.points[0].method == "same_weekday"
    assert forecast.points[0].power_w == 1000.0


def test_daily_energy_requires_complete_calendar_day() -> None:
    now = datetime(2026, 10, 4, 12, 0, tzinfo=LOCAL_TZ)
    samples = (_sample(now - timedelta(minutes=5), 1000.0),)

    forecast = BackgroundLoadModel().build(samples, now_local=now)

    assert forecast.daily_energy(now.date()) is None
    tomorrow = forecast.daily_energy(now.date() + timedelta(days=1))
    assert tomorrow is not None
    assert tomorrow.energy_kwh == 24.0


def test_complete_day_handles_dst_fall_back() -> None:
    now = datetime(2026, 10, 24, 12, 0, tzinfo=LOCAL_TZ)
    samples = (_sample(now - timedelta(minutes=5), 1000.0),)

    forecast = BackgroundLoadModel().build(samples, now_local=now)

    dst_day = forecast.daily_energy(datetime(2026, 10, 25).date())
    assert dst_day is not None
    assert dst_day.energy_kwh == 25.0
