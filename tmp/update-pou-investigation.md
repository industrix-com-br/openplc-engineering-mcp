# update_pou() Investigation

## 1. Executive Summary

This investigation evaluates the smallest safe mutation boundary for an eventual `update_pou()` MCP tool. It is based on the current `openplc-engineering-mcp` implementation and the current OpenPLC Editor `development` branch, both pinned to exact revisions in Section 2.

### Recommended direction

**Recommended.** The first version of `update_pou()` should:

- update an **existing POU by domain identity**, never by an arbitrary path;
- support **Structured Text (`.st`) only**;
- accept the **complete persisted POU file content**, not only the body and not a structured POU object;
- allow edits to documentation, function return type, POU-local declarations, and body logic;
- keep POU **name, POU type, and language immutable**;
- require an **optimistic-concurrency content hash** obtained from `read_pou()`;
- perform only lightweight envelope/identity checks before writing;
- leave IEC 61131-3 semantic validation to `compile_project()` and compiler diagnostics;
- write using a same-directory temporary file followed by atomic replacement;
- create no hidden backups;
- not compile automatically;
- explicitly treat simultaneous editing of the same project in OpenPLC Editor as unsupported in v1.

Recommended contract:

```python
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

`read_pou()` should gain one additive field:

```text
content_hash: "sha256:<hex>"
```

The hash should be calculated over the exact bytes read from the persisted POU file. The same token is then required by `update_pou()`. This creates a coherent lifecycle:

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
correct and repeat
```

### Central architectural conclusion

**Observed.** In the current OpenPLC Editor format, a POU is persisted as its own language-specific file under `pous/<pou-type>/`. `project.json` deliberately persists `pous: []`; it does not duplicate POU source. The Editor's single-file save path for an existing POU serializes that POU and writes only its POU file. [O1] [O5]

**Inferred.** Therefore an existing current-format POU can be changed independently by replacing only that POU file **provided that its identity does not change**. A rename, POU type change, or language change is a different domain operation because it changes the canonical path and may require reference updates.

**Observed.** OpenPLC Editor has recently fixed multiple data-loss paths involving graphical POU serialization and recovery. DOPE-495 prevented invalid graphical in-memory state from being reported as saved; DOPE-592 made unrecoverable graphical bodies fatal instead of replacing them with an apparently empty canvas. [O13] [O14]

**Recommended.** LD/FBD writes should therefore remain out of v1. Read support and write support do not need to have identical language scope.

### Answers to the quality-gate questions

| Question | Investigation conclusion |
| --- | --- |
| What is a current-format POU on disk? | A language-specific file under `pous/programs`, `pous/function-blocks`, or `pous/functions`. |
| How is it parsed? | Raw UTF-8 file → frontend project parser → language-specific POU parser → in-memory POU. |
| How is it saved? | In-memory POU → canonical serializer → single-file or project save → pre-serialized string → filesystem/platform writer. |
| Which artifact is authoritative? | The POU file for POU source/interface/documentation; `project.json` does not persist POU source. |
| Can one POU be changed independently? | Yes, if name/type/language remain unchanged and only the existing canonical POU file is replaced. |
| What should `update_pou()` update? | The complete existing ST POU representation. |
| Writable languages in v1? | ST only. |
| Can variables change through it? | Yes, POU-local/interface declarations are part of the complete POU representation. |
| Immutable properties? | Name, type, language/canonical file path. |
| MCP validation? | Project/target/path/hash + lightweight ST envelope and identity checks. |
| Compiler validation? | IEC syntax/semantics, types, calls, references, control logic. |
| Safe disk write? | Same-directory temp file + flush/fsync + final hash re-check + `os.replace`. |
| Partial-write prevention? | Never truncate the target directly; replacement happens only after the temporary file is complete. |
| Concurrency? | Required SHA-256 optimistic concurrency token. |
| Open Editor at same time? | Not a supported v1 workflow; watcher behavior is insufficient for conflict-safe full-POU updates. |
| Automatic compile? | No. |
| `read_pou()` change? | Add exact-byte `content_hash`; preferably read bytes once and decode UTF-8 from the same byte sequence. |
| Which failures leave disk unchanged? | All validation/hash/temp-write failures and failed atomic replacement. |
| Future tests? | Section 17 defines the matrix, including failure-integrity and stale-hash tests. |
| Minimal API? | Complete ST replacement + required expected hash, returning name + new hash. |

---

## 2. Repositories and Revisions Inspected

The analysis is intentionally pinned because both repositories are under active development.

| Repository | Branch | Revision inspected | Role |
| --- | --- | --- | --- |
| `industrix-com-br/openplc-engineering-mcp` | `main` | `9936fa2455e85f6856a7b9dc9c92a7a72200c508` | MCP architecture and current contracts |
| `Autonomy-Logic/openplc-editor` | `development` | `3652363583de7e88f64c77ba3fac204e4ee7e4ed` | Authoritative current OpenPLC Editor behavior |

Inspection date: **2026-08-30**.

The MCP revision is the merge of PR #22 (`feat: add I/O configuration inspection`). The OpenPLC Editor revision is the merge of PR #1060.

### Current-format boundary

**Observed.** OpenPLC Editor PR #411, merged as commit `2389075e7d4ce0505600852e690deff02f657419`, introduced the native text-based POU persistence model: `.st`, `.il`, `.ld`, `.fbd`, `.py`, and `.cpp`, while upstream retained legacy JSON reading for backward compatibility. [O12]

**Observed.** The MCP explicitly scopes itself to the current native-text OpenPLC Editor project representation and intentionally does not support historical JSON POU projects, migrations, format detection, or fallback behavior. [M1] [M8]

**Recommended.** The upstream legacy JSON parser branches are relevant only as historical evidence. They must not be copied into `update_pou()`.

---

## 3. Current MCP Architecture

### 3.1 Project loading and validation

**Observed.** `openplc/project.py` owns project loading/structural preconditions. It resolves the project directory, requires a `project.json`, parses it as JSON, validates the top-level project metadata used by the MCP, and provides helpers for current-format configuration access. [M3]

The important current behavior is intentionally shallow:

- project path must be non-empty;
- project directory must exist;
- `project.json` must exist and be parseable;
- supported project metadata must be present;
- the current singular `data.configuration.resource` structure is authoritative for execution/resource inspection;
- historical alternatives are not normalized into the current structure.

**Recommended.** `update_pou()` should reuse this current project boundary. It should not introduce a second, stronger whole-project validator or version detector merely because it is a write operation.

### 3.2 POU discovery and `read_pou()`

**Observed.** `openplc/pous.py` defines the POU domain surface. Current POU types are:

```text
program
function-block
function
```

Current directories are:

```text
pous/programs
pous/function-blocks
pous/functions
```

Recognized current native extensions are:

```text
.st .il .ld .fbd .py .cpp
```

`list_pous()` derives:

- POU name from the file stem;
- POU type from the directory;
- language from the extension;
- path relative to the project root.

It rejects ambiguous duplicate POU names rather than silently selecting one. [M2]

`read_pou(project_path, pou_name)`:

1. loads the project through the current project helper;
2. resolves the POU through the domain list;
3. re-checks path containment;
4. reads UTF-8 text;
5. returns `name`, `type`, `language`, `path`, and raw textual `content`.

It deliberately does **not** parse, normalize, or serialize POU source. [M2] [M7]

### 3.3 Path containment

**Observed.** `_is_contained(root, path)` resolves the candidate and requires it to remain under the resolved root. Existing tests prove that a symlink escaping the project is not exposed by POU discovery/read. [M2] [M7]

**Recommended.** A write path should reuse the same containment concept but be slightly stricter at the final target: the canonical target should be an existing regular file and should not itself be a symlink. See Section 11 and Section 16.

### 3.4 Variables

**Observed.** `list_variables()` calls `read_pou()` and performs narrow textual extraction of declaration blocks. This is a read convenience, not a complete Structured Text parser. [M4]

**Recommended.** Do not generalize the current variable extraction code into a mutation parser. `update_pou()` does not need a structured variable model if the complete ST POU is the mutation unit.

### 3.5 Compilation and diagnostics

**Observed.** `compile_project()` is separate from inspection. It invokes the OpenPLC CLI and records diagnostics for `get_diagnostics()`. Compiler state is process-local to the MCP process. [M5]

**Recommended.** `update_pou()` should preserve this separation. A successful file mutation and a successful PLC compilation are different observable facts.

### 3.6 Error and MCP registration conventions

