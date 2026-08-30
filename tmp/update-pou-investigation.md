# update_pou() Investigation

> Investigation only. This document does **not** implement `update_pou()`.
>
> Scope: the current OpenPLC Editor project format only. Historical/legacy project representations are intentionally out of scope.

This document uses four evidence labels throughout:

- **Observed** — directly supported by inspected source code, tests, pull requests, or commit history.
- **Inferred** — an architectural conclusion derived from observed behavior.
- **Recommended** — a design decision proposed for `openplc-engineering-mcp`.
- **Open question** — evidence is insufficient or the answer is deliberately deferred.

## 1. Executive Summary

The smallest safe `update_pou()` is **not** a generic file editor, an IEC 61131-3 parser, or a second OpenPLC Editor implementation.

**Observed.** In the current OpenPLC Editor format, each Program, Function Block, or Function is persisted as an independent language-specific file under `pous/`. For an existing POU, the OpenPLC save path ultimately writes that individual pre-serialized POU file; `project.json` deliberately persists `pous: []` and does not duplicate POU source. [O5] [O6] [O8]

**Observed.** OpenPLC deliberately preserves raw loaded content when an unchanged semantic model would otherwise serialize differently. Recent LD/FBD fixes show that parse/recovery/serialization mistakes can create phantom diffs or real data-loss risks. [O11] [O13] [O14] [O15]

**Inferred.** For an **existing POU whose name, type, and language stay unchanged**, the correct MCP mutation boundary is the complete persisted POU file. The MCP does not need to reconstruct an OpenPLC POU object or save the whole project.

**Recommended v1:**

- writable language: **Structured Text only**;
- supported POU types: **Program, Function Block, Function**;
- mutation unit: **complete persisted ST POU content**;
- mutable: documentation, Function return type, POU-local/interface declarations, body logic, comments, formatting;
- immutable: POU name, POU type, language, canonical path;
- concurrency: **required SHA-256 exact-byte version token** from `read_pou()`;
- validation: project/target/path/concurrency plus a deliberately small ST outer-envelope/identity check;
- semantic validation: explicit later `compile_project()` / `get_diagnostics()` calls;
- persistence: same-directory temporary file + flush/fsync + final version re-check + `os.replace()`;
- backups: none;
- live OpenPLC Editor co-editing: not a synchronized/supported v1 workflow.

Recommended contract:

```python
class PouContent(PouInfo):
    content: str
    content_hash: str


class UpdatePouResult(TypedDict):
    name: str
    content_hash: str


def update_pou(
    project_path: str,
    pou_name: str,
    content: str,
    expected_content_hash: str,
) -> UpdatePouResult:
    ...
```

Recommended lifecycle:

```text
read_pou()
    ↓ content + content_hash
reason / modify complete ST representation
    ↓
update_pou(..., expected_content_hash=...)
    ↓
compile_project()
    ↓
get_diagnostics()
    ↓
correct and repeat when necessary
```

### Quality-gate answers

| Question | Conclusion |
| --- | --- |
| What is a current-format POU on disk? | A language-specific file under `pous/programs`, `pous/function-blocks`, or `pous/functions`. |
| How is it parsed? | Raw project files → `parseProjectFiles()` → language-specific POU parser → in-memory POU. |
| How is it saved? | Editor state → language serializer → raw-content preservation decision → single-file/full-project save → platform writer. |
| Which artifact is authoritative for POU source? | The individual POU file. |
| Can an existing POU be changed independently? | Yes, if identity (name/type/language/path) is unchanged. |
| What does `update_pou()` update? | The complete existing ST POU representation. |
| Writable languages in v1? | ST only. |
| Can variables change through it? | Yes; POU declarations live in the same file. |
| Immutable POU properties? | Name, type, language, canonical path. |
| MCP validation? | Operation/identity/path/concurrency + minimal outer envelope. |
| Compiler validation? | IEC syntax/semantics, types, references, calls, control logic. |
| Safe disk write? | Same-directory temp + fsync + final hash re-check + `os.replace()`. |
| Partial-write prevention? | Never truncate the target directly. |
| Concurrent modifications? | Required exact-byte SHA-256 optimistic concurrency. |
| Open Editor simultaneously? | Unsupported as a synchronized v1 workflow; close/reopen or otherwise avoid competing edits. |
| Automatic compile? | No. |
| `read_pou()` change? | Add exact-byte `content_hash` in the same implementation PR. |
| Which failures guarantee no target mutation? | All validation, stale-version, temp-write, and pre-replace failures. |
| What proves the guarantees? | Section 17 test matrix. |
| Final minimal API? | Complete ST replacement + required expected hash, returning name + new hash. |

## 2. Repositories and Revisions Inspected

The conclusions are pinned because both repositories are actively evolving.

| Repository | Branch | Revision inspected | Role |
| --- | --- | --- | --- |
| `industrix-com-br/openplc-engineering-mcp` | `main` | `9936fa2455e85f6856a7b9dc9c92a7a72200c508` | Current MCP architecture/contracts |
| `Autonomy-Logic/openplc-editor` | `development` | `3652363583de7e88f64c77ba3fac204e4ee7e4ed` | Authoritative current Editor behavior |

Inspection date: **2026-08-30**.

The MCP revision is merge PR #22 (`feat: add I/O configuration inspection`). The OpenPLC Editor revision is merge PR #1060 (`chore(ci): trim stale commentary from the unit-tests workflow`).

### Current-format boundary

**Observed.** OpenPLC Editor PR #411, merged as `2389075e7d4ce0505600852e690deff02f657419`, introduced native language-specific POU persistence (`.st`, `.il`, `.ld`, `.fbd`, `.py`, `.cpp`). Upstream still contains compatibility logic for historical JSON POUs. [O12]

**Observed.** The MCP intentionally supports the current native-file representation only and does not reproduce OpenPLC's historical compatibility/migration behavior. [M1] [M8]

**Recommended.** Legacy parser branches are relevant only as historical evidence. Do not add format detection, fallback, migration, or JSON-POU support to `update_pou()`.

## 3. Current MCP Architecture

### 3.1 Project loading and validation

**Observed.** `openplc/project.py` owns local project preconditions. It resolves the project root, requires `project.json`, parses UTF-8 JSON, validates the top-level metadata used by the MCP, and accepts current `plc-project` / `plc-library` types. `validate_project()` is deliberately shallow. [M3]

**Recommended.** `update_pou()` should reuse this current-format project boundary. It should not create a second whole-project validator or a project-version subsystem.

### 3.2 POU discovery and `read_pou()`

**Observed.** Current MCP POU directories are:

```text
pous/functions        -> function
pous/function-blocks  -> function-block
pous/programs         -> program
```

Recognized current POU suffixes are:

```text
.st .il .ld .fbd .py .cpp
```

`list_pous()` derives name from file stem, type from directory, language from extension, and returns a project-relative path. `read_pou()` resolves by this domain name and returns the file as UTF-8 text without parsing or reserializing it. [M2]

