"""OpenPLC execution configuration inspection."""

from typing import Literal, TypedDict, cast

from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.project import load_project_document

TaskTrigger = Literal["Cyclic", "Interrupt"]


class ExecutionTask(TypedDict):
    name: str
    triggering: TaskTrigger
    interval: str | None
    priority: int


class ProgramInstance(TypedDict):
    name: str
    task: str
    program: str


class ExecutionConfiguration(TypedDict):
    tasks: list[ExecutionTask]
    program_instances: list[ProgramInstance]


def _execution_resource(project: dict[str, object]) -> dict[str, object] | None:
    """Return the current or legacy execution resource when present."""
    data = project.get("data")
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ToolError("project.json data must be an object")

    configuration = data.get("configuration")
    configuration_field = "configuration"
    if configuration is None:
        configuration = data.get("configurations")
        configuration_field = "configurations"
    if configuration is None:
        return None
    if not isinstance(configuration, dict):
        raise ToolError(f"project.json data.{configuration_field} must be an object")

    resource = configuration.get("resource")
    if resource is None:
        return None
    if not isinstance(resource, dict):
        raise ToolError(f"project.json data.{configuration_field}.resource must be an object")
    return cast(dict[str, object], resource)


def _parse_task(task: object, index: int) -> ExecutionTask:
    """Parse and validate a single execution Task from the project document."""
    if not isinstance(task, dict):
        raise ToolError(f"project.json execution task {index} must be an object")

    name = task.get("name")
    triggering = task.get("triggering")
    interval = task.get("interval")
    priority = task.get("priority")

    if not isinstance(name, str):
        raise ToolError(f"project.json execution task {index}.name must be a string")
    if triggering not in ("Cyclic", "Interrupt"):
        raise ToolError(
            f"project.json execution task {index}.triggering must be Cyclic or Interrupt"
        )
    if not isinstance(interval, str):
        raise ToolError(f"project.json execution task {index}.interval must be a string")
    if type(priority) is not int:
        raise ToolError(f"project.json execution task {index}.priority must be an integer")

    return {
        "name": name,
        "triggering": cast(TaskTrigger, triggering),
        "interval": interval if triggering == "Cyclic" else None,
        "priority": priority,
    }


def _parse_program_instance(instance: object, index: int) -> ProgramInstance:
    """Parse and validate a single Program Instance from the project document."""
    if not isinstance(instance, dict):
        raise ToolError(f"project.json program instance {index} must be an object")

    name = instance.get("name")
    task = instance.get("task")
    program = instance.get("program")

    if not isinstance(name, str):
        raise ToolError(f"project.json program instance {index}.name must be a string")
    if not isinstance(task, str):
        raise ToolError(f"project.json program instance {index}.task must be a string")
    if not isinstance(program, str):
        raise ToolError(f"project.json program instance {index}.program must be a string")

    return {"name": name, "task": task, "program": program}


def get_execution_configuration(project_path: str) -> ExecutionConfiguration:
    """Return the execution tasks and program instances of an OpenPLC project."""
    _, _, _, project = load_project_document(project_path)
    resource = _execution_resource(project)
    if resource is None:
        return {"tasks": [], "program_instances": []}

    tasks = resource.get("tasks", [])
    instances = resource.get("instances", [])
    if not isinstance(tasks, list):
        raise ToolError("project.json execution tasks must be an array")
    if not isinstance(instances, list):
        raise ToolError("project.json program instances must be an array")

    return {
        "tasks": [_parse_task(task, index) for index, task in enumerate(tasks)],
        "program_instances": [
            _parse_program_instance(instance, index) for index, instance in enumerate(instances)
        ],
    }
