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

Use `tests/test_server.py` for MCP-level contract coverage through the official SDK's in-memory `Client(mcp)` interface. This verifies tool discovery, annotations, structured content, and tool-error behavior.

Keep domain implementation behavior close to the implementation modules:

- `tests/test_project.py` for project loading, validation, and structure inspection;
- `tests/test_pous.py` for POU discovery behavior;
- `tests/test_compiler.py` for CLI compilation and diagnostics.

Direct domain tests are appropriate for implementation behavior. MCP registration behavior should remain in `test_server.py` rather than being repeated in every domain test.

## Change workflow

For implementation changes:

1. read [`index.md`](index.md) and load only the relevant documents;
2. inspect the implementation and existing tests for the affected behavior;
3. make the smallest change that satisfies the requirement;
4. update domain tests and MCP boundary tests where relevant;
5. run `pytest`, `ruff`, `pyright`, and `uv build`;
6. update only the documentation whose contract or explanation changed.

## Documentation rule

Do not turn `README.md` or a single document into a complete project manual. Keep detailed knowledge in focused files and keep [`index.md`](index.md) accurate so agents can discover the right context without loading everything.
