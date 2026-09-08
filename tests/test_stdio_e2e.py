"""Exercise the deployable MCP boundary without an OpenPLC CLI installation."""

import hashlib
import json
import sys
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_stdio_project_round_trip(tmp_path: Path) -> None:
    (tmp_path / "project.json").write_text(
        json.dumps({"meta": {"name": "Stdio project", "type": "plc-project"}}), encoding="utf-8"
    )
    source = "PROGRAM MAIN\nEND_PROGRAM\n"
    pou = tmp_path / "pous" / "programs" / "MAIN.st"
    pou.parent.mkdir(parents=True)
    pou.write_bytes(source.encode("utf-8"))
    replacement = "PROGRAM MAIN\n    (* Updated through stdio: ação *)\nEND_PROGRAM\n"
    arguments = {"project_path": str(tmp_path), "pou_name": "MAIN"}
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "openplc_engineering_mcp.server"],
        cwd=tmp_path,
    )

    # Bound protocol waits; the SDK owns and reaps the child even on failure/cancellation.
    with anyio.fail_after(30):
        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                listed = await session.list_tools()
                assert {"validate_project", "read_pou", "update_pou"} <= {
                    tool.name for tool in listed.tools
                }

                validated = await session.call_tool("validate_project", {"project_path": str(tmp_path)})
                assert not validated.is_error
                assert validated.structured_content == {
                    "valid": True,
                    "name": "Stdio project",
                    "type": "plc-project",
                    "warnings": [],
                }

                original = await session.call_tool("read_pou", arguments)
                assert not original.is_error
                assert original.structured_content is not None
                assert original.structured_content["name"] == "MAIN"
                assert original.structured_content["content"] == source
                assert original.structured_content["content_hash"] == (
                    "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest()
                )

                updated = await session.call_tool(
                    "update_pou",
                    {
                        **arguments,
                        "content": replacement,
                        "expected_content_hash": original.structured_content["content_hash"],
                    },
                )
                assert not updated.is_error
                assert updated.structured_content is not None
                new_hash = updated.structured_content["content_hash"]
                assert new_hash != original.structured_content["content_hash"]
                assert new_hash == "sha256:" + hashlib.sha256(replacement.encode("utf-8")).hexdigest()

                reread = await session.call_tool("read_pou", arguments)
                assert not reread.is_error
                assert reread.structured_content is not None
                assert reread.structured_content["content"] == replacement
                assert reread.structured_content["content_hash"] == new_hash

    # Reaching here also requires both SDK contexts to finish their shutdown paths.
    assert pou.read_bytes() == replacement.encode("utf-8")
