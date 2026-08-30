# Scope

## Current implementation

The project is an early experimental MCP server for local OpenPLC engineering operations. It currently exposes twelve tools:

- `get_project_structure` — inspect recognized project files;
- `list_pous` — discover Programs, Function Blocks, and Functions;
- `list_datatypes` — inspect project-defined enumerated, structure, and array data types;
- `get_execution_configuration` — inspect configured Tasks and Program Instances;
- `get_io_configuration` — inspect the selected device board and its active local physical I/O mapping;
- `read_pou` — read a POU by domain name;
- `update_pou` — replace the complete content of an existing Structured Text POU;
- `list_variables` — inspect variables declared by a POU;
- `list_global_variables` — inspect the project's resource-level global variables;
- `validate_project` — check shallow local project preconditions;
- `compile_project` — compile through `openplc-cli`;
- `get_diagnostics` — return `stderr` diagnostics captured from the latest compilation in the current server process.

Project, execution-configuration, physical-I/O, data-type, POU, variable, and diagnostic inspection is read-only. The only local write-capable operations are `update_pou`, which atomically replaces one existing Structured Text POU file, and compilation, which is delegated to the authoritative `openplc-cli`.

## Project format

The MCP supports only the **current OpenPLC Editor project format**.

Supported:

- current OpenPLC Editor projects;
- current POU source files under `pous/`;
- current `data.configuration` execution/resource representation;
- current `datatypes/*.dt` project-defined data types;
- current `devices/configuration.json` board selection;
- current per-board `devices/pin-mapping.json` local physical I/O mappings.

Intentionally unsupported:

- legacy OpenPLC project formats;
- historical JSON POU representations;
- historical project representations such as `data.configurations` and embedded `data.dataTypes` data-type definitions;
- historical flat pin-mapping arrays and legacy pin `name` fields;
- automatic migration or backward-compatibility parsing.

The MCP does not detect, convert, or normalize historical project versions. A legacy representation may be ignored when it is outside a tool's recognized current layout or rejected when it would otherwise make the result ambiguous.

## OpenPLC Editor compatibility

The current MCP feature set targets the OpenPLC Editor `development` branch after the upstream changes merged on August 24, 2026 for:

- `datatypes/*.dt` persistence (OpenPLC Editor PR #999);
- the headless CLI used by compilation (OpenPLC Editor PR #1026).

No published OpenPLC Editor release currently provides that complete feature set. The latest release, v4.2.11 from August 11, 2026, predates both changes.

The native text-based POU representation itself was introduced earlier by OpenPLC Editor PR #411 and shipped in v4.1.0. Therefore v4.1.0 marks the POU-format breakline, but it is **not** a complete compatibility baseline for this MCP.

Detailed project-format behavior is documented in [`openplc-projects.md`](openplc-projects.md).

## Current boundary

The implementation currently covers:

- local current-format OpenPLC Editor project paths;
- basic `project.json` metadata preconditions;
- recognized project-file inspection;
- configured execution Tasks and Program Instances;
- selected device board and active local `DevicePin` mapping inspection;
- project-defined data-type inspection from `datatypes/*.dt` files;
- POU discovery;
- POU content reading;
- Structured Text POU content replacement;
- POU variable/interface discovery;
- resource-level global variable inspection;
- CLI compilation;
- process-local compiler diagnostics;
- stdio MCP transport.

## Not implemented yet

The current server does not provide:

- POU creation, deletion, renaming, type conversion, or language conversion;
- writes to POUs in languages other than Structured Text;
- project, execution, device, data-type, or resource-level configuration modification;
- data-type creation, modification, deletion, or recursive resolution;
- built-in IEC or OpenPLC library data-type discovery;
- variable creation or modification;
- project-wide variable or reference search;
- vendor-specific VPP configuration inspection or reinterpretation;
- communication configuration or protocol-specific device inspection;
- remote-device inspection;
- deployment or upload;
- controller start/stop;
- runtime or debug sessions;
- live runtime execution or I/O state;
- runtime variable reads;
- variable forcing or releasing;
- dependency analysis;
- authentication;
- HTTP transport.

These are not all permanent exclusions. They should be added only when a concrete requirement exists and the smallest useful domain-level contract can be defined.

## Architectural non-goals

The MCP should not become:

- a generic filesystem API;
- a generic shell execution API;
- a duplicate implementation of the OpenPLC project schema;
- a project-format migration or compatibility layer;
- a complete IEC 61131-3 parser;
- a replacement for the OpenPLC Editor, CLI, compiler, or runtime;
- a framework of abstractions created only for possible future features.

## Expansion rule

Before adding a capability, ask:

1. Is this required by a real engineering workflow or experiment?
2. Can the operation be expressed as a PLC engineering concept rather than a low-level implementation detail?
3. Can existing OpenPLC behavior remain authoritative?
4. Can it be implemented without adding unnecessary layers?
5. Is it required to correctly support a project created by the current OpenPLC Editor?

If the answer is not clear, keep the current boundary unchanged.
