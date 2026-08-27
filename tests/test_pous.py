import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.pous import list_pous, read_pou


def make_project(root: Path) -> Path:
    (root / "pous" / "programs").mkdir(parents=True)
    (root / "pous" / "function-blocks").mkdir(parents=True)
    (root / "project.json").write_text(
        json.dumps({"meta": {"name": "Example", "type": "plc-project"}}), encoding="utf-8"
    )
    (root / "pous" / "programs" / "main.st").write_text("PROGRAM main\nEND_PROGRAM\n", encoding="utf-8")
    (root / "pous" / "function-blocks" / "Motor.json").write_text("{}", encoding="utf-8")
    (root / "pous" / "function-blocks" / "Motor.st").write_text(
        "FUNCTION_BLOCK Motor\nEND_FUNCTION_BLOCK\n", encoding="utf-8"
    )
    return root


def test_list_pous_prefers_source_representation(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    pous = list_pous(str(project))

    assert pous == [
        {
            "name": "Motor",
            "type": "function-block",
            "language": "st",
            "path": "pous/function-blocks/Motor.st",
        },
        {
            "name": "main",
            "type": "program",
            "language": "st",
            "path": "pous/programs/main.st",
        },
    ]


def test_json_only_pou_is_supported(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    (project / "pous" / "function-blocks" / "Motor.st").unlink()

    pous = list_pous(str(project))
    motor = next(pou for pou in pous if pou["name"] == "Motor")

    assert motor == {
        "name": "Motor",
        "type": "function-block",
        "language": None,
        "path": "pous/function-blocks/Motor.json",
    }


def test_pou_names_are_deduplicated_globally(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    (project / "pous" / "programs" / "Motor.st").write_text(
        "PROGRAM Motor\nEND_PROGRAM\n", encoding="utf-8"
    )

    pous = list_pous(str(project))
    motors = [pou for pou in pous if pou["name"] == "Motor"]

    assert motors == [
        {
            "name": "Motor",
            "type": "function-block",
            "language": "st",
            "path": "pous/function-blocks/Motor.st",
        }
    ]


def test_read_pou_returns_preferred_source_content(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    pou = read_pou(str(project), "Motor")

    assert pou == {
        "name": "Motor",
        "type": "function-block",
        "language": "st",
        "path": "pous/function-blocks/Motor.st",
        "content": "FUNCTION_BLOCK Motor\nEND_FUNCTION_BLOCK\n",
    }


def test_read_pou_supports_json_only_pou(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    (project / "pous" / "function-blocks" / "Motor.st").unlink()

    pou = read_pou(str(project), "Motor")

    assert pou == {
        "name": "Motor",
        "type": "function-block",
        "language": None,
        "path": "pous/function-blocks/Motor.json",
        "content": "{}",
    }


def test_read_pou_rejects_unknown_name(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    with pytest.raises(ToolError, match="POU not found"):
        read_pou(str(project), "Missing")


def test_read_pou_rejects_empty_name(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    with pytest.raises(ToolError, match="pou_name must not be empty"):
        read_pou(str(project), "  ")


def test_invalid_project_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="does not exist"):
        list_pous(str(tmp_path / "missing"))