**Observed.** Domain failures use `ToolError`; the server returns structured domain results and registers tools with explicit annotations. Existing project inspection tools are read-only, while compilation is a local-write operation. [M6] [M7]

**Recommended.** `update_pou()` should be registered as a **local-write** tool with `open_world_hint=False`, and should use concise `ToolError` failures instead of adding an exception hierarchy.

### 3.7 Existing writes

**Observed.** No current MCP domain tool modifies a POU. `compile_project()` may produce OpenPLC build artifacts through the CLI, but there is no generic file writer and no project-edit framework. [M5] [M8]

**Recommended.** Keep it that way. `update_pou()` should be the first narrowly scoped POU write, not the start of a general mutation framework.

### 3.8 Helpers that can legitimately be reused

Reuse:

- project loading/current-format preconditions from `project.py`;
- current POU directories/extensions/types from `pous.py`;
- POU-by-name resolution semantics;
- `_is_contained()` or an equivalently narrow containment check;
- `ToolError` conventions;
- server local-write annotations.

A small private `_resolve_pou(...)` helper inside `pous.py` could be justified if it removes duplication between `read_pou()` and `update_pou()`.

Do **not** generalize solely for this feature:

- `variables.py` into an ST parser;
- filesystem writes into a repository/service abstraction;
- POU discovery into a generic project object store;
- hashing into a project-wide versioning subsystem;
- atomic replacement into a generic transaction framework.

---

## 4. Current OpenPLC POU Persistence Model

### 4.1 Canonical directory and file model

**Observed.** OpenPLC Editor maps POU type and language directly to folder and extension. [O1]

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

Language extensions:

| Language | Extension |
| --- | --- |
| Structured Text | `.st` |
| Instruction List | `.il` |
| Ladder Diagram | `.ld` |
| Function Block Diagram | `.fbd` |
| Python | `.py` |
| C++ | `.cpp` |

POU type folders:

| POU type | Folder | Declaration keyword | Terminal keyword |
| --- | --- | --- | --- |
| Program | `pous/programs` | `PROGRAM` | `END_PROGRAM` |
| Function Block | `pous/function-blocks` | `FUNCTION_BLOCK` | `END_FUNCTION_BLOCK` |
| Function | `pous/functions` | `FUNCTION` | `END_FUNCTION` |

### 4.2 What defines POU identity?

Four pieces of state interact:

1. **Directory** determines the expected POU type when OpenPLC parses a file.
2. **Extension** determines the language parser.
3. **Filename stem** is the canonical path name used by OpenPLC save operations and by the MCP's POU discovery.
4. **Declaration inside the file** contains a POU type keyword and POU name, and for Functions a return type. [O1] [O2] [O3] [O5]

**Observed.** The current OpenPLC frontend parser receives the POU type from the path, then expects the matching declaration keyword and parses the declaration's name. It does not generally enforce that the declaration name equals the filename stem. [O2] [O3]

**Inferred.** A mismatch can therefore create an ambiguous/inconsistent persisted state: the path says one domain identity while parsed content may carry another. A write API should not create such a state.

### 4.3 `project.json` and POU source

**Observed.** The current save path intentionally writes:

```json
"pous": []
```

inside `project.json`. POU source is persisted in independent files instead. `buildPouSpec()` builds each canonical path from POU type, POU name, and language extension. [O5]

**Observed.** Program instances remain in the project configuration and reference a Program by name (`configuration.resource.instances[].program`). The MCP already exposes that relationship through `get_execution_configuration()`. [M9]

**Inferred.** Changing a Program's body, declarations, or documentation does not require rewriting the Program Instance entry. Renaming the Program is different: existing name references could become stale, so rename is outside `update_pou()`.

### 4.4 Is the POU file authoritative?

**Observed.** For POU source/interface/documentation, yes. The current OpenPLC project reader discovers POU files from the POU directories, reads their raw text, and parses them. The current full-project save serializes each POU independently. [O3] [O5] [O8]

**Answer.** For an **existing POU with unchanged name, type, and language**, replacing only its persisted POU file is consistent with the current OpenPLC save model. There is no observed second POU-content index that must be synchronized.

This answer does **not** apply to:

- rename;
- Program ↔ Function Block ↔ Function conversion;
- ST ↔ another language conversion;
- create/delete operations;
- resource-global changes stored in `project.json`;
- legacy JSON POU projects.

---

## 5. OpenPLC POU Read Path

### 5.1 Current flow

The current desktop flow is conceptually:

```text
POU file on disk
    ↓
ProjectService.readRawProjectFiles()
    ↓ raw UTF-8 POU files
Editor ProjectPort adapter
    ↓
parseProjectFiles()
    ↓
parseTextualPouFromString()       ST / IL
parseHybridPouFromString()        Python / C++
parseGraphicalPouFromString()     LD / FBD
    ↓
PLCPou in project store
    ↓
Monaco or graphical editor
```

**Observed.** `parse-project-files.ts` explicitly states that project files are read raw and that parsing is centralized on the frontend. [O3]

### 5.2 Textual ST/IL parsing

**Observed.** `parseTextualPouFromString()`:

- optionally extracts one leading `(* ... *)` documentation block;
- expects a declaration matching the POU type passed from the path;
- extracts the POU name;
- requires a return type for Functions;
- locates supported `VAR...END_VAR` sections;
- parses variables through OpenPLC's variable parser;
- requires the matching `END_PROGRAM`, `END_FUNCTION_BLOCK`, or `END_FUNCTION` token;
- returns the body as trimmed text between declarations and the terminal keyword. [O2]

This parser is useful as evidence of the file envelope but should **not** be ported into the MCP.

### 5.3 Hybrid Python/C++ parsing

**Observed.** Python and C++ POUs still use an IEC-style outer envelope for declaration and variables. Their body is preserved as foreign-language text between the declaration region and the POU terminal keyword. [O2]

### 5.4 Graphical LD/FBD parsing

**Observed.** LD/FBD use the same outer IEC declaration/variable envelope, but the body is JSON. The current parser requires:

- valid JSON;
- LD: an object with a `rungs` array;
- FBD: an object with a `rung` object containing a `nodes` array. [O2]

### 5.5 Recoverable versus unrecoverable failures

**Observed.** OpenPLC distinguishes two important cases when normal POU parsing fails. [O3]

**Recoverable declarations.** For malformed textual declarations/variables, OpenPLC can preserve raw declaration text in a fallback representation so the user can repair it.

**Unrecoverable graphical body.** If a graphical body cannot be parsed or has an invalid shape, OpenPLC now treats it as fatal rather than fabricating a blank diagram. This was specifically introduced to prevent a later save from overwriting the user's real graphical content. [O14]

**Why this matters.** `update_pou()` must not reproduce OpenPLC's recovery model. The MCP only needs enough understanding to keep the requested mutation inside the correct POU identity. Full language validation remains OpenPLC's responsibility.

### 5.6 Legacy parser paths

**Observed.** Upstream still contains legacy `.json` POU fallback/deduplication logic for backward compatibility. [O3]

**Recommended.** Ignore it. The MCP's current-format-only scope is stricter than upstream's compatibility surface.

---

## 6. OpenPLC POU Write Path

### 6.1 Current flow

The current Editor save flow is conceptually:

```text
Editor/store POU state
    ↓
sanitize / graphical write-back checks
    ↓
serializePouToText()
    ↓
serializeProjectFile() / buildPouSpec()
    ↓
ProjectPort.saveFile()            single-file save
or ProjectPort.saveProject()      full-project save
    ↓
platform adapter / IPC or web transport
    ↓
filesystem or remote project storage
```

**Observed.** `save-actions.ts` centralizes path/content production and states that the frontend performs serialization before the platform layer receives content. [O5]

### 6.2 Single-file POU save

**Observed.** For a POU, `executeSaveFile()`:

1. finds the in-memory POU by name;
2. computes its folder from POU type;
3. computes its extension from body language;
4. serializes the POU;
5. calls `projectPort.saveFile(<project>/pous/<folder>/<name><ext>, content)`;
6. updates editor dirty/snapshot state. [O5]

It does **not** rewrite `project.json` merely because the POU content changed.

### 6.3 Full-project save

**Observed.** Full save emits independent `RawProjectFile` records for POUs and separate content for `project.json`, device files, servers, remote devices, etc. The platform port receives pre-serialized strings. [O5] [O6]

**Observed.** The ProjectPort contract explicitly characterizes the persistence backend as a writer of already-serialized file content rather than the owner of POU serialization semantics. [O6]

### 6.4 Desktop versus web