**Important observed nuance.** `_list_pous()` currently deduplicates by name with a first-discovered-wins dictionary. It does **not** raise an ambiguity error. Given the current directory order, a same-stem Function is discovered before a Function Block, which is discovered before a Program; multiple recognized same-stem files can therefore be hidden by the read/list abstraction. [M2]

**Recommended.** A write operation must not inherit that silent first-wins behavior. `update_pou()` should use a small write-specific resolver that scans recognized current-format POU sources for the requested stem and:

- returns the only match;
- raises `POU not found` for zero matches;
- raises an ambiguity/project-state error for more than one match.

This does not require a generic resolver framework or a prerequisite change to `list_pous()`.

### 3.3 Path containment

**Observed.** `_is_contained(root, path)` resolves a candidate and requires the resolved path to remain under the resolved project root. Existing POU tests cover escape-through-symlink behavior. [M2] [M7]

**Recommended.** Reuse the containment concept, but make the write target stricter: it must be an existing regular file and the lexical POU path itself must not be a symlink.

### 3.4 Variables

**Observed.** `list_variables()` performs narrow read-time extraction from `read_pou()` content. It is not a full ST parser. [M4]

**Recommended.** Do not generalize it into a mutation parser. POU-local variables should change through complete POU replacement.

### 3.5 Compilation and diagnostics

**Observed.** `compile_project()` delegates to `openplc-cli`; `get_diagnostics()` exposes diagnostics from explicit compilation. [M5]

**Recommended.** Preserve this responsibility boundary. Persisting a POU and proving that the resulting project compiles are separate operations.

### 3.6 MCP registration and errors

**Observed.** Domain/input failures use `ToolError`. `server.py` is a thin registration layer. Read tools use read-only annotations; `compile_project()` uses the local-write annotation (`read_only_hint=False`, `open_world_hint=False`). [M6]

**Recommended.** Register `update_pou()` as local-write and delegate directly to the POU domain module. Do not add service/repository/adapter layers or an exception hierarchy.

### 3.7 Existing writes

**Observed.** No current MCP tool edits project source. Compilation can create build artifacts through the authoritative CLI, but there is no generic filesystem writer or mutation framework. [M5] [M8]

**Recommended.** Keep that architecture: `update_pou()` should be one domain write, not a generic write API.

### 3.8 Legitimate reuse versus over-generalization

Legitimate reuse:

- `load_project()` / current project-loading behavior;
- POU directory/language mappings from `pous.py`;
- `_is_contained()` concept;
- `PouInfo` / `PouContent` structure;
- `ToolError` conventions;
- `_LOCAL_WRITE` server annotation.

Small additions justified by this feature:

- a private exact-byte hash helper shared by `read_pou()` and `update_pou()`;
- a private update-safe POU resolver that rejects multiple matching source files;
- a private ST outer-envelope identity check;
- a private one-file atomic replacement helper local to the POU module if it improves readability.

Do **not** introduce solely for this feature:

- a generic project repository/service;
- a generic file writer;
- a generic project transaction framework;
- a generic editable-entity abstraction;
- a complete ST/IEC parser;
- a cross-language POU serializer.

## 4. Current OpenPLC POU Persistence Model

### 4.1 Canonical path model

**Observed.** Current OpenPLC maps POU type and language directly to folder and extension. [O1] [O5]

```text
<project>/
├── project.json
└── pous/
    ├── programs/
    │   └── <Name>.<language-extension>
    ├── function-blocks/
    │   └── <Name>.<language-extension>
    └── functions/
        └── <Name>.<language-extension>
```

| Language | Extension |
| --- | --- |
| Structured Text | `.st` |
| Instruction List | `.il` |
| Ladder Diagram | `.ld` |
| Function Block Diagram | `.fbd` |
| Python | `.py` |
| C++ | `.cpp` |

| POU type | Folder | Declaration | Terminal |
| --- | --- | --- | --- |
| Program | `pous/programs` | `PROGRAM` | `END_PROGRAM` |
| Function Block | `pous/function-blocks` | `FUNCTION_BLOCK` | `END_FUNCTION_BLOCK` |
| Function | `pous/functions` | `FUNCTION` | `END_FUNCTION` |

### 4.2 Identity exists in both path and content

**Observed.** The path encodes:

- type via directory;
- language via extension;
- name via filename stem.

The POU text also carries declaration type and name; Functions also carry a return type. The current OpenPLC parser receives the expected type from the path, checks the corresponding declaration keyword, and parses the declared name. It does not generally enforce declaration-name == filename-stem. [O2] [O3]

**Inferred.** A manual file such as `pous/programs/MAIN.st` declaring `PROGRAM OTHER` can create a path/content identity split. A safe mutation API should refuse to create that state even if some OpenPLC recovery path could still load it.

### 4.3 `project.json` and references

**Observed.** Current save logic writes `pous: []` in `project.json`; POU source is stored in individual files. Program Instances remain configuration objects that reference Program names. [O5] [M9]

**Observed.** OpenPLC history shows that a Program rename can require propagation into configured Program Instances, and graphical POU renames have required additional internal state synchronization. [O16]

**Inferred.** Content-only changes do not require a `project.json` rewrite when the POU's identity is unchanged. Rename is a different project-level operation and must not be hidden inside `update_pou()`.

### 4.4 Authoritative artifact

**Answer.** For source/interface/documentation of an existing current-format POU, the individual POU file is authoritative. Replacing that file is sufficient **only** when name, type, language, and canonical path remain unchanged. [O3] [O5] [O6] [O8]

The conclusion does not apply to create/delete/rename/type conversion/language conversion or resource-level configuration changes.

## 5. OpenPLC POU Read Path

### 5.1 Current flow

```text
files on disk
    ↓
raw project reader
    ↓
ProjectPort adapter
    ↓
parseProjectFiles()
    ↓
parseTextualPouFromString()       ST / IL
parseHybridPouFromString()        Python / C++
parseGraphicalPouFromString()     LD / FBD
    ↓
PLCPou in-memory representation
    ↓
Monaco / graphical editor
```

**Observed.** The port explicitly exposes raw project files; parsing is performed above the persistence writer. [O3] [O6] [O7]

### 5.2 ST/IL

**Observed.** `parseTextualPouFromString()`:

- extracts the leading OpenPLC documentation form;
- expects the declaration keyword for the path-derived POU type;
- extracts POU name;
- requires a Function return type;
- locates supported `VAR...END_VAR` sections;
- delegates variable parsing;
- requires the matching terminal keyword;
- returns the body as text. [O2]

### 5.3 Python/C++

**Observed.** Hybrid POUs use the same IEC-style declaration/interface envelope but preserve a foreign-language body. [O2] [O4]

### 5.4 LD/FBD

**Observed.** Graphical files use the IEC-style outer envelope but store the body as JSON. JSON syntax alone is insufficient: current validation requires LD to have an object with a `rungs` array and FBD to have an object with a `rung` object containing a `nodes` array. [O2]

### 5.5 Recovery behavior

**Observed.** OpenPLC deliberately distinguishes recoverable declaration failures from unrecoverable graphical-body failures. Malformed textual declarations can be preserved in fallback/raw text so the user can repair them. A graphical body that cannot be parsed or has the wrong structure is treated as unrecoverable rather than replaced with an apparently legitimate blank diagram. [O3] [O14]

