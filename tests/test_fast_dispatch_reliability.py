"""Regression coverage for transient HA outages and EV input holding."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from energymanager.actuators import ActuatorRegistry
from energymanager.config import Settings
from energymanager.control_health import ControlHealth
from energymanager.house_state import HouseState
from energymanager.planner_service import PlannerService
from energymanager.tasks import TaskRegistry


class FailingDiagnosticsClient:
    async def set_state(self, *args, **kwargs) -> None:
        raise RuntimeError("502 Bad Gateway")


class FakeController:
    enabled = True
    fault_active = False
    last_error = None
    consecutive_failures = 0
    delivery_error = None

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def apply_dispatch(self, result) -> None:
        self.calls.append("applied")

    async def safe_stop(self, reason: str) -> None:
        self.calls.append("safe_stopped")

    async def safe_zero(self, reason: str) -> None:
        self.calls.append("safe_zero")

    async def publish_command_status(self, *args, **kwargs) -> None:
        self.calls.append("published_command")

    def observe_charging(self, *args, **kwargs) -> None:
        self.calls.append("observed_charging")


def _service(ess: FakeController | None = None, ev: FakeController | None = None) -> PlannerService:
    settings = Settings()
    service = PlannerService(
        FailingDiagnosticsClient(),
        SimpleNamespace(forecast=None),  # type: ignore[arg-type]
        None,
        actuator_registry=ActuatorRegistry(settings),
        task_registry=TaskRegistry(settings.ev),
        ess_controller=ess,  # type: ignore[arg-type]
        ev_controller=ev,  # type: ignore[arg-type]
    )
    service._plan = object()  # type: ignore[assignment]
    service._latest_house_state = HouseState()
    return service


@pytest.mark.parametrize("held", [False, True])
def test_diagnostic_outage_does_not_block_ess_dispatch_or_release_ev_hold(monkeypatch, held: bool) -> None:
    ess = FakeController()
    ev = FakeController()
    service = _service(ess, ev)
    health = ControlHealth(
        state="healthy", ess_available=True, ev_available=True,
        stale_inputs=(), unavailable_inputs=(), reasons=(), replan_required=False,
        held_inputs=("ev.soc",) if held else (),
    )
    monkeypatch.setattr(service, "_evaluate_control_health", lambda state, now: health)
    monkeypatch.setattr("energymanager.planner_service.evaluate_fast_dispatch", lambda *args, **kw:
                        SimpleNamespace(command_results=(), replan_required=False))

    async def fails(*args, **kwargs) -> None:
        raise RuntimeError("502 Bad Gateway")

    monkeypatch.setattr("energymanager.planner_service.publish_fast_dispatch", fails)
    asyncio.run(service._run_fast_dispatch_once())
    assert "applied" in ess.calls
    assert "published_command" in ess.calls
    assert ("applied" in ev.calls) is not held
    assert "safe_stopped" not in ev.calls
    assert ("observed_charging" in ev.calls) is not held


def test_dispatch_loop_survives_exception(monkeypatch) -> None:
    from energymanager import planner_service

    service = _service()
    monkeypatch.setattr(planner_service, "_FAST_DISPATCH_INTERVAL_SECONDS", 0.005)
    calls = 0
    completed = asyncio.Event()

    async def one_cycle() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient HA failure")
        completed.set()

    monkeypatch.setattr(service, "_run_fast_dispatch_once", one_cycle)

    async def run() -> None:
        task = asyncio.create_task(service._fast_dispatch_loop())
        try:
            await asyncio.wait_for(completed.wait(), timeout=0.5)
            assert calls >= 2
            assert service._fast_dispatch_failed is False
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())
