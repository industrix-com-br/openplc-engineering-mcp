# openplc-engineering-mcp

A small experimental Python MCP server that exposes domain-oriented engineering operations for the [OpenPLC Editor](https://github.com/Autonomy-Logic/openplc-editor) project.

The project uses the official Model Context Protocol Python SDK and stdio transport. Inspection tools are read-only; compilation is delegated to the authoritative `openplc-cli`.

**[Documentation](https://industrix-com-br.github.io/openplc-engineering-mcp/)**

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
- `list_datatypes`
- `get_execution_configuration`
- `read_pou`
- `list_variables`
- `list_global_variables`
- `validate_project`
- `compile_project`
- `get_diagnostics`

Inspection tools are read-only. `compile_project` is a local write operation that requires `openplc-cli` on `PATH`.

## Documentation

Read the [published documentation](https://industrix-com-br.github.io/openplc-engineering-mcp/) for setup, architecture, MCP tools, OpenPLC project behavior, development, scope, and research context.

The source documentation remains in [`docs/`](docs/) and [`docs/index.md`](docs/index.md) is the entry point for agents working directly with the repository.

## Scope

This MCP supports only the **current OpenPLC Editor project format**. Legacy OpenPLC project formats, historical project representations, automatic migration, and backward-compatibility parsing are intentionally unsupported.

The current version focuses on project, execution-configuration, POU, data-type, and variable inspection and shallow project validation, plus compilation delegated to `openplc-cli`. Project modification, data-type modification, variable modification, deployment, runtime control, variable forcing, authentication, HTTP transport, and generic shell/filesystem tools are not implemented.

See [`docs/scope.md`](docs/scope.md) for the current boundary.
