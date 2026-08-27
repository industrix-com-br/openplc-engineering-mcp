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


def load_project(project_path: str) -> tuple[Path, str, ProjectType]:
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

    return root, name, cast(ProjectType, project_type)


def validate_project(project_path: str) -> ProjectValidation:
    """Shallowly confirm a directory is a loadable OpenPLC Editor project.

    Validation is intentionally limited to the MCP-local filesystem and basic
    metadata preconditions required for file-oriented operations. Authoritative
    project loading/validation semantics belong to OpenPLC and are reused via a
    future ``openplc-cli`` step rather than reproduced here.

    Unrecoverable failures (missing path/directory/``project.json``, malformed
    JSON, unsupported ``meta.type``) surface as tool errors, while
    ``warnings`` is reserved for recoverable conditions that OpenPLC loads.
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
