"""Compare budgets and research-only formulation switches on one immutable archive.

No default settings or archived inputs are changed. Run from the repository with PYTHONPATH=energymanager/src.
"""
import argparse
import functools
import json
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import highspy

from energymanager import milp_planner
from energymanager.decision_store import DecisionStore, PlanningSnapshot, canonical, decode


def metrics(plan):
    runs, length = [], 0
    for slot in plan.intervals:
        if slot.scheduled_load_w > 1:
            length += 1
        elif length:
            runs.append(length)
            length = 0
    if length:
        runs.append(length)
    return {"sessions": len(runs), "short_sessions_under_hour": sum(n < 4 for n in runs),
            "minimum_session_minutes": min(runs, default=0) * 15}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot_id")
    parser.add_argument("--archive", type=Path, default=Path(".v3-evidence/archive"))
    parser.add_argument("--candidate", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--stability", action="store_true", help="Freeze +150 W in first two slots and prior schedule")
    args = parser.parse_args()
    store = DecisionStore(args.archive)
    snapshot, document = store.read(args.snapshot_id)
    data = snapshot.inputs()
    if args.stability:
        frame = replace(data["frame"], intervals=tuple(
            replace(slot, background_load_w=slot.background_load_w + 150,
                    net_power_before_control_w=slot.net_power_before_control_w + 150) if i < 2 else slot
            for i, slot in enumerate(data["frame"].intervals)
        ))
        snapshot = PlanningSnapshot.create(frame, data["profile"], data["capacity_state"], data["policy"],
                                           previous_plan=decode(document["evaluation"]["plan"]),
                                           ev_settings=data["ev_settings"])
        store.save(snapshot, snapshot.solve(), disposition="stability_benchmark")
        data = snapshot.inputs()
    results = []
    original_refine = milp_planner.refine
    original_starts = milp_planner._add_ev_session_start_variables
    cases = [("baseline", n) for n in (30, 60, 120)] + [
        ("nonconstant_budget", 30), ("integer_starts", 30), ("cold_refinement", 30), ("presolve_off", 30)
    ]
    if args.candidate:
        cases = [("nonconstant_budget", n) for n in (30, 60, 120)]
    for variant, budget in cases:
        milp_planner.refine = functools.partial(original_refine, warm_start=variant != "cold_refinement",
                                               allocate_nonconstant=variant == "nonconstant_budget")

        def starts(model, hs, variables, values):
            result = original_starts(model, hs, variables, values)
            if variant == "integer_starts":
                for variable in variables.ev_session_start.values():
                    model.changeColIntegrality(variable.index, highspy.HighsVarType.kInteger)
            if variant == "presolve_off":
                model.setOptionValue("presolve", "off")
            return result
        milp_planner._add_ev_session_start_variables = starts
        policy = replace(data["policy"], total_seconds=budget, economic_seconds=min(30, budget / 2))
        started = perf_counter()
        result = milp_planner.evaluate_plan_milp(data["frame"], data["profile"], data["capacity_state"],
                                               policy=policy, previous_plan=data["previous_plan"])
        report = {"variant": variant, "budget": budget, "wall_seconds": perf_counter()-started,
                  "snapshot_id": snapshot.snapshot_id, "validation": result.validation_status,
                  "status": result.status, "objective_eur": result.milp_objective_eur,
                  "fragmentation": metrics(result.plan) if result.plan else None,
                  "stages": [replace(s, plan=None) for s in result.stages]}
        results.append(report)
        (args.output or Path('.v3-evidence/' + (
            'quality-candidate.json' if args.candidate else 'quality-benchmarks.json'))).write_text(
            canonical(results))
        print(json.dumps({k: v for k, v in report.items() if k != "stages"}), flush=True)
    milp_planner.refine, milp_planner._add_ev_session_start_variables = original_refine, original_starts


if __name__ == "__main__":
    main()
