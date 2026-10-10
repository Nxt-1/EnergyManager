from __future__ import annotations

from datetime import UTC, datetime, timedelta

from energymanager.control_health import evaluate_control_health
from energymanager.house_state import HouseState

_NOW = datetime(2026, 10, 10, 15, 30, tzinfo=UTC)


def _state(*, age_seconds: int = 0, ev_connected: bool = True) -> HouseState:
    state = HouseState()
    observed = _NOW - timedelta(seconds=age_seconds)
    values = {
        "grid.import_power": 500.0,
        "grid.export_power": 0.0,
        "ess.soc": 60.0,
        "ess.power": 400.0,
        "ev.connected": ev_connected,
        "ev.soc": 50.0,
    }
    for key, value in values.items():
        reading = state.ensure_input(key, f"sensor.{key.replace('.', '_')}")
        reading.set_valid(value, unit=None, observed_at_utc=observed, source_last_updated=None)
    return state


def test_control_health_is_healthy_with_fresh_inputs() -> None:
    health = evaluate_control_health(
        _state(),
        now_utc=_NOW,
        ess_control_enabled=True,
        ev_control_enabled=True,
    )

    assert health.state == "healthy"
    assert health.ess_available is True
    assert health.ev_available is True
    assert health.replan_required is False


def test_stale_ess_inputs_force_safe_fallback() -> None:
    health = evaluate_control_health(
        _state(age_seconds=60),
        now_utc=_NOW,
        ess_control_enabled=True,
        ev_control_enabled=True,
    )

    assert health.state == "safe_fallback"
    assert health.ess_available is False
    assert "grid.import_power" in health.stale_inputs
    assert health.replan_required is True


def test_disconnected_ev_degrades_without_disabling_ess() -> None:
    health = evaluate_control_health(
        _state(ev_connected=False),
        now_utc=_NOW,
        ess_control_enabled=True,
        ev_control_enabled=True,
    )

    assert health.state == "degraded"
    assert health.ess_available is True
    assert health.ev_available is False
    assert "ev:disconnected" in health.reasons
    assert health.replan_required is True
