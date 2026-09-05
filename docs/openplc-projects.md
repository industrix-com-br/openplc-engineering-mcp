# OpenPLC projects

This document describes only the [current OpenPLC Editor](https://github.com/Autonomy-Logic/openplc-editor) project behavior that the MCP depends on. It is not a replacement for the OpenPLC project schema; upstream OpenPLC behavior remains authoritative.

The MCP intentionally does not support legacy OpenPLC project formats, historical project representations, migrations, or backward-compatibility parsing. See [`scope.md`](scope.md).

## Compatibility baseline

The complete current MCP feature set targets the OpenPLC Editor `development` branch after two upstream changes merged on August 24, 2026:

- [OpenPLC Editor PR #999](https://github.com/Autonomy-Logic/openplc-editor/pull/999), which introduced the `datatypes/*.dt` persistence used by `list_datatypes()`;
- [OpenPLC Editor PR #1026](https://github.com/Autonomy-Logic/openplc-editor/pull/1026), which introduced the headless CLI used by `compile_project()`.

The latest published OpenPLC Editor release before those changes is v4.2.11, released on August 11, 2026. Consequently, no published release currently contains the complete upstream feature set expected by this MCP.

The project-format breakline is earlier and narrower: [OpenPLC Editor PR #411](https://github.com/Autonomy-Logic/openplc-editor/pull/411) moved POU persistence from JSON-centric files to native text representations and was shipped in v4.1.0. Projects using that native POU layout match the POU representation expected by this MCP, but v4.1.0 by itself does not provide the later `.dt` persistence or headless CLI required by the complete MCP feature set.

In short:

- **POU-format breakline:** OpenPLC Editor v4.1.0;
- **full MCP compatibility:** current OpenPLC Editor `development` branch after PR #999 and PR #1026;
- **legacy JSON-centric projects:** intentionally unsupported.

## Minimum project preconditions

The shared `load_project()` helper in `openplc/project.py` requires:

- a non-empty project path;
- an existing directory;
- `project.json` at the project root;
- valid JSON containing a `meta` object;
- `meta.name` as a string;
- a current supported `meta.type`.

Supported project types are:

- `plc-project`;
- `plc-library`.

The supplied path is expanded and resolved before it is returned or used by other operations.

## Recognized project layout

`get_project_structure()` always includes `project.json` and includes the following when present:

```text
library.json
devices/configuration.json
devices/pin-mapping.json
pous/functions/**
pous/function-blocks/**
pous/programs/**
devices/servers/**
devices/remote/**
datatypes/**/*.dt
```

For POU directories, recognized current source suffixes are:

```text
.st
.il
.ld
.fbd
.py
.cpp
```

Historical JSON POU files are not part of the recognized POU layout. Server and remote-device directories may still contain JSON because JSON remains part of their current representation; only `.dt` files are included from `datatypes/`.

Returned file paths are project-relative, use POSIX separators, are deduplicated, and are sorted.

## Project-defined data types

`list_datatypes()` in `openplc/datatypes.py` reads the canonical current persistence format:

```text
datatypes/<Name>.dt
```

Each `.dt` file contains one IEC `TYPE ... END_TYPE` block with exactly one supported data-type declaration. Embedded historical `project.json.data.dataTypes` definitions are not parsed. If such definitions are present without canonical `.dt` files, the tool reports an unsupported project format rather than normalizing them.

The supported derivations are the three currently persisted by OpenPLC:

- `enumerated` — enumeration values and optional initial value;
- `structure` — named fields with declared type, optional initial value, and optional inline documentation;
- `array` — base type, independent dimensions, and optional initial value.

The `.dt` parser intentionally accepts only the text forms needed by the current OpenPLC data-type serializer. It recognizes single-line enumerations and arrays plus line-oriented structures. Declared types and initial values are preserved as strings rather than converted into OpenPLC's internal variable-type representation or evaluated as IEC literals.

For example, a structure field may report:

```text
ARRAY [0..9] OF REAL
```

and a multidimensional array reports its bounds independently:

```json
["0..9", "0..4"]
```

The file name defines data-type identity. `datatypes/MotorStatus.dt` must declare `MotorStatus`; comparison is case-insensitive. A mismatch is a tool error.

The inspection is fail-closed: if an authoritative `.dt` file is unreadable, malformed, contains more than one declaration, uses an unsupported shape, or has a filename mismatch, `list_datatypes()` raises a tool error rather than returning a partial data-type list. A current-format project with no `.dt` files and no historical embedded definitions returns an empty list.

This behavior does not list built-in IEC types or library-provided types, resolve references between types, validate referenced type names semantically, or implement a complete IEC 61131-3 grammar.

## Execution configuration

The current OpenPLC Editor project representation used by the MCP stores execution configuration under:

```text
data
└── configuration
    └── resource
        ├── tasks
        ├── instances
        └── globalVariables
```

The historical `data.configurations` representation is intentionally unsupported. When it is encountered where the MCP needs the configuration resource, the tool reports an unsupported project format instead of falling back to it.

A Task contains the execution fields used by this MCP:

```text
name: string
triggering: Cyclic | Interrupt
interval: string
priority: integer
```

A Program Instance contains:

```text
name: string
task: string
program: string
```

The instance `task` field identifies the configured Task, while `program` identifies the Program POU to instantiate. The MCP preserves these references as stored and does not independently prove that the referenced Task or Program exists.

For a cyclic Task, `get_execution_configuration()` preserves the original IEC `TIME` interval string such as `T#20ms` or `T#1s`. For an interrupt Task, the public MCP contract returns `interval: null` rather than exposing the stored interval field as cyclic timing.

A project with no execution configuration returns empty Task and Program Instance lists. If Task or Program Instance data is present but structurally malformed, the MCP raises a tool error rather than returning misleading data.

`globalVariables` is physically adjacent to Tasks and Instances but is outside this inspection operation; it is exposed by `list_global_variables()`.

## Physical I/O configuration

The current OpenPLC Editor persists the selected board and local pin mappings in separate device files:

```text
devices/configuration.json  -> deviceBoard
devices/pin-mapping.json    -> Record<deviceBoard, DevicePin[]>
```

The per-board object is the canonical `pin-mapping.json` representation. OpenPLC still accepts a historical flat `DevicePin[]` on load and migrates it into the active board's bucket on save, but the MCP intentionally does not reproduce that migration path.

A current `DevicePin` contains:

```text
pin: string
pinType: digitalInput | digitalOutput | analogInput | analogOutput
address: string
alias?: string
```

`get_io_configuration()` in `openplc/io.py` reads `deviceBoard`, validates the complete canonical per-board mapping, and returns only the array stored under the active board key. Mapping arrays for other boards are retained editor state and do not describe the currently selected target.

The MCP preserves each active mapping's stored order, physical `pin`, and IEC `address` string. It maps `pinType` to the public `pin_type` field and returns a missing optional alias as `null`. It does not parse or normalize the complete IEC address grammar.

When `devices/configuration.json` is absent, the MCP follows the current OpenPLC schema default of `OpenPLC Simulator`. A missing `devices/pin-mapping.json`, an empty mapping object, or an active board with no mapping is a valid empty I/O configuration. Existing but malformed JSON or malformed current-format device structures are tool errors rather than defaults, because returning a partial or silently repaired engineering view would be misleading through MCP.

The OpenPLC Editor's schema still contains two compatibility behaviors that are intentionally not part of the MCP contract: the flat pin array and the old per-pin `name` field that is migrated to `alias`. Encountering either representation causes `get_io_configuration()` to report an unsupported project format.

Vendor Plugin Package configuration is separate. OpenPLC can compile arbitrary `DeviceConfiguration.vendorScreenData` into vendor-specific firmware configuration for boards with VPP I/O support. That blob is not a stable `DevicePin` representation and may contain board-specific module or screen state, so this MCP tool does not expose or reinterpret it. Communication settings, remote devices, protocol configuration, live I/O state, and variable-to-alias resolution are likewise separate concepts.

## Resource global variables

`list_global_variables()` in `openplc/variables.py` reads only the resource-level global variables stored under:

```text
data.configuration.resource.globalVariables
```

Each current-format variable provides the data mapped into the public variable contract: `name`, structured declared `type`, `location`, `initialValue`, and `documentation`. The MCP takes the declared type from the current type object's `value` field. The containing resource defines the scope, so the MCP always reports `class: "global"` regardless of any stored class field.

This operation intentionally does not scan POUs for `VAR_GLOBAL` declarations and does not include named global variable lists (`globalVariableLists` / GVLs), which are separate domain concepts. Missing configuration or missing `globalVariables` yields an empty result; structurally malformed current-format data is raised as a tool error.

## POU discovery

`list_pous()` in `openplc/pous.py` recursively searches:

```text
pous/functions/
pous/function-blocks/
pous/programs/
```

The reported POU language is derived from the current source-file suffix:

| Suffix | Reported language |
| --- | --- |
| `.st` | `st` |
| `.il` | `il` |
| `.ld` | `ld` |
| `.fbd` | `fbd` |
| `.py` | `python` |
| `.cpp` | `cpp` |

Historical JSON-only POUs are not discovered. POU names are deduplicated globally and results are sorted by POU type, name, and path.

## POU reading

`read_pou()` in `openplc/pous.py` reads a current-format POU source file by its domain name. The caller does not provide or need to know the underlying filesystem path.

The returned object contains the POU `name`, `type`, `language`, project-relative `path`, source `content` read as UTF-8, and an exact-byte `content_hash` (`sha256:<64 lowercase hex>`). Content is returned unchanged and the hash is computed over the exact persisted bytes before any newline normalization, so the two fields always describe the same version. This operation does not parse, normalize, summarize, or modify the content.

Discovery and reading share the same containment rule: a source file whose resolved target falls outside the project root is excluded from `list_pous()` and cannot be read by `read_pou()`. Listing and reading are therefore symmetric — a symlink cannot expose an external file through either operation.

An empty POU name, an unknown POU name, or an unreadable selected source is raised as a tool error.

## POU update

`update_pou()` in `openplc/pous.py` replaces the complete persisted representation of one existing Structured Text POU. The current OpenPLC Editor persists each Program, Function Block, or Function as an individual language-specific file under `pous/`, and saving a POU writes that single file; `project.json` persists `pous: []` and does not duplicate POU source. Replacing the single authoritative file is therefore sufficient when the POU identity is unchanged.

The operation is constrained to keep that replacement safe:

- the POU already exists and is resolved by domain name, never by a caller-supplied path;
- exactly one recognized current-format source file matches the requested stem;
- the target language is Structured Text;
- the target is an existing regular file inside the project root and is not itself a symlink;
- the replacement declares the same POU type and exactly the same name, declares a Function return type where applicable, and contains the matching terminal keyword;
- the caller supplies the exact-byte SHA-256 hash of the version the edit is based on, and a stale version rejects the write.

The envelope checks treat a leading UTF-8 BOM as whitespace before the declaration, mirroring the upstream parser, so BOM-prefixed POUs round-trip through `read_pou()` and `update_pou()` without byte normalization.

The MCP validates this operation boundary only. It does not parse or re-serialize the POU body, does not reproduce OpenPLC's parser/recovery semantics, and does not validate IEC syntax, expressions, types, or references — those remain the OpenPLC compiler's responsibility through `compile_project()` and `get_diagnostics()`.

Persistence uses a same-directory temporary file plus `os.replace()` so the original POU is never truncated and a failed update leaves the original bytes unchanged. No backup or history files are written.

Because the target is resolved from its current-format filesystem identity and the expected hash only proves which exact bytes the caller read, a malformed existing ST POU can be repaired by replacing it with a valid same-name/same-type representation.

OpenPLC Editor interaction limitation: the Editor watches POU files but only reloads a POU it considers saved/clean, and an Editor session holding unsaved state can later overwrite an MCP write. `update_pou()` is therefore not a synchronized co-editing workflow; the project should not be actively edited in the OpenPLC Editor at the same time.

## POU variable declarations

`list_variables()` in `openplc/variables.py` operates on the current source file selected by `read_pou()`.

The current OpenPLC source representation uses declaration blocks mapped by the MCP as follows:

```text
VAR_INPUT     -> input
VAR_OUTPUT    -> output
VAR_IN_OUT    -> inOut
VAR_EXTERNAL  -> external
VAR_TEMP      -> temp
VAR_GLOBAL    -> global
VAR            -> local
```

The MCP extracts only the declaration information required by its public contract: name, class, declared type, optional location, optional initial value, and optional inline documentation. It preserves declaration order and keeps type and initial-value expressions as strings rather than recreating OpenPLC's internal type model or evaluating IEC literals.

Extraction is comment-aware: `(* ... *)` comments are ignored wherever they appear, so documentation examples cannot introduce declaration blocks or variables, and only a single-line comment trailing a declaration's terminating semicolon is reported as its documentation. The accepted declaration text covers the forms the upstream serializer emits, including negative array bounds (for example `ARRAY [-2..2] OF INT`) and single-quoted string initial values reported verbatim (for example `'a;b'`). This is not a general IEC parser; unsupported declaration text remains a tool error.

The OpenPLC Editor currently allows located declarations in local and global blocks; interface, external, and temporary classes do not carry physical locations. The MCP rejects a located declaration in those classes rather than reporting a misleading representation.

A source POU with no variable blocks returns no variables. If a declaration block cannot be interpreted reliably, the MCP raises a tool error instead of treating the POU as having an empty interface.

Historical JSON POU variable representations are intentionally not parsed.

## Validation semantics

`validate_project()` is deliberately shallow.

It checks only the local filesystem and metadata preconditions required by the current MCP operations. It does not reproduce the complete OpenPLC schema and does not use compilation success as a proxy for project validity.

Unrecoverable conditions such as a missing path, a non-directory path, missing `project.json`, malformed JSON, missing or invalid metadata, or an unsupported `meta.type` are raised as tool errors.

Successful validation currently returns:

```json
{
  "valid": true,
  "name": "...",
  "type": "...",
  "warnings": []
}
```

`warnings` is currently always empty.

## OpenPLC CLI integration

`compile_project()` in `openplc/compiler.py` first applies the same `load_project()` preconditions and then runs:

```text
openplc-cli compile <resolved-project-path> --json
```

The MCP does not reproduce compilation semantics. The CLI remains authoritative for compilation, and `success` reflects only whether the CLI exited with status `0`.

CLI `stdout` is parsed as JSON when non-empty. Non-empty `stderr` lines are retained in memory for `get_diagnostics()`, except known-benign Electron platform-log lines (non-fatal D-Bus chatter from `bus.cc` / `object_proxy.cc`) and user-data scaffolding notices, which are not compile diagnostics. See [`tools.md`](tools.md) for the public compilation and diagnostics contracts.
