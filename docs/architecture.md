# Architecture

## Current boundary

```text
MCP Host / LLM Agent
        |
        | MCP over stdio
        v
OpenPLC Engineering MCP
        |
        +-- project.py ----- current OpenPLC project files
        |
        +-- execution.py --- execution configuration in project.json
        |
        +-- io.py ---------- active device board and local physical I/O mapping
        |
        +-- pous.py -------- current OpenPLC POU source files
        |
        +-- variables.py --- POU and resource global variable declarations
        |
        +-- datatypes.py --- datatypes/*.dt
        |
        +-- compiler.py ---- openplc-cli
```

The server provides a small domain-oriented interface between an MCP-compatible agent and a local OpenPLC engineering environment.

## Design principles

1. **Keep the boundary domain-oriented.** Expose PLC engineering operations rather than generic shell or filesystem tools.
2. **Use the official MCP SDK.** Do not reproduce transport, discovery, tool-calling, or protocol behavior already provided by the SDK.
3. **Keep OpenPLC authoritative.** Do not copy the complete OpenPLC project schema or reimplement compilation semantics inside the MCP server.
4. **Support the current project format only.** Historical OpenPLC project representations, migrations, and compatibility fallbacks are outside the architecture boundary.
5. **Prefer small functions and direct code.** Add layers only when a concrete requirement makes them necessary.
6. **Expand capabilities incrementally.** Current inspection and diagnostics operations are read-only. Compilation is the only local write-capable operation and delegates to `openplc-cli`.

## Module responsibilities

### `server.py`

Responsible for:

- creating the `MCPServer`;
- registering the eleven public MCP tools;
- applying tool annotations;
- exposing the package entry point;
- starting the stdio server.

It should stay thin. OpenPLC-specific behavior belongs in the `openplc` package.

### `openplc/project.py`

Responsible for project-level behavior shared by the other OpenPLC modules:

- resolving and checking project paths;
- reading and validating the minimum metadata from `project.json`;
- retaining the parsed project document for domain inspections that need it;
- providing the shared `data.configuration.resource` lookup;
- enforcing the minimum project preconditions;
- providing shallow project validation;
- listing relevant project files;
- providing the shared recognized-source-file scan used by POU and data-type discovery.

### `openplc/execution.py`

Responsible for configured execution-model inspection:

- reading `data.configuration.resource` from the validated project document;
- validating the Task and Program Instance fields required by the public contract;
- preserving cyclic IEC interval strings while returning no interval for interrupt Tasks;
- returning only Tasks and Program Instances, not neighboring configuration data.

### `openplc/io.py`

Responsible for configured local physical I/O inspection:

- applying the shared project-loading preconditions;
- reading the selected `deviceBoard` from the current device configuration;
- reading and validating the canonical per-board `DevicePin` mapping;
- returning only the active board's `pin`, `pin_type`, `address`, and optional `alias`;
- rejecting historical pin-mapping representations instead of migrating them;
- keeping communication settings, VPP vendor data, variables, and runtime state outside the contract.

The module is deliberately a focused device-I/O reader rather than a generic JSON or device service layer.

### `openplc/pous.py`

Responsible for POU behavior:

- discovering Programs, Function Blocks, and Functions from current POU source files;
- reading POU content by domain name;
- mapping recognized source suffixes to reported languages;
- returning deduplicated, sorted POU information.

### `openplc/variables.py`

Responsible for variable inspection:

- resolving the POU through the shared `read_pou()` behavior;
- extracting variables from current POU source declarations using the block classes and restrictions the OpenPLC Editor applies;
- preserving declaration order and declaration-level type strings;
- listing resource-level global variables from `data.configuration.resource.globalVariables`;
- raising tool errors when declarations cannot be interpreted reliably.

### `openplc/datatypes.py`

Responsible for project-defined data-type inspection:

- reading canonical `datatypes/**/*.dt` files;
- parsing only the enumerated, structure, and array forms persisted by the current OpenPLC Editor;
- enforcing the `.dt` filename as the data type identity;
- returning domain-readable declared types without exposing OpenPLC's internal variable-type objects;
- raising tool errors instead of returning partial results for malformed definitions.

It is deliberately not a generic IEC parser or a data-type service layer.

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
   ├── openplc.execution
   ├── openplc.io
   ├── openplc.pous
   ├── openplc.variables
   ├── openplc.datatypes
   └── openplc.compiler

openplc.execution ─► openplc.project
openplc.io ─────────► openplc.project
openplc.pous ──────► openplc.project
openplc.variables ─► openplc.pous, openplc.project
openplc.datatypes ─► openplc.project
openplc.compiler ──► openplc.project
```

`project.py` does not depend on the execution, I/O, POU, variable, data-type, or compiler modules. It is the shared lower-level dependency for local project loading, current configuration-resource lookup, and recognized source-file discovery.

There are no service, repository, adapter, client, project-version resolver, or one-file-per-tool layers.

## State

Most behavior is stateless. The only current process state is the latest compiler diagnostics stored by `openplc/compiler.py` for each resolved project path. This state is replaced by a later compilation of the same project and disappears when the server process stops.

## Transport

The current transport is stdio through the official MCP Python SDK.

HTTP transport, authentication, deployment, and runtime control are outside the current implementation boundary. See [`scope.md`](scope.md).
