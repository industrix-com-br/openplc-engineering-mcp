# MCP tools

The current server registers exactly ten domain-oriented tools. All tools use `open_world_hint: false`. Inspection and diagnostics tools are read-only; `compile_project` is registered with `read_only_hint: false` because the OpenPLC CLI may write local build artifacts.

The public registrations live in `src/openplc_engineering_mcp/server.py`. OpenPLC behavior is grouped by responsibility under `src/openplc_engineering_mcp/openplc/`.

| Tool | Read-only | Purpose |
| --- | --- | --- |
| `get_project_structure` | yes | Inspect recognized files in an OpenPLC project |
| `list_pous` | yes | Discover Programs, Function Blocks, and Functions |
| `list_datatypes` | yes | Inspect project-defined enumerated, structure, and array data types |
| `get_execution_configuration` | yes | Inspect configured Tasks and Program Instances |
| `read_pou` | yes | Read a POU by domain name without requiring its filesystem path |
| `list_variables` | yes | Inspect variables declared by a POU |
| `list_global_variables` | yes | Inspect the project's resource-level global variables |
| `validate_project` | yes | Check the MCP's shallow project preconditions |
| `compile_project` | no | Compile through `openplc-cli` |
| `get_diagnostics` | yes | Return diagnostics captured from the latest compilation |

## `get_project_structure`

Input:

- `project_path: str`

Returns:

- resolved project `path`;
- project `name`;
- project `type`;
- sorted list of recognized project `files`.

Use [`openplc-projects.md`](openplc-projects.md) for the recognized layout.

## `list_pous`

Input:

- `project_path: str`

Returns the recognized Programs, Function Blocks, and Functions. Each item contains:

- `name`;
- `type`;
- `language`;
- project-relative `path`.

See [`openplc-projects.md`](openplc-projects.md) for language mapping and deduplication behavior.

## `list_datatypes`

Input:

- `project_path: str`.

Returns only the **project-defined data types** known to the OpenPLC project, sorted by name. The current OpenPLC persistence format is authoritative when one or more files exist under `datatypes/**/*.dt`; legacy `project.json.data.dataTypes` is used only when no `.dt` files exist.

The first version exposes the three data-type derivations currently represented by OpenPLC.

Enumeration:

```json
{
  "name": "OperatingMode",
  "kind": "enumerated",
  "values": ["Auto", "Manual", "Maintenance"],
  "initial_value": "Auto"
}
```

Structure:

```json
{
  "name": "MotorStatus",
  "kind": "structure",
  "fields": [
    {
      "name": "speed",
      "type": "REAL",
      "initial_value": "0.0",
      "documentation": "Current motor speed"
    }
  ]
}
```

Array:

```json
{
  "name": "TemperatureBuffer",
  "kind": "array",
  "base_type": "REAL",
  "dimensions": ["0..99"],
  "initial_value": null
}
```

Declared field types and initial values remain strings. Inline array fields therefore remain domain-readable declarations such as `ARRAY [0..9] OF REAL`; IEC literals are not evaluated. Multidimensional array bounds are returned independently.

Each `.dt` file must contain exactly one supported `TYPE ... END_TYPE` declaration, and its declared type name must match the file name case-insensitively. Malformed or unsupported definitions raise a tool error; the MCP does not silently skip a bad type and return a partial project view. A valid project with no project-defined data types returns an empty list.

The first version intentionally does not provide:

- built-in IEC type listing;
- OpenPLC library data-type discovery;
- data-type creation, modification, or deletion;
- `read_datatype()` or `get_datatype()`;
- reference search, dependency graphs, or recursive type resolution;
- semantic validation of references between types;
- a complete IEC 61131-3 grammar or AST.

See [`openplc-projects.md`](openplc-projects.md) for the persistence and migration behavior.

## `get_execution_configuration`

Input:

- `project_path: str`.

Returns the configured execution model of the project:

```json
{
  "tasks": [
    {
      "name": "MainTask",
      "triggering": "Cyclic",
      "interval": "T#20ms",
      "priority": 0
    }
  ],
  "program_instances": [
    {
      "name": "MainInstance",
      "task": "MainTask",
      "program": "main"
    }
  ]
}
```

Each Task contains its name, triggering mode, priority, and execution interval. For a `Cyclic` Task, `interval` preserves the stored IEC `TIME` string exactly. For an `Interrupt` Task, the MCP returns `interval: null` rather than presenting the stored interval field as cyclic timing.

Each Program Instance contains its name, the Task reference, and the Program reference exactly as stored by OpenPLC. The MCP does not independently validate those references or evaluate IEC time literals.

A project with no execution configuration returns:

```json
{
  "tasks": [],
  "program_instances": []
}
```

Malformed Task or Program Instance structures that cannot be represented reliably are MCP tool errors. Global variables and other neighboring `project.json` data are intentionally outside this tool.

This tool reports the **configured execution model of the project**. It does not report which code is currently executing in a live OpenPLC Runtime; live execution state belongs to future runtime/debug tools.

See [`openplc-projects.md`](openplc-projects.md) for the project representation this inspection depends on.

## `read_pou`

Input:

- `project_path: str`;
- `pou_name: str`.

Returns one recognized POU with:

- `name`;
- `type`;
- `language`;
- project-relative `path`;
- `content` exactly as read from the selected UTF-8 source file.

