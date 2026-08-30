import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.project import get_project_structure, validate_project


def make_project(root: Path, *, project_type: str = "plc-project") -> Path:
    (root / "pous" / "programs").mkdir(parents=True)
    (root / "pous" / "function-blocks").mkdir(parents=True)
    (root / "devices").mkdir()
    (root / "project.json").write_text(
        json.dumps({"meta": {"name": "Example", "type": project_type}}), encoding="utf-8"
    )
    (root / "devices" / "configuration.json").write_text("{}", encoding="utf-8")
    (root / "pous" / "programs" / "main.st").write_text(
        "PROGRAM main\nEND_PROGRAM\n", encoding="utf-8"
    )
    (root / "pous" / "function-blocks" / "Motor.st").write_text(
        "FUNCTION_BLOCK Motor\nEND_FUNCTION_BLOCK\n", encoding="utf-8"
    )
    return root


def test_get_project_structure_uses_current_project_layout(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    structure = get_project_structure(str(project))

    assert structure["name"] == "Example"
    assert structure["type"] == "plc-project"
    assert "pous/programs/main.st" in structure["files"]
    assert "pous/function-blocks/Motor.st" in structure["files"]


def test_legacy_json_pou_is_not_in_project_structure(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    legacy_pou = project / "pous" / "function-blocks" / "Legacy.json"
    legacy_pou.write_text("{}", encoding="utf-8")

    assert "pous/function-blocks/Legacy.json" not in get_project_structure(str(project))["files"]


@pytest.mark.parametrize("project_type", ["plc-project", "plc-library"])
def test_accepted_project_types(tmp_path: Path, project_type: str) -> None:
    project = make_project(tmp_path / "project", project_type=project_type)

    result = get_project_structure(str(project))

    assert result["type"] == project_type


def test_legacy_plc_project_type_is_rejected(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project", project_type="PLC")

    with pytest.raises(ToolError, match="unsupported project.json meta.type"):
        get_project_structure(str(project))


def test_a_meta_only_project_is_recognized(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )

    result = get_project_structure(str(project))

    assert result["name"] == "Minimal"
    assert result["files"] == ["project.json"]


def test_invalid_project_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="does not exist"):
        get_project_structure(str(tmp_path / "missing"))


def test_project_path_must_be_directory(tmp_path: Path) -> None:
    project_file = tmp_path / "project.json"
    project_file.write_text("{}", encoding="utf-8")

    with pytest.raises(ToolError, match="not a directory"):
        get_project_structure(str(project_file))


def test_missing_project_json_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="does not contain project.json"):
        get_project_structure(str(tmp_path))


def test_invalid_project_json_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{not-json", encoding="utf-8")

    with pytest.raises(ToolError, match="not valid JSON"):
        get_project_structure(str(project))


def test_unsupported_meta_type_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "X", "type": "something-else"}}), encoding="utf-8"
    )

    with pytest.raises(ToolError, match="unsupported project.json meta.type"):
        get_project_structure(str(project))


def test_validate_project_reports_valid_project(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    result = validate_project(str(project))

    assert result == {
        "valid": True,
        "name": "Example",
        "type": "plc-project",
        "warnings": [],
    }


def test_validate_project_keeps_meta_only_project_valid(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )

    result = validate_project(str(project))

    assert result["valid"] is True
    assert result["warnings"] == []


@pytest.mark.parametrize(
    "content",
    [None, "{not-json", json.dumps({"meta": {"name": "X", "type": "bad"}})],
    ids=["missing-project-json", "invalid-json", "bad-type"],
)
def test_validate_project_reports_unrecoverable_failures_as_errors(
    tmp_path: Path, content: str | None
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    if content is not None:
        (project / "project.json").write_text(content, encoding="utf-8")

    with pytest.raises(ToolError):
        validate_project(str(project))
