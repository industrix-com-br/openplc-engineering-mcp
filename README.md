# openplc-engineering-mcp

A small Python MCP server that exposes domain-oriented, read-only engineering operations for OpenPLC.

The project is an early experimental implementation. Its current purpose is to establish a minimal, testable integration boundary between MCP-compatible agents and OpenPLC Editor projects.

## Architecture

```text
MCP Host / LLM Agent
        |
        | MCP
        v
OpenPLC Engineering MCP
        |
        v
OpenPLC
```

The server uses the official Model Context Protocol Python SDK and stdio transport. It does not modify OpenPLC or expose generic filesystem or shell tools.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js/npm only when using MCP Inspector (`mcp dev` uses `npx`)

## Installation

```bash
git clone https://github.com/industrix-com-br/openplc-engineering-mcp.git
cd openplc-engineering-mcp
uv sync
```

## Running

Start the stdio MCP server:

```bash
uv run openplc-engineering-mcp
```

Open it with MCP Inspector:

```bash
uv run mcp dev src/openplc_engineering_mcp/server.py --with-editable .
```

## Testing

```bash
uv run pytest
```

The tests use the official SDK's in-memory `Client(mcp)` interface rather than calling tool functions directly.

## Current tools

- `get_server_info` — reports the server's current capabilities.
- `get_project_structure` — returns the relevant structure of an OpenPLC Editor project.
- `list_pous` — lists programs, function blocks, and functions using the current OpenPLC Editor project layout.
- `validate_project` — shallowly confirms a directory is a loadable OpenPLC Editor project.

OpenPLC project inspection follows the current Editor layout: `project.json` at the project root, POUs below `pous/programs`, `pous/function-blocks`, and `pous/functions`, plus the related device and datatype locations used by the Editor.

## Project validation

The MCP deliberately does **not** reproduce the OpenPLC project schema. `_load_project()` (and the `validate_project` tool built on it) intentionally performs only the shallow, MCP-local filesystem preconditions needed for file-oriented operations:

- the path exists and is a directory;
- `project.json` exists;
- basic metadata (`meta.name`, `meta.type`) can be read when the operation needs it.

Authoritative project loading/validation semantics — including recoverable conditions that the OpenPLC Editor loads with defaults and warnings — are intended to be delegated to OpenPLC rather than reimplemented here.

### Required OpenPLC CLI capability

The current `openplc-cli` can validate a project only by running the full compiler pipeline (e.g. `openplc-cli compile <project>`), which also depends on target selection, installed hardware packages, libraries, and valid IEC code. A compile failure therefore does not imply the project structure is invalid, so the MCP does not treat compilation success as project validity.

To let the MCP delegate project validation without invoking the compiler, `openplc-cli` should expose a dedicated load/validate command, roughly:

```text
openplc-cli validate ./my-project
```

It should reuse OpenPLC's existing `loadProject()` path without compiling or requiring a target, and surface recovered-with-defaults conditions as warnings rather than hard failures. Until that command exists, `validate_project` returns a structured result distinguishing:

- unrecoverable failures (path/project not found, malformed `project.json`, unsupported `meta.type`) as tool errors;
- successfully loaded projects with `{"valid": true, "name", "type", "warnings"}`.

`warnings` is reserved for recoverable conditions that OpenPLC will expose once the CLI validation step is available.

## Scope

This version is intentionally read-only and experimental. It does not include project modification, compilation, deployment, runtime control, variable forcing, authentication, HTTP transport, or unrestricted shell/filesystem access. Those capabilities should be added only when concrete requirements justify them.