**Why it matters.** `update_pou()` should not reimplement these recovery semantics. They are evidence that OpenPLC's parsing model is richer than the MCP needs to own.

## 6. OpenPLC POU Write Path

### 6.1 Current flow

```text
Editor/store POU state
    ↓
state reconciliation / graphical write-back checks
    ↓
serializePouToText()
    ↓
pickContentForSave(...)
    ↓
ProjectPort.saveFile() or saveProject()
    ↓
platform adapter / IPC
    ↓
ProjectService / storage writer
```

### 6.2 Serialization is above the writer

**Observed.** `ProjectPort.WriteProjectFiles` states that all content is already serialized and the backend is a “dumb file writer.” `pouFiles` are pre-serialized raw path/content pairs. [O6]

**Inferred.** There is no stable backend POU-mutation API for the Python MCP to call instead of implementing a write. Calling private frontend/editor state machinery would create substantially more coupling than directly replacing the authoritative local POU file.

### 6.3 Single-file save

**Observed.** For an existing POU, OpenPLC computes canonical folder/extension/name, serializes that POU, and calls the single-file save path. `ProjectService.saveFile()` ultimately writes UTF-8 content. A content-only POU save does not require a `project.json` rewrite. [O5] [O8]

### 6.4 Full-project save

**Observed.** Full save emits POU files separately from `project.json`, device configuration, server/remote-device files, data types, and other project artifacts. The desktop writer writes these pre-serialized entries; `project.json` is handled as its own artifact. [O5] [O6] [O8]

### 6.5 POU create/rename is separate

**Observed.** `PouService` has explicit create/rename behavior. OpenPLC history demonstrates additional rename propagation requirements. [O9] [O16]

**Recommended.** Do not make `update_pou()` a create/rename/move operation.

### 6.6 Direct answer

**Can an existing current-format POU safely be modified by replacing only its persisted POU file?**

**Yes, under these constraints:**

- the POU already exists;
- exactly one current-format POU source matches the requested domain name for the write;
- its name, type, language, directory, and extension remain unchanged;
- the replacement keeps matching path/content identity;
- only that target file is replaced;
- lost updates are rejected;
- semantic correctness is checked later by the compiler.

No second POU-content artifact was observed that needs synchronization for this constrained operation.

## 7. Language-Specific Representation

| Language | Persisted body | Important risk | v1 write decision |
| --- | --- | --- | --- |
| ST | textual IEC body inside textual POU envelope | syntax/semantics delegated to compiler; identity envelope must stay correct | **Support** |
| IL | textual IL body inside same broad envelope | additional language surface with little initial experimental value | Defer |
| LD | structured JSON body inside textual envelope | graph/schema integrity; recent corruption/data-loss fixes | Do not support |
| FBD | structured JSON body inside textual envelope | graph/schema integrity; recent corruption/data-loss fixes | Do not support |
| Python | native Python body inside hybrid OpenPLC envelope | language-specific preprocessing/tooling | Defer |
| C++ | native C++ body inside hybrid OpenPLC envelope | language-specific preprocessing/build behavior | Defer |

### 7.1 Why ST only

**Recommended.** ST gives the first write feature a clear, defensible scope:

- it enables the thesis's primary modification/debugging tasks;
- it is an independent textual persisted artifact;
- complete replacement avoids MCP reserialization;
- it allows both logic and local declaration changes;
- semantic validation remains with the existing compiler;
- it avoids graphical and hybrid-language implementation ownership.

Read support and write support do not need equal language breadth.

### 7.2 Raw loaded content preservation

**Observed.** `ProjectResponse.rawLoadedFiles` is a path → raw-text map captured before parsing. The save pipeline calls `pickContentForSave()` for every file produced by `iterateProjectFiles()`; if the canonical serialized content still matches the loaded semantic baseline, OpenPLC can echo the original raw text instead of emitting the reserialized form. This mechanism applies by path across emitted project artifacts, including POUs, rather than being a POU-only concept. Unparsed `.dt` files also have an explicit raw-preservation path so they are not silently dropped. [O5] [O6] [O11]

**Observed.** OpenPLC history explicitly ties this behavior to avoiding phantom diffs and preserving trustworthy graphical content. [O15]

Consequences:

- parse → serialize is not byte-preserving by default;
- declarations/documentation/spacing may be regenerated;
- graphical JSON may be canonicalized;
- malformed-but-repairable raw text may need to survive;
- an MCP-side POU model/serializer would inherit these round-trip responsibilities.

### 7.3 Strategy comparison

#### Strategy A — parse → structured mutation → serialize

**Reject.** It duplicates OpenPLC's parser/model/serializer and creates format-preservation obligations the MCP does not need.

#### Strategy B — complete replacement representation

**Recommend for ST.** The caller supplies the exact complete new POU text; the MCP owns only domain resolution, identity safety, concurrency, and one-file persistence.

#### Strategy C — body-only replacement/splice

**Reject.** It looks smaller externally but forces the MCP to locate declaration/body boundaries correctly and prevents declaration/interface edits without adding more mutation APIs.

#### Strategy D — patch/diff

**Reject as the public domain contract.** A patch is a useful generic coding-agent primitive but exposes line/text mechanics rather than PLC domain semantics and is more sensitive to stale context.

## 8. Identity and Project Invariants

### 8.1 Immutable through `update_pou()`

| Property | Mutable? | Reason |
| --- | --- | --- |
| POU name | No | participates in canonical filename and project references |
| POU type | No | determines folder and declaration keyword |
| Programming language | No | determines extension/parser/body representation |
| Canonical POU path | No | derived from existing identity, never caller-controlled |

Example that must fail before mutation:

```text
Target: pous/programs/MAIN.st
Replacement: PROGRAM DIFFERENT_NAME
```

Likewise `PROGRAM MAIN` → `FUNCTION_BLOCK MAIN` is a different domain operation and must fail.

Use exact persisted name spelling for the identity check; do not turn a case-only difference into an implicit rename.

### 8.2 Mutable content

Complete ST replacement may change:

- documentation;
- Function return type;
- `VAR`;
- `VAR_INPUT`;
- `VAR_OUTPUT`;
- `VAR_IN_OUT`;
- other POU-local declarations accepted by OpenPLC;
- body logic;
- comments and formatting.

### 8.3 Function return type

**Observed.** Return type is declaration/interface content, not path identity. OpenPLC requires one for a Function. [O2]

**Recommended.** Require that it exists, but allow it to change. Broken callers are a compiler-level consequence, not a reason to make `update_pou()` a project-wide reference analyzer.

### 8.4 Variable modification

**Recommended.** POU-local/interface variable changes should naturally occur through complete POU replacement. Do not introduce `create_variable()`, `update_variable()`, or `delete_variable()` merely to mutate the same declaration blocks through a second path.

Resource-level globals are a separate artifact and remain outside `update_pou()`.

### 8.5 Rename

**Observed.** Program rename has required propagation to Program Instances; LD/FBD rename bugs have required synchronization of graphical flow/body names. [O16]

