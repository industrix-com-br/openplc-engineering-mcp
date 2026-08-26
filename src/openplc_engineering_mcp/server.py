from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from openplc_engineering_mcp.openplc import PouInfo, ProjectStructure
from openplc_engineering_mcp.openplc import get_project_structure as inspect_project_structure
from openplc_engineering_mcp.openplc import list_pous as inspect_pous

mcp = MCPServer("openplc-engineering")
_READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True)


@mcp.tool(annotations=_READ_ONLY)
def get_server_info() -> dict[str, object]:
    """Return basic information about this experimental OpenPLC MCP server."""
    return {
        "name": "openplc-engineering",
        "status": "experimental",
        "transport": "stdio",
        "write_operations": False,
    }


@mcp.tool(annotations=_READ_ONLY)
def get_project_structure(project_path: str) -> ProjectStructure:
    """Return the relevant file structure of an OpenPLC Editor project."""
    return inspect_project_structure(project_path)


@mcp.tool(annotations=_READ_ONLY)
def list_pous(project_path: str) -> list[PouInfo]:
    """List the programs, function blocks, and functions in an OpenPLC project."""
    return inspect_pous(project_path)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