**Observed.** The desktop adapter writes local project files through the Electron/project-service path; the web implementation routes the same serialized project concepts through its web transport. The serialization boundary remains above the platform writer. [O7] [O8]

**Implication for this MCP.** `openplc-engineering-mcp` is a local engineering integration and should write the local persisted POU directly. It does not need to reproduce the Editor's frontend/store/IPC layers.

### 6.5 Can an existing POU be safely changed by replacing only its file?

**Answer: yes, under explicit constraints.**

Required constraints:

- target already exists as a current native POU file;
- target is resolved by POU domain name, not caller-supplied path;
- POU type is unchanged;
- filename/name identity is unchanged;
- language/extension is unchanged;
- only the target file is replaced;
- stale concurrent content is rejected;
- replacement satisfies the minimal persisted envelope for that type;
- compiler validation remains a later operation.

No additional POU metadata artifact was observed that must be updated for such an in-place change.

---

## 7. Language-Specific Representation

### 7.1 Comparison

| Language | Persisted representation | Parse/serialize characteristics | Mutation risk | v1 recommendation |
| --- | --- | --- | --- | --- |
| ST | IEC outer declaration + variable blocks + textual body + terminal keyword | Serializer normalizes documentation/declarations/variables/spacing | Moderate; complete replacement avoids reserialization | **Writable** |
| IL | Same outer representation, textual IL body | Similar to ST | Moderate, but no current experimental need | Read-only in v1 |
| LD | IEC outer declaration + variables + JSON graphical body | JSON parsed, shape-validated, serialized canonically; separate graphical flow state | **High**; recent data-loss fixes | Read-only in v1 |
| FBD | IEC outer declaration + variables + JSON graphical body | Same class of graphical state/serialization concerns | **High** | Read-only in v1 |
| Python | IEC outer declaration + variables + Python textual body | Hybrid parser/foreign-language tooling | Moderate; different compiler/tooling semantics | Read-only in v1 |
| C++ | IEC outer declaration + variables + C++ textual body | Hybrid parser + native block build semantics | Moderate/high; different compiler/tooling semantics | Read-only in v1 |

### 7.2 Why ST-only is a defensible v1 scope

**Observed.** The MCP research context centers the comparison on explicit domain operations while keeping implementation behavior attributable to the integration boundary. [M8]

**Observed.** The thesis/experimental scope is primarily Structured Text for the first implementation and includes source modification, debugging, and compile/diagnose/correct loops.

**Inferred.** ST-only write support still enables the main experimental mutation tasks while avoiding the most format-sensitive graphical paths and the extra foreign-language toolchains.

**Recommended.** v1 writable language: **ST only**, across existing Program, Function Block, and Function POUs.

This is a write-scope decision, not a claim that other languages are unsupported by OpenPLC or by MCP inspection.

### 7.3 Raw-content preservation and parse→serialize drift

OpenPLC's serializer does not guarantee byte-preserving round trips:

- documentation is normalized;
- declarations are regenerated;
- parsed variables are regenerated unless preserved as raw variable text;
- body extraction trims text;
- graphical JSON is pretty-printed;
- graphical editor state has additional canonicalization concerns. [O4]

**Observed.** Current OpenPLC version-control save logic explicitly keeps both a canonical serialized snapshot and raw loaded content. If serialized state has not effectively changed, `pickContentForSave()` emits the original raw content to keep the file byte-identical and avoid parse/serialize drift. [O5] [O11]

This is strong evidence that an MCP should avoid parse→serialize work unless it owns a real domain requirement for it.

### 7.4 Strategy comparison

#### Strategy A — parse POU → mutate object → serialize whole POU

Rejected for v1.

It would require the MCP to reproduce enough of OpenPLC's parser, variable model, serializers, comments/formatting behavior, and future language changes to avoid drift. For LD/FBD it would also enter graphical-state territory that OpenPLC has recently hardened against data loss.

#### Strategy B — caller provides complete replacement representation → replace only target POU file

Recommended.

The caller owns the target file's complete new representation. The MCP owns:

- domain resolution;
- identity invariants;
- concurrency protection;
- safe persistence.

It does **not** need to reconstruct unrelated content.

#### Alternative — body-only textual splice

Not recommended. It looks smaller at the API surface but moves complexity into the implementation. The MCP must correctly locate declaration/body boundaries while preserving every comment and declaration construct. This is effectively a partial ST rewriting parser and prevents declaration changes that are central to realistic PLC edits.

---

## 8. Identity and Project Invariants

### 8.1 Immutable identity

**Recommended.** `update_pou()` must not change:

| Property | Mutable? | Reason |
| --- | --- | --- |
| POU name | **No** | Name participates in canonical filename and references. Rename is a separate cross-reference operation. |
| POU type | **No** | Type determines canonical folder and declaration keyword. Changing it is a move/conversion. |
| Programming language | **No** | Language determines extension/parser/body representation. Changing it is a file conversion. |
| Canonical POU path | **No** | Derived from existing domain identity; never caller-controlled. |

For a target `pou_name="MAIN"` discovered as:

```text
pous/programs/MAIN.st
```

the replacement must declare:

```iecst
PROGRAM MAIN
```

and must not declare:

```iecst
PROGRAM DIFFERENT_NAME
```

or:

```iecst
FUNCTION_BLOCK MAIN
```

### 8.2 Mutable POU content

The complete ST replacement should allow changes to:

- leading documentation;
- Function return type;
- `VAR` declarations;
- `VAR_INPUT`;
- `VAR_OUTPUT`;
- `VAR_IN_OUT`;
- other POU-local declaration sections accepted by OpenPLC;
- body logic;
- comments/formatting, because complete replacement means the caller supplies the intended file representation.

### 8.3 Function return type

**Observed.** A Function return type is carried in its declaration, not in its file path. OpenPLC requires one during normal textual parsing. [O2]

**Recommended.** Require a replacement Function to have a return type, but do not require it to equal the old return type. It is legitimate POU interface content. Any broken caller compatibility belongs to compiler validation.

### 8.4 Local variable modification

**Recommended.** POU-local variable creation/update/deletion should naturally occur through the complete POU replacement. Do not introduce `create_variable()`, `update_variable()`, or `delete_variable()` merely to edit the same declaration blocks through a second write path.

Two mutation surfaces for the same declarations would create:

- duplicate semantics;
- ordering/formatting questions;
- potential lost updates;
- additional concurrency interactions;
- unnecessary MCP schema surface.

Resource-level global variables are different: they live in project configuration and are not part of the POU file. `update_pou()` must not mutate them.

### 8.5 References

**Observed.** Program Instances reference a Program by name in project configuration. POU-to-POU calls/references also depend on names and interfaces at compile time. [M9]

**Recommended.** Keeping name/type/language immutable keeps `update_pou()` local. Interface changes are allowed but may produce compiler errors; this is expected and recoverable through the compile/diagnostic loop.

---

## 9. Candidate update_pou() Contracts

### 9.1 Decision matrix

| Contract | Domain abstraction | Implementation complexity | Formatting/comments | OpenPLC coupling | Validation burden | Agent usefulness | Main failure mode | Decision |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| **A. Full POU replacement** `update_pou(project, name, content, hash)` | High: update an existing named POU | **Low** | Caller controls complete target; unrelated files untouched | Low | Identity/envelope + compiler later | **High**: body + declarations + docs | Bad replacement content; controlled by hash + envelope + compile | **Recommended** |
| **B. Body-only replacement** | High superficially | Medium/high | Existing declaration formatting can be preserved only with correct splice logic | Medium | Must parse/locate body boundaries | Medium: cannot naturally change interface | Parser/splice mistakes | Reject v1 |
| **C. Structured mutation** variables/body/docs | Very high domain semantics | **Very high** | Parse→serialize drift likely | **High**: duplicates OpenPLC model | High | High | MCP becomes second Editor implementation | Reject |
| **D. Patch/diff mutation** | Low/medium; source-text operation | Medium | Can preserve untouched bytes | Low OpenPLC coupling, but high text-edit semantics | Patch applicability/conflicts | High for coding agents | Ambiguous/failed patch; exposes generic edit model | Reject |
| **E. Arbitrary file write** | **Low** | Low | Caller controlled | Low | Almost none | High but unsafe | Escapes PLC domain boundary | Reject |

### 9.2 Option A — complete replacement

Conceptual contract:

```python
update_pou(project_path, pou_name, content, expected_content_hash)
```

This remains domain-specific because the caller never selects a filesystem path. The MCP resolves the authoritative target from the existing POU identity and refuses identity changes.

