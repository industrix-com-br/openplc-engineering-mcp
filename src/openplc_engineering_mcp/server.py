from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from openplc_engineering_mcp.openplc import PouInfo, ProjectStructure, ProjectValidation
from openplc_engineering_mcp.openplc import get_project_structure as inspect_project_structure
from openplc_engineering_mcp.openplc import list_pous as inspect_pous
from openplc_engineering_mcp.openplc import validate_project as inspect_project

mcp = MCPServer("openplc-engineering")
_READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


@mcp.tool(annotations=_READ_ONLY)
def get_project_structure(project_path: str) -> ProjectStructure:
    """Return the relevant file structure of an OpenPLC Editor project."""
    return inspect_project_structure(project_path)


@mcp.tool(annotations=_READ_ONLY)
def list_pous(project_path: str) -> list[PouInfo]:
    """List the programs, function blocks, and functions in an OpenPLC project."""
    return inspect_pous(project_path)


@mcp.tool(annotations=_READ_ONLY)
def validate_project(project_path: str) -> ProjectValidation:
    """Confirm a directory meets the MCP's shallow OpenPLC project preconditions."""
    return inspect_project(project_path)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
