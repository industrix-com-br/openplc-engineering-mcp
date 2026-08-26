# openplc-engineering-mcp

A small experimental Python MCP server that exposes domain-oriented engineering operations for OpenPLC.

The project uses the official Model Context Protocol Python SDK and stdio transport. Inspection tools are read-only; compilation is delegated to the authoritative `openplc-cli`.

## Quick start

Requirements: Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/industrix-com-br/openplc-engineering-mcp.git
cd openplc-engineering-mcp
uv sync
uv run openplc-engineering-mcp
```

Run the test suite with:

```bash
uv run pytest
```

## Current tools

- `get_project_structure`
- `list_pous`
- `validate_project`
- `compile_project`
- `get_diagnostics`

Inspection tools are read-only. `compile_project` is a local write operation that requires `openplc-cli` on `PATH`.

## Documentation

Start with [`docs/index.md`](docs/index.md).

It is the documentation entry point for both humans and agents and maps each kind of task to the minimum set of documentation and source files that should be loaded.

## Scope

The current version focuses on project inspection and shallow project validation, plus compilation delegated to `openplc-cli`. Project modification, deployment, runtime control, variable forcing, authentication, HTTP transport, and generic shell/filesystem tools are not implemented.

See [`docs/scope.md`](docs/scope.md) for the current boundary.