**Recommended.** If rename is ever needed, investigate and implement a distinct `rename_pou()` contract. It is not an `update_pou()` option.

## 9. Candidate update_pou() Contracts

| Contract | Domain abstraction | Complexity | Formatting/comments | OpenPLC coupling | Validation burden | Agent utility | Main failure mode | Decision |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| A. Complete POU replacement | High | **Low** | caller controls exact target representation | Low | identity/envelope + compiler later | **High** | stale/bad complete content | **Recommended** |
| B. Body-only replacement | High superficially | Medium/High | requires reliable splice logic | Medium | body-boundary parsing | Medium | splice/parser error; cannot change declarations naturally | Reject |
| C. Structured POU mutation | Very high | **Very High** | parse→serialize drift becomes MCP responsibility | **Very High** | full parser/model/serializer | High | MCP becomes second Editor | Reject |
| D. Patch/diff | Generic source abstraction | Medium | preserves untouched bytes if patch applies | Low OpenPLC, high text-edit coupling | patch context/conflicts | High | stale/ambiguous patch | Reject |
| E. Arbitrary file write | Low domain value | Low | caller controlled | Low | almost none | High but unsafe | arbitrary file mutation | Reject |

### External inspiration, not OpenPLC evidence

- CODESYS's Development System MCP Server publicly describes domain operations for reading projects, creating/modifying POUs using Structured Text, compilation, and compiler errors. That supports the general separation of POU mutation from compiler feedback, but does not define OpenPLC persistence. [X1]
- SemaPLC emphasizes project grounding and explicit verification/compilation/runtime gates; its relevance is the validation workflow rather than an OpenPLC edit contract. [X2]
- SWE-agent exposes generic source-edit operations. It is a useful contrast for why this MCP should not expose `path + patch` as the PLC-domain API. [X3]

## 10. Validation Boundary

The MCP should validate whether the **requested write is a well-defined safe update of the same persisted domain object**. It should not validate the PLC program completely.

| Check | Classification | Reason |
| --- | --- | --- |
| project exists/current MCP project preconditions | **Required** | existing domain boundary |
| non-empty POU name | **Required** | existing contract |
| exactly one recognized current-format source matches requested stem | **Required for write** | prevent silent first-wins mutation |
| target language is ST | **Required** | explicit v1 scope |
| target path is derived by MCP and contained in root | **Required** | prevent arbitrary write |
| lexical target is not a symlink | **Required** | avoid alias-write semantics |
| resolved target exists and is a regular file | **Required** | update, not create |
| expected hash format is valid | **Required** | concurrency contract |
| expected hash matches current exact bytes | **Required** | lost-update protection |
| replacement is non-empty/non-whitespace | **Required** | complete POU representation |
| replacement encodes as UTF-8 | **Required** | persisted text contract |
| replacement declaration type matches target | **Required** | identity invariant |
| replacement declaration name exactly matches target | **Required** | identity invariant |
| Function has a return type | **Required** | minimal current OpenPLC envelope |
| matching `END_*` exists after declaration | **Required lightweight envelope** | reject obviously incomplete replacement |
| parse all variable declarations | **Do not implement** | OpenPLC/compiler responsibility |
| validate ST grammar | **Delegate to `compile_project()`** | compiler responsibility |
| validate data types/calls/references | **Delegate to compiler** | semantic validation |
| validate functional behavior | **Outside `update_pou()`** | runtime/test responsibility |
| validate LD/FBD JSON | **Not applicable in v1** | not writable |
| legacy detection/migration | **Do not implement** | explicit scope exclusion |

### 10.1 Minimal ST envelope check

A small private check can mirror only the outer facts the current OpenPLC parser expects:

1. allow leading whitespace and the leading `(* ... *)` documentation form;
2. require the declaration keyword derived from the existing POU type;
3. capture the declared name and require exact equality with the persisted target name;
4. for Functions, require a non-empty return-type token;
5. require the corresponding terminal keyword after the declaration.

Do not parse variables, expressions, statements, calls, initializers, comments in the body, timer syntax, or type semantics.

### 10.2 Repairing an already malformed ST POU

**Recommended.** Do not require the old content to parse fully. The target is found from current-format filesystem identity, and the expected hash proves which exact bytes the caller read. A valid replacement with the same canonical name/type can therefore repair a malformed source file.

## 11. Atomicity and Failure Integrity

### 11.1 Direct overwrite versus atomic replacement

| Mechanism | Benefit | Failure risk | Decision |
| --- | --- | --- | --- |
| direct truncate/write | simplest | interruption/disk failure can leave partial/empty POU | Reject |
| same-directory temp + `os.replace()` | small, one-file safety | replacement can still fail due permissions/locks | **Recommend** |
| generic transaction/backup system | stronger multi-file abstraction | unnecessary complexity | Reject |

**Observed.** OpenPLC desktop writes ultimately use direct file writes. The MCP does not need to copy that weaker failure mode. [O8]

### 11.2 Minimum safe mechanism

1. derive the lexical target from the discovered POU relative path;
2. reject if that lexical target is a symlink;
3. resolve it strictly and verify containment + regular-file status;
4. read exact current bytes and verify expected hash;
5. validate/encode the complete replacement before changing the target;
6. create a temporary file in `target.parent`;
7. write all bytes, flush, `fsync()`;
8. preserve the original normal file mode where appropriate;
9. re-verify lexical target state and re-read/re-hash immediately before replacement;
10. `os.replace(temp, target)`;
11. best-effort clean the temp file on every pre-replace failure.

Same-directory placement keeps the rename on one filesystem.

A parent-directory `fsync()` would strengthen power-loss durability on some POSIX filesystems, but is not needed unless the MCP explicitly promises crash-consistent persistence across power loss.

### 11.3 No-op replacement

**Recommended.** If `new_hash == current_hash`, return success without physically replacing the file. This avoids unnecessary mtime changes and Editor watcher activity while preserving the same result contract.

### 11.4 Guarantee

Before successful `os.replace()`, validation, stale-version, encoding, temp-write, fsync, and re-check failures must leave the original target bytes unchanged.

`os.replace()` is appropriate for ordinary local filesystems. Windows file sharing/locks or unusual/network filesystems may cause replacement to fail; surface that failure rather than falling back to direct truncation.

### 11.5 Backups

**Recommended: none.** `.bak`, `backup/`, and hidden history are not OpenPLC project semantics, pollute repositories across repeated agent calls, and create retention policy. Git/version control plus optimistic concurrency and atomic replacement are cleaner boundaries.

## 12. Concurrency and External Modification

### 12.1 Lost-update risk

```text
read MAIN at A
    ↓
Editor/other process writes B
    ↓
agent writes full replacement derived from A
    ↓
B is silently lost
```

A complete replacement has a high lost-update blast radius.

### 12.2 Candidate mechanisms

| Mechanism | Assessment | Decision |
| --- | --- | --- |
| mtime | metadata, resolution/collision issues | Reject |
| size + mtime | still does not identify content | Reject |
| MCP-owned incrementing version | requires persistent server state | Reject |
| full previous content | exact but request-heavy | Reject |
| SHA-256 exact persisted bytes | stateless, deterministic, content-based | **Recommend** |