### 9.3 Option B — body-only

A body-only API would have to merge a body into an existing file. The apparently convenient schema:

```python
update_pou(project_path, pou_name, body)
```

hides substantial implementation ownership:

- locate all declaration blocks safely;
- preserve comments and whitespace;
- recognize the correct terminal keyword;
- handle body constructs that resemble declaration delimiters;
- decide what to do with variable changes;
- eventually branch by language.

It is less capable for the experiments and more parser-heavy internally.

### 9.4 Option C — structured mutation

A structured POU object would force the MCP to maintain a parallel representation of:

- variables;
- type definitions;
- body language/value;
- documentation;
- function return types;
- serialization rules.

That is directly contrary to the project's `less is more` architecture.

### 9.5 Option D — patch/diff

General coding agents such as SWE-agent expose source editors based on exact string replacement, insert operations, or patches. That design is useful for generic codebases, but its abstraction is fundamentally “edit this file/text range,” not “update this POU.” [X3]

A patch API would make the MCP baseline more similar to direct filesystem editing and weaken the experimental distinction the repository explicitly wants to preserve. [M8]

### 9.6 External domain inspiration

These are **design references, not OpenPLC evidence**:

- CODESYS's official Development System MCP Server explicitly advertises reading project contents, creating/modifying POUs using Structured Text, and compiling/retrieving compiler errors. This supports the general separation between domain-level POU mutation and compiler feedback, but does not define OpenPLC persistence semantics. [X1]
- SemaPLC emphasizes project-grounded generation plus externally verified compilation/runtime gates. Its relevance here is the validation workflow, not the exact edit API. [X2]

---

## 10. Validation Boundary

The MCP should validate only what is required to make the **write operation itself** well-defined and safe.

### 10.1 Validation classification

| Check | Classification | Rationale |
| --- | --- | --- |
| Project exists/current MCP project preconditions | **Required** | Reuse existing domain boundary. |
| POU exists by domain name | **Required** | `update`, not create. |
| POU name non-empty | **Required** | Existing read contract. |
| Target current language is ST | **Required** | v1 write scope. |
| Target path derived by MCP and contained in project | **Required** | Prevent arbitrary write. |
| Target exists and is a regular file | **Required** | Mutation of existing POU only. |
| Target is not a symlink | **Required for write** | Avoid alias/write-surprise semantics even for in-root links. |
| Replacement is non-empty/non-whitespace | **Required** | Empty file cannot represent the target POU. |
| Replacement is valid UTF-8 text | **Required** | Current persistence is UTF-8 text. Python `str` already guarantees characters; encoding can still fail on invalid surrogate content. |
| Replacement declaration has expected POU type | **Required** | Identity invariant. |
| Replacement declaration name exactly equals target name | **Required** | Identity invariant. |
| Replacement Function has a return type | **Required** | Minimal persisted envelope expected by OpenPLC parser. |
| Matching terminal keyword is present after declaration | **Required** | Minimal persisted envelope expected by OpenPLC parser. |
| Expected content hash matches current exact bytes | **Required** | Lost-update protection. |
| Parse all variable declarations | **Should not be implemented** | Compiler/OpenPLC responsibility; would duplicate parser semantics. |
| Validate ST body syntax | **Delegate to `compile_project()`** | Compiler responsibility. |
| Validate data types/references/function calls | **Delegate to compiler** | Project semantic validation. |
| Validate functional control behavior | **Outside `update_pou()`** | Runtime/test responsibility. |
| Validate LD/FBD JSON | **Not implemented in v1** | Those languages are non-writable. |
| Detect/migrate legacy formats | **Should not be implemented** | Explicitly out of project scope. |

### 10.2 Minimal ST envelope validation

**Recommended.** Implement a deliberately small validator that answers only:

> “Does this complete replacement still represent the same ST POU identity and outer file envelope?”

It can follow the same high-level envelope OpenPLC expects without reproducing variable or body parsing:

1. tolerate leading whitespace and the single leading `(* ... *)` documentation form used by the current OpenPLC serializer/parser;
2. require the expected declaration keyword derived from existing POU type;
3. capture the declaration name and require exact equality with `pou_name`;
4. for Function, require a non-empty return type token;
5. require the corresponding terminal keyword somewhere after the declaration.

Do not parse:

- individual variables;
- initial values;
- comments within the body;
- expressions;
- statements;
- calls;
- types;
- timer syntax;
- control-flow semantics.

### 10.3 Why not automatically run the OpenPLC parser before writing?

The OpenPLC parser is TypeScript frontend code, not a stable Python library exposed to this MCP. Reimplementing it would violate the architecture. Calling the entire Editor just to validate a textual replacement would add an unnecessary dependency and coupling.

### 10.4 Current malformed POU

**Recommended.** The target is identified by current-format canonical file identity (folder + filename + extension), as the MCP already does. `update_pou()` should not require the *old* content to parse successfully before it can be repaired. The required expected hash proves which exact bytes the caller read; the **replacement** must restore/retain the canonical name/type envelope.

This allows the tool to repair malformed ST while still preventing accidental rename/type conversion.

---

## 11. Atomicity and Failure Integrity

### 11.1 Direct overwrite versus replacement

| Mechanism | Advantage | Failure risk | Recommendation |
| --- | --- | --- | --- |
| `Path.write_text()` / direct truncate-write | Simplest | Process/disk failure after truncate can leave partial/empty POU | Reject for mutation tool |
| temp file + `os.replace()` | Small implementation; target changes only after temp is complete | Replacement can fail due permissions/locks; residual race before replace | **Recommended** |
| general transaction/backup subsystem | Stronger multi-file semantics | Large complexity with no current need | Reject |

**Observed.** OpenPLC Editor's local save implementation ultimately writes files directly; however, MCP's mutation API has no need to preserve that exact failure mode. [O8]

**Recommended.** Use the minimum mechanism that prevents a partially written POU from replacing the original.

### 11.2 Minimum safe mechanism

1. Resolve and validate the existing target.
2. Read current bytes and verify the expected hash.
3. Validate/encode replacement before creating any replacement state.
4. Create a temporary file in the **same directory** as the target.
5. Write all replacement bytes.
6. Flush and `fsync()` the temporary file.
7. Preserve the target's normal file mode on the temporary file where applicable.
8. Re-read/re-hash the target immediately before replacement; abort if the expected hash no longer matches.
9. `os.replace(temp_path, target_path)`.
10. Remove the temp file on any pre-replace failure.

The same-directory requirement avoids cross-filesystem rename semantics.

### 11.3 What does this guarantee?

Before successful `os.replace()`:

- the original target is not truncated;
- validation failures leave it unchanged;
- stale-hash failures leave it unchanged;
- temp-write/fsync failures leave it unchanged;
- a failed replacement leaves it unchanged under normal filesystem semantics.

After successful replacement, the complete new byte sequence is the target.

### 11.4 Durability versus atomic replacement

`fsync()` of the temp file is proportionate because the point of the helper is to avoid replacing a valid POU with buffered/partial content. A parent-directory `fsync()` would improve crash durability on some POSIX filesystems, but it is not required for the v1 contract unless the project later promises power-loss crash consistency.

### 11.5 Platform implications

- `os.replace()` is the correct Python primitive for replacing an existing path atomically when source and destination are on the same filesystem.
- On Windows, a file held with restrictive sharing/locking may cause replacement to fail; surface this as a write failure rather than falling back to direct truncation.
- Network or unusual filesystems can have weaker rename/durability guarantees. The MCP currently targets normal local project directories; do not build a distributed transaction layer for hypothetical network storage.

### 11.6 Backups

**Recommended.** `update_pou()` should not create `.bak`, `backup/`, or history files.

Reasons:

- they are not part of OpenPLC project semantics;
- repeated agent calls would pollute the repository;
- backup naming/retention becomes hidden policy;
- Git/version-control workflows are the appropriate durable history mechanism;
- optimistic concurrency and atomic replacement address the write-integrity problem directly.

---

## 12. Concurrency and External Modification

### 12.1 Lost-update scenario

Without concurrency protection:

```text
Agent: read MAIN at version A
        ↓
Editor/another process writes version B
        ↓
Agent writes replacement derived from A
        ↓
version B is silently lost
```

This is realistic because OpenPLC Editor explicitly watches POU files for external changes. [O10]

### 12.2 Candidate version mechanisms

