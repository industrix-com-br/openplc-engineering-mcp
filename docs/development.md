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

`tests/test_stdio_e2e.py` validates the deployable MCP boundary: the SDK launches a separate server process with the current Python interpreter (`-m openplc_engineering_mcp.server`) and communicates over real stdio. It covers initialization, tool discovery, project validation, and a POU read/update/read round trip. SDK context managers own process cleanup, and protocol waits are bounded. This test runs in the normal suite without OpenPLC or `openplc-cli`.

Keep domain implementation behavior close to the implementation modules:

- `tests/test_project.py` for project loading, validation, and structure inspection;
- `tests/test_execution.py` for Task and Program Instance inspection;
- `tests/test_io.py` for physical I/O configuration inspection;
- `tests/test_pous.py` for POU discovery, reading, and update behavior;
- `tests/test_variables.py` for POU and resource-level global variable inspection;
- `tests/test_datatypes.py` for project-defined data-type inspection;
- `tests/test_compiler.py` for CLI compilation and diagnostics.

Direct domain tests are appropriate for implementation behavior. MCP registration behavior should remain in `test_server.py` rather than being repeated in every domain test.

## Documentation site

The files in `docs/` are the single source for the MkDocs site.

Build locally with:

```bash
python -m pip install -r requirements-docs.txt
mkdocs serve
```

Changes merged to `main` are published by `.github/workflows/docs.yml`. GitHub Pages must use **GitHub Actions** as its publishing source.

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
