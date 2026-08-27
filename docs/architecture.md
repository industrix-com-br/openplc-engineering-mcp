# Architecture

## Current boundary

```text
MCP Host / LLM Agent
        |
        | MCP over stdio
        v
OpenPLC Engineering MCP
        |
        +-- project.py ---- local OpenPLC project files
        |
        +-- pous.py ------- local OpenPLC project files
        |
        +-- compiler.py --- openplc-cli
```

The server provides a small domain-oriented interface between an MCP-compatible agent and a local OpenPLC engineering environment.

## Design principles

1. **Keep the boundary domain-oriented.** Expose PLC engineering operations rather than generic shell or filesystem tools.
2. **Use the official MCP SDK.** Do not reproduce transport, discovery, tool-calling, or protocol behavior already provided by the SDK.
3. **Keep OpenPLC authoritative.** Do not copy the complete OpenPLC project schema or reimplement compilation semantics inside the MCP server.
4. **Prefer small functions and direct code.** Add layers only when a concrete requirement makes them necessary.
5. **Expand capabilities incrementally.** Current inspection and diagnostics operations are read-only. Compilation is the only local write-capable operation and delegates to `openplc-cli`.

## Module responsibilities

### `server.py`

Responsible for:

- creating the `MCPServer`;
- registering the five public MCP tools;
- applying tool annotations;
- exposing the package entry point;
- starting the stdio server.

It should stay thin. OpenPLC-specific behavior belongs in the `openplc` package.

### `openplc/project.py`

Responsible for project-level behavior shared by the other OpenPLC modules:

- resolving and checking project paths;
- reading basic metadata from `project.json`;
- enforcing the minimum project preconditions;
- providing shallow project validation;
- listing relevant project files;
- providing the shared recognized-source-file scan used by POU discovery.

### `openplc/pous.py`

Responsible for POU behavior:

- discovering Programs, Function Blocks, and Functions;
- mapping recognized suffixes to reported languages;
- preferring a source representation over JSON when both exist;
- returning deduplicated, sorted POU information.

### `openplc/compiler.py`

Responsible for compiler behavior:

- validating the project through the shared `load_project()` preconditions;
- delegating compilation to `openplc-cli`;
- parsing non-empty CLI `stdout` as JSON;
- capturing non-empty `stderr` lines as diagnostics;
- keeping the latest diagnostics in process memory per resolved project path.

A separate CLI abstraction is not needed while compilation is the only feature that executes `openplc-cli`.

## Dependency direction

```text
server.py
   ├── openplc.project
   ├── openplc.pous
   └── openplc.compiler

openplc.pous ──────► openplc.project
openplc.compiler ──► openplc.project
```

`project.py` does not depend on the POU or compiler modules. It is the shared lower-level dependency for local project loading and recognized source-file discovery.

There are no service, repository, adapter, client, or one-file-per-tool layers.

## State

Most behavior is stateless. The only current process state is the latest compiler diagnostics stored by `openplc/compiler.py` for each resolved project path. This state is replaced by a later compilation of the same project and disappears when the server process stops.

## Transport

The current transport is stdio through the official MCP Python SDK.

HTTP transport, authentication, deployment, and runtime control are outside the current implementation boundary. See [`scope.md`](scope.md).