| Mechanism | Strength | Weakness | Decision |
| --- | --- | --- | --- |
| mtime only | Cheap | Timestamp granularity/collisions; metadata not content | Reject |
| size + mtime | Better than mtime | Same-size rapid edits can collide | Reject |
| opaque incrementing MCP version | Clear API | Requires persistent state/database; breaks across processes | Reject |
| full previous content | Exact | Bloats request; duplicates content | Reject |
| SHA-256 of exact persisted bytes | Stateless, content-based, portable | Small CPU cost; cannot eliminate final filesystem TOCTOU | **Recommended** |

### 12.3 Required, not optional

**Recommended.** `expected_content_hash` should be **required in v1**.

Making it optional turns the safe path into an opt-in and preserves the most damaging write failure: silent lost updates. The intended domain workflow already requires the agent to inspect an existing POU before modifying it, so requiring the token does not create an artificial workflow step.

If a future use case genuinely needs a blind overwrite, that should be an explicit design decision rather than `expected_content_hash=None` silently disabling protection.

### 12.4 Hash definition

Recommended token format:

```text
sha256:<64 lowercase hex characters>
```

Compute it over the exact POU file bytes, before newline normalization or parse/serialization.

### 12.5 `read_pou()` implication

**Recommended.** In the same future PR:

- read the POU bytes once;
- hash those exact bytes;
- decode those same bytes as UTF-8 for `content`;
- return `content_hash`.

This is preferable to separately calling text and byte reads. It also avoids unintentional universal-newline normalization when the returned content is meant to serve as the basis for complete-file replacement.

Backward-compatibility impact:

- adding `content_hash` is additive for normal MCP JSON consumers;
- exact-dictionary unit tests must be updated;
- preserving exact line endings may make the returned text more faithful on CRLF files than the current `Path.read_text()` path. This is a small behavior correction and should be documented in the implementation PR.

### 12.6 Re-check before replace

The hash should be checked twice:

1. before expensive preparation/temp write;
2. again immediately before `os.replace()`.

This narrows the concurrency window while preserving a small implementation.

### 12.7 Residual race

**Open limitation.** Portable local filesystem APIs do not provide a simple compare-and-swap replacement of “replace this path only if its current content hash equals X.” Another process can theoretically modify the path between the final hash check and `os.replace()`.

**Recommended.** Accept this residual TOCTOU risk for v1. Eliminating it would require locking, OS-specific handles, or coordination with OpenPLC Editor—complexity disproportionate to the local cooperative engineering threat model.

---

## 13. Open Editor Interaction

This is a real limitation, not a hypothetical one.

### 13.1 What OpenPLC Editor currently does

**Observed.** The textual/hybrid Monaco POU editor watches the canonical POU file when native file watching is available. On an external change it first checks whether the Editor currently considers the file saved. [O10]

- If the Editor considers the POU **saved**, it reads the file and reparses it.
- If the Editor considers the POU **unsaved**, the external update is ignored by that reload path.

**Observed.** The current watcher reload path updates the textual **body** in project state. It does not equivalently rebuild all POU declarations/documentation through the full project-open path. [O10]

### 13.2 Consequences for `update_pou()`

Scenario A — Editor has unsaved changes:

```text
MCP writes new MAIN.st
Editor ignores external reload because file is dirty
User/Editor later saves stale in-memory state
MCP update can be overwritten
```

Scenario B — Editor is saved but MCP changes declarations/documentation:

```text
MCP writes new full MAIN.st
Editor watcher notices change
watcher refreshes body
variables/documentation may remain stale in Editor state
later Editor save can reserialize stale interface metadata
```

### 13.3 Recommended supported workflow

**Recommended.** v1 should explicitly document:

> Do not use `update_pou()` while the same OpenPLC project is actively open for editing in OpenPLC Editor. Close the project/Editor or otherwise ensure there is no competing Editor session before mutation.

The MCP does not currently have a reliable Editor-session/lock API, so this should be a documented limitation rather than an unreliable runtime check.

### 13.4 Why the hash is still valuable

The expected hash protects against changes that happen **before** the MCP write. It does not prevent another application from overwriting the MCP result afterward. Both protections would require different coordination mechanisms.

---

## 14. Relationship with Existing MCP Tools

### 14.1 Tool interaction table

| Tool | Change required for `update_pou()`? | Relationship |
| --- | --- | --- |
| `get_project_structure()` | No | Naturally reflects existing project structure; update does not create/move POU. |
| `list_pous()` | No | Source of domain discovery; update preserves identity. |
| `read_pou()` | **Yes, additive** | Return exact-byte `content_hash`. |
| `list_variables()` | No | Reads the post-update POU naturally. |
| `list_global_variables()` | No | Resource globals are outside POU file mutation. |
| `list_datatypes()` | No | Data types remain separate project artifacts. |
| `get_execution_configuration()` | No | Program instance names stay unchanged. |
| `get_io_configuration()` | No | Unrelated artifact. |
| `validate_project()` | No | Existing project-level structural validation remains separate. |
| `compile_project()` | No | Called explicitly after mutation. |
| `get_diagnostics()` | No | Reports the compile result from explicit compilation. |

### 14.2 Should compilation be automatic?

**Recommended: no.**

Automatic compile would conflate:

- persistence success;
- compiler success;
- diagnostics production.

Keeping operations separate provides:

- clear responsibility boundaries;
- lower `update_pou()` latency;
- the ability to write an intermediate broken state and then fix it;
- explicit compiler diagnostics;
- observable compile attempts/tool calls for experiments;
- simpler recovery when compilation fails.

Expected agent loop:

```text
update_pou()
    ↓ persisted successfully
compile_project()
    ↓ success/failure
get_diagnostics()
    ↓
optional read/update retry
```

### 14.3 Separate variable mutation tools

**Recommended.** Do not add POU-local variable mutation tools merely because `list_variables()` exists. The read decomposition is useful for understanding; the write decomposition does not need to mirror it.

A complete ST POU replacement already exposes the same underlying engineering information without creating multiple competing mutation paths.

---

## 15. Experimental Implications

### 15.1 Functional equivalence with the baseline

The research compares:

```text
LLM Agent → filesystem / CLI → OpenPLC
```

against:

```text
LLM Agent → domain MCP → OpenPLC
```

**Observed.** The repository's research documentation explicitly requires the MCP to expose stable domain operations without collapsing into generic filesystem/shell access. [M8]

**Recommended.** Full ST POU replacement preserves functional equivalence well:

- baseline agent can replace the same authoritative `.st` file using filesystem tools;
- MCP agent can replace the same authoritative `.st` file through `update_pou()`;
- both compile through the same OpenPLC CLI/compiler path;
- MCP adds target/identity/concurrency guards but does not synthesize PLC logic or perform hidden semantic validation.

This is an interface difference, not a fundamentally different engineering task.

### 15.2 Experimental task classes enabled

`update_pou()` would support tasks such as:

- change a motor start/stop condition;
- add an interlock;
- change a timer preset;
- add or remove POU-local variables;
- add an input/output/in-out declaration;
- correct an undeclared variable by adding its declaration;
- fix a syntax/compiler error;
- change a Function return type and then resolve resulting compiler errors;
- correct Function Block calls;
- implement compile → diagnose → correct loops;
- modify documentation together with engineering code when required.

### 15.3 Why ST-only is sufficient for first experiments

ST supports the key mutation/debugging workflows without giving the MCP a graphical model that the baseline agent would also need to understand. This creates a clean experimental boundary and keeps implementation complexity from becoming a confounder.

### 15.4 External research/design references

**External inspiration, not OpenPLC-derived fact.**

- CODESYS Development System MCP Server advertises domain tools for reading projects, creating/modifying POUs using Structured Text, and compiler/error access. This independently supports an ST-centered domain operation plus separate compiler feedback. [X1]
- SemaPLC's results emphasize that source generation alone is insufficient and that compilation/runtime verification should gate claims of success. This supports preserving explicit validation steps after update. [X2]
- SWE-agent's source editing tools use generic `path` + string/patch operations. That is useful baseline inspiration but is specifically the abstraction this MCP should avoid exposing. [X3]

---

## 16. Risks and Failure Modes

