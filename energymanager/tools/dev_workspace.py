"""External development runs and explicit, completion-based cleanup; never installation data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from uuid import uuid4


SCHEMA = "energymanager-development-run-v1"
PROJECT = Path(__file__).resolve().parents[2]


def workspace_root(root: Path | None = None) -> Path:
    """Resolve a project-specific directory outside this Git checkout."""
    selected = root or Path(os.environ.get(
        "ENERGYMANAGER_DEV_HOME",
        str(Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "project-data" / "EnergyManager"),
    ))
    selected = selected.expanduser().resolve()
    if selected == selected.parent or selected.is_relative_to(PROJECT) or PROJECT.is_relative_to(selected):
        raise ValueError("Development storage must be outside the Git checkout, in a dedicated directory")
    return selected


def create_run(prefix: str, output_root: Path | None = None) -> Path:
    """Create an owned synthetic run; cleanup requires a separate completion record."""
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", prefix):
        raise ValueError("Invalid run prefix")
    parent = workspace_root(output_root) if output_root else workspace_root() / "runs"
    parent.mkdir(parents=True, exist_ok=True)
    run = parent / f"{prefix}-{uuid4().hex}"
    run.mkdir()
    (run / "run.json").write_text(json.dumps({
        "schema": SCHEMA, "id": run.name, "owner_pid": os.getpid(),
        "synthetic": True, "complete": False,
    }, indent=2), encoding="utf-8")
    return run


def process_alive(pid: int) -> bool:
    if os.name == "nt":
        # os.kill(pid, 0) is not a portable Windows liveness check.
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, check=True,
        )
        return any(len(row) > 1 and row[1] == str(pid) for row in csv.reader(result.stdout.splitlines()))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def checked_run(runs: Path, run: Path) -> dict:
    """Reject redirected trees before reading ownership or recursively deleting files."""
    if runs.is_symlink() or runs.is_junction() or run.is_symlink() or run.is_junction():
        raise ValueError("Linked run directories cannot be cleaned")
    if not run.is_dir() or run.resolve().parent != runs.resolve():
        raise ValueError("Run must be a direct child of the configured runs directory")
    for directory, subdirs, files in os.walk(run, followlinks=False):
        for name in [*subdirs, *files]:
            entry = Path(directory) / name
            if entry.is_symlink() or entry.is_junction():
                raise ValueError("Run contains a link or junction")
    data = json.loads((run / "run.json").read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA or data.get("id") != run.name or data.get("synthetic") is not True:
        raise ValueError("Not an owned synthetic development run")
    if type(data.get("owner_pid")) is not int or data["owner_pid"] <= 0:
        raise ValueError("Run owner is missing")
    if process_alive(data["owner_pid"]):
        raise ValueError("Run owner is still active")
    return data


def complete_run(root: Path, identity: str, record: Path, reason: str) -> None:
    """The operator confirms verified success or extracted failure evidence, without an age cutoff."""
    if Path(identity).name != identity or identity in (".", ".."):
        raise ValueError("Supply a run ID, not a path")
    runs = workspace_root(root) / "runs"
    run = runs / identity
    data = checked_run(runs, run)
    record = record.resolve(strict=True)
    if not record.is_file() or record.is_relative_to(runs.resolve()) or not reason.strip():
        raise ValueError("Keep a verification/diagnostic record outside runs and supply a completion reason")
    data.update(complete=True, record=str(record), record_sha256=hashlib.sha256(record.read_bytes()).hexdigest(),
                reason=reason.strip())
    (run / "run.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def cleanup(root: Path, *, apply: bool = False) -> list[dict]:
    """Preview by default. Only explicitly completed runs with retained evidence qualify."""
    runs = workspace_root(root) / "runs"
    if not runs.exists():
        return []
    if runs.is_symlink() or runs.is_junction():
        raise ValueError("Linked runs directory cannot be cleaned")
    results = []
    for run in sorted(runs.iterdir()):
        result = {"run": run.name, "removed": False, "eligible": False}
        try:
            data = checked_run(runs, run)
            if data.get("complete") is not True:
                raise ValueError("Completion/evidence extraction has not been recorded")
            record = Path(data["record"]).resolve(strict=True)
            if record.is_relative_to(runs.resolve()) or not record.is_file():
                raise ValueError("Retained record must be outside runs")
            if hashlib.sha256(record.read_bytes()).hexdigest() != data["record_sha256"]:
                raise ValueError("Retained record changed; review completion again")
            result.update(eligible=True, reason=data["reason"])
            if apply:
                # Recheck ownership, links and the exact resolved child immediately before removal.
                checked_run(runs, run)
                shutil.rmtree(run)
                result["removed"] = True
        except (OSError, ValueError, KeyError) as error:
            result["reason"] = str(error)
        results.append(result)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Dedicated external development directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("path", help="Print the external project-data directory")
    finished = commands.add_parser("complete", help="Confirm verified success or extracted diagnostic evidence")
    finished.add_argument("run")
    finished.add_argument("--record", type=Path, required=True)
    finished.add_argument("--reason", required=True)
    clean = commands.add_parser("cleanup", help="Preview eligible completed synthetic runs")
    clean.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        root = workspace_root(args.root)
        if args.command == "path":
            print(root)
        elif args.command == "complete":
            complete_run(root, args.run, args.record, args.reason)
            print(f"Completion recorded: {args.run}")
        else:
            results = cleanup(root, apply=args.apply)
            print(json.dumps(results, indent=2))
            if args.apply and any(item["eligible"] and not item["removed"] for item in results):
                raise SystemExit(1)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
