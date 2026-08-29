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
| Add or change an MCP tool | [`tools.md`](tools.md), [`architecture.md`](architecture.md) | `src/openplc_engineering_mcp/server.py`, relevant `src/openplc_engineering_mcp/openplc/` module, `tests/test_server.py` |
| Change OpenPLC project discovery or validation | [`openplc-projects.md`](openplc-projects.md), [`tools.md`](tools.md) | `src/openplc_engineering_mcp/openplc/project.py`, `tests/test_project.py` |
| Change POU discovery or access | [`openplc-projects.md`](openplc-projects.md), [`tools.md`](tools.md) | `src/openplc_engineering_mcp/openplc/pous.py`, `tests/test_pous.py` |
| Change POU variable inspection | [`openplc-projects.md`](openplc-projects.md), [`tools.md`](tools.md) | `src/openplc_engineering_mcp/openplc/variables.py`, `tests/test_variables.py` |
| Change OpenPLC compilation or diagnostics | [`tools.md`](tools.md), [`architecture.md`](architecture.md) | `src/openplc_engineering_mcp/openplc/compiler.py`, `tests/test_compiler.py` |
| Change MCP registration or transport behavior | [`architecture.md`](architecture.md), [`tools.md`](tools.md) | `src/openplc_engineering_mcp/server.py`, `tests/test_server.py` |
| Add or update tests, linting, or type checking | [`development.md`](development.md) | `pyproject.toml`, relevant tests |
| Decide whether a feature belongs in the current implementation | [`scope.md`](scope.md), [`architecture.md`](architecture.md) | [`research.md`](research.md) when the research rationale matters |
| Understand the thesis / experimental role of the repository | [`research.md`](research.md) | [`scope.md`](scope.md), [`architecture.md`](architecture.md) |

## Document map

### [`getting-started.md`](getting-started.md)

Load for installation, execution, MCP Inspector, and local verification commands.

### [`architecture.md`](architecture.md)

Load for system boundaries, module responsibilities, dependency direction, and process state.

### [`tools.md`](tools.md)

Load for the current seven MCP tools, inputs, outputs, annotations, errors, and diagnostics behavior.

### [`openplc-projects.md`](openplc-projects.md)

Load for project preconditions, recognized project layout, POU discovery, validation, and CLI integration semantics.

### [`development.md`](development.md)

Load for tests, linting, type checking, and the expected change workflow.

### [`scope.md`](scope.md)

Load before adding new capabilities. It defines what exists now and what is intentionally absent.

### [`research.md`](research.md)

Load only when a task depends on the research objective or experimental design of the project.

## Source map

The implementation is intentionally small and organized by domain responsibility:

| File | Responsibility |
| --- | --- |
| `src/openplc_engineering_mcp/server.py` | MCP server creation, seven tool registrations, annotations, and stdio entry point |
| `src/openplc_engineering_mcp/openplc/project.py` | Project loading preconditions, shallow validation, structure inspection, and shared source-file scanning |
| `src/openplc_engineering_mcp/openplc/pous.py` | POU discovery and reading, language mapping, representation preference, and deduplication |
| `src/openplc_engineering_mcp/openplc/variables.py` | POU variable extraction from source declarations or structured JSON POU data |
| `src/openplc_engineering_mcp/openplc/compiler.py` | `openplc-cli` compilation, JSON output parsing, and process-local diagnostics |
| `tests/test_server.py` | MCP-level contract tests using the official SDK client |
| `tests/test_project.py` | Project behavior tests |
| `tests/test_pous.py` | POU behavior tests |
| `tests/test_variables.py` | POU variable extraction tests |
| `tests/test_compiler.py` | Compiler and diagnostics behavior tests |
| `pyproject.toml` | Package metadata, dependencies, scripts, linting, and type-checking configuration |

## Documentation maintenance

Keep each document focused on one concern. When a document starts mixing unrelated concerns, split it and update this index rather than growing a single large reference file.
