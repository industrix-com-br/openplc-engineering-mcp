import json
from pathlib import Path

import pytest
from mcp import Client
from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent

from openplc_engineering_mcp.server import mcp


def tool_text(result: CallToolResult) -> str:
    assert result.content
    return TextContent.model_validate(result.content[0]).text


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as connected:
        yield connected


@pytest.mark.anyio
async def test_server_and_tools_are_discoverable(client: Client) -> None:
    assert isinstance(mcp, MCPServer)
    listed = await client.list_tools()
    tools = {tool.name: tool for tool in listed.tools}
    assert set(tools) == {
        "compile_project",
        "get_diagnostics",
        "get_project_structure",
        "list_pous",
        "read_pou",
        "validate_project",
    }
    assert tools["compile_project"].annotations
    assert tools["compile_project"].annotations.read_only_hint is False
    assert all(tool.annotations and tool.annotations.open_world_hint is False for tool in listed.tools)
    assert all(
        tool.annotations and tool.annotations.read_only_hint
        for name, tool in tools.items()
        if name != "compile_project"
    )


@pytest.mark.anyio
async def test_tool_call_returns_structured_content(client: Client, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )

    result = await client.call_tool("validate_project", {"project_path": str(project)})

    assert not result.is_error
    assert result.structured_content == {
        "valid": True,
        "name": "Minimal",
        "type": "plc-project",
        "warnings": [],
    }


@pytest.mark.anyio
async def test_read_pou_returns_structured_content(client: Client, tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "pous" / "programs").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )
    (project / "pous" / "programs" / "main.st").write_text(
        "PROGRAM main\nEND_PROGRAM\n", encoding="utf-8"
    )

    result = await client.call_tool(
        "read_pou", {"project_path": str(project), "pou_name": "main"}
    )

    assert not result.is_error
    assert result.structured_content == {
        "name": "main",
        "type": "program",
        "language": "st",
        "path": "pous/programs/main.st",
        "content": "PROGRAM main\nEND_PROGRAM\n",
    }


@pytest.mark.anyio
async def test_tool_errors_are_exposed_through_mcp(client: Client, tmp_path: Path) -> None:
    result = await client.call_tool("validate_project", {"project_path": str(tmp_path / "missing")})

    assert result.is_error
    assert "does not exist" in tool_text(result)
