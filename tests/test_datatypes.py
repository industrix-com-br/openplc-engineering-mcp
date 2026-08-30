import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.datatypes import list_datatypes


def make_project(tmp_path: Path, data: object | None = None) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    document: dict[str, object] = {"meta": {"name": "Minimal", "type": "plc-project"}}
    if data is not None:
        document["data"] = data
    (project / "project.json").write_text(json.dumps(document), encoding="utf-8")
    return project


def write_datatype(project: Path, name: str, content: str) -> None:
    directory = project / "datatypes"
    directory.mkdir(exist_ok=True)
    (directory / f"{name}.dt").write_text(content, encoding="utf-8")


def test_empty_project_returns_no_datatypes(tmp_path: Path) -> None:
    project = make_project(tmp_path)

    assert list_datatypes(str(project)) == []


def test_lists_enumerated_datatype(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    write_datatype(
        project,
        "OperatingMode",
        """TYPE
  OperatingMode : (Auto, Manual, Maintenance) := Auto;
END_TYPE
""",
    )

    assert list_datatypes(str(project)) == [
        {
            "name": "OperatingMode",
            "kind": "enumerated",
            "values": ["Auto", "Manual", "Maintenance"],
            "initial_value": "Auto",
        }
    ]


def test_lists_structure_datatype(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    write_datatype(
        project,
        "MotorStatus",
        """TYPE
  MotorStatus : STRUCT
    running : BOOL;
    speed : REAL := 0.0; (* Current motor speed *)
    history : ARRAY [0..9] OF REAL;
  END_STRUCT;
END_TYPE
""",
    )

    assert list_datatypes(str(project)) == [
        {
            "name": "MotorStatus",
            "kind": "structure",
            "fields": [
                {
                    "name": "running",
                    "type": "BOOL",
                    "initial_value": None,
                    "documentation": None,
                },
                {
                    "name": "speed",
                    "type": "REAL",
                    "initial_value": "0.0",
                    "documentation": "Current motor speed",
                },
                {
                    "name": "history",
                    "type": "ARRAY [0..9] OF REAL",
                    "initial_value": None,
                    "documentation": None,
                },
            ],
        }
    ]


def test_lists_multidimensional_array_datatype(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    write_datatype(
        project,
        "TemperatureBuffer",
        """TYPE
  TemperatureBuffer : ARRAY [0..9, 0..4] OF REAL := [0.0];
END_TYPE
""",
    )

    assert list_datatypes(str(project)) == [
        {
            "name": "TemperatureBuffer",
            "kind": "array",
            "base_type": "REAL",
            "dimensions": ["0..9", "0..4"],
            "initial_value": "[0.0]",
        }
    ]


def test_datatypes_are_sorted_by_name(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    write_datatype(project, "Zulu", "TYPE\nZulu : (A, B);\nEND_TYPE\n")
    write_datatype(project, "Alpha", "TYPE\nAlpha : ARRAY [0..1] OF INT;\nEND_TYPE\n")

    assert [data_type["name"] for data_type in list_datatypes(str(project))] == ["Alpha", "Zulu"]


def test_project_json_datatypes_are_unsupported(tmp_path: Path) -> None:
    project = make_project(
        tmp_path,
        {
            "dataTypes": [
                {
                    "name": "OperatingMode",
                    "derivation": "enumerated",
                    "values": [{"description": "Auto"}],
                }
            ]
        },
    )

    with pytest.raises(ToolError, match="Unsupported OpenPLC project format"):
        list_datatypes(str(project))


def test_invalid_dt_raises_tool_error(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    write_datatype(project, "Broken", "TYPE\nBroken : SOMETHING INVALID;\nEND_TYPE\n")

    with pytest.raises(ToolError, match='Could not read data type "Broken"'):
        list_datatypes(str(project))


def test_dt_filename_must_match_declared_name(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    write_datatype(project, "Alpha", "TYPE\nBeta : (A, B);\nEND_TYPE\n")

    with pytest.raises(ToolError, match="does not match filename identity"):
        list_datatypes(str(project))
