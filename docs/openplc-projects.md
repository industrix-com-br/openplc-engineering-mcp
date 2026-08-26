# OpenPLC projects

This document describes only the OpenPLC project behavior that the MCP currently depends on.

It is not a replacement for the OpenPLC project schema.

## Minimum project preconditions

The current `_load_project()` helper requires:

- a non-empty project path;
- an existing directory;
- `project.json` at the project root;
- valid JSON containing a `meta` object;
- `meta.name` as a string;
- a supported `meta.type`.

Supported project types are currently:

- `plc-project`;
- `plc-library`;
- `PLC`.

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

POU-like files are recognized with these suffixes:

| Suffix | Reported language |
| --- | --- |
| `.st` | `st` |
| `.il` | `il` |
| `.ld` | `ld` |
| `.fbd` | `fbd` |
| `.py` | `python` |
| `.cpp` | `cpp` |
| `.json` | `null` |

## POU discovery

`list_pous()` searches the function, function-block, and program directories recursively.

POU names are deduplicated globally. When both a `.json` representation and a recognized source representation exist for the same POU name, the source representation is preferred.

A JSON-only POU remains visible with `language: null`.

## Validation semantics

`validate_project()` is deliberately shallow.

It checks only the MCP-local filesystem and basic metadata preconditions needed by the current file-oriented operations. It does **not** reproduce the full OpenPLC schema and does not use compilation success as a proxy for project validity.

Unrecoverable conditions such as a missing path, missing `project.json`, malformed JSON, or unsupported `meta.type` are raised as tool errors.

Successful validation currently returns:

```json
{
  "valid": true,
  "name": "...",
  "type": "...",
  "warnings": []
}
```

`warnings` is reserved for recoverable conditions that OpenPLC itself can identify when authoritative loading is delegated to it.

## OpenPLC CLI gap

The current OpenPLC CLI can validate indirectly only by running the compiler pipeline. Compilation also depends on target selection, hardware packages, libraries, and valid IEC code, so compile failure does not prove the project structure is invalid.

A future authoritative validation integration should use a dedicated OpenPLC load/validate capability, conceptually similar to:

```text
openplc-cli validate ./my-project
```

Such a command should reuse OpenPLC's own project-loading path without compiling. Until an equivalent capability exists, the MCP should keep validation shallow rather than duplicate OpenPLC semantics in Python.
