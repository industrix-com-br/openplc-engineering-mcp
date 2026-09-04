"""OpenPLC CLI compilation and process-local diagnostics."""

import json
import re
import subprocess
from typing import TypedDict

from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.project import load_project


class CompileResult(TypedDict):
    success: bool
    exit_code: int
    output: object | None


_CHROMIUM_LOG_LINE = re.compile(r"^\[\d+(?::\d+)?:\d+/\d+\.\d+:[A-Z]+:")


def _is_platform_noise(line: str) -> bool:
    """Electron platform logs and user-data scaffolding reach stderr without being compile diagnostics."""
    return (
        _CHROMIUM_LOG_LINE.match(line) is not None
        or line.startswith("File already exists at ")
        or line == "Skipping creation."
    )


_LAST_DIAGNOSTICS: dict[str, list[str]] = {}


def compile_project(project_path: str) -> CompileResult:
    """Compile an OpenPLC project and cache stderr diagnostics for this process."""
    root, _, _ = load_project(project_path)

    try:
        result = subprocess.run(
            ["openplc-cli", "compile", str(root), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ToolError("openplc-cli was not found on PATH") from exc
    except OSError as exc:
        raise ToolError(f"Could not run openplc-cli: {exc}") from exc

    _LAST_DIAGNOSTICS[str(root)] = [
        stripped
        for line in result.stderr.splitlines()
        if (stripped := line.strip()) and not _is_platform_noise(stripped)
    ]

    output: object | None = None
    if result.stdout.strip():
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ToolError("openplc-cli returned invalid JSON") from exc

    return {
        "success": result.returncode == 0,
        "exit_code": result.returncode,
        "output": output,
    }


def get_diagnostics(project_path: str) -> list[str]:
    """Return diagnostics from the project's most recent compilation in this process."""
    root, _, _ = load_project(project_path)
    try:
        return _LAST_DIAGNOSTICS[str(root)]
    except KeyError as exc:
        raise ToolError("No compilation diagnostics are available for this project") from exc
