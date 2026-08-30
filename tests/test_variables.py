import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.variables import list_global_variables, list_variables


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


def test_list_variables_expands_comma_separated_names_in_order(tmp_path: Path) -> None:
    project = make_source_project(
        tmp_path / "project",
        "FUNCTION_BLOCK Motor\nVAR_INPUT\n    Start, Stop : BOOL;\nEND_VAR\nEND_FUNCTION_BLOCK\n",
    )

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
            "name": "Stop",
            "class": "input",
            "type": "BOOL",
            "location": None,
            "initial_value": None,
            "documentation": None,
        },
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


def make_configuration_project(root: Path, resource: dict[str, object]) -> Path:
    root.mkdir()
    (root / "project.json").write_text(
        json.dumps(
            {
                "meta": {"name": "Example", "type": "plc-project"},
                "data": {"configuration": {"resource": resource}},
            }
        ),
        encoding="utf-8",
    )
    return root


GLOBAL_VARIABLES: list[dict[str, object]] = [
    {
        "name": "EmergencyStop",
        "type": {"definition": "base-type", "value": "BOOL"},
        "location": "%IX0.0",
        "initialValue": "",
        "documentation": "Emergency stop input",
    },
    {
        "name": "CycleCount",
        "type": {"definition": "base-type", "value": "INT"},
        "location": "",
        "initialValue": "0",
        "documentation": "",
    },
]


def test_list_global_variables_returns_resource_global_variables(tmp_path: Path) -> None:
    project = make_configuration_project(tmp_path / "project", {"globalVariables": GLOBAL_VARIABLES})

    assert list_global_variables(str(project)) == [
        {
            "name": "EmergencyStop",
            "class": "global",
            "type": "BOOL",
            "location": "%IX0.0",
            "initial_value": None,
            "documentation": "Emergency stop input",
        },
        {
            "name": "CycleCount",
            "class": "global",
            "type": "INT",
            "location": None,
            "initial_value": "0",
            "documentation": None,
        },
    ]


def test_list_global_variables_preserves_stored_order(tmp_path: Path) -> None:
    project = make_configuration_project(tmp_path / "project", {"globalVariables": GLOBAL_VARIABLES})

    names = [variable["name"] for variable in list_global_variables(str(project))]

    assert names == ["EmergencyStop", "CycleCount"]


def test_list_global_variables_forces_global_class(tmp_path: Path) -> None:
    variable = {
        "name": "Counter",
        "class": "local",
        "type": {"definition": "base-type", "value": "INT"},
        "location": "",
        "initialValue": "",
        "documentation": "",
    }
    project = make_configuration_project(tmp_path / "project", {"globalVariables": [variable]})

    assert list_global_variables(str(project))[0]["class"] == "global"


def test_list_global_variables_returns_empty_list_without_configuration(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "project.json").write_text(
        json.dumps({"meta": {"name": "Example", "type": "plc-project"}}), encoding="utf-8"
    )

    assert list_global_variables(str(root)) == []


def test_list_global_variables_returns_empty_list_when_global_variables_absent(tmp_path: Path) -> None:
    project = make_configuration_project(tmp_path / "project", {"tasks": []})

    assert list_global_variables(str(project)) == []


def test_list_global_variables_rejects_string_type_representation(tmp_path: Path) -> None:
    variable = {
        "name": "Counter",
        "type": "INT",
        "location": "",
        "initialValue": "",
        "documentation": "",
    }
    project = make_configuration_project(tmp_path / "project", {"globalVariables": [variable]})

    with pytest.raises(ToolError, match="declared type must be an object"):
        list_global_variables(str(project))


@pytest.mark.parametrize(
    ("variable", "match"),
    [
        ("not-an-object", "is not an object"),
        ({"type": {"definition": "base-type", "value": "INT"}}, "missing a name"),
        ({"name": "Counter"}, "declared type must be an object"),
    ],
)
def test_list_global_variables_rejects_malformed_variables(
    tmp_path: Path, variable: object, match: str
) -> None:
    project = make_configuration_project(
        tmp_path / "project", {"globalVariables": [variable]}
    )

    with pytest.raises(ToolError, match=match):
        list_global_variables(str(project))


def test_list_global_variables_rejects_non_array_global_variables(tmp_path: Path) -> None:
    project = make_configuration_project(
        tmp_path / "project", {"globalVariables": {"name": "Counter"}}
    )

    with pytest.raises(ToolError, match="global variables must be an array"):
        list_global_variables(str(project))
