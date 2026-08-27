# MCP tools

The current server registers exactly five domain-oriented tools. All tools use `open_world_hint: false`. Inspection and diagnostics tools are read-only; `compile_project` is registered with `read_only_hint: false` because the OpenPLC CLI may write local build artifacts.

The public registrations live in `src/openplc_engineering_mcp/server.py`. OpenPLC behavior is grouped by responsibility under `src/openplc_engineering_mcp/openplc/`.

| Tool | Read-only | Purpose |
| --- | --- | --- |
| `get_project_structure` | yes | Inspect recognized files in an OpenPLC project |
| `list_pous` | yes | Discover Programs, Function Blocks, and Functions |
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