### 12.3 Required expected hash

**Recommended.** Make `expected_content_hash` required in v1. An optional token would leave blind full-file overwrite as a valid normal mode. Project-grounded modification tasks already require reading the existing POU.

Token format:

```text
sha256:<64 lowercase hex characters>
```

Hash the exact file bytes, before newline normalization or parsing.

### 12.4 `read_pou()` change

In the same future PR:

```text
raw = target.read_bytes()
content = raw.decode("utf-8")
content_hash = "sha256:" + sha256(raw).hexdigest()
```

Read bytes once so `content` and `content_hash` describe the same exact version. This also avoids universal-newline normalization when the returned string is the basis for a complete-file update.

This is additive for normal MCP consumers, though exact-dictionary tests must change.

### 12.5 Re-check and residual race

Check the expected hash once before preparation and again immediately before `os.replace()`.

**Open limitation.** There remains a narrow TOCTOU window between the final check and replacement. Eliminating it portably would require locks, OS-specific handles, or Editor coordination. That complexity is disproportionate to the current local cooperative threat model and should not be introduced in v1.

## 13. Open Editor Interaction

### 13.1 External file watching

**Observed.** The desktop textual/hybrid Monaco editor watches its canonical POU file when file-watcher capability is available. On an external change:

- a POU considered **saved/clean** is re-read;
- a POU considered **unsaved/dirty** is not reloaded by that path. [O10]

**Observed.** The inspected reload handler parses the POU but updates the textual body state; it does not perform the same full interface/documentation hydration as a full project-open path. [O10]

### 13.2 Consequences

Dirty Editor case:

```text
MCP writes MAIN.st
Editor ignores external reload
later Editor save writes stale in-memory state
MCP result can be overwritten
```

Clean Editor + declaration change case:

```text
MCP writes full MAIN.st
watcher reloads body
interface/documentation state may remain stale
later Editor save can reserialize stale declarations
```

The MCP hash only protects the MCP from overwriting a change that happened **before its own write**. It cannot stop the Editor from overwriting the MCP result afterward.

### 13.3 v1 policy

**Recommended.** Do not claim synchronized co-editing. Document that the same project should not be actively edited in OpenPLC Editor during `update_pou()`. The safe operational practice is to close the project/Editor before mutation, or reopen/reload the project after MCP writes before further GUI editing.

Do not detect running Editor processes, inject into private IPC/store state, or add a cross-process lock without an upstream-supported contract.

## 14. Relationship with Existing MCP Tools

| Tool | Required change? | Relationship |
| --- | --- | --- |
| `get_project_structure()` | No | identity/path does not change |
| `list_pous()` | No public change required | discovery remains read-only; update uses a stricter private collision check |
| `read_pou()` | **Yes, additive** | return exact-byte `content_hash` |
| `list_variables()` | No | reads changed declarations after update |
| `list_global_variables()` | No | resource globals are outside POU file |
| `list_datatypes()` | No | separate artifact |
| `get_execution_configuration()` | No | rename is forbidden, so Program Instance names do not change |
| `get_io_configuration()` | No | unrelated artifact |
| `validate_project()` | No | remains shallow project precondition check |
| `compile_project()` | No | explicit post-update semantic validation |
| `get_diagnostics()` | No | reports explicit compilation result |

### 14.1 Automatic compilation

**Recommended: no.** Automatic update+compile would conflate persistence success and compiler success, increase cost/latency, complicate recovery, and hide compile-attempt/tool-call observations that matter experimentally.

Keep:

```text
update_pou()
compile_project()
get_diagnostics()
```

as separate observable operations.

### 14.2 Local variable mutation tools

**Recommended: no new variable CRUD tools as part of this feature.** Read decomposition and write decomposition do not need to be symmetric. Complete ST replacement already provides one authoritative write path for POU-local declarations.

## 15. Experimental Implications

The research compares:

```text
LLM Agent → filesystem / CLI → OpenPLC
```

against:

```text
LLM Agent → domain-specific MCP → OpenPLC
```

### 15.1 Functional equivalence

**Recommended.** Complete ST replacement preserves functional equivalence well:

- a baseline agent edits the authoritative `.st` file through filesystem tools;
- an MCP agent edits the same authoritative `.st` file through domain identity;
- both later compile through OpenPLC tooling;
- the MCP adds target/identity/concurrency safeguards but does not synthesize logic or perform hidden semantic validation.

The engineering artifact is equivalent; the interaction interface differs.

### 15.2 Enabled task classes

The contract supports:

- modify start/stop logic;
- add interlocks;
- change timer parameters;
- add/remove/change POU-local variables;
- change input/output/in-out declarations;
- repair undeclared-variable or other compiler errors;
- correct POU implementation/calls;
- change Function return/interface and resolve resulting compiler errors;
- compile → diagnose → correct loops.

### 15.3 ST-only experimental scope

ST is sufficient for a meaningful first experimental write surface and avoids making graphical-model engineering a confounder. A required read/hash is also consistent with realistic project-grounded modification tasks: an agent should inspect existing logic before replacing it.

## 16. Risks and Failure Modes

| Risk | Cause | v1 mitigation | Residual risk |
| --- | --- | --- | --- |
| arbitrary file write | caller controls filesystem path | caller supplies only POU name; MCP derives recognized target | local filesystem race remains possible |
| wrong same-name target | current read/list first-wins deduplication | update-specific resolver rejects >1 recognized match | malformed project requires manual repair |
| accidental rename | replacement declares different name | exact identity check | none for this operation boundary |
| type/language conversion | declaration/extension differs | immutable target type/language | semantic ST errors remain compiler concern |
| lost update | stale full-file edit | required exact-byte SHA-256 + final re-check | narrow final TOCTOU window |
| target truncation | interrupted direct write | temp + atomic replace | filesystem-specific replacement semantics |
| parse→serialize drift | MCP reconstructs POU | never reserialize target through MCP model | caller may intentionally reformat content |
| LD/FBD corruption | graphical JSON/state complexity | no graphical writes in v1 | future support needs separate investigation |
| Editor overwrites MCP | simultaneous GUI editing | unsupported synchronized workflow | no cross-process lock |
| backup/temp pollution | hidden recovery files | no backups; cleanup temp | crash can leave an orphan temp |
| compilably invalid ST | mutation changes semantics | explicit compile/diagnostics | intermediate invalid source is allowed by design |
| legacy-format confusion | upstream fallback exists | current-format sources only | mixed/manual unsupported projects may fail |

### 16.1 Error model

Use existing `ToolError` conventions; do not add an exception class hierarchy. Message literals follow the existing style of quoting the offending value with double quotes (for example, `POU not found: "MAIN"`).

Meaningful failures:

User/agent input:

```text
POU name must not be empty
Replacement POU content must not be empty
Invalid expected content hash
Replacement POU name does not match target "MAIN"
Replacement POU type does not match target type "program"
Replacement Function must declare a return type
Replacement POU is missing END_PROGRAM
```