The caller identifies the POU by name rather than by filesystem path. `read_pou()` uses the same discovery and representation preference rules as `list_pous()`: a recognized source representation is preferred over a same-name `.json` representation, while JSON-only POUs remain readable with `language: null`.

An empty `pou_name`, an unknown POU name, or an unreadable source file is exposed as an MCP tool error. The first version intentionally performs no parsing, normalization, dependency analysis, or modification of the POU content.

See [`openplc-projects.md`](openplc-projects.md) for the underlying project behavior.

## `list_variables`

Input:

- `project_path: str`;
- `pou_name: str`.

Returns the variables declared by the selected POU in declaration order. Each item contains:

```json
{
  "name": "Start",
  "class": "input",
  "type": "BOOL",
  "location": null,
  "initial_value": null,
  "documentation": null
}
```

Supported variable classes are:

| OpenPLC declaration block | MCP class |
| --- | --- |
| `VAR_INPUT` | `input` |
| `VAR_OUTPUT` | `output` |
| `VAR_IN_OUT` | `inOut` |
| `VAR_EXTERNAL` | `external` |
| `VAR_TEMP` | `temp` |
| `VAR_GLOBAL` | `global` |
| `VAR` | `local` |

The `type` field preserves the declared type as a domain-readable string such as `BOOL`, `TON`, or `ARRAY[0..9] OF INT`. Initial values remain declaration-level strings and are not evaluated. A declared `AT` binding is returned as `location`; absent location, initial value, or documentation is returned as `null`.

`list_variables()` builds on `read_pou()` and therefore uses the same POU name resolution and representation preference. Recognized source representations are inspected for declaration blocks. A selected legacy JSON-only POU is read from its structured variable data rather than interpreted as IEC source text.

A valid POU with no variable declarations returns an empty list. Empty or unknown POU names, unsupported JSON variable representations, and malformed declarations that prevent reliable extraction are MCP tool errors. Parse failures are not converted to an empty list.

The first version intentionally does not provide:

- variable creation or updates;
- project-wide variable search or reference analysis;
- runtime variable reads, forcing, or debug state;
- dependency analysis;
- a structured mirror of OpenPLC's internal type model.

See [`openplc-projects.md`](openplc-projects.md) for the OpenPLC behavior this extraction depends on.

## `list_global_variables`

Input:

- `project_path: str`.

Returns the project's **resource-level global variables** — exactly the entries stored under `data.configuration.resource.globalVariables` — in stored order. Each item uses the same public variable representation as [`list_variables`](#list_variables):

```json
{
  "name": "EmergencyStop",
  "class": "global",
  "type": "BOOL",
  "location": "%IX0.0",
  "initial_value": null,
  "documentation": "Emergency stop input"
}
```

`class` is always `global` because the containing resource defines the scope, regardless of any stored class field. Declared types and initial values are preserved as strings; empty stored optional values (`""`) are normalized to `null` exactly like `list_variables()`.

The tool intentionally returns only `configuration.resource.globalVariables`. It does not scan POUs for `VAR_GLOBAL` declarations and it does not include named global variable lists (`globalVariableLists` / GVLs); those are separate domain concepts.

```text
list_variables(project_path, pou_name)    -> variables declared by one POU
list_global_variables(project_path)       -> configuration.resource.globalVariables
```

A project with no execution configuration or no `globalVariables` returns an empty list. A non-array `globalVariables` value, or an individual variable that cannot be represented reliably, is raised as an MCP tool error rather than being converted into an empty result.

See [`openplc-projects.md`](openplc-projects.md) for the underlying project representation.

## `validate_project`

Input:

- `project_path: str`

Returns a successful shallow validation result:

```json
{
  "valid": true,
  "name": "Example",
  "type": "plc-project",
  "warnings": []
}
```

Unrecoverable local precondition failures are MCP tool errors rather than `{ "valid": false }` results.

The tool does not perform compiler-level or runtime-level validation. See [`openplc-projects.md`](openplc-projects.md).

## `compile_project`

Input:

- `project_path: str`

After resolving and validating the project path, the implementation runs:

```text
openplc-cli compile <resolved-project-path> --json
```

It returns:

- `success`: whether the CLI exited with status `0`;
- `exit_code`: the CLI exit code;
- `output`: parsed JSON from CLI `stdout`, or `null` when `stdout` is empty.

The command must be available as `openplc-cli` on `PATH`. A missing executable, an OS error while starting the process, or non-JSON non-empty `stdout` is exposed as an MCP tool error.

Non-empty lines from CLI `stderr` are captured as diagnostics for [`get_diagnostics`](#get_diagnostics).

## `get_diagnostics`

Input:

- `project_path: str`

Returns the `stderr` lines captured from the project's most recent `compile_project` call.

Diagnostics are intentionally process-local:

- they are stored in memory, keyed by the resolved project path;
- a later compilation of the same project replaces the previous diagnostics;
- they are not persisted across server restarts;
- calling this tool before a compilation for that project raises an MCP tool error.

An executed compilation with no `stderr` produces an empty list.

## Adding a tool

Before adding a new tool:

1. verify that the operation belongs inside the current scope;
2. keep the public tool domain-oriented;
3. keep the MCP registration in `server.py` thin;
4. place OpenPLC-specific behavior in the smallest cohesive domain module;
5. test MCP contract behavior through the official MCP SDK client;
6. test domain behavior in the corresponding domain test module;
7. update this document when the public tool contract changes.
