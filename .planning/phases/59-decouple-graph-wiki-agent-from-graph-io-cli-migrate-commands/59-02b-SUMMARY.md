---
phase: 59
plan: 02b
subsystem: graph-wiki-agent
tags: [refactor, graph-io, mcp, scan, decoupling, typed-api]
requires:
  - graph_io.queries.* typed API (describe_*, find)
  - graph_io.update.run (raises on error, silent on success)
  - graph_io.render.format_* + render (promoted public formatter, Plan 01)
provides:
  - graph_module.run_build(repo, workspace, *, full) -> (exit_code, stdout, stderr)
  - graph_module.run_describe(kind, identifier, repo, workspace) -> (exit_code, stdout, stderr)
  - graph_module.run_query(repo, workspace, *, name, kind, in_package) -> (exit_code, stdout, stderr)
  - graph_module._connect_or_error(workspace) -> (conn|None, exit_code, stderr)
  - graph_module.DESCRIBE_REQUIRES_IDENTIFIER: dict[str, bool]
affects:
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
tech-stack:
  added: []
  patterns:
    - "Printing-free core functions returning (exit_code, stdout, stderr) shared by CLI + MCP + scan (D-02 single source of truth)"
    - "Thin Typer wrappers echo core stdout/stderr + write trace + raise typer.Exit"
key-files:
  created: []
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
    - agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py
    - agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py
    - agents/graph-wiki-agent/tests/unit/test_commands_scan.py
    - agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py
    - agents/graph-wiki-agent/tests/commands/test_scan_parity.py
    - agents/graph-wiki-agent/tests/test_command_overrides.py
decisions:
  - "D-02 honored: zero duplicated formatting/exit-code logic — CLI, MCP, and scan all route through run_build/run_describe/run_query"
  - "DESCRIBE_REQUIRES_IDENTIFIER replaces the deleted _DESCRIBE_DISPATCH (module, id_attr) tuple; MCP only needed the id_attr-is-not-None semantics, expressed as a bool"
  - "run_query returns the truncation notice in the stderr slot (matches where CLI's _notice wrote it)"
metrics:
  duration: ~7m
  completed: 2026-05-29
---

# Phase 59 Plan 02b: Reconnect MCP + scan consumers to the typed graph_io API Summary

Migrated the two unplanned consumers of `commands/graph.py`'s deleted Phase-38 shim (`_build_namespace`/`_capture_run`/`ops_update`/`q_find`/`_DESCRIBE_DISPATCH`) onto three new printing-free core functions, restoring import-time health of the MCP server and the scanner without reintroducing any `graph_io.cli` import.

## What was built

Three reusable core functions added to `commands/graph.py`, each returning `tuple[int, str, str]` = (exit_code, stdout, stderr) with no printing, no `typer.Exit`, no trace writes:

- **`run_build(repo, workspace, *, full)`** — wraps `update.run`; maps `NotInGitRepoError`/`UpdateInProgressError`/`SchemaMismatchError`/`Exception`/success to the same exit codes `graph_build_cmd` used. `update.run` is silent (D-06) so stdout is always `""`; errors go to the stderr slot as `error: {exc}`. No `--model` note (CLI-only).
- **`run_describe(kind, identifier, repo, workspace)`** — covers all 6 kinds, including the bare-vs-`package:entry` entry-point disambiguation with `AMBIGUOUS(7)` and the domain packages/subdomains SQL queries. Success returns the exact `_render.format_<kind>(...)` human string (byte-identical); not-found → GENERIC; ambiguous → AMBIGUOUS; store errors → NOT_INITIALIZED/SCHEMA_MISMATCH.
- **`run_query(repo, workspace, *, name, kind, in_package)`** — preserves the D-07 `--in-package` no-match → GENERIC(1) quirk; truncation notice is returned in the stderr slot.

Plus `_connect_or_error(workspace)` (printing-free connect+map) which `_open_graph_conn` now wraps (CLI behavior unchanged), and the public `DESCRIBE_REQUIRES_IDENTIFIER` mapping.

The Typer command bodies were refactored to call these cores via a shared `_describe_cli` helper (6 describe commands collapse to thin wrappers) plus updated `graph_build_cmd`/`graph_query_cmd`. They echo the returned stdout/stderr, write the same trace records (exit_code from the core return), keep the CLI-only `--model` note and the missing-filter exit-2 guard, and `raise typer.Exit(code)` on nonzero. CLI per-stream output stays byte-identical.

Consumer migrations:
- **`mcp/server.py`** — `graph_build`/`graph_describe`/`graph_query` now call the core funcs; `graph_describe` validates via `DESCRIBE_REQUIRES_IDENTIFIER` (identifier-required → exit 2) instead of `_DESCRIBE_DISPATCH`. Trace writes + `_pack_output` retained.
- **`scan.py`** — pre-scan build block now calls `run_build(repo, _workspace_root, full=False)` (imported as `_cg_run_build`); surrounding logging/branching preserved. `_cg_stdout` is `""` (D-06).

## Verification (all gates green)

1. **SC#1** `grep -rn "graph_io.cli" agents/graph-wiki-agent/src/` → CLEAN (empty).
2. **Import smoke** `from graph_wiki_agent.commands import graph, scan; from graph_wiki_agent.mcp import server` → OK.
3. **Agent suite** `uv run pytest --ignore=tests/unit/test_commands_graph.py -q` → **333 passed, 11 skipped** (19 snapshots passed). The 11 skips are pre-existing (Phase 45 D-08 legacy-fanout removals + integration env-gated tests).
4. **graph-io cg suite** `uv run pytest tests/test_cli_format.py tests/test_cli_describe.py tests/test_cli_exit_codes.py tests/test_cli_anti_regression.py -q` → **55 passed, 1 xfailed** (cg behavior untouched).

## Deviations from Plan

### Auto-fixed / design choices

**1. [Rule 3 - structural] `_describe_cli` shared wrapper introduced**
- The design said "refactor the existing Typer command bodies to call these core functions." Rather than duplicate the same echo/trace/exit boilerplate across all 6 describe commands, I extracted a single `_describe_cli(*, kind, identifier, command, trace, workspace)` helper. The 6 commands are now thin wrappers. No behavior change; keeps the codebase free of 6x near-identical blocks (Karpathy simplicity).

**2. [Behavioral note] Trace-on-store-error for describe**
- In the old code, `_open_graph_conn` raised `typer.Exit(NOT_INITIALIZED/SCHEMA_MISMATCH)` *before* any trace record was written on a connect failure. With the core-function refactor, `_describe_cli` now writes a trace record (with the mapped exit code) even on store-error branches. This affects only the trace JSONL contents on the (awkward-to-provoke, D-09 mock-class) store-error path — **stdout/stderr remain byte-identical**. The new behavior is arguably more correct (the error is now traced) and no existing test asserted the absence of that record. Flagged for transparency.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary surface introduced. The MCP `_StdoutGuard` invariant is preserved (core funcs return strings, never print to stdout).

## Self-Check: PASSED

- Files modified exist and compile (import smoke OK).
- Commits verified present:
  - `aac5c6d` refactor(59-02b): add run_build/run_describe/run_query core funcs to graph.py
  - `2747428` feat(59-02b): migrate MCP graph tools onto typed run_build/describe/query
  - `3ad6883` feat(59-02b): migrate scan.py pre-scan build off deleted graph shim
  - `9258f13` test(59-02b): update affected tests to typed run_build/describe/query reality
