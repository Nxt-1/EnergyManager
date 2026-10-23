"""Sequential, synthetic, real-solver release acceptance runs; never opens an integration."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from time import monotonic

from energymanager.domain import Goal, Policy, encode
from energymanager.forecasts import demo_snapshot
from energymanager.planner import Planner
from energymanager.validation import validate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("mixed", "winter", "permission"), default="mixed")
    parser.add_argument("--budget", type=float, default=120)
    args = parser.parse_args()
    policy = replace(Policy(), planning_budget_seconds=args.budget)
    s = demo_snapshot(policy=policy, season="winter" if args.case == "winter" else "mixed")
    if args.case == "permission":
        goal = Goal(
            "urgent",
            "Synthetic urgent manual goal",
            s.observation.at + timedelta(hours=1),
            56,
            priority=90,
        )
        s = demo_snapshot(start=s.observation.at, policy=policy, season="winter", goals=(goal,))
    s = replace(s, id=f"release-fixture-{args.case}-1")
    before = monotonic()
    result = Planner().plan(s)
    elapsed = monotonic() - before
    errors = (
        validate(s, result["flows"], result.get("service"))
        if result.get("valid")
        else [result.get("reason", "invalid")]
    )
    assert (s.intervals[-1].end - s.intervals[0].start).total_seconds() == 168 * 3600
    assert max(i.hours for i in s.intervals) <= 5 / 60 + 1e-9
    artifact = Path("artifacts") / f"release-{args.case}.json"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text(encode({"snapshot": s, "result": result}), encoding="utf-8")
    report = {
        "case": args.case,
        "fixture_digest": s.digest,
        "provenance": s.provenance,
        "python": platform.python_version(),
        "system": platform.platform(),
        "versions": {name: importlib.metadata.version(name) for name in ("highspy", "numpy", "aiohttp")},
        "budget_seconds": args.budget,
        "wall_seconds": elapsed,
        "horizon_hours": 168,
        "max_interval_seconds": max(i.hours for i in s.intervals) * 3600,
        "intervals": len(s.intervals),
        "valid": result.get("valid", False),
        "errors": errors,
        "status": result["status"],
        "summary": result.get("summary"),
        "stages": result["stages"],
        "permissions": result.get("permission_proposals", []),
        "minimum_grid_certified": result.get("minimum_grid_certified", False),
    }
    output = Path("docs") / f"benchmark-{args.case}.json"
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "stages"}, indent=2), flush=True)
    raise SystemExit(1 if errors or elapsed > args.budget + 0.5 else 0)


if __name__ == "__main__":
    main()