Project state:

```text
POU not found: "MAIN"
Ambiguous POU name: "MAIN"
POU language "ld" is not supported for update; v1 supports Structured Text only
POU target is not a regular project file
POU target is a symbolic link and cannot be updated
```

Concurrency:

```text
POU changed since it was read: "MAIN"; call read_pou() again before updating
```

I/O:

```text
Could not update POU "MAIN": <concise OS error>
```

Compiler errors remain compiler diagnostics, not `update_pou()` validation errors.

### 16.2 Failure-integrity invariant

Every failure before successful atomic replacement must leave the target's original bytes unchanged. No validation error may partially mutate the POU.

## 17. Future Test Matrix

### 17.1 Happy path

- update existing ST Program;
- update existing ST Function Block;
- update existing ST Function;
- change body only;
- change documentation;
- change `VAR`, `VAR_INPUT`, `VAR_OUTPUT`, `VAR_IN_OUT` declarations;
- change Function return type;
- `read_pou()` after update returns exact replacement + new hash;
- `list_variables()` observes changed declarations;
- explicit `compile_project()` succeeds for a valid integration fixture.

### 17.2 Exact-content behavior

- replacement persists byte-for-byte after UTF-8 encoding;
- LF remains LF;
- CRLF can be read/hashed without normalization and round-trip unchanged when content is unchanged;
- comments/spacing supplied by caller remain exact;
- unrelated POU files remain byte-identical;
- `project.json` remains byte-identical;
- no-op replacement does not physically replace/touch the file where the test can reliably assert it.

### 17.3 Identity / ambiguity protection

- target `MAIN`, replacement declares `DIFFERENT_NAME` → error, no write;
- Program target, Function Block declaration → error;
- Function Block target, Program declaration → error;
- Function without return type → error;
- missing matching terminal → error;
- zero matching target → not found;
- two recognized same-stem current POU source files → update-specific ambiguity error, no write;
- test must explicitly document that this is stricter than current read/list first-wins deduplication.

### 17.4 Unsupported languages

Existing `.il`, `.ld`, `.fbd`, `.py`, `.cpp` targets must reject before mutation and preserve original bytes.

### 17.5 Filesystem protection

- symlink escaping project is rejected;
- in-project symlink target is rejected;
- target removed between discovery and write → error;
- target replaced by directory/non-regular entry → error;
- temp creation failure → original unchanged;
- temp write failure → original unchanged;
- fsync failure → original unchanged;
- `os.replace()` failure → original unchanged and temp cleaned when possible;
- target mode preserved where platform behavior is testable.

### 17.6 Concurrency

- `read_pou()` hash is deterministic for exact bytes;
- matching expected hash permits update;
- stale expected hash rejects update;
- stale rejection preserves the external writer's bytes;
- modification between first and final hash checks is detected;
- returned new hash matches exact replacement bytes;
- malformed token rejects before mutation.

### 17.7 Repair scenario

- malformed existing ST is still identified from canonical path;
- caller presents exact hash;
- valid same-name/same-type replacement repairs it;
- update does not require old content to parse fully.

### 17.8 Server contract

- tool is registered;
- `read_only_hint=False`, `open_world_hint=False`;
- successful update result is `{name, content_hash}`;
- `read_pou()` result adds `content_hash` while preserving existing fields;
- errors surface through existing MCP conventions.

### 17.9 No hidden side effects

- no `.bak`;
- no backup directory;
- no automatic compile;
- no `project.json` modification;
- no unrelated file modification;
- failed update does not change compiler diagnostic cache.

### 17.10 Manual Editor-interaction verification

A full Electron integration suite is not required merely for this MCP PR, but the documented limitation should be manually rechecked against the then-current Editor:

- clean textual POU external body update;
- dirty textual POU external update;
- external declaration/variable update;
- project reopen loads the complete MCP-written representation.

## 18. Decision Table

| Design question | Recommended decision | Confidence | Evidence |
| --- | --- | --- | --- |
| Writable languages | **ST only in v1** | High | textual persistence + experimental scope; graphical data-loss history [O13] [O14] |
| Supported POU types | Program, Function Block, Function | High | same ST envelope with type-specific declaration/terminal [O1] [O2] |
| Mutation unit | **Existing named POU** | High | per-file persistence [O5] [O6] |
| Full POU vs body only | **Complete persisted POU content** | High | avoids splice/parser ownership; declarations are part of same artifact [O2] [O4] |
| Allow variable changes | **Yes** | High | declarations are in the POU file [O2] [O4] |
| Separate variable CRUD now | **No** | High | would duplicate the same write semantics |
| Allow documentation changes | Yes | High | same persisted representation [O2] [O4] |
| Allow Function return-type changes | Yes | Medium/High | interface content, not path identity [O2] |
| Allow rename | **No** | High | separate filesystem/reference propagation concerns [O9] [O16] |
| Allow type change | No | High | directory + declaration identity [O1] |
| Allow language change | No | High | extension/parser/body identity [O1] |
| Automatic compile | **No** | High | existing explicit compiler/diagnostics boundary [M5] |
| Atomic write | **same-dir temp + fsync + `os.replace()`** | High | prevents target truncation without transaction framework |
| No-op physical write | Skip it | High | avoids unnecessary mtime/watcher activity |
| Concurrency hash | **Required exact-byte SHA-256** | High | full-replacement lost-update risk + external modifications [O10] |
| Backup files | No | High | not OpenPLC semantics; hidden policy/clutter |
| `read_pou()` change | Add `content_hash` in same PR | High | directly supports safe update lifecycle |
| Duplicate-name handling | Update resolver rejects ambiguity | High | current read/list silently dedupe; write must not pick implicitly [M2] |
| Result fields | `name`, `content_hash` | High | smallest useful post-write result |
| Graphical writes | No v1 | High | concrete corruption/recovery history [O13] [O14] [O15] |
| Editor open simultaneously | Unsupported synchronized workflow | High | dirty-state gate + partial reload behavior [O10] |
| Legacy handling | None | High | explicit MCP scope [M1] [M8] |
| ST AST/full parser | Do not add | High | duplicates OpenPLC [O2] |
| Patch/diff public API | Do not use | Medium/High | generic text abstraction, not domain mutation [X3] |

## 19. Recommended Contract

### 19.1 Public types

Preserve the existing type shape rather than creating a duplicate POU representation:

```python
class PouContent(PouInfo):
    content: str
    content_hash: str


class UpdatePouResult(TypedDict):
    name: str
    content_hash: str
```

No new `PouLanguage`/parallel POU schema is required solely for this feature.

### 19.2 Public function

```python
def update_pou(
    project_path: str,
    pou_name: str,
    content: str,
    expected_content_hash: str,
) -> UpdatePouResult:
    ...
```

### 19.3 Parameters

`project_path`
: Same current-format local project-root semantics as existing MCP project tools.

`pou_name`
: Existing domain POU name/file stem, never a caller-supplied path. For the write, recognized current-format source files must contain exactly one matching stem.

`content`
: Complete new UTF-8 persisted representation of the target ST POU, including declaration/interface/body/terminal and optional documentation. Not a body fragment and not a patch.

