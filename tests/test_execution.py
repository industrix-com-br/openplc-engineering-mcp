import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.execution import get_execution_configuration


def make_project(root: Path, *, data: object | None = None) -> Path:
    root.mkdir()
    project: dict[str, object] = {"meta": {"name": "Example", "type": "plc-project"}}
    if data is not None:
        project["data"] = data
    (root / "project.json").write_text(json.dumps(project), encoding="utf-8")
    return root


def resource_data(*, tasks: object = None, instances: object = None) -> dict[str, object]:
    resource: dict[str, object] = {}
    if tasks is not None:
        resource["tasks"] = tasks
    if instances is not None:
        resource["instances"] = instances
    return {"configuration": {"resource": resource}}


def test_cyclic_task_and_program_instance_preserve_configuration(tmp_path: Path) -> None:
    project = make_project(
        tmp_path / "project",
        data=resource_data(
            tasks=[
                {
                    "name": "MainTask",
                    "triggering": "Cyclic",
                    "interval": "T#20ms",
                    "priority": 0,
                }
            ],
            instances=[{"name": "MainInstance", "task": "MainTask", "program": "main"}],
        ),
    )

    result = get_execution_configuration(str(project))

    assert result == {
        "tasks": [
            {
                "name": "MainTask",
                "triggering": "Cyclic",
                "interval": "T#20ms",
                "priority": 0,
            }
        ],
        "program_instances": [
            {"name": "MainInstance", "task": "MainTask", "program": "main"}
        ],
    }


def test_multiple_tasks_and_program_instances_are_returned_in_order(tmp_path: Path) -> None:
    project = make_project(
        tmp_path / "project",
        data=resource_data(
            tasks=[
                {
                    "name": "FastTask",
                    "triggering": "Cyclic",
                    "interval": "T#10ms",
                    "priority": 0,
                },
                {
                    "name": "SlowTask",
                    "triggering": "Cyclic",
                    "interval": "T#1s",
                    "priority": 5,
                },
            ],
            instances=[
                {"name": "Control", "task": "FastTask", "program": "control"},
                {"name": "Logging", "task": "SlowTask", "program": "logging"},
            ],
        ),
    )

    result = get_execution_configuration(str(project))

    assert [task["name"] for task in result["tasks"]] == ["FastTask", "SlowTask"]
    assert [instance["name"] for instance in result["program_instances"]] == [
        "Control",
        "Logging",
    ]


def test_interrupt_task_does_not_expose_stored_interval(tmp_path: Path) -> None:
    project = make_project(
        tmp_path / "project",
        data=resource_data(
            tasks=[
                {
                    "name": "InterruptTask",
                    "triggering": "Interrupt",
                    "interval": "T#20ms",
                    "priority": 1,
                }
            ]
        ),
    )

    result = get_execution_configuration(str(project))

    assert result["tasks"][0]["interval"] is None


def test_absent_execution_configuration_returns_empty_lists(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    assert get_execution_configuration(str(project)) == {
        "tasks": [],
        "program_instances": [],
    }


def test_legacy_configurations_form_is_supported(tmp_path: Path) -> None:
    project = make_project(
        tmp_path / "project",
        data={
            "configurations": {
                "resource": {
                    "tasks": [
                        {
                            "name": "LegacyTask",
                            "triggering": "Cyclic",
                            "interval": "T#100ms",
                            "priority": 2,
                        }
                    ],
                    "instances": [
                        {"name": "LegacyInstance", "task": "LegacyTask", "program": "legacy"}
                    ],
                }
            }
        },
    )

    result = get_execution_configuration(str(project))

    assert result["tasks"][0]["name"] == "LegacyTask"
    assert result["program_instances"][0]["program"] == "legacy"


def test_malformed_tasks_structure_is_rejected(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project", data=resource_data(tasks={}))

    with pytest.raises(ToolError, match="execution tasks must be an array"):
        get_execution_configuration(str(project))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", 1),
        ("triggering", "Event"),
        ("interval", None),
        ("priority", True),
    ],
)
def test_malformed_task_fields_are_rejected(tmp_path: Path, field: str, value: object) -> None:
    task: dict[str, object] = {
        "name": "MainTask",
        "triggering": "Cyclic",
        "interval": "T#20ms",
        "priority": 0,
    }
    task[field] = value
    project = make_project(tmp_path / "project", data=resource_data(tasks=[task]))

    with pytest.raises(ToolError, match=rf"execution task 0\.{field}"):
        get_execution_configuration(str(project))


def test_malformed_instances_structure_is_rejected(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project", data=resource_data(instances={}))

    with pytest.raises(ToolError, match="program instances must be an array"):
        get_execution_configuration(str(project))


@pytest.mark.parametrize(
    ("field", "value"),
    [("name", 1), ("task", None), ("program", 3)],
)
def test_malformed_program_instance_fields_are_rejected(
    tmp_path: Path, field: str, value: object
) -> None:
    instance: dict[str, object] = {"name": "MainInstance", "task": "MainTask", "program": "main"}
    instance[field] = value
    project = make_project(tmp_path / "project", data=resource_data(instances=[instance]))

    with pytest.raises(ToolError, match=rf"program instance 0\.{field}"):
        get_execution_configuration(str(project))


def test_existing_project_loading_errors_are_preserved(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="does not exist"):
        get_execution_configuration(str(tmp_path / "missing"))
