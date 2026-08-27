# Architecture

## Current boundary

```text
MCP Host / LLM Agent
        |
        | MCP
        v
OpenPLC Engineering MCP
        |
        v
OpenPLC project
```

The server provides a small domain-oriented interface between an MCP-compatible agent and OpenPLC engineering data.

## Design principles

1. **Keep the boundary domain-oriented.** Expose PLC engineering operations rather than generic shell or filesystem tools.
2. **Use the official MCP SDK.** Do not reproduce transport, discovery, tool-calling, or protocol behavior already provided by the SDK.
3. **Keep OpenPLC authoritative.** Do not copy the complete OpenPLC project schema or reimplement OpenPLC loading semantics inside the MCP server.
4. **Prefer small functions and direct code.** Add layers only when a concrete requirement makes them necessary.
5. **Expand capabilities incrementally.** The inspection surface is read-only; the only write operation is `compile_project`, which delegates to the authoritative `openplc-cli`. The server should not carry architecture for hypothetical future operations.

## Module responsibilities

### `server.py`

Responsible for:

- creating the `MCPServer`;
- registering public MCP tools;
- applying tool annotations;
- exposing the package entry point;
- starting the stdio server.

It should stay thin. OpenPLC-specific behavior belongs in the `openplc` package.

### `openplc/project.py`

Responsible for project-level behavior:

- checking the minimum filesystem preconditions for an OpenPLC project;
- reading basic project metadata;
- providing shallow project validation;
- listing relevant project files.

### `openplc/pous.py`

Responsible for POU behavior:

- discovering programs, function blocks, and functions;
- recognizing supported POU representations;
- preferring source representations over JSON when both exist;
- keeping POU discovery logic together for future POU read/write operations.

### `openplc/compiler.py`

Responsible for compiler behavior:

- delegating compilation to `openplc-cli`;
- parsing the CLI JSON result;
- capturing compiler diagnostics from `stderr`;
- returning diagnostics from the most recent compilation.

Compilation shells out to the authoritative `openplc-cli` rather than reimplementing the compiler. A separate CLI abstraction is not needed while compilation is the only feature that executes it.

## Dependency direction

```text
server.py
   ├── openplc.project
   ├── openplc.pous
   └── openplc.compiler

openplc.pous ──────► openplc.project
openplc.compiler ──► openplc.project
```

`project.py` does not depend on the POU or compiler modules. This keeps project loading as the shared lower-level dependency without adding service, repository, adapter, or client layers.

## Transport

The current transport is stdio through the official MCP Python SDK.

HTTP transport, authentication, sessions, deployment, and runtime control are outside the current implementation boundary. See [`scope.md`](scope.md).
