"""OpenPLC project loading, validation, and structure inspection."""

import json
from pathlib import Path
from typing import Literal, TypedDict, cast

from mcp.server.mcpserver.exceptions import ToolError

ProjectType = Literal["plc-project", "plc-library", "PLC"]


class ProjectStructure(TypedDict):
    path: str
    name: str
    type: ProjectType
    files: list[str]


class ProjectValidation(TypedDict):
    valid: bool
    name: str | None
    type: ProjectType | None
    warnings: list[str]


_PROJECT_TYPES = {"plc-project", "plc-library", "PLC"}
_SOURCE_SUFFIXES = {".st", ".il", ".ld", ".fbd", ".py", ".cpp", ".json"}


def load_project_document(
    project_path: str,
) -> tuple[Path, str, ProjectType, dict[str, object]]:
    """Load an OpenPLC project while retaining its parsed project.json document.

    Returns:
        The resolved project root, project name, project type, and the parsed project.json
        document for domain inspections that need it.

    Raises:
        ToolError: If the project path or project.json is invalid.
    """
    if not project_path.strip():
        raise ToolError("project_path must not be empty")

    root = Path(project_path).expanduser().resolve()
    if not root.exists():
        raise ToolError(f'Project path does not exist: "{root}"')
    if not root.is_dir():
        raise ToolError(f'Project path is not a directory: "{root}"')

    project_file = root / "project.json"
    if not project_file.is_file():
        raise ToolError(f'OpenPLC project not recognized: "{root}" does not contain project.json')

    try:
        content = project_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ToolError(f"Could not read project.json: {exc}") from exc

    try:
        project = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ToolError(f"project.json is not valid JSON: {exc.msg}") from exc

    if not isinstance(project, dict):
        raise ToolError("OpenPLC project not recognized: project.json must contain a JSON object")

    meta = project.get("meta")
    if not isinstance(meta, dict):
        raise ToolError("OpenPLC project not recognized: project.json is missing meta")

    name = meta.get("name")
    project_type = meta.get("type")
    if not isinstance(name, str):
        raise ToolError("OpenPLC project not recognized: project.json meta.name must be a string")
    if project_type not in _PROJECT_TYPES:
        raise ToolError("OpenPLC project not recognized: unsupported project.json meta.type")

    return root, name, cast(ProjectType, project_type), cast(dict[str, object], project)


def load_project(project_path: str) -> tuple[Path, str, ProjectType]:
    """Load the basic metadata required from an OpenPLC Editor project.

    Returns:
        The resolved project root, project name, and project type.

    Raises:
        ToolError: If the project path or project.json is invalid.
    """
    root, name, project_type, _ = load_project_document(project_path)
    return root, name, project_type


def validate_project(project_path: str) -> ProjectValidation:
    """Check the MCP's shallow OpenPLC project preconditions.

    Raises:
        ToolError: If the project path or required metadata is invalid.
    """
    _, name, project_type = load_project(project_path)
    return {
        "valid": True,
        "name": name,
        "type": project_type,
        "warnings": [],
    }


def list_source_files(root: Path, relative_dir: str, suffixes: set[str]) -> list[Path]:
    """Return recognized source files under a project-relative directory, sorted."""
    directory = root / relative_dir
    if not directory.is_dir():
        return []

    return sorted(
        path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() in suffixes
    )


def _recognized_files(root: Path, relative_dir: str, suffixes: set[str]) -> list[str]:
    return [
        path.relative_to(root).as_posix() for path in list_source_files(root, relative_dir, suffixes)
    ]


def get_project_structure(project_path: str) -> ProjectStructure:
    """Inspect the relevant on-disk structure of an OpenPLC Editor project."""
    root, name, project_type = load_project(project_path)

    files = ["project.json"]
    for relative_path in ("library.json", "devices/configuration.json", "devices/pin-mapping.json"):
        if (root / relative_path).is_file():
            files.append(relative_path)

    for relative_dir in ("pous/functions", "pous/function-blocks", "pous/programs"):
        files.extend(_recognized_files(root, relative_dir, _SOURCE_SUFFIXES))

    files.extend(_recognized_files(root, "devices/servers", _SOURCE_SUFFIXES))
    files.extend(_recognized_files(root, "devices/remote", _SOURCE_SUFFIXES))
    files.extend(_recognized_files(root, "datatypes", {".dt"}))

    return {
        "path": str(root),
        "name": name,
        "type": project_type,
        "files": sorted(set(files)),
    }
