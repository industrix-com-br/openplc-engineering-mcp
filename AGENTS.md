# Agent instructions

This repository implements an MCP server for the [OpenPLC Editor](https://github.com/Autonomy-Logic/openplc-editor) project. Treat upstream OpenPLC behavior as authoritative when validating project semantics or CLI behavior.

1. Read [`docs/index.md`](docs/index.md) first.
2. Do not preload every document or source file.
3. Use the task routing table in `docs/index.md` to load only the relevant context.
4. Treat implementation and tests as the source of truth when documentation and code disagree.
5. Update the relevant focused document when behavior, architecture, tooling, or scope changes.
6. Keep documentation small and link to another document instead of duplicating detailed explanations.

Project principles:

- prefer the simplest implementation that solves the current requirement;
- use the official MCP Python SDK rather than reproducing SDK behavior;
- expose domain-oriented PLC engineering operations, not generic shell or filesystem access;
- do not reproduce OpenPLC validation or project semantics when OpenPLC can remain authoritative;
- add abstractions only when a concrete requirement justifies them.
