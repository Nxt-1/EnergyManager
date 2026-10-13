"""Offline interface: python -m energymanager.replay --help."""

import argparse
from pathlib import Path

from .counterfactual import CounterfactualRequest, compare
from .decision_store import DecisionStore, canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path("/data/planner-v3"))
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list")
    for command in ("show", "replay", "regenerate", "counterfactual"):
        child = sub.add_parser(command)
        child.add_argument("snapshot_id")
        if command == "counterfactual":
            child.add_argument("kind", choices=("forbid_ev", "continuous_ev", "no_grid_import"))
            child.add_argument("start", type=int)
            child.add_argument("end", type=int)
    args = parser.parse_args()
    store = DecisionStore(args.archive)
    if args.action == "list":
        print(canonical(store.list_ids()))
        return
    snapshot, document = store.read(args.snapshot_id)
    if args.action == "show":
        result = document
    elif args.action == "regenerate":
        result = snapshot.regenerate()
    elif args.action == "replay":
        result = snapshot.solve()
    else:
        result = compare(snapshot, CounterfactualRequest(args.kind, args.start, args.end))
    print(canonical(result))


if __name__ == "__main__":
    main()
