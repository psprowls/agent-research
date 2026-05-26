---
status: testing
phase: 38-graph-wiki-agent-graph-subcommand
source:
  - .planning/phases/38-graph-wiki-agent-graph-subcommand/38-01-SUMMARY.md
  - .planning/phases/38-graph-wiki-agent-graph-subcommand/38-02-SUMMARY.md
started: "2026-05-26T20:50:00Z"
updated: "2026-05-26T20:50:00Z"
---

## Current Test

number: 1
name: `graph-wiki-agent graph --help` shows 3 subcommands (SC#1)
expected: |
  Run from repo root:
    uv run --package graph-wiki-agent graph-wiki-agent graph --help

  Output lists exactly 3 subcommands: `build`, `describe`, `query`.
  No additional subcommands. SC#1 mandates "exactly 3".
awaiting: user response

## Tests

### 1. `graph --help` shows 3 subcommands (SC#1)
expected: Run `graph-wiki-agent graph --help`. Output lists exactly 3 subcommands: build, describe, query. No more, no fewer.
result: [pending]

### 2. `graph build --help` shows only `--trace` and `--model` beyond cg's flags (SC#2)
expected: Run `graph-wiki-agent graph build --help`. Options include `--trace` and `--model` as the only agent-specific additions beyond what `cg update` accepts. (`--full` may also appear — it's cg's own flag for full rebuild.)
result: [pending]

### 3. `graph describe --help` shows 6 kind sub-sub-commands (D-08)
expected: Run `graph-wiki-agent graph describe --help`. Output shows 6 nested subcommands corresponding to the 6 cg describe kinds: `package`, `path`, `repository`, `domain`, `entry-point`, `test-suite`.
result: [pending]

### 4. `graph describe package <name>` works (D-08 + cg parity)
expected: Run `graph-wiki-agent graph describe package graph-io`. Output mirrors `cg describe-package graph-io` semantics — shows the package description (name, URI, files/entry-points if any). Exit code 0.
result: [pending]

### 5. `graph query --name <X>` mirrors `cg find` (Phase 36 parity)
expected: Run `graph-wiki-agent graph query --name SubagentPool --kind class`. Same result as `cg find --name SubagentPool --kind class`: returns the SubagentPool class node, exit 0.
result: [pending]

### 6. `graph build --trace` writes a JSONL trace file (SC#3)
expected: Run `graph-wiki-agent graph build --trace`. After completion: a new file appears under `.graph-wiki/traces/` matching `<ISO-timestamp>-graph-build.jsonl`. Contents are line-delimited JSON records with `schema_version`, `event`, `command`, `args`, `exit_code`, `duration_ms` fields. (`--model` flag if set is recorded but not LLM-invoked per planner finding — ops_update is pure Python.)
result: [pending]

### 7. MCP tools registered (SC#4)
expected: Inspect `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` (or list MCP tools via an MCP host if you have one connected). Three tools are registered with the `graph_` prefix: `graph_build`, `graph_describe`, `graph_query`. They appear alongside existing `wiki_*` tools.
result: [pending]

## Summary

total: 7
passed: 0
issues: 0
pending: 7
skipped: 0

## Gaps

[none yet]
