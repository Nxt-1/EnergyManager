"""Reproducible synthetic seven-day benchmark and small quantitative counterfactual.

Run: PYTHONPATH=energymanager/src .venv/bin/python tools/benchmark_v3.py
No network, Home Assistant or hardware access. Outputs .v3-evidence/.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from math import pi, sin
from pathlib import Path
from time import perf_counter

from energymanager.actuators import EssActuatorSnapshot, EssCapabilities, EvActuatorSnapshot, EvCapabilities
from energymanager.config import EvSettings, EvWeeklyScheduleEntry
from energymanager.counterfactual import CounterfactualRequest, compare
from energymanager.decision_store import DecisionStore, PlanningSnapshot, canonical
from energymanager.economics import CapacityPeakState, TariffProfile
from energymanager.hierarchy import HierarchyPolicy
from energymanager.planner import EnergyPlan, PlanInterval
from energymanager.requirements import explain_ev_tasks
from energymanager.tasks import TaskRegistry


def scenario(count=672):
    start = datetime(2026, 10, 12, 0, tzinfo=UTC)
    ess = EssActuatorSnapshot(
        "ess", "storage", True, True, "ready", False, 50, 0, EssCapabilities(10, 10, 100, 2000, 2000, 0.95, 0.95)
    )
    ev = EvActuatorSnapshot(
        "ev",
        "flexible_load",
        True,
        True,
        "ready",
        False,
        True,
        50,
        0,
        EvCapabilities(6, 16, 230, True, True, 46.8, 0.9),
    )
    settings = EvSettings(
        battery_capacity_kwh=46.8,
        minimum_soc_percent=50,
        target_soc_percent=80,
        weekly_schedule=(EvWeeklyScheduleEntry((0, 1, 2, 3, 4), "07:00", "18:00", 50, 8),),
    )
    tasks = TaskRegistry(settings).snapshots((ess, ev), now_utc=start, local_tz=UTC)
    intervals = []
    for i in range(count):
        hour = (i % 96) / 4
        pv = max(0, sin((hour - 6) / 12 * pi)) * 2500
        load = 550 + (700 if 18 <= hour < 21 else 0)
        intervals.append(PlanInterval(start + timedelta(minutes=15 * i), load, 0, pv, 0, pv, load - pv))
    plan = EnergyPlan(
        start,
        tuple(intervals),
        actuator_snapshots=(ess, ev),
        tasks=tasks,
        ess_resource=ess.capabilities,
        ess_initial_soc_percent=50,
        requirements=explain_ev_tasks(tasks, (ess, ev), start),
    )
    tariff = TariffProfile("synthetic-flat", start, 0.30, 0.04, 4.0, 2.5)
    peak = CapacityPeakState("2026-10", 4.0, 4.0, start, "synthetic", True, 0, 1)
    return plan, tariff, peak, settings


def main():
    root = Path(".v3-evidence")
    store = DecisionStore(root / "archive")
    plan, tariff, peak, settings = scenario()
    policy = HierarchyPolicy(total_seconds=30, economic_seconds=15)
    frozen = PlanningSnapshot.create(plan, tariff, peak, policy, ev_settings=settings)
    started = perf_counter()
    result = frozen.solve()
    elapsed = perf_counter() - started
    store.save(frozen, result, disposition="benchmark_only")
    # Small forced deadline, PV opportunity at beginning: intervention has measurable costs.
    start = plan.generated_at_utc
    single = EvSettings(
        battery_capacity_kwh=46.8, minimum_soc_percent=60, target_soc_percent=60, departure_time_local="02:00"
    )
    tasks = TaskRegistry(single).snapshots(plan.actuator_snapshots, now_utc=start, local_tz=UTC)
    intervals = tuple(
        replace(
            slot,
            pv_ac_power_w=5000 if i < 4 else 0,
            pv_power_w=5000 if i < 4 else 0,
            net_power_before_control_w=slot.background_load_w - (5000 if i < 4 else 0),
        )
        for i, slot in enumerate(plan.intervals[:8])
    )
    small = replace(
        plan, intervals=intervals, tasks=tasks, requirements=explain_ev_tasks(tasks, plan.actuator_snapshots, start)
    )
    counter_snapshot = PlanningSnapshot.create(
        small, tariff, peak, HierarchyPolicy(total_seconds=6, economic_seconds=3), ev_settings=single
    )
    comparison = compare(counter_snapshot, CounterfactualRequest("forbid_ev", 0, 4))
    store.save(counter_snapshot, comparison["baseline"], disposition="counterfactual_baseline")
    (root / "counterfactual.json").write_text(canonical(comparison) + "\n")
    report = {
        "model": "3.0-preview.2",
        "solver": result.solver_version,
        "threads": 1,
        "seven_day_snapshot_id": frozen.snapshot_id,
        "horizon_intervals": len(plan.intervals),
        "wall_seconds": elapsed,
        "status": result.status,
        "adoption_ready": result.adoption_ready,
        "reason": result.reason,
        "objective_eur": result.milp_objective_eur,
        "ev_sessions": result.ev_session_count,
        "stages": [
            {
                "name": s.name,
                "status": s.status,
                "seconds": s.runtime_seconds,
                "objective": s.objective,
                "gap": s.gap,
                "accepted": s.accepted,
            }
            for s in result.stages
        ],
        "counterfactual_snapshot_id": counter_snapshot.snapshot_id,
        "counterfactual_delta": comparison["delta"],
        "counterfactual_baseline_cost": comparison["baseline"].milp_cost,
        "counterfactual_alternative_cost": comparison["alternative"].milp_cost,
    }
    (root / "benchmark.json").write_text(canonical(report) + "\n")
    print(canonical(report))
    if not result.adoption_ready or comparison["delta"] is None:
        raise SystemExit("benchmark failed; inspect preserved evidence")


if __name__ == "__main__":
    main()
