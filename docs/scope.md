# Scope

## Current implementation

The project is an early experimental, read-only MCP server for OpenPLC engineering inspection.

It currently provides:

- MCP server metadata;
- OpenPLC project structure inspection;
- POU discovery;
- shallow project validation.

## Not implemented yet

The current server does not provide:

- project or POU modification;
- variable creation or modification;
- compilation;
- compiler diagnostics;
- deployment or upload;
- controller start/stop;
- runtime sessions;
- runtime variable reads;
- variable forcing or releasing;
- authentication;
- HTTP transport.

These are not all permanent exclusions. They should be added only when a concrete requirement exists and the smallest useful domain-level contract can be defined.

## Architectural non-goals

The MCP should not become:

- a generic filesystem API;
- a generic shell execution API;
- a duplicate implementation of the OpenPLC project schema;
- a replacement for the OpenPLC Editor, CLI, compiler, or runtime;
- a framework of abstractions created only for possible future features.

## Expansion rule

Before adding a capability, ask:

1. Is this required by a real engineering workflow or experiment?
2. Can the operation be expressed as a PLC engineering concept rather than a low-level implementation detail?
3. Can existing OpenPLC behavior remain authoritative?
4. Can it be implemented without adding unnecessary layers?

If the answer is not clear, keep the current boundary unchanged.
