"""OpenPLC POU discovery, reading, and updating."""

import contextlib
import hashlib
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Literal, TypedDict

from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.project import list_source_files, load_project

PouType = Literal["program", "function-block", "function"]


class PouInfo(TypedDict):
    """The public identity of one POU recognized by the current project layout."""

    name: str
    type: PouType
    language: str
    path: str


class PouContent(PouInfo):
    """A readable POU's identity plus its exact source content and content hash."""

    content: str
    content_hash: str


class UpdatePouResult(TypedDict):
    """The name and new exact-byte content hash of an updated POU."""

    name: str
    content_hash: str


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
_POU_DECLARATION_KEYWORDS: dict[PouType, str] = {
    "program": "PROGRAM",
    "function-block": "FUNCTION_BLOCK",
    "function": "FUNCTION",
}
_POU_TERMINAL_KEYWORDS: dict[PouType, str] = {
    "program": "END_PROGRAM",
    "function-block": "END_FUNCTION_BLOCK",
    "function": "END_FUNCTION",
}
_CONTENT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DOCUMENTATION_RE = re.compile(r"^[\s\ufeff]*\(\*\s*(.*?)\s*\*\)\s*\n", re.DOTALL)


def _content_hash(raw: bytes) -> str:
    """Return the exact-byte SHA-256 version token used for POU content."""
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _is_contained(root: Path, path: Path) -> bool:
    """Check whether a path's resolved target stays inside the project root."""
    try:
        return path.resolve().is_relative_to(root)
    except (OSError, RuntimeError):
        return False


def _list_pous(root: Path) -> list[PouInfo]:
    """List POUs recognized by the current OpenPLC Editor project layout."""
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
            if info["name"] not in by_name:
                by_name[info["name"]] = info

    return sorted(by_name.values(), key=lambda pou: (pou["type"], pou["name"], pou["path"]))


def list_pous(project_path: str) -> list[PouInfo]:
    """List POUs recognized by the current OpenPLC Editor project layout."""
    root, _, _ = load_project(project_path)
    return _list_pous(root)


def read_pou(project_path: str, pou_name: str) -> PouContent:
    """Read a current-format POU by name, with an exact-byte content hash."""
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
        raw = path.read_bytes()
    except (OSError, RuntimeError) as exc:
        raise ToolError(f'Could not read POU "{pou_name}": {exc}') from exc

    try:
        content = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ToolError(f'Could not read POU "{pou_name}": source is not valid UTF-8') from exc

    return {
        "name": pou["name"],
        "type": pou["type"],
        "language": pou["language"],
        "path": pou["path"],
        "content": content,
        "content_hash": _content_hash(raw),
    }


def _find_pou_matches(root: Path, pou_name: str) -> list[PouInfo]:
    """Find every recognized current-format POU source whose stem matches the name."""
    matches: list[PouInfo] = []
    for pou_type, relative_dir in _POU_DIRECTORIES:
        for path in list_source_files(root, relative_dir, set(_POU_LANGUAGES)):
            if path.stem != pou_name or not _is_contained(root, path):
                continue
            matches.append(
                {
                    "name": path.stem,
                    "type": pou_type,
                    "language": _POU_LANGUAGES[path.suffix.lower()],
                    "path": path.relative_to(root).as_posix(),
                }
            )
    return matches


def _validate_st_envelope(content: str, pou_type: PouType, pou_name: str) -> None:
    """Check only the outer Structured Text identity facts OpenPLC expects."""
    declaration_keyword = _POU_DECLARATION_KEYWORDS[pou_type]
    remaining = _DOCUMENTATION_RE.sub("", content, count=1)
    declaration = re.match(
        rf"^[\s\ufeff]*({declaration_keyword})\s+(\w+)(?:\s*:\s*(\w+))?", remaining, re.IGNORECASE
    )
    if declaration is None:
        raise ToolError(f'Replacement POU type does not match target type "{pou_type}"')
    if declaration.group(2) != pou_name:
        raise ToolError(f'Replacement POU name does not match target "{pou_name}"')
    if pou_type == "function" and declaration.group(3) is None:
        raise ToolError("Replacement Function must declare a return type")

    terminal_keyword = _POU_TERMINAL_KEYWORDS[pou_type]
    if re.search(rf"\b{terminal_keyword}\b", remaining[declaration.end() :], re.IGNORECASE) is None:
        raise ToolError(f"Replacement POU is missing {terminal_keyword}")


