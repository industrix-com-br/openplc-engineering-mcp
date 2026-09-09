"""Concise engineering navigation composed from existing domain inspections."""

from typing import TypedDict

from openplc_engineering_mcp.openplc.datatypes import list_datatypes
from openplc_engineering_mcp.openplc.execution import get_execution_configuration
from openplc_engineering_mcp.openplc.io import get_io_configuration
from openplc_engineering_mcp.openplc.pous import list_pous
from openplc_engineering_mcp.openplc.project import ProjectType, get_project_structure
from openplc_engineering_mcp.openplc.variables import list_global_variables


class PouOverview(TypedDict):
    programs: list[str]
    function_blocks: list[str]
    functions: list[str]


class ExecutionOverview(TypedDict):
    tasks: list[str]
    program_instances: list[str]


class IOOverview(TypedDict):
    device_board: str
    mapping_count: int


class ProjectOverview(TypedDict):
    name: str
    type: ProjectType
    pous: PouOverview
    datatypes: list[str]
    global_variables: list[str]
    execution: ExecutionOverview
    io: IOOverview | None
    files: list[str]


def get_project_overview(project_path: str) -> ProjectOverview:
    """Return a navigation projection, preserving reader ordering and ToolError failures."""
    structure = get_project_structure(project_path)
    pous = list_pous(project_path)
    datatypes = list_datatypes(project_path)
    globals_ = list_global_variables(project_path)
    execution = get_execution_configuration(project_path)
    io: IOOverview | None = None
    if structure["type"] == "plc-project":
        configuration = get_io_configuration(project_path)
        io = {
            "device_board": configuration["device_board"],
            "mapping_count": len(configuration["io_points"]),
        }
    return {
        "name": structure["name"],
        "type": structure["type"],
        "pous": {
            "programs": [pou["name"] for pou in pous if pou["type"] == "program"],
            "function_blocks": [pou["name"] for pou in pous if pou["type"] == "function-block"],
            "functions": [pou["name"] for pou in pous if pou["type"] == "function"],
        },
        "datatypes": [datatype["name"] for datatype in datatypes],
        "global_variables": [variable["name"] for variable in globals_],
        "execution": {
            "tasks": [task["name"] for task in execution["tasks"]],
            "program_instances": [instance["name"] for instance in execution["program_instances"]],
        },
        "io": io,
        "files": structure["files"],
    }
