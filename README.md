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

OpenPLC project inspection follows the current Editor layout: `project.json` at the project root, POUs below `pous/programs`, `pous/function-blocks`, and `pous/functions`, plus the related device and datatype locations used by the Editor.

## Scope

This version is intentionally read-only and experimental. It does not include project modification, compilation, deployment, runtime control, variable forcing, authentication, HTTP transport, or unrestricted shell/filesystem access. Those capabilities should be added only when concrete requirements justify them.
