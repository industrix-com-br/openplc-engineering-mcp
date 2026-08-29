"""MCP tool registration and stdio server entry point."""

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from openplc_engineering_mcp.openplc.compiler import CompileResult
from openplc_engineering_mcp.openplc.compiler import compile_project as compile_openplc_project
from openplc_engineering_mcp.openplc.compiler import get_diagnostics as read_compile_diagnostics
from openplc_engineering_mcp.openplc.pous import PouContent, PouInfo
from openplc_engineering_mcp.openplc.pous import list_pous as inspect_pous
from openplc_engineering_mcp.openplc.pous import read_pou as inspect_pou
from openplc_engineering_mcp.openplc.project import ProjectStructure, ProjectValidation
from openplc_engineering_mcp.openplc.project import get_project_structure as inspect_project_structure
from openplc_engineering_mcp.openplc.project import validate_project as inspect_project
from openplc_engineering_mcp.openplc.variables import VariableInfo
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
def read_pou(project_path: str, pou_name: str) -> PouContent:
    """Read a POU from an OpenPLC project by name."""
    return inspect_pou(project_path, pou_name)


@mcp.tool(annotations=_READ_ONLY)
def list_variables(project_path: str, pou_name: str) -> list[VariableInfo]:
    """List variables declared by a POU in an OpenPLC project."""
    return inspect_variables(project_path, pou_name)


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
