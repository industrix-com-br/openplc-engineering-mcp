# Documentation index

This file is the entry point for project documentation.

The documentation is organized for **progressive disclosure**: read this index first, then load only the files needed for the task at hand.

## Agent loading rule

1. Read this file first.
2. Identify the task in the routing table below.
3. Load only the listed documentation and source files.
4. Expand to other files only when the task actually requires them.
5. Treat code and tests as authoritative if they differ from documentation.

Do not load the entire `docs/` directory by default.

## Task routing

| Task | Read first | Then inspect when needed |
| --- | --- | --- |
| Understand the project quickly | [`architecture.md`](architecture.md), [`scope.md`](scope.md) | `README.md` |
| Install, run, or inspect the server | [`getting-started.md`](getting-started.md) | `pyproject.toml`, `src/openplc_engineering_mcp/server.py` |
| Add or change an MCP tool | [`tools.md`](tools.md), [`architecture.md`](architecture.md) | `src/openplc_engineering_mcp/server.py`, `src/openplc_engineering_mcp/openplc.py`, `tests/test_server.py` |
| Change OpenPLC project discovery or validation | [`openplc-projects.md`](openplc-projects.md), [`tools.md`](tools.md) | `src/openplc_engineering_mcp/openplc.py`, `tests/test_server.py` |
| Change MCP registration or transport behavior | [`architecture.md`](architecture.md), [`tools.md`](tools.md) | `src/openplc_engineering_mcp/server.py` |
| Add or update tests, linting, or type checking | [`development.md`](development.md) | `pyproject.toml`, `tests/test_server.py` |
| Decide whether a feature belongs in the current implementation | [`scope.md`](scope.md), [`architecture.md`](architecture.md) | [`research.md`](research.md) when the research rationale matters |
| Understand the thesis / experimental role of the repository | [`research.md`](research.md) | [`scope.md`](scope.md), [`architecture.md`](architecture.md) |

## Document map

### [`getting-started.md`](getting-started.md)

Load for installation, execution, MCP Inspector, and local verification commands.

### [`architecture.md`](architecture.md)

Load for system boundaries, module responsibilities, and architectural principles.

### [`tools.md`](tools.md)

Load for the current MCP tool inventory, inputs, outputs, and behavior.

### [`openplc-projects.md`](openplc-projects.md)

Load for the OpenPLC Editor project layout, POU discovery, and validation semantics.

### [`development.md`](development.md)

Load for tests, linting, type checking, and the expected change workflow.

### [`scope.md`](scope.md)

Load before adding new capabilities. It defines what exists now and what is intentionally absent.

### [`research.md`](research.md)

Load only when a task depends on the research objective or experimental design of the project.

## Source map

The implementation is intentionally small:

| File | Responsibility |
| --- | --- |
| `src/openplc_engineering_mcp/server.py` | MCP server creation, tool registration, annotations, and stdio entry point |
| `src/openplc_engineering_mcp/openplc.py` | OpenPLC project loading preconditions, project inspection, POU discovery, and validation |
| `tests/test_server.py` | MCP-level integration tests using the official SDK client |
| `pyproject.toml` | Package metadata, dependencies, scripts, linting, and type-checking configuration |

## Documentation maintenance

Keep each document focused on one concern. When a document starts mixing unrelated concerns, split it and update this index rather than growing a single large reference file.
