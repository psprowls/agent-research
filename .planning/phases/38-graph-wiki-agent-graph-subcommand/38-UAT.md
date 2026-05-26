---
status: complete
phase: 38-graph-wiki-agent-graph-subcommand
source:
  - .planning/phases/38-graph-wiki-agent-graph-subcommand/38-01-SUMMARY.md
  - .planning/phases/38-graph-wiki-agent-graph-subcommand/38-02-SUMMARY.md
started: "2026-05-26T20:50:00Z"
updated: "2026-05-26T21:15:00Z"
---

## Current Test

[testing complete]

## Tests

### 1. `graph --help` shows 3 subcommands (SC#1)
expected: Run `graph-wiki-agent graph --help`. Output lists exactly 3 subcommands: build, describe, query. No more, no fewer.
result: pass
note: Output shows exactly `build`, `query`, `describe` — no extras.

### 2. `graph build --help` shows only `--trace` and `--model` beyond cg's flags (SC#2)
expected: Run `graph-wiki-agent graph build --help`. Options include `--trace` and `--model` as the only agent-specific additions beyond what `cg update` accepts. (`--full` may also appear — it's cg's own flag for full rebuild.)
result: pass
note: Agent-specific flags `--trace` and `--model` present. `--full` (cg's full rebuild) and `--workspace` (standard agent flag) also shown; nothing extraneous.

### 3. `graph describe --help` shows 6 kind sub-sub-commands (D-08)
expected: Run `graph-wiki-agent graph describe --help`. Output shows 6 nested subcommands corresponding to the 6 cg describe kinds: `package`, `path`, `repository`, `domain`, `entry-point`, `test-suite`.
result: pass
note: All 6 kinds listed verbatim — package, path, repository, domain, entry-point, test-suite.

### 4. `graph describe package <name>` works (D-08 + cg parity)
expected: Run `graph-wiki-agent graph describe package graph-io`. Output mirrors `cg describe-package graph-io` semantics — shows the package description (name, URI, files/entry-points if any). Exit code 0.
result: pass
note: Output shows package name, language, version, file count, and per-kind counts. Matches cg describe-package semantics.

### 5. `graph query --name <X>` mirrors `cg find` (Phase 36 parity)
expected: Run `graph-wiki-agent graph query --name SubagentPool --kind class`. Same result as `cg find --name SubagentPool --kind class`: returns the SubagentPool class node, exit 0.
result: pass
note: Matches Phase 36 `cg find` output exactly — `class SubagentPool packages/subagent-runtime/src/subagent_runtime/pool.py 89 {'language': 'python'}`.

### 6. `graph build --trace` writes a JSONL trace file (SC#3)
expected: Run `graph-wiki-agent graph build --trace`. After completion: a new file appears under `.graph-wiki/traces/` matching `<ISO-timestamp>-graph-build.jsonl`. Contents are line-delimited JSON records with `schema_version`, `event`, `command`, `args`, `exit_code`, `duration_ms` fields. (`--model` flag if set is recorded but not LLM-invoked per planner finding — ops_update is pure Python.)
result: pass
note: |
  Trace file written to workspace-relative path: `graph-wiki/.graph-wiki/traces/2026-05-26T20-42-26Z-graph-build.jsonl`.
  Two JSONL records — `graph_build_start` (exit_code null, duration_ms 0) and `graph_build_complete` (exit_code 0, duration_ms 754).
  All required fields present plus bonus `timestamp` and `model_id`. Schema v1.

### 7. MCP tools registered (SC#4)
expected: Inspect `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` (or list MCP tools via an MCP host if you have one connected). Three tools are registered with the `graph_` prefix: `graph_build`, `graph_describe`, `graph_query`. They appear alongside existing `wiki_*` tools.
result: pass
note: All 3 tools registered in `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` — `graph_build` (L512), `graph_describe` (L558), `graph_query` (L601), alongside existing `wiki_*` tools (wiki_log L169, wiki_bootstrap L216, plus 4 others).

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
