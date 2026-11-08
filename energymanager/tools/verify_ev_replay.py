"""Offline EV acceptance replays; archives remain private and are never live inputs."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Any
from unittest.mock import patch

from energymanager.domain import Snapshot, encode, json_data
from energymanager.optimization import JointModel
from energymanager.planner import Planner
from energymanager.validation import accounting, rolling_comparison_errors, validate


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--matched", type=Path)
    parser.add_argument("--budget", type=float, default=120)
    args = parser.parse_args()
    archive = json.loads(args.dataset.read_bytes())
    snapshot = Snapshot.from_dict(archive.get("snapshot", archive))
    if archive.get("digest"):
        assert snapshot.digest == archive["digest"]
    snapshot = replace(snapshot, policy=replace(snapshot.policy, planning_budget_seconds=args.budget))
    matched = json.loads(args.matched.read_bytes()) if args.matched else None
    selected = matched.get("result", matched) if matched else None
    original_init, original_run, original_seed, original_solar = (
        JointModel.__init__, Planner.run_model, Planner.starting_point, Planner.prefer_solar)

    def initialize(model: JointModel, *positional: Any, **keywords: Any) -> None:
        original_init(model, *positional, **keywords)
        if selected and model.optional:
            f, m, v = selected["flows"], model.linear, model.linear.variables
            m.equality([(v["ev_energy"][-1], 1)], f["ev_energy"][-1])
            m.equality([(v["grid_cumulative"][-1], 1)], f["grid_cumulative"][-1])
            warm = model.warm_from(f)
            for objective in (model.economic, model.cash):
                m.row(list(objective.items()), upper=model.value(objective, warm)
                      + snapshot.policy.polish_tolerance_eur + 1e-6)

    def starting(planner: Planner, model: JointModel) -> list[float] | None:
        if selected and model.optional:
            warm = model.warm_from(selected["flows"])
            if model.linear.accepts(warm):
                return warm
        return original_seed(planner, model)

    def solve(planner: Planner, name: str, model: JointModel, allowance: float,
              warm: list[float] | None = None, **kwargs: Any) -> dict[str, Any]:
        if selected and name == "required_reference":
            f = selected["reference_flows"]
            values = model.warm_from(f)
            assert model.linear.accepts(values) and not validate(snapshot, f, selected.get("service"))
            return {"status": "Conditioned common reference", "feasible": True, "values": values, "flows": f}
        return original_run(planner, name, model, allowance, warm, **kwargs)

    def solar(planner: Planner, model: JointModel, result: dict[str, Any], allowance: float) -> dict[str, Any]:
        if selected and model.optional and not model.linear.accepts(model.warm_from(result["flows"])):
            warm = model.warm_from(selected["flows"])
            if model.linear.accepts(warm):
                result = {"status": "Matched-energy checked seed", "feasible": True,
                          "values": warm, "flows": selected["flows"]}
        return original_solar(planner, model, result, allowance)

    started = monotonic()
    with patch.object(JointModel, "__init__", initialize), patch.object(Planner, "starting_point", starting), \
            patch.object(Planner, "run_model", solve), patch.object(Planner, "prefer_solar", solar):
        result = Planner().plan(snapshot)
    elapsed = monotonic() - started
    errors = []
    if result.get("valid"):
        effective = Snapshot.from_dict(result["effective_snapshot"]) if result.get("effective_snapshot") else snapshot
        errors = validate(effective, result["flows"], result.get("service"))
        errors += rolling_comparison_errors(effective, result["reference_flows"], result["flows"])
        if result.get("deadline_guard", {}).get("status") == "certified":
            from energymanager.deadline_audit import validate_certificate
            errors += validate_certificate(result["deadline_guard"])
        metrics = accounting(effective, result["flows"])
        if selected:
            for name in ("ev_energy", "grid_cumulative"):
                if abs(result["flows"][name][-1] - selected["flows"][name][-1]) > 1e-5:
                    errors.append("Matched energy changed: " + name)
    else:
        errors = [result.get("reason", "No valid plan")]
        metrics = {}
    report = {"scope": "conditioned equal-energy" if selected else "fresh snapshot only",
              "snapshot_digest": snapshot.digest, "wall_seconds": elapsed, "budget_seconds": args.budget,
              "horizon_hours": sum(i.hours for i in snapshot.intervals), "errors": errors,
              "valid": result.get("valid"), "status": result["status"], "metrics": metrics,
              "starts": sum(result.get("flows", {}).get("start", [])),
              "grid_ev_kwh": result.get("flows", {}).get("grid_cumulative", [None])[-1],
              "terminal_ev_kwh": result.get("flows", {}).get("ev_energy", [None])[-1],
              "reference_fingerprint": sha256(encode(result["reference_flows"]).encode()).hexdigest()
              if result.get("valid") else None,
              "guard_status": result.get("deadline_guard", {}).get("status"),
              "coherent_candidate": result.get("coherent_candidate"), "stages": result.get("stages", [])}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encode({"snapshot": json_data(snapshot), "result": result}), encoding="utf-8")
    args.output.with_suffix(".report.json").write_text(encode(report), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in ("stages",)}), flush=True)
    if errors or elapsed > args.budget + .5:
        raise SystemExit(1)


if __name__ == "__main__":
    run()
