import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.variables import list_variables


def make_source_project(
    root: Path,
    content: str,
    *,
    name: str = "Motor",
    pou_dir: str = "function-blocks",
) -> Path:
    (root / "pous" / pou_dir).mkdir(parents=True)
    (root / "project.json").write_text(
        json.dumps({"meta": {"name": "Example", "type": "plc-project"}}), encoding="utf-8"
    )
    (root / "pous" / pou_dir / f"{name}.st").write_text(content, encoding="utf-8")
    return root


def make_json_project(
    root: Path,
    content: str,
    *,
    name: str = "Motor",
    pou_dir: str = "function-blocks",
) -> Path:
    (root / "pous" / pou_dir).mkdir(parents=True)
    (root / "project.json").write_text(
        json.dumps({"meta": {"name": "Example", "type": "plc-project"}}), encoding="utf-8"
    )
    (root / "pous" / pou_dir / f"{name}.json").write_text(content, encoding="utf-8")
    return root


def test_list_variables_reads_basic_local_variable(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        "FUNCTION_BLOCK Motor\nVAR\n    Counter : INT;\nEND_VAR\nEND_FUNCTION_BLOCK\n",
    )

    assert list_variables(str(project), "Motor") == [
        {
            "name": "Counter",
            "class": "local",
            "type": "INT",
            "location": None,
            "initial_value": None,
            "documentation": None,
        }
    ]


def test_list_variables_preserves_interface_classes_and_order(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        """FUNCTION_BLOCK Motor
VAR_INPUT
    Enable : BOOL;
END_VAR
VAR_OUTPUT
    Running : BOOL;
END_VAR
VAR_IN_OUT
    Setpoint : REAL;
END_VAR
VAR_EXTERNAL
    SharedState : DINT;
END_VAR
VAR_TEMP
    Working : INT;
END_VAR
VAR_GLOBAL
    GlobalCounter : INT;
END_VAR
VAR
    Attempts : INT;
END_VAR
END_FUNCTION_BLOCK
""",
    )

    variables = list_variables(str(project), "Motor")

    assert [(variable["name"], variable["class"]) for variable in variables] == [
        ("Enable", "input"),
        ("Running", "output"),
        ("Setpoint", "inOut"),
        ("SharedState", "external"),
        ("Working", "temp"),
        ("GlobalCounter", "global"),
        ("Attempts", "local"),
    ]


def test_list_variables_preserves_initial_value(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        "FUNCTION_BLOCK Motor\nVAR\n    Counter : INT := 10;\nEND_VAR\nEND_FUNCTION_BLOCK\n",
    )

    assert list_variables(str(project), "Motor")[0]["initial_value"] == "10"


def test_list_variables_preserves_location_and_documentation(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        """FUNCTION_BLOCK Motor
VAR
    MotorOutput AT %QX0.0 : BOOL; (* Requested motor output *)
END_VAR
END_FUNCTION_BLOCK
""",
    )

    variable = list_variables(str(project), "Motor")[0]

    assert variable["location"] == "%QX0.0"
    assert variable["documentation"] == "Requested motor output"


def test_list_variables_preserves_location_on_global_variable(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        "PROGRAM Main\nVAR_GLOBAL\n    Coil AT %QX0.1 : BOOL;\nEND_VAR\nEND_PROGRAM\n",
        name="Main",
        pou_dir="programs",
    )

    variable = list_variables(str(project), "Main")[0]

    assert variable["class"] == "global"
    assert variable["location"] == "%QX0.1"


def test_list_variables_preserves_array_type(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        """FUNCTION_BLOCK Motor
VAR
    Values : ARRAY[0..9] OF INT;
END_VAR
END_FUNCTION_BLOCK
""",
    )

    assert list_variables(str(project), "Motor")[0]["type"] == "ARRAY[0..9] OF INT"


def test_list_variables_returns_empty_list_when_pou_has_no_declarations(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        "FUNCTION_BLOCK Motor\nEND_FUNCTION_BLOCK\n",
    )

    assert list_variables(str(project), "Motor") == []


