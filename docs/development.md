# Development

## Local checks

Install dependencies:

```bash
uv sync
```

Run the test suite:

```bash
uv run pytest
```

Run linting:

```bash
uv run ruff check .
```

Run static type checking:

```bash
uv run pyright
```

The project configuration for dependencies, Ruff, and Pyright is in `pyproject.toml`.

## Test approach

Tests should exercise MCP tools through the official SDK's in-memory `Client(mcp)` interface rather than calling registered tool functions directly.

This verifies the public MCP boundary, tool discovery, structured content, annotations, and tool-error behavior.

Current MCP integration coverage is in `tests/test_server.py`.

## Change workflow

For implementation changes:

1. read [`index.md`](index.md) and load only the relevant documents;
2. inspect the implementation and existing tests for the affected behavior;
3. make the smallest change that satisfies the requirement;
4. add or update tests at the public MCP boundary;
5. run `pytest`, `ruff`, and `pyright`;
6. update only the documentation whose contract or explanation changed.

## Documentation rule

Do not turn `README.md` or a single document into a complete project manual. Keep detailed knowledge in focused files and keep [`index.md`](index.md) accurate so agents can discover the right context without loading everything.
