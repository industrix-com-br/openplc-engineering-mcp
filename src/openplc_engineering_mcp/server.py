"""MCP tool registration and stdio server entry point."""

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from openplc_engineering_mcp.openplc.compiler import CompileResult
from openplc_engineering_mcp.openplc.compiler import compile_project as compile_openplc_project
from openplc_engineering_mcp.openplc.compiler import get_diagnostics as read_compile_diagnostics
from openplc_engineering_mcp.openplc.datatypes import DataTypeInfo
from openplc_engineering_mcp.openplc.datatypes import list_datatypes as inspect_datatypes
from openplc_engineering_mcp.openplc.execution import ExecutionConfiguration
from openplc_engineering_mcp.openplc.execution import (
    get_execution_configuration as inspect_execution_configuration,
)
from openplc_engineering_mcp.openplc.io import IOConfiguration
from openplc_engineering_mcp.openplc.io import get_io_configuration as inspect_io_configuration
from openplc_engineering_mcp.openplc.pous import PouContent, PouInfo, UpdatePouResult
from openplc_engineering_mcp.openplc.pous import list_pous as inspect_pous
from openplc_engineering_mcp.openplc.pous import read_pou as inspect_pou
from openplc_engineering_mcp.openplc.pous import update_pou as update_pou_source
from openplc_engineering_mcp.openplc.project import ProjectStructure, ProjectValidation
from openplc_engineering_mcp.openplc.project import get_project_structure as inspect_project_structure
from openplc_engineering_mcp.openplc.project import validate_project as inspect_project
from openplc_engineering_mcp.openplc.variables import VariableInfo
from openplc_engineering_mcp.openplc.variables import list_global_variables as inspect_global_variables
from openplc_engineering_mcp.openplc.variables import list_variables as inspect_variables

mcp = MCPServer("openplc-engineering")
_READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)
_LOCAL_WRITE = ToolAnnotations(read_only_hint=False, open_world_hint=False)


@mcp.tool(annotations=_READ_ONLY)
def get_project_structure(project_path: str) -> ProjectStructure:
    """Return the relevant file structure of an OpenPLC Editor project."""
    return inspect_project_structure(project_path)


@mcp.tool(annotations=_READ_ONLY)
def list_pous(project_path: str) -> list[PouInfo]:
    """List the programs, function blocks, and functions in an OpenPLC project."""
    return inspect_pous(project_path)


@mcp.tool(annotations=_READ_ONLY)
def list_datatypes(project_path: str) -> list[DataTypeInfo]:
    """List the project-defined data types of an OpenPLC project."""
    return inspect_datatypes(project_path)


@mcp.tool(annotations=_READ_ONLY)
def get_execution_configuration(project_path: str) -> ExecutionConfiguration:
    """Return the execution tasks and program instances of an OpenPLC project."""
    return inspect_execution_configuration(project_path)


@mcp.tool(annotations=_READ_ONLY)
def get_io_configuration(project_path: str) -> IOConfiguration:
    """Return the selected device board and its active physical I/O mapping."""
    return inspect_io_configuration(project_path)


@mcp.tool(annotations=_READ_ONLY)
def read_pou(project_path: str, pou_name: str) -> PouContent:
    """Read a POU from an OpenPLC project by name."""
    return inspect_pou(project_path, pou_name)


@mcp.tool(annotations=_LOCAL_WRITE)
def update_pou(
    project_path: str, pou_name: str, content: str, expected_content_hash: str
) -> UpdatePouResult:
    """Replace the complete content of an existing Structured Text POU.

    The POU is selected by domain name; the caller never supplies a filesystem
    path. The POU name, type, language, and canonical path are immutable through
    this operation, and the replacement must declare the same POU identity.
    expected_content_hash must be the content_hash returned by read_pou() for the
    version the replacement is based on; a stale hash rejects the update.
    Structured Text is the only writable language. Compilation is not triggered
    automatically; call compile_project() explicitly afterwards.
    """
    return update_pou_source(project_path, pou_name, content, expected_content_hash)


@mcp.tool(annotations=_READ_ONLY)
def list_variables(project_path: str, pou_name: str) -> list[VariableInfo]:
    """List variables declared by a POU in an OpenPLC project."""
    return inspect_variables(project_path, pou_name)


@mcp.tool(annotations=_READ_ONLY)
def list_global_variables(project_path: str) -> list[VariableInfo]:
    """List the resource-level global variables configured in an OpenPLC project.

    This returns only configuration.resource.globalVariables; POU VAR_GLOBAL
    declarations and named global variable lists (GVLs) are separate concepts
    outside this tool.
    """
    return inspect_global_variables(project_path)


@mcp.tool(annotations=_READ_ONLY)
def validate_project(project_path: str) -> ProjectValidation:
    """Confirm a directory meets the MCP's shallow OpenPLC project preconditions."""
    return inspect_project(project_path)


@mcp.tool(annotations=_LOCAL_WRITE)
def compile_project(project_path: str) -> CompileResult:
    """Compile an OpenPLC project using openplc-cli."""
    return compile_openplc_project(project_path)


@mcp.tool(annotations=_READ_ONLY)
def get_diagnostics(project_path: str) -> list[str]:
    """Return diagnostics from the project's most recent compilation."""
    return read_compile_diagnostics(project_path)


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