def test_list_variables_rejects_unknown_pou(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        "FUNCTION_BLOCK Motor\nEND_FUNCTION_BLOCK\n",
    )

    with pytest.raises(ToolError, match="POU not found"):
        list_variables(str(project), "Missing")


def test_list_variables_rejects_empty_pou_name(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        "FUNCTION_BLOCK Motor\nEND_FUNCTION_BLOCK\n",
    )

    with pytest.raises(ToolError, match="pou_name must not be empty"):
        list_variables(str(project), "  ")


def test_list_variables_rejects_malformed_declaration(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        "FUNCTION_BLOCK Motor\nVAR\n    Counter : INT\nEND_VAR\nEND_FUNCTION_BLOCK\n",
    )

    with pytest.raises(ToolError, match="Could not read variables"):
        list_variables(str(project), "Motor")


def test_list_variables_rejects_unterminated_variable_block(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        "FUNCTION_BLOCK Motor\nVAR\n    Counter : INT;\nEND_FUNCTION_BLOCK\n",
    )

    with pytest.raises(ToolError, match="missing END_VAR"):
        list_variables(str(project), "Motor")


def test_list_variables_supports_json_only_pou(tmp_path: Path) -> None:
    pou = {
        "name": "Motor",
        "pouType": "function-block",
        "interface": {
            "variables": [
                {
                    "name": "Start",
                    "class": "input",
                    "type": {"definition": "base-type", "value": "BOOL"},
                    "location": "",
                    "initialValue": None,
                    "documentation": "",
                    "debug": False,
                },
                {
                    "name": "Attempts",
                    "class": "local",
                    "type": {"definition": "base-type", "value": "INT"},
                    "location": "",
                    "initialValue": "0",
                    "documentation": "Retry count",
                    "debug": False,
                },
            ]
        },
        "body": {"language": "st", "value": ""},
    }
    project = make_json_project(tmp_path / "project", json.dumps(pou))

    assert list_variables(str(project), "Motor") == [
        {
            "name": "Start",
            "class": "input",
            "type": "BOOL",
            "location": None,
            "initial_value": None,
            "documentation": None,
        },
        {
            "name": "Attempts",
            "class": "local",
            "type": "INT",
            "location": None,
            "initial_value": "0",
            "documentation": "Retry count",
        },
    ]


def test_json_function_return_type_is_not_reported_as_variable(tmp_path: Path) -> None:
    pou = {
        "name": "Calculate",
        "pouType": "function",
        "interface": {
            "returnType": "REAL",
            "variables": [
                {
                    "name": "Value",
                    "class": "input",
                    "type": {"definition": "base-type", "value": "REAL"},
                    "location": "",
                    "initialValue": None,
                    "documentation": "",
                }
            ],
        },
        "body": {"language": "st", "value": ""},
    }
    project = make_json_project(
        tmp_path / "project", json.dumps(pou), name="Calculate", pou_dir="functions"
    )

    variables = list_variables(str(project), "Calculate")

    assert [variable["name"] for variable in variables] == ["Value"]


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("{not json", "invalid JSON"),
        (json.dumps({"name": "Motor"}), "unsupported JSON POU representation"),
        (json.dumps({"interface": {"variables": {"name": "X"}}}), "must be a list"),
        (
            json.dumps(
                {
                    "interface": {
                        "variables": [
                            {"name": "X", "type": {"definition": "base-type", "value": "BOOL"}}
                        ]
                    }
                }
            ),
            "unsupported or missing class",
        ),
    ],
)
def test_list_variables_rejects_unreadable_json_pous(
    tmp_path: Path, content: str, match: str
) -> None:
    project = make_json_project(tmp_path / "project", content)

    with pytest.raises(ToolError, match=match):
        list_variables(str(project), "Motor")


def test_function_return_type_is_not_reported_as_variable(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        """FUNCTION Calculate : REAL
VAR_INPUT
    Value : REAL;
END_VAR
Calculate := Value;
END_FUNCTION
""",
        name="Calculate",
        pou_dir="functions",
    )

    variables = list_variables(str(project), "Calculate")

    assert [variable["name"] for variable in variables] == ["Value"]
