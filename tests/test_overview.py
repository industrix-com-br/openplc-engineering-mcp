import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.overview import get_project_overview
from openplc_engineering_mcp.openplc.project import get_project_structure


def write(project: Path, path: str, content: str) -> None:
    target = project / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def make_project(project: Path, project_type: str = "plc-project", resource: object = None) -> None:
    write(
        project,
        "project.json",
        json.dumps(
            {
                "meta": {"name": "Conveyor", "type": project_type},
                "data": {"configuration": {"resource": resource}},
            }
        ),
    )


@pytest.mark.parametrize("project_type", ["plc-project", "plc-library"])
def test_empty_overview(tmp_path: Path, project_type: str) -> None:
    make_project(tmp_path, project_type)
    assert get_project_overview(str(tmp_path)) == {
        "name": "Conveyor",
        "type": project_type,
        "pous": {"programs": [], "function_blocks": [], "functions": []},
        "datatypes": [],
        "global_variables": [],
        "execution": {"tasks": [], "program_instances": []},
        "io": None
        if project_type == "plc-library"
        else {
            "device_board": "OpenPLC Simulator",
            "mapping_count": 0,
        },
        "files": ["project.json"],
    }


@pytest.mark.parametrize("project_type", ["plc-project", "plc-library"])
def test_engineering_projection_and_read_only_ordering(tmp_path: Path, project_type: str) -> None:
    make_project(
        tmp_path,
        project_type,
        {
            "tasks": [
                {"name": n, "triggering": "Cyclic", "interval": "T#20ms", "priority": 0}
                for n in ["ZTask", "ATask"]
            ],
            "instances": [
                {"name": n, "task": "ZTask", "program": "MAIN"} for n in ["ZInstance", "AInstance"]
            ],
            "globalVariables": [
                {"name": n, "type": {"definition": "base-type", "value": "BOOL"}}
                for n in ["ZGlobal", "AGlobal"]
            ],
        },
    )
    for path in [
        "programs/Z.st",
        "programs/MAIN.st",
        "function-blocks/Motor.ld",
        "functions/Add.st",
        "programs/Add.st",
    ]:
        # Discovery must not parse or return POU bodies, including duplicate names.
        write(tmp_path, f"pous/{path}", "opaque source")
    write(tmp_path, "datatypes/ZState.dt", "TYPE\nZState : (Off, On);\nEND_TYPE\n")
    write(tmp_path, "datatypes/AState.dt", "TYPE\nAState : (Off, On);\nEND_TYPE\n")
    write(tmp_path, "devices/configuration.json", '{"deviceBoard": "Arduino Uno"}')
    write(
        tmp_path,
        "devices/pin-mapping.json",
        json.dumps(
            {
                "Arduino Uno": [{"pin": "2", "pinType": "digitalInput", "address": "%IX0.0"}],
                "Inactive": [],
            }
        ),
    )
    for path in ["library.json", "devices/remote/Remote.json", "devices/servers/Server.st"]:
        write(tmp_path, path, "opaque artifact")
    for path in ["secret.txt", "pous/programs/legacy.json", "build/generated.st"]:
        write(tmp_path, path, "not recognized")
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = get_project_overview(str(tmp_path))
    assert result == get_project_overview(str(tmp_path))
    assert result["pous"] == {
        "programs": ["MAIN", "Z"],
        "function_blocks": ["Motor"],
        "functions": ["Add"],
    }
    assert result["datatypes"] == ["AState", "ZState"]
    assert result["global_variables"] == ["ZGlobal", "AGlobal"]
    assert result["execution"] == {
        "tasks": ["ZTask", "ATask"],
        "program_instances": ["ZInstance", "AInstance"],
    }
    assert result["io"] == (
        None
        if project_type == "plc-library"
        else {
            "device_board": "Arduino Uno",
            "mapping_count": 1,
        }
    )
    assert result["files"] == get_project_structure(str(tmp_path))["files"]
    assert not {"secret.txt", "pous/programs/legacy.json", "build/generated.st"} & set(result["files"])
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    ("path", "content", "message"),
    [
        ("project.json", "{", "not valid JSON"),
        ("project.json", '{"meta": {"name": "X", "type": "unknown"}}', "unsupported"),
        ("datatypes/Bad.dt", "invalid", "Could not read data type"),
        ("devices/pin-mapping.json", "[]", "per-board"),
        ("devices/configuration.json", "{", "not valid JSON"),
    ],
)
def test_malformed_reader_input(tmp_path: Path, path: str, content: str, message: str) -> None:
    make_project(tmp_path)
    write(tmp_path, path, content)
    with pytest.raises(ToolError, match=message):
        get_project_overview(str(tmp_path))


@pytest.mark.parametrize("resource", [{"tasks": {}}, {"instances": {}}, {"globalVariables": {}}])
def test_malformed_configuration(tmp_path: Path, resource: object) -> None:
    make_project(tmp_path, resource=resource)
    with pytest.raises(ToolError, match="must be an array"):
        get_project_overview(str(tmp_path))


@pytest.mark.parametrize("path", ["", "missing"])
def test_invalid_project_path(tmp_path: Path, path: str) -> None:
    with pytest.raises(ToolError):
        get_project_overview(str(tmp_path / path) if path else "")


def test_library_does_not_read_physical_io(tmp_path: Path) -> None:
    make_project(tmp_path, "plc-library")
    write(tmp_path, "devices/configuration.json", "invalid")
    assert get_project_overview(str(tmp_path))["io"] is None
