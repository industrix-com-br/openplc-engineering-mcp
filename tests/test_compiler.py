import json
import subprocess
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.compiler import compile_project, get_diagnostics


def make_project(root: Path) -> Path:
    root.mkdir()
    (root / "project.json").write_text(
        json.dumps({"meta": {"name": "Example", "type": "plc-project"}}), encoding="utf-8"
    )
    return root


def test_compile_project_and_get_diagnostics(tmp_path: Path, monkeypatch) -> None:
    project = make_project(tmp_path / "project")

    def fake_run(args, **kwargs):
        assert args == ["openplc-cli", "compile", str(project.resolve()), "--json"]
        assert kwargs == {"capture_output": True, "text": True, "check": False}
        return subprocess.CompletedProcess(
            args,
            4,
            stdout='{"code":"compile_failed"}',
            stderr="main.st:1: error: undeclared variable\n",
        )

    monkeypatch.setattr("openplc_engineering_mcp.openplc.compiler.subprocess.run", fake_run)

    compiled = compile_project(str(project))

    assert compiled == {
        "success": False,
        "exit_code": 4,
        "output": {"code": "compile_failed"},
    }
    assert get_diagnostics(str(project)) == ["main.st:1: error: undeclared variable"]


def test_compile_project_diagnostics_exclude_platform_noise(tmp_path: Path, monkeypatch) -> None:
    project = make_project(tmp_path / "project")

    def fake_run(args, **kwargs):
        stderr = "\n".join(
            [
                "[165795:0904/202137.665319:ERROR:bus.cc(408)] Failed to connect to the bus",
                "File already exists at /home/allan/.config/open-plc-editor/User/settings.json.",
                "Skipping creation.",
                "main.st:1: error: undeclared variable",
                "[165795:0904/202137.665399:ERROR:object_proxy.cc(576)] Failed to call method",
            ]
        )
        return subprocess.CompletedProcess(args, 4, stdout="", stderr=stderr)

    monkeypatch.setattr("openplc_engineering_mcp.openplc.compiler.subprocess.run", fake_run)

    compiled = compile_project(str(project))

    assert compiled["success"] is False
    assert get_diagnostics(str(project)) == ["main.st:1: error: undeclared variable"]


def test_compile_project_reports_missing_cli(tmp_path: Path, monkeypatch) -> None:
    project = make_project(tmp_path / "project")

    def missing_cli(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("openplc_engineering_mcp.openplc.compiler.subprocess.run", missing_cli)

    with pytest.raises(ToolError, match="openplc-cli was not found on PATH"):
        compile_project(str(project))


def test_get_diagnostics_requires_compilation(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    with pytest.raises(ToolError, match="No compilation diagnostics are available"):
        get_diagnostics(str(project))
