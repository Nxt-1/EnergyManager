from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from energymanager.pv_forecast import (
    PV_PLANES,
    PlaneWeatherHour,
    PlaneWeatherSeries,
    build_pv_forecast,
    calibrated_group_factor,
)

LOCAL_TZ = ZoneInfo("Europe/Brussels")


def _series(plane_key: str, values: list[tuple[datetime, float, float]]) -> PlaneWeatherSeries:
    return PlaneWeatherSeries(
        plane_key=plane_key,
        hours=tuple(
            PlaneWeatherHour(
                period_end_local=timestamp,
                global_tilted_irradiance_wm2=irradiance,
                temperature_c=temperature,
                cloud_cover_pct=25.0,
                direct_radiation_wm2=400.0,
                diffuse_radiation_wm2=100.0,
            )
            for timestamp, irradiance, temperature in values
        ),
    )


def _all_plane_series(period_end: datetime, irradiance: float = 500.0) -> dict[str, PlaneWeatherSeries]:
    values = [(period_end, irradiance, 20.0)]
    return {plane.key: _series(plane.key, values) for plane in PV_PLANES}


def test_four_physical_planes_match_installation() -> None:
    planes = {plane.key: plane for plane in PV_PLANES}

    assert planes["front_roof"].peak_power_w == 3280.0
    assert planes["rear_roof"].peak_power_w == 1640.0
    assert planes["rear_flat"].peak_power_w == 820.0
    assert planes["shed"].peak_power_w == 6180.0
    assert planes["shed"].tilt_deg == 9.5
    assert planes["shed"].azimuth_deg == -40.0
    assert planes["shed"].temperature_coefficient_per_c == pytest.approx(-0.0029)


def test_weak_irradiance_blends_seed_calibration_back_to_physical_model() -> None:
    timestamp = datetime(2026, 9, 20, 15, 0, tzinfo=LOCAL_TZ)

    assert calibrated_group_factor("front", timestamp, 75.0) == pytest.approx(1.0)
    assert calibrated_group_factor("rear", timestamp, 75.0) == pytest.approx(1.0)


def test_rear_seed_calibration_changes_with_observed_season() -> None:
    early = datetime(2026, 8, 27, 16, 0, tzinfo=LOCAL_TZ)
    late = datetime(2026, 9, 26, 16, 0, tzinfo=LOCAL_TZ)

    early_factor = calibrated_group_factor("rear", early, 500.0)
    late_factor = calibrated_group_factor("rear", late, 500.0)

    assert early_factor == pytest.approx(0.57)
    assert late_factor == pytest.approx(0.50)
    assert late_factor < early_factor


def test_rear_seasonal_factor_clamps_outside_observed_window() -> None:
    before = datetime(2026, 1, 15, 16, 0, tzinfo=LOCAL_TZ)
    first_anchor = datetime(2026, 8, 27, 16, 0, tzinfo=LOCAL_TZ)
    after = datetime(2026, 12, 1, 16, 0, tzinfo=LOCAL_TZ)
    last_anchor = datetime(2026, 9, 26, 16, 0, tzinfo=LOCAL_TZ)

    assert calibrated_group_factor("rear", before, 500.0) == calibrated_group_factor(
        "rear", first_anchor, 500.0
    )
    assert calibrated_group_factor("rear", after, 500.0) == calibrated_group_factor(
        "rear", last_anchor, 500.0
    )


def test_shed_has_no_empirical_seed_correction() -> None:
    timestamp = datetime(2026, 9, 26, 16, 0, tzinfo=LOCAL_TZ)

    assert calibrated_group_factor("shed", timestamp, 800.0) == pytest.approx(1.0)


def test_forecast_builds_group_and_total_power() -> None:
    period_end = datetime(2026, 9, 26, 14, 0, tzinfo=LOCAL_TZ)
    forecast = build_pv_forecast(
        _all_plane_series(period_end),
        generated_at_utc=datetime(2026, 9, 26, 12, 0, tzinfo=UTC),
    )

    point = forecast.points[0]
    assert point.front_power_w > 0
    assert point.rear_power_w > 0
    assert point.shed_power_w > 0
    assert point.total_power_w == pytest.approx(
        point.front_power_w + point.rear_power_w + point.shed_power_w
    )
    assert point.front_power_w <= point.front_raw_power_w
    assert point.rear_power_w <= point.rear_raw_power_w
    assert point.shed_power_w == pytest.approx(point.shed_raw_power_w)


def test_daily_energy_assigns_midnight_ending_hour_to_previous_day() -> None:
    target = date(2026, 10, 3)
    points = [
        datetime(2026, 10, 3, 23, 0, tzinfo=LOCAL_TZ),
        datetime(2026, 10, 4, 0, 0, tzinfo=LOCAL_TZ),
        datetime(2026, 10, 4, 1, 0, tzinfo=LOCAL_TZ),
    ]
    values = [(timestamp, 200.0, 15.0) for timestamp in points]
    series = {plane.key: _series(plane.key, values) for plane in PV_PLANES}
    forecast = build_pv_forecast(series)

    daily = forecast.daily_energy(target)

    assert daily is not None
    expected = forecast.points[0].total_power_w + forecast.points[1].total_power_w
    assert daily.total_kwh == pytest.approx(expected / 1000.0)


def test_next_hour_returns_first_interval_ending_after_now() -> None:
    start = datetime(2026, 10, 3, 12, 0, tzinfo=LOCAL_TZ)
    times = [start + timedelta(hours=index) for index in range(1, 4)]
    values = [(timestamp, 300.0, 15.0) for timestamp in times]
    series = {plane.key: _series(plane.key, values) for plane in PV_PLANES}
    forecast = build_pv_forecast(series)

    point = forecast.next_hour(start + timedelta(minutes=30))

    assert point is not None
    assert point.period_end_local == start + timedelta(hours=1)


def test_missing_plane_is_rejected() -> None:
    period_end = datetime(2026, 10, 3, 14, 0, tzinfo=LOCAL_TZ)
    series = _all_plane_series(period_end)
    del series["shed"]

    with pytest.raises(ValueError, match="Missing PV plane"):
        build_pv_forecast(series)