| Risk | Cause | v1 mitigation | Residual risk |
| --- | --- | --- | --- |
| Arbitrary file write | Caller controls path | Caller supplies POU name only; MCP derives canonical existing path | Malicious local filesystem race remains outside normal threat model |
| Accidental rename | Replacement declaration name differs | Exact declaration-name check | Compiler may still expose other semantic name issues in body |
| Type conversion | Declaration keyword differs | Require existing target type keyword | None for supported envelope |
| Language conversion | Changing extension/body representation | Target must already be ST; no extension parameter | ST body can still be semantically invalid; compiler catches |
| Lost update | Stale read | Required exact-byte SHA-256 token; final re-check | Tiny TOCTOU window before replace |
| Truncated POU | Direct overwrite interrupted | Temp file + atomic replace | Filesystem-specific rename guarantees |
| Parse→serialize drift | MCP reconstructs POU | Do not parse/serialize complete POU | Caller intentionally controls target replacement bytes |
| Graphical corruption | LD/FBD JSON/flow state | No LD/FBD writes in v1 | Future expansion requires a new investigation/design decision |
| Editor overwrites MCP result | Simultaneous open session | Document unsupported concurrent Editor workflow | No cross-process lock in v1 |
| Hidden project pollution | Backup/temp artifacts | No backups; clean temporary on failure | Orphan temp possible after process crash before cleanup |
| Broken PLC semantics | Invalid ST/types/calls | Explicit compile/diagnostics after update | Update itself can persist compilably invalid intermediate state by design |
| Legacy ambiguity | Upstream accepts JSON fallback | MCP current-format native files only | Mixed/manual projects outside supported contract |

### 16.1 Error model

Use the existing `ToolError` model with meaningful domain messages. No exception hierarchy is necessary.

Recommended categories/messages:

**User/agent input**

```text
POU name must not be empty
Replacement POU content must not be empty
Replacement POU name does not match target 'MAIN'
Replacement POU type does not match target type 'program'
Replacement Function must declare a return type
Replacement POU is missing END_PROGRAM
```

**Project state**

```text
POU not found: MAIN
POU language 'ld' is not supported for update; v1 supports Structured Text only
POU target is not a regular project file: ...
POU target is a symbolic link and cannot be updated
```

**Concurrency**

```text
POU changed since it was read: MAIN; call read_pou() again before updating
```

**I/O**

```text
Could not write POU 'MAIN': <concise OS error>
```

**Compiler errors**

Do **not** convert compiler diagnostics into `update_pou()` errors. The update may legitimately persist an intermediate ST state that requires a later compile/fix iteration.

### 16.2 Failure-integrity rule

**Recommended invariant.** Any `update_pou()` call that returns an error before successful atomic replacement must leave the original POU bytes unchanged.

---

## 17. Future Test Matrix

Do not implement these tests in this investigation. The implementation PR should include them.

### 17.1 Happy path

- update existing ST Program;
- update existing ST Function Block;
- update existing ST Function;
- change only body logic;
- change local `VAR` declarations;
- change `VAR_INPUT`;
- change `VAR_OUTPUT`;
- change `VAR_IN_OUT`;
- change documentation;
- change Function return type;
- `read_pou()` after write returns replacement content and new hash;
- `list_variables()` after write reflects changed declarations;
- explicit `compile_project()` can be called after write;
- valid replacement compiles in an integration fixture where CLI availability is part of the test environment.

### 17.2 Exact content behavior

- replacement text is persisted byte-for-byte after UTF-8 encoding;
- LF content remains LF;
- CRLF content can be read/hashed without normalization and, if returned unchanged, written back with CRLF unchanged;
- comments and spacing supplied by caller remain exactly as supplied;
- unrelated POU files remain byte-identical;
- `project.json` remains byte-identical for an in-place POU update.

### 17.3 Identity protection

- target `MAIN`, replacement declares `DIFFERENT_NAME` → error, no write;
- target Program, replacement declares Function Block → error, no write;
- target Function Block, replacement declares Program → error;
- Function without return type → error;
- missing required terminal keyword → error;
- wrong target POU name → normal `POU not found` behavior;
- duplicate/ambiguous existing POU name follows existing discovery error semantics.

### 17.4 Unsupported languages

For existing targets:

- `.il` → reject before mutation;
- `.ld` → reject before mutation;
- `.fbd` → reject before mutation;
- `.py` → reject before mutation;
- `.cpp` → reject before mutation.

Each test should assert original bytes unchanged.

### 17.5 Filesystem protection

- external symlink target is not discoverable/resolvable;
- symlink inside project is rejected for write even if it resolves inside project;
- target removed after discovery → error, no other path written;
- target replaced with directory/non-regular entry → error;
- temporary-file creation failure leaves original unchanged;
- temp write failure leaves original unchanged;
- fsync failure leaves original unchanged;
- `os.replace()` failure leaves original unchanged and temp is cleaned when possible;
- target mode is preserved across successful replacement where platform supports it.

### 17.6 Concurrency

- `read_pou()` returns deterministic hash for exact bytes;
- matching expected hash permits update;
- stale expected hash rejects update;
- stale rejection leaves original byte-identical;
- modification after first hash check but before final check is detected;
- returned new hash equals replacement exact bytes;
- malformed hash token rejects before mutation.

### 17.7 Repair scenario

- existing ST file has malformed body/declaration details but is still resolved by canonical path;
- caller has exact hash;
- valid replacement with correct canonical name/type can repair it;
- MCP does not require full old-content parseability.

### 17.8 Server contract

- `update_pou` appears in tool list;
- tool is annotated as local write, not read-only;
- `open_world_hint=False` remains consistent;
- structured successful result is `{name, content_hash}`;
- `read_pou` structured result includes `content_hash`;
- ToolErrors surface through existing MCP conventions.

### 17.9 No hidden side effects

- no `.bak` file;
- no backup directory;
- no automatic compile invocation;
- no modification of `project.json`;
- no modification of unrelated files;
- failed update does not change compiler diagnostic cache.

---

## 18. Decision Table

| Design question | Recommended decision | Confidence | Evidence |
| --- | --- | --- | --- |
| Writable languages | **ST only in v1** | High | ST supports thesis mutation tasks; LD/FBD have recent corruption/recovery complexity; Python/C++ add unrelated toolchain semantics. [M8] [O13] [O14] |
| Mutation unit | **Existing named POU** | High | MCP already discovers by POU identity; OpenPLC persists each POU independently. [M2] [O5] |
| Full POU vs body only | **Complete persisted POU content** | High | Body-only requires text merge/parser ownership and cannot naturally change declarations. [O2] [O4] |
| Allow variable changes | **Yes, through complete POU content** | High | Variables are part of the POU file; separate variable writers would duplicate semantics. [O2] [O4] |
| Allow documentation changes | **Yes** | High | Documentation is persisted in same POU representation. [O2] [O4] |
| Allow Function return-type changes | **Yes** | Medium/High | Return type is interface content, not path identity; compiler can validate dependents. [O2] |
| Allow rename | **No** | High | Name determines filename and references; OpenPLC has a separate rename flow. [O5] [O9] |
| Allow POU type change | **No** | High | Type changes canonical folder/declaration semantics. [O1] |
| Allow language change | **No** | High | Language determines extension/parser/body representation. [O1] |
| Automatic compile | **No** | High | Existing MCP separates compile/diagnostics; experiments benefit from observable steps. [M5] [M8] |
| Atomic write | **Yes: same-dir temp + fsync + `os.replace`** | High | Prevents truncation/partial-file failure without transaction framework. |
| Concurrency hash | **Required SHA-256 exact-byte token** | High | Real external-edit workflow exists; avoids silent lost updates with stateless small contract. [O10] |
| Hash optional? | **No** | High | Optional token leaves blind overwrite as default-valid behavior. |
| Backup files | **No** | High | Not OpenPLC semantics; Git/atomicity are cleaner responsibility boundaries. |
| `read_pou()` changes | **Add `content_hash`; read/hash same exact bytes** | High | Required for safe lifecycle; additive public field. [M2] |
| Result fields | **`name`, `content_hash` only** | High | Success implies updated; path/type/language/content are redundant. |
| Graphical write support | **No v1** | High | DOPE-495/592 show concrete data-loss complexity. [O13] [O14] |
| Editor open simultaneously | **Document unsupported v1** | High | Watcher ignores external changes while dirty and does not fully hydrate all POU metadata. [O10] |
| Legacy project handling | **None** | High | Explicit MCP scope; upstream compatibility paths must not leak in. [M1] [O12] |
| Structured IEC parser/AST | **Do not add** | High | Violates project architecture and duplicates OpenPLC. [M1] [O2] |
| Patch/diff API | **Do not use for domain tool** | Medium/High | Generic source-edit abstraction weakens MCP domain boundary. [M8] [X3] |

---

## 19. Recommended Contract

### 19.1 Public types