`expected_content_hash`
: Required `sha256:<hex>` token from the `read_pou()` version on which the edit is based.

### 19.4 Result

```json
{
  "name": "MAIN",
  "content_hash": "sha256:..."
}
```

Do not return:

- `updated: true` — successful return already means success;
- path/type/language — unchanged and already known;
- previous hash — caller already supplied it;
- complete content — caller just supplied it and can re-read if needed.

### 19.5 Preconditions

- current MCP project-loading rules pass;
- exactly one recognized source matches `pou_name` for update resolution;
- target language is ST;
- target is an existing regular non-symlink file inside project root;
- replacement is non-empty UTF-8 text;
- expected hash is well formed and matches current exact bytes;
- declaration type/name match target identity;
- Function has a return type;
- matching terminal keyword exists.

### 19.6 Invariants

Must stay unchanged:

```text
POU name
POU type
language
canonical path
```

May change:

```text
documentation
Function return type
POU-local/interface declarations
body logic
comments
formatting
```

### 19.7 Side effects

Exactly one intended persistent side effect: replace the existing target `.st` POU file (or do nothing physically when replacement bytes are identical).

No automatic compile, project-wide save, backup/history, creation, deletion, rename, or unrelated file write.

### 19.8 Error conditions

- normal project/path errors;
- POU not found;
- ambiguous matching POU source;
- unsupported target language;
- invalid target filesystem state;
- malformed/stale expected hash;
- empty/UTF-8-invalid replacement;
- replacement name/type mismatch;
- missing Function return type;
- missing matching terminal keyword;
- temp write/fsync/atomic-replace failure.

Compiler diagnostics are not `update_pou()` errors.

### 19.9 `read_pou()` change

Same future PR, not a prerequisite PR:

```text
raw = target.read_bytes()
content = raw.decode("utf-8")
content_hash = "sha256:" + sha256(raw).hexdigest()
```

### 19.10 Future implementation PR scope

**Recommended:** one complete vertical PR; no prerequisite PR is technically required at the inspected revisions.

That future PR should contain only what is needed to make the feature complete:

- `openplc/pous.py`: safe resolver, exact-byte hash/read change, ST outer-envelope check, atomic one-file write, `UpdatePouResult`, `update_pou()`;
- `server.py`: one local-write MCP registration;
- tests: domain + MCP contract + failure integrity + concurrency + supported/unsupported language matrix;
- documentation: tool contract, ST-only write scope, concurrency token, explicit compile lifecycle, Open Editor simultaneous-edit limitation;
- no new dependency unless the implementation unexpectedly proves standard-library primitives insufficient;
- no generic mutation framework;
- no unrelated tool changes.

The additive `read_pou()` hash belongs in the same PR because it exists specifically to make this write lifecycle safe.

## 20. Recommended Write Algorithm

High-level pseudocode only:

```text
function update_pou(project_path, pou_name, content, expected_content_hash):
    validate pou_name/content/hash-token shape

    root = load project using existing current-format helper

    matches = scan recognized current-format POU sources whose stem == pou_name
    if matches == 0:
        fail not found
    if matches > 1:
        fail ambiguous; do not use current first-wins read/list behavior
    target_info = matches[0]

    if target_info.language != ST:
        fail unsupported language

    lexical_target = root / target_info.relative_path
    if lexical_target is a symlink:
        fail

    resolved_target = lexical_target.resolve(strict=True)
    verify resolved_target is contained in resolved root
    verify resolved_target is a regular file

    current_bytes = read resolved_target bytes
    current_hash = sha256 token(current_bytes)
    if current_hash != expected_content_hash:
        fail stale update

    validate replacement outer ST envelope only:
        expected declaration keyword from target POU type
        declaration name exactly equals target stem
        Function has return type when applicable
        matching END_* exists after declaration

    replacement_bytes = UTF-8 encode(content)
    new_hash = sha256 token(replacement_bytes)

    if new_hash == current_hash:
        return {name: pou_name, content_hash: new_hash}

    create temporary file in lexical_target.parent
    try:
        write all replacement_bytes
        flush
        fsync temporary file
        preserve original normal file mode where appropriate

        re-check lexical target is not symlink
        resolve/check containment + regular-file state again
        latest_bytes = read target again
        if sha256 token(latest_bytes) != expected_content_hash:
            fail stale update; original target remains untouched

        os.replace(temp, lexical_target)
    except:
        best-effort delete temp
        translate operation failure to concise ToolError

    return {name: pou_name, content_hash: new_hash}
```

Do not call the compiler from this algorithm.

## 21. Non-Goals

The future feature must not attempt to:

- create/delete/rename POUs;
- change POU type;
- convert languages;
- write IL, LD, FBD, Python, or C++ in v1;
- create separate POU-local variable CRUD paths;
- mutate resource globals;
- rewrite Program Instances;
- refactor project references after rename;
- parse complete IEC 61131-3/ST grammar;
- build an ST AST;
- reproduce OpenPLC serializers or graphical flow state;
- reproduce OpenPLC fallback/recovery behavior;
- support/migrate historical JSON POU projects;
- expose arbitrary paths or a generic filesystem write tool;
- create backups/history;
- compile automatically;
- synchronize with a live OpenPLC Editor editing session;
- provide multi-file transactions;
- guarantee distributed/network-filesystem transaction semantics.

## 22. Open Questions

The central v1 design has no architectural blocker at the inspected revisions. Remaining questions are bounded:

### 22.1 Network-mounted projects

**Open question.** If NFS/SMB/cloud-mounted workspaces become a supported target, revalidate `os.replace()`/durability semantics for those filesystems. Do not add distributed transaction complexity now.

### 22.2 Coordinated Editor sessions

**Open question.** A future supported OpenPLC external mutation/reload/lock API could change the recommended synchronization boundary. No such stable contract was found for conflict-safe full-POU co-editing in the inspected implementation.

### 22.3 IL write support

**Open question.** IL is textually closer to ST than graphical/hybrid languages, but no current experimental requirement justifies expanding v1. Evaluate it only when a concrete need exists.

### 22.4 Graphical write support

**Open question.** LD/FBD need a separate investigation if requested. Recent history demonstrates that syntactically valid JSON alone is not sufficient to establish a safe diagram state.

### 22.5 Future upstream changes

**Open question.** Before implementation, compare this pinned OpenPLC revision with then-current `development`. If persistence/save/watch semantics changed, update the investigation rather than silently relying on 2026-08-30 behavior.

## 23. Evidence / Source References

### MCP repository

**[M1] Architecture/scope**  
`industrix-com-br/openplc-engineering-mcp` @ `9936fa2455e85f6856a7b9dc9c92a7a72200c508`  
`AGENTS.md`  
<https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/AGENTS.md>

**[M2] POU discovery/read**  
`src/openplc_engineering_mcp/openplc/pous.py` — `_is_contained`, `_list_pous`, `list_pous`, `read_pou`, `PouInfo`, `PouContent`; importantly, current name deduplication is first-discovered-wins.  
<https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/src/openplc_engineering_mcp/openplc/pous.py>

