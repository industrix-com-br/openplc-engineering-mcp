# Scope

## Current implementation

The project is an early experimental MCP server for local OpenPLC engineering operations. It currently exposes six tools:

- `get_project_structure` — inspect recognized project files;
- `list_pous` — discover Programs, Function Blocks, and Functions;
- `read_pou` — read a POU's preferred representation by domain name;
- `validate_project` — check shallow local project preconditions;
- `compile_project` — compile through `openplc-cli`;
- `get_diagnostics` — return `stderr` diagnostics captured from the latest compilation in the current server process.

Project inspection and diagnostics are read-only. Compilation is the only local write-capable operation and is delegated to the authoritative `openplc-cli`.

## Current boundary

The implementation currently covers:

- local OpenPLC Editor project paths;
- basic `project.json` metadata preconditions;
- recognized project-file inspection;
- POU discovery;
- POU content reading;
- CLI compilation;
- process-local compiler diagnostics;
- stdio MCP transport.

## Not implemented yet

The current server does not provide:

- project or POU modification;
- variable discovery, creation, or modification;
- deployment or upload;
- controller start/stop;
- runtime or debug sessions;
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
