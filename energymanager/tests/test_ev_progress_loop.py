"""Small deterministic closed loop; full-horizon performance is measured separately."""

from dataclasses import replace
from datetime import timedelta

import pytest

from energymanager.control import FastControl
from energymanager.domain import Goal, Interval, Snapshot, json_data, time_grid
from energymanager.ev_progress import EVProgress
from energymanager.execution import execution_identity, freeze_execution
from energymanager.live_inputs import Reading
from energymanager.planner import Planner
from energymanager.store import Store
from energymanager.validation import validate
from test_ev_progress import AT, C, P, sample


def test_real_replans_keep_49_percent_and_finish_once_with_persistent_total(tmp_path):
    c = replace(C, phases=(1,))
    p = replace(P, planning_budget_seconds=2, automatic_peak_kw=3.5)
    goals = (Goal("first", "SYNTHETIC top-up", AT + timedelta(hours=1), target_soc_percent=50),
             Goal("overlap", "SYNTHETIC same stock", AT + timedelta(minutes=50), target_soc_percent=50))
    path = tmp_path / "progress.sqlite"
    store = Store(path)
    progress = EVProgress(store)
    control = FastControl(c, p)
    old = None
    total = 100.0
    stored = power = 0.0
    inputs = []
    plans = []
    for seconds in range(2100):
        at = AT + timedelta(seconds=seconds)
        if seconds == 400:
            store.close()
            store = Store(path)
            progress = EVProgress(store)
            control = FastControl(c, p, store.get("ev_task"))
        raw = replace(sample(seconds), ev_power_kw=power, house_kw=.4, ess_kwh=c.ess_min_kwh)
        reading = Reading.parse("sensor.synthetic_eto", {"state": str(total),
            "attributes": {"unit_of_measurement": "kWh"}}, at, "kWh", 30, nonnegative=True)
        observation = progress.update(raw, reading, "sensor.synthetic_eto", c, p)
        if seconds in (0, 120, 240, 360, 480, 600, 720, 900, 1200, 1800):
            if seconds == 600:
                goals = (replace(goals[0], revision=2), goals[1])
            points = time_grid(at, 1, boundaries=tuple(g.deadline for g in goals))
            s = Snapshot("synthetic-" + str(seconds), 1, observation, at, "SYNTHETIC grid-only",
                tuple(Interval(a, b, .4, 0, 0) for a, b in zip(points, points[1:])), goals, c, p)
            s = freeze_execution(s, old, {"phase": 1, "ready_at": at.isoformat()})
            inputs.append(s.observation.ev_kwh)
            result = Planner().plan(s)
            assert result["valid"], result
            assert validate(s, result["flows"], result["service"]) == []
            assert result["execution_id"] == execution_identity(result)
            plans.append(result)
            old = result
        command = control.tick(observation, at, old, 1)
        store.put("ev_task", json_data(control.ev_task))
        power = command.ev_kw
        total += power / 3600
        stored += power * c.ev_efficiency / 3600
    assert inputs == sorted(inputs)
    assert all(plan["id"] != other["id"] for plan, other in zip(plans, plans[1:]))
    assert stored >= .468 - .02
    authorized = max(plans[0]["flows"]["ev_energy"]) - 22.932
    assert stored <= authorized + .001  # Meter/control quantum, not another top-up.
    assert all(max(r["flows"]["ev_energy"]) <= 22.932 + authorized + .001 for r in plans)
    assert power == 0, {"stored": stored, "task": control.ev_task,
        "plans": [(r["flows"]["ev_energy"][0], max(r["flows"]["ev_energy"]),
                   sum(r["flows"]["grid_ev"])) for r in plans]}
    assert sum(plans[-1]["flows"]["grid_ev"]) == pytest.approx(0)
    assert observation.ev_progress["reported_kwh"] == 22.932
    assert observation.ev_kwh == pytest.approx(22.932 + stored)
    store.close()
