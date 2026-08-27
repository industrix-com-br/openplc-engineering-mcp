# MCP tools

Inspection tools are read-only and operate within the bounded local OpenPLC project context. `compile_project` is the single exception: it is a local write operation that invokes the authoritative `openplc-cli`.

The public registrations live in `src/openplc_engineering_mcp/server.py`. OpenPLC project behavior is grouped by responsibility under `src/openplc_engineering_mcp/openplc/`.

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

See [`openplc-projects.md`](openplc-projects.md) for language and deduplication behavior.

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

The tool intentionally does not claim compiler-level or runtime-level validity. See [`openplc-projects.md`](openplc-projects.md).

## `compile_project`

Input:

- `project_path: str`

Runs `openplc-cli compile ./project --json` and returns:

- `success`: whether the CLI exited with status `0`;
- `exit_code`: the CLI exit code;
- `output`: the parsed JSON result from the CLI (or `null` when stdout is empty).

The command must be `openplc-cli` on `PATH`, otherwise an MCP tool error is raised. Compiler diagnostics are captured from the CLI's `stderr` for the [`get_diagnostics`](#get_diagnostics) tool.

This is the only non-read-only tool; it is registered with `read_only_hint: false` because compilation is a local write operation.

## `get_diagnostics`

Input:

- `project_path: str`

Returns the `stderr` diagnostics from the project's most recent [`compile_project`](#compile_project) call as a list of lines. Raises an MCP tool error when the project has not been compiled yet.

## Adding a tool

Before adding a new tool:

1. verify that the operation belongs inside the current scope;
2. keep the public tool domain-oriented;
3. keep the MCP registration in `server.py` thin;
4. place OpenPLC-specific behavior in the smallest cohesive domain module;
5. test MCP contract behavior through the official MCP SDK client;
6. test domain behavior in the corresponding domain test module;
7. update this document when the public tool contract changes.