def _verify_update_target(root: Path, pou_name: str, target: Path) -> None:
    """Verify the POU target is a regular file contained in the project."""
    if target.is_symlink():
        raise ToolError("POU target is a symbolic link and cannot be updated")
    try:
        resolved = target.resolve(strict=True)
    except OSError:
        raise ToolError("POU target is not a regular project file") from None
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ToolError("POU target is not a regular project file")


def _write_pou_atomically(
    root: Path,
    pou_name: str,
    lexical_target: Path,
    replacement_raw: bytes,
    expected_content_hash: str,
) -> None:
    """Stage complete bytes beside the target and atomically replace the POU."""
    try:
        original_mode = stat.S_IMODE(lexical_target.stat().st_mode)
    except OSError as exc:
        raise ToolError(f'Could not update POU "{pou_name}": {exc}') from exc

    temp_path: Path | None = None
    try:
        try:
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{lexical_target.name}.", suffix=".tmp", dir=lexical_target.parent
            )
        except OSError as exc:
            raise ToolError(f'Could not update POU "{pou_name}": {exc}') from exc
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as temp_file:
                temp_file.write(replacement_raw)
                temp_file.flush()
                os.chmod(temp_path, original_mode)
                os.fsync(temp_file.fileno())
        except OSError as exc:
            raise ToolError(f'Could not update POU "{pou_name}": {exc}') from exc

        _verify_update_target(root, pou_name, lexical_target)
        try:
            latest_raw = lexical_target.read_bytes()
        except OSError as exc:
            raise ToolError(f'Could not update POU "{pou_name}": {exc}') from exc
        if _content_hash(latest_raw) != expected_content_hash:
            raise ToolError(
                f'POU changed since it was read: "{pou_name}"; call read_pou() again before updating'
            )

        try:
            os.replace(temp_path, lexical_target)
        except OSError as exc:
            raise ToolError(f'Could not update POU "{pou_name}": {exc}') from exc
        temp_path = None
    finally:
        if temp_path is not None:
            with contextlib.suppress(OSError):
                temp_path.unlink()


def update_pou(
    project_path: str,
    pou_name: str,
    content: str,
    expected_content_hash: str,
) -> UpdatePouResult:
    """Replace the complete persisted content of an existing Structured Text POU.

    The POU name, type, language, and canonical path are immutable. The expected
    content hash must match the exact bytes returned by read_pou() so stale
    updates are rejected. Success means the complete replacement was atomically
    persisted; compilation remains an explicit, separate operation.

    Raises:
        ToolError: If the project, POU identity, concurrency token, replacement
            envelope, or filesystem state makes the update unsafe.
    """
    if not pou_name.strip():
        raise ToolError("pou_name must not be empty")
    if not content.strip():
        raise ToolError("Replacement POU content must not be empty")
    if not _CONTENT_HASH_RE.match(expected_content_hash):
        raise ToolError("Invalid expected content hash")

    root, _, _ = load_project(project_path)

    matches = _find_pou_matches(root, pou_name)
    if not matches:
        raise ToolError(f'POU not found: "{pou_name}"')
    if len(matches) > 1:
        raise ToolError(f'Ambiguous POU name: "{pou_name}"')
    target = matches[0]

    if target["language"] != "st":
        raise ToolError(
            f'POU language "{target["language"]}" is not supported for update; '
            "v1 supports Structured Text only"
        )

    lexical_target = root / target["path"]
    _verify_update_target(root, pou_name, lexical_target)

    try:
        current_raw = lexical_target.read_bytes()
    except OSError as exc:
        raise ToolError(f'Could not update POU "{pou_name}": {exc}') from exc
    current_hash = _content_hash(current_raw)
    if current_hash != expected_content_hash:
        raise ToolError(
            f'POU changed since it was read: "{pou_name}"; call read_pou() again before updating'
        )

    _validate_st_envelope(content, target["type"], target["name"])

    try:
        replacement_raw = content.encode("utf-8")
    except UnicodeError as exc:
        raise ToolError("Replacement POU content must be UTF-8 encodable") from exc

    new_hash = _content_hash(replacement_raw)
    if new_hash == current_hash:
        return {"name": pou_name, "content_hash": new_hash}

    _write_pou_atomically(root, pou_name, lexical_target, replacement_raw, expected_content_hash)
    return {"name": pou_name, "content_hash": new_hash}
