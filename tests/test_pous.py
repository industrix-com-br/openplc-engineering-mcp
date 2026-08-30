import hashlib
import json
import os
import tempfile
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.compiler import get_diagnostics
from openplc_engineering_mcp.openplc.pous import list_pous, read_pou, update_pou
from openplc_engineering_mcp.openplc.variables import list_variables


def make_project(root: Path) -> Path:
    (root / "pous" / "programs").mkdir(parents=True)
    (root / "pous" / "function-blocks").mkdir(parents=True)
    (root / "project.json").write_text(
        json.dumps({"meta": {"name": "Example", "type": "plc-project"}}), encoding="utf-8"
    )
    (root / "pous" / "programs" / "main.st").write_text(
        "PROGRAM main\nEND_PROGRAM\n", encoding="utf-8"
    )
    (root / "pous" / "function-blocks" / "Motor.st").write_text(
        "FUNCTION_BLOCK Motor\nEND_FUNCTION_BLOCK\n", encoding="utf-8"
    )
    return root


MAIN_PROGRAM = (
    "PROGRAM MAIN\nVAR\n    counter : INT;\nEND_VAR\n    counter := counter + 1;\nEND_PROGRAM\n"
)
MOTOR_BLOCK = "FUNCTION_BLOCK Motor\nVAR_INPUT\n    Start : BOOL;\nEND_VAR\nEND_FUNCTION_BLOCK\n"
ADD_TEN_FUNCTION = (
    "FUNCTION AddTen : INT\n"
    "VAR_INPUT\n    value : INT;\nEND_VAR\n"
    "    AddTen := value + 10;\n"
    "END_FUNCTION\n"
)


def make_update_project(root: Path) -> Path:
    """Create a minimal project with one Program, Function Block, and Function ST POU."""
    (root / "pous" / "programs").mkdir(parents=True)
    (root / "pous" / "function-blocks").mkdir(parents=True)
    (root / "pous" / "functions").mkdir(parents=True)
    (root / "project.json").write_text(
        json.dumps({"meta": {"name": "Example", "type": "plc-project"}}), encoding="utf-8"
    )
    (root / "pous" / "programs" / "MAIN.st").write_text(MAIN_PROGRAM, encoding="utf-8")
    (root / "pous" / "function-blocks" / "Motor.st").write_text(MOTOR_BLOCK, encoding="utf-8")
    (root / "pous" / "functions" / "AddTen.st").write_text(ADD_TEN_FUNCTION, encoding="utf-8")
    return root


def sha256_token(raw: bytes) -> str:
    """Return the exact-byte sha256: token expected for raw persisted bytes."""
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def current_hash(project: Path, pou_name: str) -> str:
    """Return the current read_pou() content hash for one POU."""
    return read_pou(str(project), pou_name)["content_hash"]


def tree_entries(root: Path) -> list[str]:
    """List every path under root as sorted project-relative posix strings."""
    return sorted(str(path.relative_to(root)) for path in root.rglob("*"))