**[M3] Project loading/current-format boundary**  
`src/openplc_engineering_mcp/openplc/project.py`  
<https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/src/openplc_engineering_mcp/openplc/project.py>

**[M4] POU variable inspection**  
`src/openplc_engineering_mcp/openplc/variables.py`  
<https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/src/openplc_engineering_mcp/openplc/variables.py>

**[M5] Compiler/diagnostics separation**  
`src/openplc_engineering_mcp/openplc/compiler.py`  
<https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/src/openplc_engineering_mcp/openplc/compiler.py>

**[M6] MCP registrations/annotations**  
`src/openplc_engineering_mcp/server.py`  
<https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/src/openplc_engineering_mcp/server.py>

**[M7] POU/server tests**  
<https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/tests/test_pous.py>  
<https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/tests/test_server.py>

**[M8] Scope/research/project-format documentation**  
<https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/docs/research.md>  
<https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/docs/scope.md>  
<https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/docs/openplc-projects.md>

**[M9] Program Instance → Program reference**  
`src/openplc_engineering_mcp/openplc/execution.py`  
<https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/src/openplc_engineering_mcp/openplc/execution.py>

### OpenPLC Editor current implementation

**[O1] POU folder/extension/declaration mapping**  
`Autonomy-Logic/openplc-editor` @ `3652363583de7e88f64c77ba3fac204e4ee7e4ed`  
`src/frontend/utils/PLC/pou-file-extensions.ts`  
<https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/frontend/utils/PLC/pou-file-extensions.ts>

**[O2] Language-specific POU parsers**  
`src/frontend/utils/PLC/pou-text-parser.ts` — `parseTextualPouFromString`, `parseHybridPouFromString`, `parseGraphicalPouFromString`.  
<https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/frontend/utils/PLC/pou-text-parser.ts>

**[O3] Raw project parse/recovery path**  
`src/backend/shared/utils/parse-project-files.ts` — `parseProjectFiles`, `parsePouFile`, fallback behavior, `UnrecoverablePouError`.  
<https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/backend/shared/utils/parse-project-files.ts>

**[O4] POU serializer**  
`src/frontend/utils/PLC/pou-text-serializer.ts`  
<https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/frontend/utils/PLC/pou-text-serializer.ts>

**[O5] Save path / `project.json` / per-file serialization / raw fallback**  
`src/frontend/services/save-actions.ts`  
<https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/frontend/services/save-actions.ts>

**[O6] Project persistence port**  
`src/middleware/shared/ports/project-port.ts` — raw project files, `rawLoadedFiles`, pre-serialized `WriteProjectFiles`, file-watcher contract.  
<https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/middleware/shared/ports/project-port.ts>

**[O7] Desktop adapter**  
`src/middleware/adapters/editor/project-adapter.ts`  
<https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/middleware/adapters/editor/project-adapter.ts>

**[O8] Desktop raw filesystem persistence**  
`src/backend/editor/services/project-service/index.ts` — project/file writes.  
<https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/backend/editor/services/project-service/index.ts>

**[O9] Explicit POU create/rename service**  
`src/backend/editor/services/pou-service/index.ts`  
<https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/backend/editor/services/pou-service/index.ts>

**[O10] External change watcher/reload**  
`src/frontend/components/_features/[workspace]/editor/monaco/index.tsx`  
<https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/frontend/components/_features/%5Bworkspace%5D/editor/monaco/index.tsx>

**[O11] Byte-stable raw-content selection**  
`src/frontend/utils/version-control-content.ts` — `pickContentForSave`.  
<https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/frontend/utils/version-control-content.ts>

### OpenPLC history revealing write invariants

**[O12] Native current POU files**  
PR #411 — “New project format”, merge `2389075e7d4ce0505600852e690deff02f657419`.  
<https://github.com/Autonomy-Logic/openplc-editor/pull/411>

**[O13] DOPE-495 — stale graphical write-back protection**  
Core fix `3da85070966c5a7803313483ec1f61cbb9d426e3`. A failed graphical write-back could otherwise serialize stale state; save is aborted instead of overwriting disk.  
<https://github.com/Autonomy-Logic/openplc-editor/commit/3da85070966c5a7803313483ec1f61cbb9d426e3>

**[O14] DOPE-592 — unrecoverable graphical body protection**  
PR #1055, merged as `acaaf7dcf55b0490394bccf04105fab64c319c8d`; commit `ac52930777b8386a21273a6a462248b97be6a261` is a review-follow-up commit within that PR. An unreadable graphical POU must not become a savable blank canvas.  
<https://github.com/Autonomy-Logic/openplc-editor/pull/1055>  
<https://github.com/Autonomy-Logic/openplc-editor/commit/ac52930777b8386a21273a6a462248b97be6a261>

**[O15] Phantom-diff/raw graphical preservation**  
Commit `ec9ef062f5bd99842fda4aac91badc1f1f236049`.  
<https://github.com/Autonomy-Logic/openplc-editor/commit/ec9ef062f5bd99842fda4aac91badc1f1f236049>

**[O16] Rename propagation/invariants**  
Commit `65be936a6123c0cbcd6df688db62293ae3c688b3` — Program-instance rename propagation and LD/FBD flow/body-name consistency.  
<https://github.com/Autonomy-Logic/openplc-editor/commit/65be936a6123c0cbcd6df688db62293ae3c688b3>

**[O17] Save-queue concurrency/interruption history**  
Commit `a6999a8c7c95b5b6eab1eed5226fbb6865ca4b75` — makes the save queue per-file. The commit's own message notes the save-queue half is mirrored rather than exercised in this codebase; cited as upstream design history only.  
<https://github.com/Autonomy-Logic/openplc-editor/commit/a6999a8c7c95b5b6eab1eed5226fbb6865ca4b75>

### External design references — inspiration only

**[X1] CODESYS Development System MCP Server**  
Official release page; public capabilities include reading project contents, creating/modifying POUs using Structured Text, compilation, and compiler errors.  
<https://www.codesys.com/ecosystem/release-lifecycle/releases-updates/development-system-mcp-server/>

**[X2] SemaPLC**  
Yanlun Tu et al., “SemaPLC: A Project-Grounded, Verification-Gated Agent Harness for PLC Code Generation”, 2026.  
Repository inspected at `midea-ai/SemaPLC` main `1c41c1bcb69bb43c51d7d0faed30a2b1930d67fe`.  
<https://github.com/midea-ai/SemaPLC/tree/1c41c1bcb69bb43c51d7d0faed30a2b1930d67fe>  
<https://arxiv.org/abs/2608.18565>

**[X3] SWE-agent source editing**  
Generic path/text editing as contrast to the intended PLC-domain boundary.  
<https://swe-agent.com/latest/config/tools/>

---

### Final recommendation

Implement `update_pou()` as a **Structured-Text-only, complete-content replacement of exactly one existing named POU, guarded by immutable POU identity, exact-byte optimistic concurrency, strict project/filesystem containment, and atomic one-file replacement, with compilation and diagnostics remaining explicit separate MCP operations**.