```python
class PouContent(TypedDict):
    name: str
    type: PouType
    language: PouLanguage
    path: str
    content: str
    content_hash: str


class UpdatePouResult(TypedDict):
    name: str
    content_hash: str
```

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

### 19.3 Parameter semantics

`project_path`
: Existing current-format OpenPLC project root, following the same contract as the other project tools.

`pou_name`
: Existing domain POU name. It is not a path and cannot contain instructions for another file. Resolution follows the existing `list_pous()`/`read_pou()` semantics.

`content`
: Complete new UTF-8 persisted representation of the target **Structured Text** POU, including declaration/interface/body/terminal keyword and optional documentation.

`expected_content_hash`
: Required `sha256:<hex>` token from the `read_pou()` result on which the update was based. Any mismatch means the target changed and the operation must abort without writing.

### 19.4 Result

```json
{
  "name": "MAIN",
  "content_hash": "sha256:..."
}
```

Do not return:

- `updated: true` — successful return already means success;
- `path` — unnecessary filesystem detail;
- `type`/`language` — unchanged and already known;
- `previous_content_hash` — caller already supplied it;
- complete updated content — caller just supplied it and can call `read_pou()` if a post-write read is required.

### 19.5 Supported languages

v1:

```text
Structured Text only
```

Supported existing POU types:

```text
Program
Function Block
Function
```

### 19.6 Preconditions

- project satisfies existing MCP current-project loading rules;
- POU exists by current domain identity;
- target is `.st`;
- target is an existing regular non-symlink file under project root;
- replacement is non-empty UTF-8 text;
- expected hash is well formed and equals current exact target bytes;
- replacement declares the target's existing POU type;
- replacement declaration name exactly equals `pou_name`;
- Function replacement contains a return type;
- matching terminal keyword exists.

### 19.7 Invariants

Must remain unchanged:

```text
POU name
POU type
programming language
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

### 19.8 Side effects

Only one intended persistent side effect:

```text
replace the existing target ST POU file
```

No:

- automatic compilation;
- project.json rewrite;
- backup/history creation;
- POU creation/deletion/rename;
- other file modification.

### 19.9 Error conditions

- existing project/path errors;
- POU not found/ambiguous;
- unsupported target language;
- invalid target filesystem state;
- invalid expected hash format;
- stale expected hash;
- empty replacement;
- replacement name mismatch;
- replacement type mismatch;
- missing Function return type;
- missing matching end keyword;
- UTF-8 encoding failure;
- temporary write/fsync failure;
- atomic replacement failure.

Compiler diagnostics are not `update_pou()` errors.

### 19.10 `read_pou()` contract change

This should happen in the **same future PR**, not a prerequisite PR, because the hash exists solely to make the new write lifecycle safe.

Recommended implementation-level behavior:

```text
raw = target.read_bytes()
content = raw.decode("utf-8")
content_hash = "sha256:" + sha256(raw).hexdigest()
```

This keeps content and concurrency version tied to one exact disk read.

---

## 20. Recommended Write Algorithm

High-level pseudocode only:

```text
function update_pou(project_path, pou_name, content, expected_content_hash):
    validate non-empty pou_name
    validate expected_content_hash format
    validate content is not empty/whitespace-only

    load project using existing current-format project helper

    resolve existing POU by domain name
    if not found / ambiguous:
        fail without mutation

    if POU language != ST:
        fail unsupported-language without mutation

    derive target path from resolved POU information
    resolve project root

    verify target is contained in project root
    verify target exists
    verify target is a regular file
    verify target is not a symbolic link

    current_bytes = read target bytes
    current_hash = sha256 token(current_bytes)
    if current_hash != expected_content_hash:
        fail stale-update without mutation

    validate replacement ST outer envelope only:
        expected declaration keyword from existing POU type
        declaration name exactly equals pou_name
        Function has return type when target is Function
        expected END_* keyword exists after declaration

    replacement_bytes = UTF-8 encode(content)
    new_hash = sha256 token(replacement_bytes)

    create temporary file in target parent directory
    try:
        write all replacement_bytes to temp
        flush temp
        fsync temp
        apply original normal file mode where supported

        verify target is still regular/non-symlink/contained
        latest_bytes = read target bytes
        if sha256 token(latest_bytes) != expected_content_hash:
            fail stale-update; original remains unchanged

        atomically replace target with temp using os.replace
    except:
        delete temp when possible
        raise concise ToolError

    return {
        name: pou_name,
        content_hash: new_hash,
    }