def file_snapshot(root: Path) -> dict[Path, bytes]:
    """Map every file under root to its bytes by project-relative path."""
    return {
        path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


def assert_tree_unchanged(root: Path, snapshot: dict[Path, bytes]) -> None:
    """Assert the project tree still matches a previous file_snapshot()."""
    assert file_snapshot(root) == snapshot


def test_list_pous_uses_current_source_representation(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    pous = list_pous(str(project))

    assert pous == [
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


def test_json_only_pou_is_not_supported(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    (project / "pous" / "function-blocks" / "Motor.st").unlink()
    (project / "pous" / "function-blocks" / "Motor.json").write_text("{}", encoding="utf-8")

    assert all(pou["name"] != "Motor" for pou in list_pous(str(project)))
    with pytest.raises(ToolError, match="POU not found"):
        read_pou(str(project), "Motor")


def test_pou_names_are_deduplicated_globally(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    (project / "pous" / "programs" / "Motor.st").write_text(
        "PROGRAM Motor\nEND_PROGRAM\n", encoding="utf-8"
    )

    pous = list_pous(str(project))
    motors = [pou for pou in pous if pou["name"] == "Motor"]

    assert motors == [
        {
            "name": "Motor",
            "type": "function-block",
            "language": "st",
            "path": "pous/function-blocks/Motor.st",
        }
    ]


def test_read_pou_returns_source_content(tmp_path: Path) -> None:
    """read_pou() returns identity, exact source content, and the exact-byte hash."""
    project = make_project(tmp_path / "project")

    pou = read_pou(str(project), "Motor")

    assert pou == {
        "name": "Motor",
        "type": "function-block",
        "language": "st",
        "path": "pous/function-blocks/Motor.st",
        "content": "FUNCTION_BLOCK Motor\nEND_FUNCTION_BLOCK\n",
        "content_hash": sha256_token(b"FUNCTION_BLOCK Motor\nEND_FUNCTION_BLOCK\n"),
    }


def test_read_pou_rejects_unknown_name(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    with pytest.raises(ToolError, match="POU not found"):
        read_pou(str(project), "Missing")


def test_read_pou_rejects_empty_name(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    with pytest.raises(ToolError, match="pou_name must not be empty"):
        read_pou(str(project), "  ")


def test_escaping_symlink_is_not_listed_nor_read(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    external_source = tmp_path / "External.st"
    external_source.write_text("FUNCTION_BLOCK External\nEND_FUNCTION_BLOCK\n", encoding="utf-8")
    (project / "pous" / "function-blocks" / "External.st").symlink_to(external_source)

    names = [pou["name"] for pou in list_pous(str(project))]
    assert "External" not in names

    with pytest.raises(ToolError, match="POU not found"):
        read_pou(str(project), "External")


def test_invalid_project_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="does not exist"):
        list_pous(str(tmp_path / "missing"))


def test_read_pou_content_hash_is_a_deterministic_exact_byte_token(tmp_path: Path) -> None:
    """Repeated reads return the same hash computed over the exact persisted bytes."""
    project = make_update_project(tmp_path / "project")

    first = read_pou(str(project), "MAIN")
    second = read_pou(str(project), "MAIN")

    assert first["content_hash"] == second["content_hash"]
    assert first["content_hash"] == sha256_token(MAIN_PROGRAM.encode("utf-8"))


def test_read_pou_preserves_crlf_bytes_and_hash(tmp_path: Path) -> None:
    """CRLF source bytes are preserved in content and covered by the hash."""
    project = make_update_project(tmp_path / "project")
    crlf = MAIN_PROGRAM.replace("\n", "\r\n")
    (project / "pous" / "programs" / "MAIN.st").write_bytes(crlf.encode("utf-8"))

    pou = read_pou(str(project), "MAIN")

    assert pou["content"] == crlf
    assert pou["content_hash"] == sha256_token(crlf.encode("utf-8"))


def test_update_st_program_replaces_complete_content(tmp_path: Path) -> None:
    """A Program replacement persists byte-for-byte and returns the new hash."""
    project = make_update_project(tmp_path / "project")
    replacement = "PROGRAM MAIN\nVAR\n    flag : BOOL;\nEND_VAR\n    flag := TRUE;\nEND_PROGRAM\n"

    result = update_pou(str(project), "MAIN", replacement, current_hash(project, "MAIN"))

    target = project / "pous" / "programs" / "MAIN.st"
    assert target.read_bytes() == replacement.encode("utf-8")
    assert result == {"name": "MAIN", "content_hash": sha256_token(replacement.encode("utf-8"))}


def test_update_st_function_block(tmp_path: Path) -> None:
    """A Function Block replacement persists byte-for-byte and returns the new hash."""
    project = make_update_project(tmp_path / "project")
    replacement = (
        "FUNCTION_BLOCK Motor\n"
        "VAR_INPUT\n    Start : BOOL;\nEND_VAR\n"
        "VAR\n    latch : BOOL;\nEND_VAR\n"
        "    latch := Start;\n"
        "END_FUNCTION_BLOCK\n"
    )

    result = update_pou(str(project), "Motor", replacement, current_hash(project, "Motor"))

    target = project / "pous" / "function-blocks" / "Motor.st"
    assert target.read_bytes() == replacement.encode("utf-8")
    assert result["content_hash"] == sha256_token(replacement.encode("utf-8"))


def test_update_st_function(tmp_path: Path) -> None:
    """A Function replacement persists byte-for-byte and returns the new hash."""
    project = make_update_project(tmp_path / "project")
    replacement = (
        "FUNCTION AddTen : INT\n"
        "VAR_INPUT\n    value : INT;\nEND_VAR\n"
        "VAR\n    offset : INT := 10;\nEND_VAR\n"
        "    AddTen := value + offset;\n"
        "END_FUNCTION\n"
    )

    result = update_pou(str(project), "AddTen", replacement, current_hash(project, "AddTen"))

    target = project / "pous" / "functions" / "AddTen.st"
    assert target.read_bytes() == replacement.encode("utf-8")
    assert result["content_hash"] == sha256_token(replacement.encode("utf-8"))


def test_update_changes_function_return_type(tmp_path: Path) -> None:
    """A Function's return type changes through the complete replacement."""
    project = make_update_project(tmp_path / "project")
    replacement = ADD_TEN_FUNCTION.replace("FUNCTION AddTen : INT", "FUNCTION AddTen : DINT")

    update_pou(str(project), "AddTen", replacement, current_hash(project, "AddTen"))

    assert (project / "pous" / "functions" / "AddTen.st").read_text(encoding="utf-8") == replacement


def test_update_changes_documentation(tmp_path: Path) -> None:
    """A leading documentation block changes through the complete replacement."""
    project = make_update_project(tmp_path / "project")
    replacement = "(* Pump station control loop. *)\nPROGRAM MAIN\nEND_PROGRAM\n"

    update_pou(str(project), "MAIN", replacement, current_hash(project, "MAIN"))

    assert (project / "pous" / "programs" / "MAIN.st").read_text(encoding="utf-8") == replacement


def test_update_declaration_changes_are_visible_to_list_variables(tmp_path: Path) -> None:
    """Declaration changes made by update_pou() are visible to list_variables()."""
    project = make_update_project(tmp_path / "project")
    replacement = (
        "FUNCTION_BLOCK Motor\n"
        "VAR_INPUT\n    Start : BOOL;\n    Stop : BOOL;\nEND_VAR\n"
        "VAR_OUTPUT\n    Running : BOOL;\nEND_VAR\n"
        "VAR_IN_OUT\n    Interlock : BOOL;\nEND_VAR\n"
        "END_FUNCTION_BLOCK\n"
    )

    update_pou(str(project), "Motor", replacement, current_hash(project, "Motor"))

    variables = list_variables(str(project), "Motor")
    assert [(variable["name"], variable["class"]) for variable in variables] == [
        ("Start", "input"),
        ("Stop", "input"),
        ("Running", "output"),
        ("Interlock", "inOut"),
    ]


def test_read_pou_after_update_returns_replacement_and_new_hash(tmp_path: Path) -> None:
    """read_pou() after an update returns the replacement and its hash."""
    project = make_update_project(tmp_path / "project")
    replacement = "PROGRAM MAIN\nEND_PROGRAM\n"

    result = update_pou(str(project), "MAIN", replacement, current_hash(project, "MAIN"))

    pou = read_pou(str(project), "MAIN")
    assert pou["content"] == replacement
    assert pou["content_hash"] == result["content_hash"]


def test_update_writes_replacement_exactly_as_provided(tmp_path: Path) -> None:
    """Comments, spacing, and tabs are persisted exactly as provided."""
    project = make_update_project(tmp_path / "project")
    replacement = (
        "(* keep  this   spacing *)\n"
        "PROGRAM MAIN\n"
        "VAR\n"
        "      spaced    :    INT := 3;   (* trailing *)\n"
        "END_VAR\n"
        "\tcounter := spaced;\n"
        "END_PROGRAM\n"
    )

    update_pou(str(project), "MAIN", replacement, current_hash(project, "MAIN"))

    assert (project / "pous" / "programs" / "MAIN.st").read_bytes() == replacement.encode("utf-8")


def test_update_crlf_content_round_trips_without_normalization(tmp_path: Path) -> None:
    """CRLF replacement bytes round-trip without newline normalization."""
    project = make_update_project(tmp_path / "project")
    crlf_original = MAIN_PROGRAM.replace("\n", "\r\n")
    (project / "pous" / "programs" / "MAIN.st").write_bytes(crlf_original.encode("utf-8"))
    pou = read_pou(str(project), "MAIN")
    replacement = "PROGRAM MAIN\r\n    counter := 0;\r\nEND_PROGRAM\r\n"

    result = update_pou(str(project), "MAIN", replacement, pou["content_hash"])

    target = project / "pous" / "programs" / "MAIN.st"
    assert target.read_bytes() == replacement.encode("utf-8")
    assert result["content_hash"] == sha256_token(replacement.encode("utf-8"))


def test_update_bom_prefixed_pou_round_trips_without_stripping(tmp_path: Path) -> None:
    """BOM-prefixed POUs round-trip through read_pou() and update_pou() with the BOM preserved."""
    project = make_update_project(tmp_path / "project")
    bom_original = "\ufeff" + MAIN_PROGRAM
    target = project / "pous" / "programs" / "MAIN.st"
    target.write_bytes(bom_original.encode("utf-8"))
    pou = read_pou(str(project), "MAIN")

    assert pou["content"] == bom_original
    assert pou["content_hash"] == sha256_token(bom_original.encode("utf-8"))

    result = update_pou(str(project), "MAIN", pou["content"], pou["content_hash"])

    assert result == {"name": "MAIN", "content_hash": pou["content_hash"]}
    assert target.read_bytes() == bom_original.encode("utf-8")

    bom_replacement = "\ufeffPROGRAM MAIN\n    counter := 0;\nEND_PROGRAM\n"
    result = update_pou(str(project), "MAIN", bom_replacement, result["content_hash"])

    assert target.read_bytes() == bom_replacement.encode("utf-8")
    assert result["content_hash"] == sha256_token(bom_replacement.encode("utf-8"))


def test_update_bom_prefixed_pou_with_documentation(tmp_path: Path) -> None:
    """A BOM before a leading documentation block is accepted and persisted."""
    project = make_update_project(tmp_path / "project")
    replacement = "\ufeff(* Pump station control loop. *)\nPROGRAM MAIN\nEND_PROGRAM\n"

    update_pou(str(project), "MAIN", replacement, current_hash(project, "MAIN"))

    assert (project / "pous" / "programs" / "MAIN.st").read_bytes() == replacement.encode("utf-8")


def test_update_only_touches_the_target_file(tmp_path: Path) -> None:
    """An update changes only the target POU file and no other project file."""
    project = make_update_project(tmp_path / "project")
    snapshot = {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }

    update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", current_hash(project, "MAIN"))

    after = {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }
    assert set(after) == set(snapshot)
    for relative, raw in snapshot.items():
        if relative == Path("pous/programs/MAIN.st"):
            continue
        assert after[relative] == raw


def test_noop_update_does_not_physically_replace_the_file(tmp_path: Path) -> None:
    """A byte-identical replacement returns success without replacing the file."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    before = target.stat()

    result = update_pou(str(project), "MAIN", MAIN_PROGRAM, current_hash(project, "MAIN"))

    assert result == {"name": "MAIN", "content_hash": sha256_token(MAIN_PROGRAM.encode("utf-8"))}
    after = target.stat()
    assert after.st_mtime_ns == before.st_mtime_ns
    assert after.st_ino == before.st_ino


def test_update_preserves_target_file_mode(tmp_path: Path) -> None:
    """The target's file mode is preserved across the replacement."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    os.chmod(target, 0o600)

    update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", current_hash(project, "MAIN"))

    assert target.stat().st_mode & 0o777 == 0o600


def test_update_creates_no_backup_or_temporary_files(tmp_path: Path) -> None:
    """A successful update leaves no backup or temporary files behind."""
    project = make_update_project(tmp_path / "project")
    before = tree_entries(project)

    update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", current_hash(project, "MAIN"))

    assert tree_entries(project) == before


def test_update_does_not_trigger_compilation(tmp_path: Path, monkeypatch) -> None:
    """update_pou() persists without spawning compilation subprocesses."""
    project = make_update_project(tmp_path / "project")

    def forbidden_run(*args, **kwargs):
        raise AssertionError("update_pou must not compile the project")

    monkeypatch.setattr("openplc_engineering_mcp.openplc.compiler.subprocess.run", forbidden_run)

    update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", current_hash(project, "MAIN"))

    with pytest.raises(ToolError, match="No compilation diagnostics are available"):
        get_diagnostics(str(project))


def test_update_rejects_changed_pou_name(tmp_path: Path) -> None:
    """A replacement declaring a different POU name is rejected and changes nothing."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    original = target.read_bytes()

    with pytest.raises(ToolError, match='Replacement POU name does not match target "MAIN"'):
        update_pou(
            str(project), "MAIN", "PROGRAM DIFFERENT_NAME\nEND_PROGRAM\n", current_hash(project, "MAIN")
        )

    assert target.read_bytes() == original


@pytest.mark.parametrize(
    ("pou_name", "replacement", "target_type"),
    [
        ("MAIN", "FUNCTION_BLOCK MAIN\nEND_FUNCTION_BLOCK\n", "program"),
        ("Motor", "PROGRAM Motor\nEND_PROGRAM\n", "function-block"),
        ("AddTen", "FUNCTION_BLOCK AddTen\nEND_FUNCTION_BLOCK\n", "function"),
        ("MAIN", "this is not a POU declaration", "program"),
    ],
)
def test_update_rejects_changed_pou_type(
    tmp_path: Path, pou_name: str, replacement: str, target_type: str
) -> None:
    """A replacement declaring a different POU type is rejected and changes nothing."""
    project = make_update_project(tmp_path / "project")
    snapshot = file_snapshot(project)

    with pytest.raises(
        ToolError, match=f'Replacement POU type does not match target type "{target_type}"'
    ):
        update_pou(str(project), pou_name, replacement, current_hash(project, pou_name))

    assert_tree_unchanged(project, snapshot)


def test_update_rejects_function_without_return_type(tmp_path: Path) -> None:
    """A Function replacement without a return type is rejected and changes nothing."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "functions" / "AddTen.st"
    original = target.read_bytes()

    with pytest.raises(ToolError, match="Replacement Function must declare a return type"):
        update_pou(str(project), "AddTen", "FUNCTION AddTen\nEND_FUNCTION\n", current_hash(project, "AddTen"))

    assert target.read_bytes() == original


@pytest.mark.parametrize(
    ("pou_name", "replacement", "terminal"),
    [
        ("MAIN", "PROGRAM MAIN\n", "END_PROGRAM"),
        ("Motor", "FUNCTION_BLOCK Motor\n", "END_FUNCTION_BLOCK"),
        ("AddTen", "FUNCTION AddTen : INT\nEND_FUNCTION_BLOCK\n", "END_FUNCTION"),
    ],
)
def test_update_rejects_missing_terminal_keyword(
    tmp_path: Path, pou_name: str, replacement: str, terminal: str
) -> None:
    """A replacement missing its END_* terminal keyword is rejected and changes nothing."""
    project = make_update_project(tmp_path / "project")
    snapshot = file_snapshot(project)

    with pytest.raises(ToolError, match=f"Replacement POU is missing {terminal}"):
        update_pou(str(project), pou_name, replacement, current_hash(project, pou_name))

    assert_tree_unchanged(project, snapshot)


def test_update_rejects_unknown_pou(tmp_path: Path) -> None:
    """Updating an unknown POU name is rejected and changes nothing."""
    project = make_update_project(tmp_path / "project")
    snapshot = file_snapshot(project)

    with pytest.raises(ToolError, match='POU not found: "Missing"'):
        update_pou(
            str(project),
            "Missing",
            "PROGRAM Missing\nEND_PROGRAM\n",
            sha256_token(b"PROGRAM Missing\nEND_PROGRAM\n"),
        )

    assert_tree_unchanged(project, snapshot)


def test_update_rejects_ambiguous_duplicate_stem(tmp_path: Path) -> None:
    """A stem claimed by multiple recognized sources is rejected as ambiguous."""
    project = make_update_project(tmp_path / "project")
    duplicate = project / "pous" / "programs" / "Motor.st"
    duplicate.write_text("PROGRAM Motor\nEND_PROGRAM\n", encoding="utf-8")
    snapshot = file_snapshot(project)

    assert [pou["type"] for pou in list_pous(str(project)) if pou["name"] == "Motor"] == [
        "function-block"
    ]

    with pytest.raises(ToolError, match='Ambiguous POU name: "Motor"'):
        update_pou(
            str(project),
            "Motor",
            "FUNCTION_BLOCK Motor\nEND_FUNCTION_BLOCK\n",
            current_hash(project, "Motor"),
        )

    assert_tree_unchanged(project, snapshot)


@pytest.mark.parametrize(
    ("suffix", "language"),
    [
        (".il", "il"),
        (".ld", "ld"),
        (".fbd", "fbd"),
        (".py", "python"),
        (".cpp", "cpp"),
    ],
)
def test_update_rejects_unsupported_languages(tmp_path: Path, suffix: str, language: str) -> None:
    """Non-ST POU sources are rejected for update with their bytes unchanged."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "function-blocks" / f"Legacy{suffix}"
    target.write_bytes(b"original legacy body")

    with pytest.raises(
        ToolError,
        match=f'POU language "{language}" is not supported for update; v1 supports Structured Text only',
    ):
        update_pou(
            str(project),
            "Legacy",
            "FUNCTION_BLOCK Legacy\nEND_FUNCTION_BLOCK\n",
            sha256_token(b"original legacy body"),
        )

    assert target.read_bytes() == b"original legacy body"


def test_update_still_reads_unsupported_language_pous(tmp_path: Path) -> None:
    """Non-ST POU sources remain readable through read_pou()."""
    project = make_update_project(tmp_path / "project")
    (project / "pous" / "function-blocks" / "Legacy.ld").write_text(
        '{"name": "Legacy", "rungs": []}', encoding="utf-8"
    )

    pou = read_pou(str(project), "Legacy")

    assert pou["language"] == "ld"
    assert pou["content"] == '{"name": "Legacy", "rungs": []}'


@pytest.mark.parametrize(
    "expected_hash",
    [
        "",
        "sha256:",
        "sha256:abc",
        "sha256:" + "a" * 63,
        "sha256:" + "a" * 65,
        "sha256:" + "A" * 64,
        "sha256:" + "g" * 64,
        "md5:" + "a" * 64,
    ],
)
def test_update_rejects_malformed_expected_hash(tmp_path: Path, expected_hash: str) -> None:
    """Malformed expected content hashes are rejected and change nothing."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    original = target.read_bytes()

    with pytest.raises(ToolError, match="Invalid expected content hash"):
        update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", expected_hash)

    assert target.read_bytes() == original


def test_update_rejects_stale_hash_and_preserves_external_bytes(tmp_path: Path) -> None:
    """A stale hash rejects the update and preserves externally written bytes."""
    project = make_update_project(tmp_path / "project")
    pou = read_pou(str(project), "MAIN")
    external_bytes = b"PROGRAM MAIN\n    (* written by another process *)\nEND_PROGRAM\n"
    (project / "pous" / "programs" / "MAIN.st").write_bytes(external_bytes)

    with pytest.raises(ToolError, match='POU changed since it was read: "MAIN"'):
        update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", pou["content_hash"])

    assert (project / "pous" / "programs" / "MAIN.st").read_bytes() == external_bytes


def test_update_rejects_modification_between_hash_checks(tmp_path: Path, monkeypatch) -> None:
    """A modification between the first and final hash checks rejects the update."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    pou = read_pou(str(project), "MAIN")
    external_bytes = b"PROGRAM MAIN\n    (* concurrent writer *)\nEND_PROGRAM\n"
    real_mkstemp = tempfile.mkstemp

    def mkstemp_with_concurrent_write(*args, **kwargs):
        target.write_bytes(external_bytes)
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr(
        "openplc_engineering_mcp.openplc.pous.tempfile.mkstemp", mkstemp_with_concurrent_write
    )

    with pytest.raises(ToolError, match='POU changed since it was read: "MAIN"'):
        update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", pou["content_hash"])

    assert target.read_bytes() == external_bytes
    assert tree_entries(project / "pous" / "programs") == ["MAIN.st"]


def test_update_rejects_empty_pou_name(tmp_path: Path) -> None:
    """An empty POU name is rejected."""
    project = make_update_project(tmp_path / "project")

    with pytest.raises(ToolError, match="pou_name must not be empty"):
        update_pou(str(project), "  ", "PROGRAM MAIN\nEND_PROGRAM\n", "sha256:" + "a" * 64)


def test_update_rejects_empty_replacement_content(tmp_path: Path) -> None:
    """Whitespace-only replacement content is rejected and changes nothing."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    original = target.read_bytes()

    with pytest.raises(ToolError, match="Replacement POU content must not be empty"):
        update_pou(str(project), "MAIN", "   \n", current_hash(project, "MAIN"))

    assert target.read_bytes() == original


def test_update_rejects_non_utf8_encodable_replacement(tmp_path: Path) -> None:
    """Non-UTF-8-encodable replacement content is rejected and changes nothing."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    original = target.read_bytes()

    with pytest.raises(ToolError, match="Replacement POU content must be UTF-8 encodable"):
        update_pou(str(project), "MAIN", "PROGRAM MAIN\n\ud800\nEND_PROGRAM\n", current_hash(project, "MAIN"))

    assert target.read_bytes() == original


def test_update_rejects_project_path_outside_a_project(tmp_path: Path) -> None:
    """A project path that does not exist is rejected."""
    with pytest.raises(ToolError, match="does not exist"):
        update_pou(
            str(tmp_path / "missing"), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", "sha256:" + "a" * 64
        )


def test_malformed_existing_pou_can_be_repaired(tmp_path: Path) -> None:
    """A malformed existing ST POU can be repaired via exact-hash replacement."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    target.write_text("garbage {{{ not parseable as a POU", encoding="utf-8")
    pou = read_pou(str(project), "MAIN")
    replacement = "PROGRAM MAIN\nEND_PROGRAM\n"

    result = update_pou(str(project), "MAIN", replacement, pou["content_hash"])

    assert target.read_text(encoding="utf-8") == replacement
    assert result["content_hash"] == sha256_token(replacement.encode("utf-8"))


def test_update_rejects_symlink_target_inside_the_project(tmp_path: Path) -> None:
    """A symlinked POU target inside the project is rejected for update."""
    project = make_update_project(tmp_path / "project")
    real_target = project / "pous" / "programs" / "MAIN.st"
    alias = project / "pous" / "programs" / "Alias.st"
    alias.symlink_to(real_target)
    original = real_target.read_bytes()
    replacement = "PROGRAM Alias\nEND_PROGRAM\n"

    with pytest.raises(ToolError, match="POU target is a symbolic link and cannot be updated"):
        update_pou(str(project), "Alias", replacement, sha256_token(original))

    assert real_target.read_bytes() == original
    assert alias.is_symlink()


def test_update_rejects_pou_resolving_outside_the_project(tmp_path: Path) -> None:
    """A POU source resolving outside the project root is not updatable."""
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    external_pou = external_dir / "Only.st"
    external_pou.write_text("PROGRAM Only\nEND_PROGRAM\n", encoding="utf-8")

    project = tmp_path / "project"
    (project / "pous").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"meta": {"name": "Example", "type": "plc-project"}}), encoding="utf-8"
    )
    (project / "pous" / "programs").symlink_to(external_dir)

    with pytest.raises(ToolError, match='POU not found: "Only"'):
        update_pou(
            str(project),
            "Only",
            "PROGRAM Only\nEND_PROGRAM\n",
            sha256_token(external_pou.read_bytes()),
        )

    assert external_pou.read_text(encoding="utf-8") == "PROGRAM Only\nEND_PROGRAM\n"


def test_update_rejects_target_removed_before_final_check(tmp_path: Path, monkeypatch) -> None:
    """A target removed before the final check rejects the update without litter."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    pou = read_pou(str(project), "MAIN")
    real_mkstemp = tempfile.mkstemp

    def mkstemp_removing_target(*args, **kwargs):
        target.unlink()
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr("openplc_engineering_mcp.openplc.pous.tempfile.mkstemp", mkstemp_removing_target)

    with pytest.raises(ToolError, match="POU target is not a regular project file"):
        update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", pou["content_hash"])

    assert not target.exists()
    assert tree_entries(project / "pous" / "programs") == []


def test_update_rejects_target_replaced_by_directory_before_final_check(
    tmp_path: Path, monkeypatch
) -> None:
    """A target replaced by a directory before the final check rejects the update."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    pou = read_pou(str(project), "MAIN")
    real_mkstemp = tempfile.mkstemp

    def mkstemp_replacing_target_with_directory(*args, **kwargs):
        target.unlink()
        target.mkdir()
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr(
        "openplc_engineering_mcp.openplc.pous.tempfile.mkstemp",
        mkstemp_replacing_target_with_directory,
    )

    with pytest.raises(ToolError, match="POU target is not a regular project file"):
        update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", pou["content_hash"])

    assert target.is_dir()
    assert tree_entries(project / "pous" / "programs") == ["MAIN.st"]


def test_update_temp_creation_failure_leaves_target_unchanged(tmp_path: Path, monkeypatch) -> None:
    """A temp-file creation failure leaves the target unchanged with no litter."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    original = target.read_bytes()
    pou = read_pou(str(project), "MAIN")

    def failing_mkstemp(*args, **kwargs):
        raise PermissionError("simulated temp creation failure")

    monkeypatch.setattr("openplc_engineering_mcp.openplc.pous.tempfile.mkstemp", failing_mkstemp)

    with pytest.raises(ToolError, match='Could not update POU "MAIN"'):
        update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", pou["content_hash"])

    assert target.read_bytes() == original
    assert tree_entries(project / "pous" / "programs") == ["MAIN.st"]


def test_update_temp_write_failure_leaves_target_unchanged(tmp_path: Path, monkeypatch) -> None:
    """A temp-file write failure leaves the target unchanged with no litter."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    original = target.read_bytes()
    pou = read_pou(str(project), "MAIN")
    real_mkstemp = tempfile.mkstemp

    def read_only_mkstemp(*args, **kwargs):
        fd, temp_name = real_mkstemp(*args, **kwargs)
        os.close(fd)
        return os.open(temp_name, os.O_RDONLY), temp_name

    monkeypatch.setattr("openplc_engineering_mcp.openplc.pous.tempfile.mkstemp", read_only_mkstemp)

    with pytest.raises(ToolError, match='Could not update POU "MAIN"'):
        update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", pou["content_hash"])

    assert target.read_bytes() == original
    assert tree_entries(project / "pous" / "programs") == ["MAIN.st"]


def test_update_fsync_failure_leaves_target_unchanged(tmp_path: Path, monkeypatch) -> None:
    """An fsync failure leaves the target unchanged with no litter."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    original = target.read_bytes()
    pou = read_pou(str(project), "MAIN")

    def failing_fsync(fd):
        raise OSError("simulated fsync failure")

    monkeypatch.setattr("openplc_engineering_mcp.openplc.pous.os.fsync", failing_fsync)

    with pytest.raises(ToolError, match='Could not update POU "MAIN"'):
        update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", pou["content_hash"])

    assert target.read_bytes() == original
    assert tree_entries(project / "pous" / "programs") == ["MAIN.st"]


def test_update_replace_failure_leaves_target_unchanged(tmp_path: Path, monkeypatch) -> None:
    """A final os.replace() failure leaves the target unchanged with no litter."""
    project = make_update_project(tmp_path / "project")
    target = project / "pous" / "programs" / "MAIN.st"
    original = target.read_bytes()
    pou = read_pou(str(project), "MAIN")

    def failing_replace(src, dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("openplc_engineering_mcp.openplc.pous.os.replace", failing_replace)

    with pytest.raises(ToolError, match='Could not update POU "MAIN"'):
        update_pou(str(project), "MAIN", "PROGRAM MAIN\nEND_PROGRAM\n", pou["content_hash"])

    assert target.read_bytes() == original
    assert tree_entries(project / "pous" / "programs") == ["MAIN.st"]
