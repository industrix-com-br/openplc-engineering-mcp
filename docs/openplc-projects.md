# OpenPLC projects

This document describes only the [OpenPLC Editor](https://github.com/Autonomy-Logic/openplc-editor) project behavior that the MCP currently depends on. It is not a replacement for the OpenPLC project schema; upstream OpenPLC behavior remains authoritative.

## Minimum project preconditions

The shared `load_project()` helper in `openplc/project.py` requires:

- a non-empty project path;
- an existing directory;
- `project.json` at the project root;
- valid JSON containing a `meta` object;
- `meta.name` as a string;
- a supported `meta.type`.

Supported project types are:

- `plc-project`;
- `plc-library`;
- `PLC`.

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

For the POU, server, and remote directories, recognized file suffixes are:

```text
.st
.il
.ld
.fbd
.py
.cpp
.json
```

Only `.dt` files are included from `datatypes/`.

Returned file paths are project-relative, use POSIX separators, are deduplicated, and are sorted.

## Execution configuration

The current OpenPLC Editor stores the project execution configuration under:

```text
data
└── configuration
    └── resource
        ├── tasks
        ├── instances
        └── globalVariables
```

Its project loader also accepts the legacy `data.configurations` field. The MCP follows the same compatibility rule: `data.configuration` is preferred when present, with `data.configurations` used as the legacy fallback.

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

`globalVariables` is physically adjacent to Tasks and Instances but is outside this inspection operation; it is exposed by `list_global_variables()`. See below. The MCP also does not parse `TIME` literals, apply new priority constraints, validate references, or infer live runtime execution state.

## Resource global variables

`list_global_variables()` in `openplc/variables.py` reads only the resource-level global variables stored under:

```text
data.configuration.resource.globalVariables
```

with the same legacy `data.configurations.resource` fallback used for execution configuration. This lookup is shared by the execution and global-variable inspections through `get_configuration_resource()` in `openplc/project.py`.

Each stored variable provides the data mapped into the public variable contract (`name`, declared `type`, `location`, `initialValue`, `documentation`). The containing resource defines the scope, so the MCP always reports `class: "global"` regardless of any stored class field, and reuses the same JSON type and empty-string normalization as legacy JSON POU variables.

This operation is intentionally narrow. It does not scan POUs for `VAR_GLOBAL` declarations and it does not include named global variable lists (`globalVariableLists` / GVLs), which are separate domain concepts. Missing configuration or missing `globalVariables` yields an empty result; structurally malformed data is raised as a tool error.

## POU discovery

`list_pous()` in `openplc/pous.py` recursively searches:

```text
pous/functions/
pous/function-blocks/
pous/programs/
```

The reported POU language is derived from the file suffix:

| Suffix | Reported language |
| --- | --- |
| `.st` | `st` |
| `.il` | `il` |
| `.ld` | `ld` |
| `.fbd` | `fbd` |
| `.py` | `python` |
| `.cpp` | `cpp` |
| `.json` | `null` |

POU names are deduplicated globally. When both a `.json` representation and a recognized source representation exist for the same name, the source representation is preferred. A JSON-only POU remains visible with `language: null`.

Results are sorted by POU type, name, and path.

## POU reading

`read_pou()` in `openplc/pous.py` reads a POU by its domain name. The caller does not provide or need to know the underlying filesystem path.

The function uses the same discovery result as `list_pous()`, so representation selection remains consistent: when both a recognized source file and a same-name `.json` file exist, the source file is read; a JSON-only POU is read directly and reports `language: null`.

The returned object contains the POU `name`, `type`, `language`, project-relative `path`, and the source `content` read as UTF-8. Content is returned unchanged; the MCP does not parse, normalize, summarize, or otherwise interpret it in this operation.

Discovery and reading share the same containment rule: a source file whose resolved target falls outside the project root is excluded from `list_pous()` and cannot be read by `read_pou()`. Listing and reading are therefore symmetric — a symlink cannot expose an external file through either operation.

An empty POU name, an unknown POU name, or an unreadable selected source is raised as a tool error.

## POU variable declarations

`list_variables()` in `openplc/variables.py` operates on the representation already selected by `read_pou()` rather than locating POU files independently.

For recognized source representations, the current OpenPLC Editor represents POU variables in declaration blocks using these classes:

```text
VAR_INPUT     -> input
VAR_OUTPUT    -> output
VAR_IN_OUT    -> inOut
VAR_EXTERNAL  -> external
VAR_TEMP      -> temp
VAR_GLOBAL    -> global
VAR            -> local
```

The MCP extracts only the declaration information required by its public contract: name, class, declared type, optional location, optional initial value, and optional inline documentation. It preserves declaration order and keeps type and initial-value expressions as strings rather than recreating OpenPLC's internal structured type model or evaluating IEC literals.

The OpenPLC Editor currently allows located declarations in local and global blocks; interface, external, and temporary classes do not carry physical locations. The MCP rejects a located declaration in those classes rather than reporting a misleading variable representation.

Current OpenPLC project parsing also supports legacy JSON POU files whose interface variables are already structured. When `read_pou()` selects a JSON-only POU, `list_variables()` reads those structured variables and maps the OpenPLC type object's declared `value` to the MCP's type string.

A source POU with no variable blocks returns no variables. If a declaration block exists but cannot be interpreted reliably, the MCP raises a tool error instead of treating the POU as having an empty interface. This keeps malformed declaration text distinct from a valid POU with no declarations.

This behavior is intentionally narrow. The MCP does not reproduce the complete IEC 61131-3 grammar or the complete OpenPLC project model.

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
