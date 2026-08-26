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


def make_project(root: Path, *, project_type: str = "plc-project") -> Path:
    (root / "pous" / "programs").mkdir(parents=True)
    (root / "pous" / "function-blocks").mkdir(parents=True)
    (root / "devices").mkdir()
    (root / "project.json").write_text(
        json.dumps(
            {
                "meta": {"name": "Example", "type": project_type},
                "data": {
                    "configuration": {"resource": {"tasks": [], "instances": [], "globalVariables": []}}
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
        "validate_project",
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
    assert structure.structured_content["type"] == "plc-project"
    assert "pous/programs/main.st" in structure.structured_content["files"]
    assert "pous/function-blocks/Motor.st" in structure.structured_content["files"]
    assert "pous/function-blocks/Motor.json" in structure.structured_content["files"]

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
async def test_json_only_pou_is_supported(client: Client, tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    (project / "pous" / "function-blocks" / "Motor.st").unlink()

    pous = await client.call_tool("list_pous", {"project_path": str(project)})
    assert not pous.is_error
    assert pous.structured_content is not None
    motor = next(pou for pou in pous.structured_content["result"] if pou["name"] == "Motor")
    assert motor == {
        "name": "Motor",
        "type": "function-block",
        "language": None,
        "path": "pous/function-blocks/Motor.json",
    }


@pytest.mark.anyio
async def test_pou_names_are_deduplicated_globally(client: Client, tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    (project / "pous" / "programs" / "Motor.st").write_text("PROGRAM Motor\nEND_PROGRAM\n", encoding="utf-8")

    pous = await client.call_tool("list_pous", {"project_path": str(project)})
    assert not pous.is_error
    assert pous.structured_content is not None
    motors = [pou for pou in pous.structured_content["result"] if pou["name"] == "Motor"]
    assert motors == [
        {
            "name": "Motor",
            "type": "function-block",
            "language": "st",
            "path": "pous/function-blocks/Motor.st",
        }
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("project_type", ["plc-project", "plc-library", "PLC"])
async def test_accepted_project_types(client: Client, tmp_path: Path, project_type: str) -> None:
    project = make_project(tmp_path / "project", project_type=project_type)
    result = await client.call_tool("get_project_structure", {"project_path": str(project)})
    assert not result.is_error
    assert result.structured_content["type"] == project_type


@pytest.mark.anyio
async def test_a_meta_only_project_is_recognized(client: Client, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )

    result = await client.call_tool("get_project_structure", {"project_path": str(project)})
    assert not result.is_error
    assert result.structured_content["name"] == "Minimal"
    assert result.structured_content["files"] == ["project.json"]


@pytest.mark.anyio
@pytest.mark.parametrize("tool_name", ["get_project_structure", "list_pous"])
async def test_invalid_project_path_returns_tool_error(
    client: Client, tmp_path: Path, tool_name: str
) -> None:
    result = await client.call_tool(tool_name, {"project_path": str(tmp_path / "missing")})
    assert result.is_error
    assert "does not exist" in tool_text(result)


@pytest.mark.anyio
async def test_project_path_must_be_directory(client: Client, tmp_path: Path) -> None:
    project_file = tmp_path / "project.json"
    project_file.write_text("{}", encoding="utf-8")

    result = await client.call_tool("get_project_structure", {"project_path": str(project_file)})
    assert result.is_error
    assert "not a directory" in tool_text(result)


@pytest.mark.anyio
async def test_missing_project_json_is_rejected(client: Client, tmp_path: Path) -> None:
    result = await client.call_tool("get_project_structure", {"project_path": str(tmp_path)})
    assert result.is_error
    assert "does not contain project.json" in tool_text(result)


@pytest.mark.anyio
async def test_invalid_project_json_is_rejected(client: Client, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{not-json", encoding="utf-8")

    result = await client.call_tool("get_project_structure", {"project_path": str(project)})
    assert result.is_error
    assert "not valid JSON" in tool_text(result)


@pytest.mark.anyio
async def test_unsupported_meta_type_is_rejected(client: Client, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "X", "type": "something-else"}}), encoding="utf-8"
    )

    result = await client.call_tool("get_project_structure", {"project_path": str(project)})
    assert result.is_error
    assert "unsupported project.json meta.type" in tool_text(result)


@pytest.mark.anyio
async def test_validate_project_reports_valid_project(client: Client, tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    result = await client.call_tool("validate_project", {"project_path": str(project)})
    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content == {
        "valid": True,
        "name": "Example",
        "type": "plc-project",
        "warnings": [],
    }


@pytest.mark.anyio
async def test_validate_project_keeps_meta_only_project_valid(client: Client, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )

    result = await client.call_tool("validate_project", {"project_path": str(project)})
    assert not result.is_error
    assert result.structured_content["valid"] is True
    assert result.structured_content["warnings"] == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "content",
    [None, "{not-json", json.dumps({"meta": {"name": "X", "type": "bad"}})],
    ids=["missing-project-json", "invalid-json", "bad-type"],
)
async def test_validate_project_reports_unrecoverable_failures_as_errors(
    client: Client, tmp_path: Path, content: str | None
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    if content is not None:
        (project / "project.json").write_text(content, encoding="utf-8")

    result = await client.call_tool("validate_project", {"project_path": str(project)})
    assert result.is_error
