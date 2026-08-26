# Getting started

Use this document for local setup and execution only.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js/npm only when using MCP Inspector through `mcp dev`

## Install

```bash
git clone https://github.com/industrix-com-br/openplc-engineering-mcp.git
cd openplc-engineering-mcp
uv sync
```

## Run the MCP server

The package exposes the `openplc-engineering-mcp` console script and uses stdio transport.

```bash
uv run openplc-engineering-mcp
```

## Open with MCP Inspector

```bash
uv run mcp dev src/openplc_engineering_mcp/server.py --with-editable .
```

## Verify the project

```bash
uv run pytest
uv run ruff check .
uv run pyright
```

For test conventions and development rules, continue with [`development.md`](development.md).
