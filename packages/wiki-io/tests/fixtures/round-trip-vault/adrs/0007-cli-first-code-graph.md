---
title: "ADR-0007: CLI-first surface for lattice-graph — `cg` before MCP"
category: adr
summary: v1 ships the cg console-script (on lattice-graph-core) plus 3 slash commands that shell to it; the MCP server adapter slips to v1.1 so the library boundary is exercised through a thin testable adapter first.
adr_id: "0007"
status: accepted
decision_date: 2026-05-07
deciders: [Patrick Sprowls]
supersedes:
superseded_by:
tags: [adr, lattice-graph, cli, mcp, adapters, scope]
updated: 2026-05-07
tokens: 530
---

# ADR-0007: CLI-first surface for lattice-graph — `cg` before MCP

**Status:** accepted (2026-05-07)

## Context

[[wiki/plugins/lattice-graph/lattice-graph]] needs to expose its query surface through some adapter — CLI, MCP server, slash commands, or all of the above. Building the MCP server first risks shipping a transport before the underlying library boundary is well exercised; a misshapen library forced through MCP first tends to grow MCP-specific quirks that leak back into the library.

## Decision

v1 ships the **`cg` console-script entry point** (on [[wiki/packages/lattice-graph-core/lattice-graph-core]]) plus **3 slash commands** that shell out to it. The MCP server adapter slips to **v1.1**.

Rationale: exercise the library boundary by use through a thin testable adapter (the CLI) before adding a second adapter (MCP). The CLI is small, scriptable, and trivially testable; if the library shape is wrong, it shows up in CLI ergonomics first and gets fixed cheaply.

## Consequences

- v1 ships sooner; MCP work is descoped from the v1 critical path.
- The CLI becomes the canonical adapter and reference implementation; the MCP adapter follows the same shape when it lands.
- Users who need MCP-first integration must wait for v1.1 or shell to `cg` from their MCP host as an interim.
- The library API is forced to be CLI-shaped (subcommands, JSON I/O, exit codes) — generally a healthy constraint, but may require minor reshaping when MCP arrives if MCP-native idioms differ.

## Related

- [[wiki/plugins/lattice-graph/lattice-graph]]
- [[wiki/packages/lattice-graph-core/lattice-graph-core]]
- [[wiki/adrs/0008-single-writer-code-db]]
