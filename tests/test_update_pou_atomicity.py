import json
import os
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import openplc_engineering_mcp.openplc.pous as pous_module
from openplc_engineering_mcp.openplc.pous import read_pou, update_pou


ORIGINAL = "PROGRAM MAIN\nEND_PROGRAM\n"
REPLACEMENT = "PROGRAM MAIN\nVAR\n    flag : BOOL;\nEND_VAR\n    flag := TRUE;\nEND_PROGRAM\n"


def make_project(root: Path) -> Path:
    """Create the smallest current-format project needed for POU updates."""
    (root / "pous" / "programs").mkdir(parents=True)
    (root / "project.json").write_text(
        json.dumps({"meta": {"name": "Example", "type": "plc-project"}}), encoding="utf-8"
    )
    (root / "pous" / "programs" / "MAIN.st").write_text(ORIGINAL, encoding="utf-8")
    return root


def temp_files(target: Path) -> list[Path]:
    """Return update_pou temporary files beside one target."""
    return list(target.parent.glob(f".{target.name}.*.tmp"))


def test_update_fsyncs_after_preserving_target_mode(tmp_path: Path, monkeypatch) -> None:
    """The staged file mode is applied before its final pre-commit fsync."""
    project = make_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    expected_hash = read_pou(str(project), "MAIN")["content_hash"]
    events: list[str] = []
    real_chmod = os.chmod
    real_fsync = os.fsync

    def recording_chmod(path, mode):
        events.append("chmod")
        real_chmod(path, mode)

    def recording_fsync(fd):
        events.append("fsync")
        real_fsync(fd)

    monkeypatch.setattr(pous_module.os, "chmod", recording_chmod)
    monkeypatch.setattr(pous_module.os, "fsync", recording_fsync)

    update_pou(str(project), "MAIN", REPLACEMENT, expected_hash)

    assert events == ["chmod", "fsync"]
    assert target.read_text(encoding="utf-8") == REPLACEMENT


def test_update_mode_preservation_failure_leaves_target_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    """A failure while preparing temp-file metadata never reaches the real POU."""
    project = make_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    original = target.read_bytes()
    expected_hash = read_pou(str(project), "MAIN")["content_hash"]

    def failing_chmod(*args, **kwargs):
        raise PermissionError("simulated chmod failure")

    monkeypatch.setattr(pous_module.os, "chmod", failing_chmod)

    with pytest.raises(ToolError, match='Could not update POU "MAIN"'):
        update_pou(str(project), "MAIN", REPLACEMENT, expected_hash)

    assert target.read_bytes() == original
    assert temp_files(target) == []


def test_update_preserves_external_bytes_when_target_goes_stale_before_commit(
    tmp_path: Path, monkeypatch
) -> None:
    """A stale target found after staging is never overwritten by the candidate."""
    project = make_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    expected_hash = read_pou(str(project), "MAIN")["content_hash"]
    external_bytes = b"PROGRAM MAIN\n(* external edit *)\nEND_PROGRAM\n"
    real_verify = pous_module._verify_update_target
    verify_calls = 0

    def edit_before_final_verify(root, pou_name, lexical_target):
        nonlocal verify_calls
        verify_calls += 1
        if verify_calls == 2:
            lexical_target.write_bytes(external_bytes)
        real_verify(root, pou_name, lexical_target)

    monkeypatch.setattr(pous_module, "_verify_update_target", edit_before_final_verify)

    with pytest.raises(ToolError, match='POU changed since it was read: "MAIN"'):
        update_pou(str(project), "MAIN", REPLACEMENT, expected_hash)

    assert target.read_bytes() == external_bytes
    assert temp_files(target) == []
