from pathlib import Path
from typing import Literal, TypedDict

from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.project import list_source_files, load_project

PouType = Literal["program", "function-block", "function"]


class PouInfo(TypedDict):
    name: str
    type: PouType
    language: str | None
    path: str


class PouContent(PouInfo):
    content: str


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
    ".json": None,
}


def _is_contained(root: Path, path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root)
    except (OSError, RuntimeError):
        return False


def _list_pous(root: Path) -> list[PouInfo]:
    by_name: dict[str, PouInfo] = {}

    for pou_type, relative_dir in _POU_DIRECTORIES:
        for path in list_source_files(root, relative_dir, set(_POU_LANGUAGES)):
            if not _is_contained(root, path):
                continue
            suffix = path.suffix.lower()
            info: PouInfo = {
                "name": path.stem,
                "type": pou_type,
                "language": _POU_LANGUAGES[suffix],
                "path": path.relative_to(root).as_posix(),
            }
            existing = by_name.get(info["name"])
            if existing is None or (existing["language"] is None and suffix != ".json"):
                by_name[info["name"]] = info

    return sorted(by_name.values(), key=lambda pou: (pou["type"], pou["name"], pou["path"]))


def list_pous(project_path: str) -> list[PouInfo]:
    """List POUs recognized by the current OpenPLC Editor project layout."""
    root, _, _ = load_project(project_path)
    return _list_pous(root)


def read_pou(project_path: str, pou_name: str) -> PouContent:
    """Read the preferred representation of a POU by name."""
    if not pou_name.strip():
        raise ToolError("pou_name must not be empty")

    root, _, _ = load_project(project_path)
    pou = next((item for item in _list_pous(root) if item["name"] == pou_name), None)
    if pou is None:
        raise ToolError(f'POU not found: "{pou_name}"')

    path = root / pou["path"]
    try:
        if not _is_contained(root, path):
            raise ToolError(f'Could not read POU "{pou_name}": source is outside the project')
        content = path.read_text(encoding="utf-8")
    except (OSError, RuntimeError, UnicodeError) as exc:
        raise ToolError(f'Could not read POU "{pou_name}": {exc}') from exc

    return {
        "name": pou["name"],
        "type": pou["type"],
        "language": pou["language"],
        "path": pou["path"],
        "content": content,
    }
