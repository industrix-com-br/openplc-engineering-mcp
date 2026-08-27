from collections.abc import Iterator
from pathlib import Path
from typing import Literal, TypedDict

from openplc_engineering_mcp.openplc.project import _load_project

PouType = Literal["program", "function-block", "function"]


class PouInfo(TypedDict):
    name: str
    type: PouType
    language: str | None
    path: str


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


def _iter_pou_files(root: Path, relative_dir: str) -> Iterator[Path]:
    directory = root / relative_dir
    if not directory.is_dir():
        return

    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in _POU_LANGUAGES:
            yield path


def list_pous(project_path: str) -> list[PouInfo]:
    """List POUs recognized by the current OpenPLC Editor project layout."""
    root, _, _ = _load_project(project_path)
    by_name: dict[str, PouInfo] = {}

    for pou_type, relative_dir in _POU_DIRECTORIES:
        for path in _iter_pou_files(root, relative_dir):
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
