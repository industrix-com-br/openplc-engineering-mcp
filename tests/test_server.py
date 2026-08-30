import hashlib
import json
from pathlib import Path

import pytest
from mcp import Client
from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent

from openplc_engineering_mcp.server import mcp


def sha256_token(raw: bytes) -> str:
    """Return the exact-byte sha256: token expected for raw persisted bytes."""
    return "sha256:" + hashlib.sha256(raw).hexdigest()


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
    """The server lists exactly the twelve domain tools with correct annotations."""
    assert isinstance(mcp, MCPServer)
    listed = await client.list_tools()
    tools = {tool.name: tool for tool in listed.tools}
    assert set(tools) == {
        "compile_project",
        "get_diagnostics",
        "get_execution_configuration",
        "get_io_configuration",
        "get_project_structure",
        "list_datatypes",
        "list_global_variables",
        "list_pous",
        "list_variables",
        "read_pou",
        "update_pou",
        "validate_project",
    }
    assert tools["list_datatypes"].annotations
    assert tools["list_datatypes"].annotations.read_only_hint is True
    assert tools["list_datatypes"].annotations.open_world_hint is False
    assert tools["list_global_variables"].annotations
    assert tools["list_global_variables"].annotations.read_only_hint is True
    assert tools["list_global_variables"].annotations.open_world_hint is False
    assert tools["compile_project"].annotations
    assert tools["compile_project"].annotations.read_only_hint is False
    assert tools["update_pou"].annotations
    assert tools["update_pou"].annotations.read_only_hint is False
    assert tools["update_pou"].annotations.open_world_hint is False
    assert tools["get_execution_configuration"].annotations
    assert tools["get_execution_configuration"].annotations.read_only_hint is True
    assert tools["get_execution_configuration"].annotations.open_world_hint is False
    assert tools["get_io_configuration"].annotations
    assert tools["get_io_configuration"].annotations.read_only_hint is True
    assert tools["get_io_configuration"].annotations.open_world_hint is False
    assert tools["list_variables"].annotations
    assert tools["list_variables"].annotations.read_only_hint is True
    assert tools["list_variables"].annotations.open_world_hint is False
    assert all(tool.annotations and tool.annotations.open_world_hint is False for tool in listed.tools)
    assert all(
        tool.annotations and tool.annotations.read_only_hint
        for name, tool in tools.items()
        if name not in {"compile_project", "update_pou"}
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
async def test_execution_configuration_returns_structured_content(
    client: Client, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps(
            {
                "meta": {"name": "Minimal", "type": "plc-project"},
                "data": {
                    "configuration": {
                        "resource": {
                            "tasks": [
                                {
                                    "name": "MainTask",
                                    "triggering": "Cyclic",
                                    "interval": "T#20ms",
                                    "priority": 0,
                                }
                            ],
                            "instances": [
                                {
                                    "name": "MainInstance",
                                    "task": "MainTask",
                                    "program": "main",
                                }
                            ],
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = await client.call_tool(
        "get_execution_configuration", {"project_path": str(project)}
    )

    assert not result.is_error
    assert result.structured_content == {
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


@pytest.mark.anyio
async def test_execution_configuration_errors_are_exposed_through_mcp(
    client: Client, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps(
            {
                "meta": {"name": "Minimal", "type": "plc-project"},
                "data": {"configuration": {"resource": {"tasks": {}}}},
            }
        ),
        encoding="utf-8",
    )

    result = await client.call_tool(
        "get_execution_configuration", {"project_path": str(project)}
    )

    assert result.is_error
    assert "execution tasks must be an array" in tool_text(result)


@pytest.mark.anyio
async def test_io_configuration_returns_structured_content(client: Client, tmp_path: Path) -> None:
    """get_io_configuration returns the active board and its I/O points as structured content."""
    project = tmp_path / "project"
    devices = project / "devices"
    devices.mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )
    (devices / "configuration.json").write_text(
        json.dumps({"deviceBoard": "Arduino Uno"}), encoding="utf-8"
    )
    (devices / "pin-mapping.json").write_text(
        json.dumps(
            {
                "Arduino Uno": [
                    {
                        "pin": "2",
                        "pinType": "digitalInput",
                        "address": "%IX0.0",
                        "alias": "StartButton",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = await client.call_tool("get_io_configuration", {"project_path": str(project)})

    assert not result.is_error
    assert result.structured_content == {
        "device_board": "Arduino Uno",
        "io_points": [
            {
                "pin": "2",
                "pin_type": "digitalInput",
                "address": "%IX0.0",
                "alias": "StartButton",
            }
        ],
    }


@pytest.mark.anyio
async def test_io_configuration_errors_are_exposed_through_mcp(
    client: Client, tmp_path: Path
) -> None:
    """Unsupported pin-mapping formats surface as MCP tool errors from get_io_configuration."""
    project = tmp_path / "project"
    devices = project / "devices"
    devices.mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )
    (devices / "configuration.json").write_text(
        json.dumps({"deviceBoard": "Arduino Uno"}), encoding="utf-8"
    )
    (devices / "pin-mapping.json").write_text(
        json.dumps(
            [
                {
                    "pin": "2",
                    "pinType": "digitalInput",
                    "address": "%IX0.0",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = await client.call_tool("get_io_configuration", {"project_path": str(project)})

    assert result.is_error
    assert "Unsupported OpenPLC project format" in tool_text(result)


@pytest.mark.anyio
async def test_list_datatypes_returns_structured_content(client: Client, tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "datatypes").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )
    (project / "datatypes" / "OperatingMode.dt").write_text(
        "TYPE\nOperatingMode : (Auto, Manual) := Auto;\nEND_TYPE\n", encoding="utf-8"
    )

    result = await client.call_tool("list_datatypes", {"project_path": str(project)})

    assert not result.is_error
    assert result.structured_content == {
        "result": [
            {
                "name": "OperatingMode",
                "kind": "enumerated",
                "values": ["Auto", "Manual"],
                "initial_value": "Auto",
            }
        ]
    }


@pytest.mark.anyio
async def test_list_datatype_errors_are_exposed_through_mcp(client: Client, tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "datatypes").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )
    (project / "datatypes" / "Alpha.dt").write_text(
        "TYPE\nBeta : (A, B);\nEND_TYPE\n", encoding="utf-8"
    )

    result = await client.call_tool("list_datatypes", {"project_path": str(project)})

    assert result.is_error
    assert "does not match filename identity" in tool_text(result)


@pytest.mark.anyio
async def test_read_pou_returns_structured_content(client: Client, tmp_path: Path) -> None:
    """read_pou() returns identity, content, and content_hash as structured content."""
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
        "content_hash": sha256_token(b"PROGRAM main\nEND_PROGRAM\n"),
    }


@pytest.mark.anyio
async def test_update_pou_schemas_match_the_public_contract(client: Client) -> None:
    """update_pou and read_pou expose the documented input and output schemas."""
    listed = await client.list_tools()
    tool = next(tool for tool in listed.tools if tool.name == "update_pou")

    assert set(tool.input_schema["properties"]) == {
        "project_path",
        "pou_name",
        "content",
        "expected_content_hash",
    }
    assert set(tool.input_schema["required"]) == {
        "project_path",
        "pou_name",
        "content",
        "expected_content_hash",
    }
    assert tool.output_schema is not None
    assert set(tool.output_schema["properties"]) == {"name", "content_hash"}
    assert set(tool.output_schema["required"]) == {"name", "content_hash"}

    read_tool = next(tool for tool in listed.tools if tool.name == "read_pou")
    assert read_tool.output_schema is not None
    assert "content_hash" in read_tool.output_schema["properties"]


@pytest.mark.anyio
async def test_update_pou_returns_structured_content(client: Client, tmp_path: Path) -> None:
    """update_pou returns the updated name and hash and persists the replacement."""
    project = tmp_path / "project"
    (project / "pous" / "programs").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )
    (project / "pous" / "programs" / "main.st").write_text(
        "PROGRAM main\nEND_PROGRAM\n", encoding="utf-8"
    )
    replacement = "PROGRAM main\n    (* updated *)\nEND_PROGRAM\n"

    result = await client.call_tool(
        "update_pou",
        {
            "project_path": str(project),
            "pou_name": "main",
            "content": replacement,
            "expected_content_hash": sha256_token(b"PROGRAM main\nEND_PROGRAM\n"),
        },
    )

    assert not result.is_error
    assert result.structured_content == {
        "name": "main",
        "content_hash": sha256_token(replacement.encode("utf-8")),
    }
    assert (project / "pous" / "programs" / "main.st").read_text(encoding="utf-8") == replacement


@pytest.mark.anyio
async def test_update_pou_errors_are_exposed_through_mcp(client: Client, tmp_path: Path) -> None:
    """Stale-hash update failures surface as MCP tool errors."""
    project = tmp_path / "project"
    (project / "pous" / "programs").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )
    (project / "pous" / "programs" / "main.st").write_text(
        "PROGRAM main\nEND_PROGRAM\n", encoding="utf-8"
    )

    result = await client.call_tool(
        "update_pou",
        {
            "project_path": str(project),
            "pou_name": "main",
            "content": "PROGRAM main\nEND_PROGRAM\n",
            "expected_content_hash": "sha256:" + "0" * 64,
        },
    )

    assert result.is_error
    assert "POU changed since it was read" in tool_text(result)


@pytest.mark.anyio
async def test_list_variables_returns_structured_content(client: Client, tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "pous" / "function-blocks").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )
    (project / "pous" / "function-blocks" / "Motor.st").write_text(
        """FUNCTION_BLOCK Motor
VAR_INPUT
    Start : BOOL;
END_VAR
END_FUNCTION_BLOCK
""",
        encoding="utf-8",
    )

    result = await client.call_tool(
        "list_variables", {"project_path": str(project), "pou_name": "Motor"}
    )

    assert not result.is_error
    assert result.structured_content == {
        "result": [
            {
                "name": "Start",
                "class": "input",
                "type": "BOOL",
                "location": None,
                "initial_value": None,
                "documentation": None,
            }
        ]
    }


@pytest.mark.anyio
async def test_list_variables_errors_are_exposed_through_mcp(client: Client, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Minimal", "type": "plc-project"}}), encoding="utf-8"
    )

    result = await client.call_tool(
        "list_variables", {"project_path": str(project), "pou_name": "Missing"}
    )

    assert result.is_error
    assert "POU not found" in tool_text(result)


@pytest.mark.anyio
async def test_list_global_variables_returns_structured_content(
    client: Client, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps(
            {
                "meta": {"name": "Minimal", "type": "plc-project"},
                "data": {
                    "configuration": {
                        "resource": {
                            "globalVariables": [
                                {
                                    "name": "EmergencyStop",
                                    "type": {"definition": "base-type", "value": "BOOL"},
                                    "location": "%IX0.0",
                                    "initialValue": "",
                                    "documentation": "Emergency stop input",
                                }
                            ]
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = await client.call_tool("list_global_variables", {"project_path": str(project)})

    assert not result.is_error
    assert result.structured_content == {
        "result": [
            {
                "name": "EmergencyStop",
                "class": "global",
                "type": "BOOL",
                "location": "%IX0.0",
                "initial_value": None,
                "documentation": "Emergency stop input",
            }
        ]
    }


@pytest.mark.anyio
async def test_list_global_variables_errors_are_exposed_through_mcp(
    client: Client, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps(
            {
                "meta": {"name": "Minimal", "type": "plc-project"},
                "data": {"configuration": {"resource": {"globalVariables": {}}}},
            }
        ),
        encoding="utf-8",
    )

    result = await client.call_tool("list_global_variables", {"project_path": str(project)})

    assert result.is_error
    assert "global variables must be an array" in tool_text(result)


@pytest.mark.anyio
async def test_tool_errors_are_exposed_through_mcp(client: Client, tmp_path: Path) -> None:
    result = await client.call_tool("validate_project", {"project_path": str(tmp_path / "missing")})

    assert result.is_error
    assert "does not exist" in tool_text(result)
