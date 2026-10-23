from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from hashlib import sha256

from aiohttp import web

from . import __version__
from .domain import Policy, Snapshot, encode
from .configuration import configured_application, create_configuration_if_missing
from .forecasts import demo_snapshot
from .planner import Planner
from .service import Application
from .store import Store
from .web import create_web


def main() -> None:
    parser = argparse.ArgumentParser(description="EnergyManager 4: joint EV/ESS planning and control")
    parser.add_argument("--version", action="version", version=f"EnergyManager {__version__}")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--data", type=Path, default=Path("runtime/energymanager-v4.sqlite3"))
    parser.add_argument("--fixture", type=Path)
    parser.add_argument(
        "--config", type=Path, help="Configured HA/forecast boundaries; control disabled by default"
    )
    parser.add_argument("--addon", action="store_true")
    parser.add_argument("--ingress", action="store_true")
    parser.add_argument("--budget", type=float, default=120)
    parser.add_argument(
        "--scenario", choices=("mixed", "winter"), default="mixed", help="Explicit synthetic demo weather"
    )
    parser.add_argument("--solve", type=Path, help="Save one complete offline decision and exit")
    args = parser.parse_args()
    configuration_path: Path | None = args.config
    if args.addon:
        options = json.loads(Path("/data/options.json").read_text(encoding="utf-8"))
        args.budget = float(options.get("planning_budget_seconds", 120))
        configuration_path = Path(options.get("configuration_file", "/config/energymanager.json"))
        if options.get("mode") == "configured":
            args.config = configuration_path
    if not 1 <= args.budget <= 600:
        parser.error("Planning budget must be between 1 and 600 seconds")
    if args.config and (args.fixture or args.solve):
        parser.error("Configured service inputs cannot be combined with offline fixture/solve mode")
    if args.fixture and not args.solve:
        parser.error("Frozen fixtures use --solve; use demo or configured inputs for the running service")
    if configuration_path:
        try:
            created = create_configuration_if_missing(configuration_path)
        except OSError as exc:
            parser.error(f"Cannot create configuration at {configuration_path}: {exc}")
        if created:
            print(
                f"Created starter configuration at {configuration_path}. "
                "Edit its example settings before using configured inputs. Hardware control is disabled.",
                flush=True,
            )
    policy = replace(Policy(), planning_budget_seconds=args.budget)
    snapshot = demo_snapshot(policy=policy, season=args.scenario)
    if args.fixture:
        payload = json.loads(args.fixture.read_text(encoding="utf-8"))
        data = payload.get("snapshot", payload)
        expected = payload.get("result", {}).get("input_digest")
        if expected and sha256(encode(data).encode()).hexdigest() != expected:
            parser.error("Frozen decision input checksum mismatch")
        snapshot = Snapshot.from_dict(data)
        snapshot = replace(snapshot, policy=replace(snapshot.policy, planning_budget_seconds=args.budget))
    if args.solve:
        result = Planner().plan(snapshot)
        args.solve.parent.mkdir(parents=True, exist_ok=True)
        args.solve.write_text(encode({"snapshot": snapshot, "result": result}), encoding="utf-8")
        print(
            json.dumps(
                {
                    k: v
                    for k, v in result.items()
                    if k in ("status", "valid", "summary", "seconds", "stages", "reason")
                },
                indent=2,
            )
        )
        raise SystemExit(0 if result.get("valid") else 1)
    args.data.parent.mkdir(parents=True, exist_ok=True)
    store = Store(args.data)
    application = (
        configured_application(args.config, store)
        if args.config
        else Application(store, policy=policy, snapshot=snapshot, demo=not bool(args.fixture))
    )
    web.run_app(create_web(application), host="0.0.0.0" if args.ingress else "127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
