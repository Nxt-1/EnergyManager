"""Cleanup must preserve active work, original evidence and unreviewed failures."""

import json
import os
from pathlib import Path
import subprocess

import pytest

from tools import dev_workspace as workspace


def stopped_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "external"
    monkeypatch.setenv("ENERGYMANAGER_DEV_HOME", str(root))
    run = workspace.create_run("synthetic-test")
    (run / "synthetic.sqlite").write_bytes(b"synthetic fixture")
    monkeypatch.setattr(workspace, "process_alive", lambda _: False)
    return root, run


def test_external_output_and_explicit_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run = stopped_run(tmp_path, monkeypatch)
    assert run.parent == root / "runs"
    assert workspace.create_run("explicit", tmp_path / "alternate").parent == tmp_path / "alternate"
    with pytest.raises(ValueError, match="outside"):
        workspace.create_run("invalid", workspace.PROJECT / "artifacts")
    with pytest.raises(ValueError):
        workspace.create_run("../escape")


def test_preview_and_apply_only_after_evidence_retained(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run = stopped_run(tmp_path, monkeypatch)
    record = root / "verified.json"
    record.write_text('{"verified": true}', encoding="utf-8")
    original = root / "evidence" / "installation.sqlite3"
    original.parent.mkdir()
    original.write_bytes(b"original incident evidence")
    assert not workspace.cleanup(root, apply=True)[0]["eligible"]
    workspace.complete_run(root, run.name, record, "Verification recorded; no publication needed")
    assert workspace.cleanup(root)[0]["eligible"] and run.exists()
    assert workspace.cleanup(root, apply=True)[0]["removed"] and not run.exists()
    assert original.read_bytes() == b"original incident evidence"


def test_active_owner_and_changed_record_block_removal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run = stopped_run(tmp_path, monkeypatch)
    record = root / "diagnosis.txt"
    record.write_text("Extracted minimal reproduction", encoding="utf-8")
    workspace.complete_run(root, run.name, record, "Diagnostic evidence extracted")
    monkeypatch.setattr(workspace, "process_alive", lambda _: True)
    assert not workspace.cleanup(root, apply=True)[0]["removed"]
    monkeypatch.setattr(workspace, "process_alive", lambda _: False)
    record.write_text("Changed after completion", encoding="utf-8")
    assert not workspace.cleanup(root, apply=True)[0]["eligible"]
    assert run.exists()


def test_invalid_and_unowned_paths_are_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run = stopped_run(tmp_path, monkeypatch)
    record = run / "report.json"
    record.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        workspace.complete_run(root, run.name, record, "success")
    with pytest.raises(ValueError):
        workspace.complete_run(root, "../evidence", record, "success")
    unknown = root / "runs" / "user-data"
    unknown.mkdir()
    (unknown / "original.txt").write_text("preserve", encoding="utf-8")
    (run / "run.json").write_text(json.dumps({"schema": "something else"}), encoding="utf-8")
    assert all(not result["removed"] for result in workspace.cleanup(root, apply=True))
    assert unknown.exists() and run.exists()


def test_linked_content_is_not_followed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run = stopped_run(tmp_path, monkeypatch)
    outside = tmp_path / "original"
    outside.mkdir()
    link = run / "redirect"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        # Junction creation does not require Windows developer-mode symlink privileges.
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True)
    try:
        assert not workspace.cleanup(root, apply=True)[0]["eligible"]
        assert outside.exists()
    finally:
        if os.name == "nt":
            link.rmdir()


def test_real_current_process_is_detected() -> None:
    assert workspace.process_alive(os.getpid())