```

### Important implementation notes

- Do not create a reusable “project transaction” class.
- Do not create a generic `write_file(path, content)` public/internal API unless another concrete feature independently needs it.
- Keep envelope validation next to POU mutation logic, probably in `pous.py` as a small private helper.
- Keep hash calculation a tiny private helper if it avoids duplication between `read_pou()` and `update_pou()`.
- Do not parse variable blocks as part of update validation.
- Do not run the compiler from this function.

---

## 21. Non-Goals

The future `update_pou()` feature should explicitly not attempt to:

- create a POU;
- delete a POU;
- rename a POU;
- change a POU type;
- convert a POU language;
- edit LD/FBD diagrams;
- write Python/C++ POUs in v1;
- write IL in v1;
- create/update/delete POU-local variables through separate APIs;
- mutate resource-global variables;
- update Program Instance configuration;
- refactor project-wide references after a rename;
- parse the full IEC 61131-3 grammar;
- create an ST AST;
- reproduce OpenPLC's POU serializer;
- reproduce OpenPLC's graphical flow model;
- reproduce OpenPLC's fallback parser/recovery behavior;
- support historical JSON POU projects;
- auto-migrate projects;
- expose arbitrary paths;
- expose a generic file writer;
- create backups;
- automatically compile;
- synchronize with a live OpenPLC Editor editing session;
- provide multi-file transactions;
- guarantee atomic semantics on arbitrary network/distributed filesystems.

---

## 22. Open Questions

The central v1 contract can be implemented without unresolved architectural discovery. The remaining questions are deliberately bounded.

### 22.1 Network-mounted projects

**Open question.** The MCP currently behaves as a local project tool. If users later require NFS/SMB/cloud-mounted workspaces, `os.replace()` durability/atomicity assumptions should be revalidated for those filesystems. No evidence supports adding that complexity now.

### 22.2 Coordinated OpenPLC Editor sessions

**Open question.** A future Editor API could theoretically provide project/file locks or a complete external reload contract. None was found in the current integration surface that would make cross-process full-POU editing conflict-safe. Until then, simultaneous editing remains unsupported.

### 22.3 IL write support

**Open question.** IL uses the same broad textual persistence pattern as ST and would be technically easier to add than graphical/hybrid languages. There is currently no experimental requirement that justifies expanding v1. If that requirement appears, evaluate it as a small follow-up rather than pre-generalizing the implementation.

### 22.4 Graphical write support

**Open question.** LD/FBD should require a separate design investigation if ever requested. Recent OpenPLC history shows that syntactically valid JSON is not sufficient to prove a safe diagram state and that stale flow write-back can cause data loss. Raw full-file replacement might still be possible under a different contract, but it should not be inferred from the ST design.

### 22.5 Future upstream persistence changes

**Open question.** OpenPLC Editor is evolving quickly. Any implementation agent should compare the pinned upstream revision in this document with the then-current `development` head before implementing. If POU persistence/save semantics have changed, update this investigation rather than assuming the 2026-08-30 conclusions still hold.

---

## 23. Evidence / Source References

All repository links below are pinned where practical. “Observed” claims above derive from these sources. “Inferred” and “Recommended” statements are architectural conclusions based on them.

### MCP repository

**[M1] Architecture and scope instructions**  
`industrix-com-br/openplc-engineering-mcp` @ `9936fa2455e85f6856a7b9dc9c92a7a72200c508`  
`AGENTS.md`  
https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/AGENTS.md  
Behavior: current-format only; OpenPLC authoritative; domain operations over generic filesystem/shell; avoid unnecessary abstractions/parsers.

**[M2] POU discovery and read contract**  
`src/openplc_engineering_mcp/openplc/pous.py`  
https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/src/openplc_engineering_mcp/openplc/pous.py  
Functions/types: `_is_contained`, `_list_pous`, `list_pous`, `read_pou`, `PouInfo`, `PouContent`.  
Behavior: file-stem domain identity, current native extensions, path containment, raw UTF-8 read.

**[M3] Project loading/current configuration boundary**  
`src/openplc_engineering_mcp/openplc/project.py`  
https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/src/openplc_engineering_mcp/openplc/project.py

**[M4] POU variable inspection**  
`src/openplc_engineering_mcp/openplc/variables.py`  
https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/src/openplc_engineering_mcp/openplc/variables.py  
Behavior: narrow read-time declaration extraction over `read_pou()` content.

**[M5] Compile/diagnostics separation**  
`src/openplc_engineering_mcp/openplc/compiler.py`  
https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/src/openplc_engineering_mcp/openplc/compiler.py

**[M6] MCP registration conventions**  
`src/openplc_engineering_mcp/server.py`  
https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/src/openplc_engineering_mcp/server.py

**[M7] Existing POU/server tests**  
`tests/test_pous.py`, `tests/test_server.py`  
https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/tests/test_pous.py  
https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/tests/test_server.py

**[M8] Research/experimental boundary**  
`docs/research.md`, `docs/scope.md`, `docs/openplc-projects.md`  
https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/docs/research.md  
https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/docs/scope.md  
https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/docs/openplc-projects.md

**[M9] Execution references**  
`src/openplc_engineering_mcp/openplc/execution.py`  
https://github.com/industrix-com-br/openplc-engineering-mcp/blob/9936fa2455e85f6856a7b9dc9c92a7a72200c508/src/openplc_engineering_mcp/openplc/execution.py  
Behavior: `configuration.resource.instances[].program` is exposed as Program Instance → Program reference.

### OpenPLC Editor current implementation

**[O1] POU folder/extension/declaration mapping**  
`Autonomy-Logic/openplc-editor` @ `3652363583de7e88f64c77ba3fac204e4ee7e4ed`  
`src/frontend/utils/PLC/pou-file-extensions.ts`  
https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/frontend/utils/PLC/pou-file-extensions.ts

**[O2] Language-specific POU parsers**  
`src/frontend/utils/PLC/pou-text-parser.ts`  
https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/frontend/utils/PLC/pou-text-parser.ts  
Functions: `parseTextualPouFromString`, `parseHybridPouFromString`, `parseGraphicalPouFromString`, `isGraphicalBodyShape`, `findLastEndVarIndex`.

**[O3] Raw project read → frontend parse flow and recovery**  
`src/backend/shared/utils/parse-project-files.ts`  
https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/backend/shared/utils/parse-project-files.ts  
Functions/types: `parseProjectFiles`, `parsePouFile`, `createFallbackPou`, `UnrecoverablePouError`, `detectPouTypeFromPath`, `getBaseNameFromPath`.

**[O4] POU serialization**  
`src/frontend/utils/PLC/pou-text-serializer.ts`  
https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/frontend/utils/PLC/pou-text-serializer.ts  
Behavior: canonical outer representation; variable/documentation/body serialization; graphical JSON pretty printing.

**[O5] Canonical save paths and single-file/full-project save**  
`src/frontend/services/save-actions.ts`  
https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/frontend/services/save-actions.ts  
Functions: `buildProjectJsonContent`, `buildPouSpec`, `iterateProjectFiles`, `serializeProjectFile`, `executeSaveProject`, `executeSaveFile`, `reloadPouFromDisk`.  
Key behavior: `project.json` emits `pous: []`; POU single-file save writes only canonical POU path; graphical stale-flow saves are blocked.

**[O6] Project persistence port**  
`src/middleware/shared/ports/project-port.ts`  
https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/middleware/shared/ports/project-port.ts  
Behavior: save payloads contain already-serialized strings; platform persistence is below the serialization boundary.

**[O7] Desktop ProjectPort adapter**  
`src/middleware/adapters/editor/project-adapter.ts`  
https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/middleware/adapters/editor/project-adapter.ts  
Behavior: raw project read + frontend parse; save/write delegated through bridge.

**[O8] Desktop project service / raw filesystem persistence**  
`src/backend/editor/services/project-service/index.ts`  
https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/backend/editor/services/project-service/index.ts  
Functions include raw project read and project/file write operations.

**[O9] POU create/rename service**  
`src/backend/editor/services/pou-service/index.ts`  
https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/backend/editor/services/pou-service/index.ts  
Behavior: create and rename are explicit operations; canonical extension/name participate in file path.

**[O10] External file watcher behavior in textual/hybrid POU editor**  
`src/frontend/components/_features/[workspace]/editor/monaco/index.tsx`  
https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/frontend/components/_features/%5Bworkspace%5D/editor/monaco/index.tsx  
Behavior: watches canonical POU path; reload only when file is considered saved; external reload updates body state through the textual/hybrid parser path.

**[O11] Raw-content preservation against parse/serialize drift**  
`src/frontend/utils/version-control-content.ts`  
https://github.com/Autonomy-Logic/openplc-editor/blob/3652363583de7e88f64c77ba3fac204e4ee7e4ed/src/frontend/utils/version-control-content.ts  
Function: `pickContentForSave`.  
Behavior: when canonical serialized state is unchanged, reuse raw content to keep output byte-identical and avoid parse/serialize drift.

### OpenPLC Editor history relevant to write safety

**[O12] Native text POU format introduction**  
PR #411 — “New project format”  
Merge commit: `2389075e7d4ce0505600852e690deff02f657419`  
https://github.com/Autonomy-Logic/openplc-editor/pull/411  
Behavior: introduced native language-specific POU files and retained upstream JSON compatibility.

**[O13] DOPE-495 — graphical stale write-back/data-loss prevention**  
Merge PR #973: `d282c2d9435ada6632773acc9365881373486747`  
Core fix: `3da85070966c5a7803313483ec1f61cbb9d426e3`  
https://github.com/Autonomy-Logic/openplc-editor/commit/3da85070966c5a7803313483ec1f61cbb9d426e3  
Observed issue: a failed graphical flow write-back could serialize stale pre-edit body, mark it saved, and lose the user's edit. The fix aborts single-file save instead of overwriting disk with stale content.

**[O14] DOPE-592 — unrecoverable graphical body protection**  
Key commits:

- `2a9b23573c19c40fe5b9effe3089c17559d35838`
- `ac52930777b8386a21273a6a462248b97be6a261`
- `a4efd9cf1e6af292a65247384ae3d9f16f1e6f62`
- `fc620e11d9203c8a47c03e9e7273509026175a71`

https://github.com/Autonomy-Logic/openplc-editor/commit/ac52930777b8386a21273a6a462248b97be6a261  
https://github.com/Autonomy-Logic/openplc-editor/commit/a4efd9cf1e6af292a65247384ae3d9f16f1e6f62  
Observed issue: invalid/wrong-shaped graphical body recovery could present a blank diagram that a subsequent save might persist over the real content. Current behavior distinguishes unrecoverable graphical content and prevents unsafe persistence.

**[O15] Byte-identical graphical/raw preservation history**  
Commit `ec9ef062f5bd99842fda4aac91badc1f1f236049` — “fix: eliminate phantom source-control diffs in graphical editors”  
https://github.com/Autonomy-Logic/openplc-editor/commit/ec9ef062f5bd99842fda4aac91badc1f1f236049  
Observed motivation: unmodified graphical POUs could acquire phantom diffs or state changes through load/serialize behavior; preserving raw/canonical state was necessary for trustworthy persistence.

### External design references — inspiration only

**[X1] CODESYS Development System MCP Server**  
Official CODESYS release page, version 1.0.0.0 released 2026-04-28; version 1.1.0.0 released 2026-07-22.  
https://www.codesys.com/ecosystem/release-lifecycle/releases-updates/development-system-mcp-server/  
Relevant advertised capabilities: read project contents; create/modify POUs using Structured Text; use compiler and retrieve compiler errors.

**[X2] SemaPLC**  
Yanlun Tu et al., “SemaPLC: A Project-Grounded, Verification-Gated Agent Harness for PLC Code Generation”, arXiv:2608.18565, 2026.  
https://arxiv.org/abs/2608.18565  
Relevant design inspiration: project grounding and explicit compilation/runtime verification rather than treating source generation as completion.

**[X3] SWE-agent generic source editing interface**  
`SWE-agent/tools/edit_anthropic/config.yaml`  
https://github.com/SWE-agent/SWE-agent/blob/main/tools/edit_anthropic/config.yaml  
Relevant contrast: generic path-based `str_replace`/insert/create editing is appropriate for a coding agent but is intentionally lower-level than this MCP's POU domain boundary.

---

### Final recommendation in one sentence

Implement `update_pou()` as a **Structured-Text-only, complete-file replacement of an existing named POU, guarded by immutable POU identity, exact-byte optimistic concurrency, strict project/path containment, and atomic replacement, with compilation and diagnostics remaining explicit separate MCP operations**.
