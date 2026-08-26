# Research context

Load this document only when a task depends on the academic or experimental purpose of the repository.

## Role of the repository

`openplc-engineering-mcp` is intended to serve as the software artifact for research on how LLM agents interact with IEC 61131-3 PLC engineering environments through a domain-specific Model Context Protocol interface.

The project itself is not the scientific contribution merely because it implements MCP. Its value is as an experimental integration layer that can be evaluated against lower-level agent access.

## Core comparison

The research can compare two interaction models:

```text
Baseline                         MCP

LLM Agent                        LLM Agent
  |                                |
  +-- filesystem                   | MCP
  +-- shell                        v
        |                    OpenPLC Engineering MCP
        v                           |
      OpenPLC                       v
                                 OpenPLC
```

The baseline requires the agent to understand project paths, representations, commands, and tool-specific details directly.

The MCP approach exposes PLC engineering concepts and encapsulates lower-level implementation details.

## Research question

The central question is whether a domain-specific MCP integration layer measurably changes the quality of LLM-agent interaction with a PLC engineering environment compared with direct file and command-line access.

Relevant dimensions include:

- task success and correctness;
- robustness and invalid operations;
- tool-call and token efficiency;
- implementation-specific context requirements;
- portability across models or agent frameworks;
- controllability of available operations.

## Implication for implementation

The implementation should remain suitable for controlled comparison. Prefer explicit domain operations and stable contracts over exposing generic mechanisms that would collapse the distinction between the MCP configuration and the direct-access baseline.

The repository should also remain small enough that experimental behavior can be understood, reproduced, and attributed to the integration boundary rather than to unnecessary framework complexity.
