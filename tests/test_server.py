import json
from pathlib import Path

import pytest
from mcp import Client
from mcp.server import MCPServer

from openplc_engineering_mcp.server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as connected:
        yield connected


def make_project(root: Path) -> Path:
    (root / "pous" / "programs").mkdir(parents=True)
    (root / "pous" / "function-blocks").mkdir(parents=True)
    (root / "devices").mkdir()
    (root / "project.json").write_text(
        json.dumps(
            {
                "meta": {"name": "Example", "type": "plc-project"},
                "data": {
                    "configuration": {
                        "resource": {"tasks": [], "instances": [], "globalVariables": []}
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "devices" / "configuration.json").write_text("{}", encoding="utf-8")
    (root / "pous" / "programs" / "main.st").write_text("PROGRAM main\nEND_PROGRAM\n", encoding="utf-8")
    (root / "pous" / "function-blocks" / "Motor.json").write_text("{}", encoding="utf-8")
    (root / "pous" / "function-blocks" / "Motor.st").write_text(
        "FUNCTION_BLOCK Motor\nEND_FUNCTION_BLOCK\n", encoding="utf-8"
    )
    return root


@pytest.mark.anyio
async def test_server_and_tools_are_discoverable(client: Client) -> None:
    assert isinstance(mcp, MCPServer)
    listed = await client.list_tools()
    assert {tool.name for tool in listed.tools} == {
        "get_server_info",
        "get_project_structure",
        "list_pous",
    }
    assert all(tool.annotations and tool.annotations.read_only_hint for tool in listed.tools)


@pytest.mark.anyio
async def test_get_server_info_can_be_called(client: Client) -> None:
    result = await client.call_tool("get_server_info", {})
    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["name"] == "openplc-engineering"
    assert result.structured_content["write_operations"] is False


@pytest.mark.anyio
async def test_openplc_tools_use_current_project_layout(client: Client, tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    structure = await client.call_tool("get_project_structure", {"project_path": str(project)})
    assert not structure.is_error
    assert structure.structured_content is not None
    assert structure.structured_content["name"] == "Example"
    assert "pous/programs/main.st" in structure.structured_content["files"]

    pous = await client.call_tool("list_pous", {"project_path": str(project)})
    assert not pous.is_error
    assert pous.structured_content is not None
    assert pous.structured_content["result"] == [
        {
            "name": "Motor",
            "type": "function-block",
            "language": "st",
            "path": "pous/function-blocks/Motor.st",
        },
        {
            "name": "main",
            "type": "program",
            "language": "st",
            "path": "pous/programs/main.st",
        },
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("tool_name", ["get_project_structure", "list_pous"])
async def test_invalid_project_path_returns_tool_error(client: Client, tmp_path: Path, tool_name: str) -> None:
    result = await client.call_tool(tool_name, {"project_path": str(tmp_path / "missing")})
    assert result.is_error
    assert "does not exist" in result.content[0].text


@pytest.mark.anyio
async def test_project_path_must_be_directory(client: Client, tmp_path: Path) -> None:
    project_file = tmp_path / "project.json"
    project_file.write_text("{}", encoding="utf-8")

    result = await client.call_tool("get_project_structure", {"project_path": str(project_file)})
    assert result.is_error
    assert "not a directory" in result.content[0].text


@pytest.mark.anyio
async def test_project_json_must_include_data_object(client: Client, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Invalid", "type": "plc-project"}}),
        encoding="utf-8",
    )

    result = await client.call_tool("get_project_structure", {"project_path": str(project)})
    assert result.is_error
    assert "project.json data must be an object" in result.content[0].text
