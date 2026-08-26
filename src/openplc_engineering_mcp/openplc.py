import json
from collections.abc import Iterator
from pathlib import Path
from typing import Literal, TypedDict, cast

from mcp.server.mcpserver.exceptions import ToolError

ProjectType = Literal["plc-project", "plc-library", "PLC"]
PouType = Literal["program", "function-block", "function"]


class ProjectStructure(TypedDict):
    path: str
    name: str
    type: ProjectType
    files: list[str]


class PouInfo(TypedDict):
    name: str
    type: PouType
    language: str
    path: str


_PROJECT_TYPES = {"plc-project", "plc-library", "PLC"}
_POU_DIRECTORIES: tuple[tuple[PouType, str], ...] = (
    ("function", "pous/functions"),
    ("function-block", "pous/function-blocks"),
    ("program", "pous/programs"),
)
_POU_LANGUAGES = {
    ".st": "st",
    ".il": "il",
    ".ld": "ld",
    ".fbd": "fbd",
    ".py": "python",
    ".cpp": "cpp",
}


def _load_project(project_path: str) -> tuple[Path, str, ProjectType]:
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


def _iter_pou_files(root: Path, relative_dir: str, suffixes: set[str]) -> Iterator[Path]:
    directory = root / relative_dir
    if not directory.is_dir():
        return

    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in suffixes:
            yield path


def _recognized_files(root: Path, relative_dir: str, suffixes: set[str]) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in _iter_pou_files(root, relative_dir, suffixes))


def get_project_structure(project_path: str) -> ProjectStructure:
    """Inspect the relevant on-disk structure of an OpenPLC Editor project."""
    root, name, project_type = _load_project(project_path)

    files = ["project.json"]
    for relative_path in ("library.json", "devices/configuration.json", "devices/pin-mapping.json"):
        if (root / relative_path).is_file():
            files.append(relative_path)

    suffixes = set(_POU_LANGUAGES)
    for _, relative_dir in _POU_DIRECTORIES:
        files.extend(_recognized_files(root, relative_dir, suffixes))

    files.extend(_recognized_files(root, "devices/servers", suffixes))
    files.extend(_recognized_files(root, "devices/remote", suffixes))
    files.extend(_recognized_files(root, "datatypes", {".dt"}))

    return {
        "path": str(root),
        "name": name,
        "type": project_type,
        "files": sorted(set(files)),
    }


def list_pous(project_path: str) -> list[PouInfo]:
    """List POUs recognized by the current OpenPLC Editor project layout."""
    root, _, _ = _load_project(project_path)
    result: list[PouInfo] = []
    suffixes = set(_POU_LANGUAGES)

    for pou_type, relative_dir in _POU_DIRECTORIES:
        seen: set[str] = set()
        for path in _iter_pou_files(root, relative_dir, suffixes):
            name = path.stem
            if name in seen:
                continue
            seen.add(name)
            result.append(
                {
                    "name": name,
                    "type": pou_type,
                    "language": _POU_LANGUAGES[path.suffix.lower()],
                    "path": path.relative_to(root).as_posix(),
                }
            )

    return sorted(result, key=lambda pou: (pou["type"], pou["name"], pou["path"]))
