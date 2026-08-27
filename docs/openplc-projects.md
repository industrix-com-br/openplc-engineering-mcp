# OpenPLC projects

This document describes only the OpenPLC project behavior that the MCP currently depends on. It is not a replacement for the OpenPLC project schema.

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

The returned object contains the POU `name`, `type`, `language`, project-relative `path`, and the source `content` read as UTF-8. Content is returned unchanged; the MCP does not parse, normalize, summarize, or otherwise interpret it in this operation. The resolved source must remain inside the project root, so a POU symlink cannot expose an external file.

An empty POU name, an unknown POU name, or an unreadable selected source is raised as a tool error.

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
