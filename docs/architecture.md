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
5. **Expand capabilities incrementally.** The current read-only server should not carry architecture for hypothetical future operations.

## Module responsibilities

### `server.py`

Responsible for:

- creating the `MCPServer`;
- registering public MCP tools;
- applying tool annotations;
- exposing the package entry point;
- starting the stdio server.

It should stay thin. OpenPLC-specific behavior belongs outside the MCP registration layer.

### `openplc.py`

Responsible for the current OpenPLC-facing behavior:

- checking the minimum filesystem preconditions for an OpenPLC project;
- reading basic project metadata;
- listing relevant project files;
- discovering POUs;
- providing shallow project validation.

## Dependency direction

`server.py` calls domain functions from `openplc.py`. The OpenPLC module does not depend on MCP tool registration.

This keeps protocol registration separate from project inspection without introducing additional service or repository layers that are not currently needed.

## Transport

The current transport is stdio through the official MCP Python SDK.

HTTP transport, authentication, sessions, deployment, and runtime control are outside the current implementation boundary. See [`scope.md`](scope.md).
