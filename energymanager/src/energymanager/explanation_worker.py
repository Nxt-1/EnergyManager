"""Isolated diagnostic subprocess: frozen inputs in, compact comparison out. No HA imports."""
import hashlib
import json
import os
import resource
import sys
from dataclasses import replace

from .counterfactual import CounterfactualRequest, compare
from .decision_store import PlanningSnapshot, canonical, encode
from .explanations import comparison_view


def main():
    os.nice(10)
    resource.setrlimit(resource.RLIMIT_CPU, (64, 65))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    request = json.loads(sys.stdin.buffer.read(32 * 1024 * 1024 + 4096))
    original = PlanningSnapshot(request["snapshot_id"], request["payload"])
    data = original.inputs()
    # Preserve all inputs/tolerances; only limit the diagnostic solve budget explicitly.
    policy = replace(data["policy"], total_seconds=min(30, data["policy"].total_seconds),
                     economic_seconds=min(15, data["policy"].economic_seconds))
    raw = json.loads(original.payload)
    raw["policy"] = encode(policy)
    payload = canonical(raw)
    frozen = PlanningSnapshot(hashlib.sha256(payload.encode()).hexdigest()[:32], payload)
    result = comparison_view(compare(frozen, CounterfactualRequest(**request["intervention"])))
    result["source_snapshot_id"] = original.snapshot_id
    result["diagnostic_policy"] = encode(policy)
    print(canonical(result))


if __name__ == "__main__":
    main()
