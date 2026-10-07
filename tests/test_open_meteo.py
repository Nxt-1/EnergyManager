from __future__ import annotations

from energymanager.open_meteo import OpenMeteoError, _parse_plane_response


def test_open_meteo_response_is_parsed_to_local_hour_records() -> None:
    payload = {
        "hourly": {
            "time": ["2026-10-03T12:00", "2026-10-03T13:00"],
            "global_tilted_irradiance": [250.0, 300.0],
            "temperature_2m": [15.0, 16.0],
            "cloud_cover": [20.0, 30.0],
            "direct_radiation": [180.0, 210.0],
            "diffuse_radiation": [70.0, 90.0],
        }
    }

    series = _parse_plane_response("front_roof", payload)

    assert series.plane_key == "front_roof"
    assert len(series.hours) == 2
    assert series.hours[0].period_end_local.hour == 12
    assert series.hours[1].direct_radiation_wm2 == 210.0


def test_open_meteo_missing_required_array_is_rejected() -> None:
    payload = {
        "hourly": {
            "time": ["2026-10-03T12:00"],
            "temperature_2m": [15.0],
        }
    }

    try:
        _parse_plane_response("front_roof", payload)
    except OpenMeteoError as exc:
        assert "global_tilted_irradiance" in str(exc)
    else:
        raise AssertionError("Expected OpenMeteoError")


def test_open_meteo_uses_knmi_seamless_for_eight_calendar_days() -> None:
    from energymanager.open_meteo import FORECAST_DAYS, FORECAST_MODEL

    assert FORECAST_MODEL == "knmi_seamless"
    assert FORECAST_DAYS == 8
