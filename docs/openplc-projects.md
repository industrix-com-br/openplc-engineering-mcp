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

The returned object contains the POU `name`, `type`, `language`, project-relative `path`, and source `content` read as UTF-8. Content is returned unchanged; this operation does not parse, normalize, summarize, or modify it.

Discovery and reading share the same containment rule: a source file whose resolved target falls outside the project root is excluded from `list_pous()` and cannot be read by `read_pou()`. Listing and reading are therefore symmetric — a symlink cannot expose an external file through either operation.

An empty POU name, an unknown POU name, or an unreadable selected source is raised as a tool error.

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

CLI `stdout` is parsed as JSON when non-empty. Non-empty `stderr` lines are retained in memory for `get_diagnostics()`. See [`tools.md`](tools.md) for the public compilation and diagnostics contracts.
