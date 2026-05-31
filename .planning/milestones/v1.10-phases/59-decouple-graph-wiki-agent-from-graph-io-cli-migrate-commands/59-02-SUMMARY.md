---
phase: 59-decouple-graph-wiki-agent-from-graph-io-cli-migrate-commands
plan: 02
subsystem: graph-wiki-agent
tags: [graph-wiki-agent, graph-io, typed-api, refactor, exit-codes, trace]

requires:
  - phase: 59-decouple-graph-wiki-agent-from-graph-io-cli-migrate-commands
    plan: 01
    provides: graph_io.render public module with render() + 6 format_<kind>() functions

provides:
  - commands/graph.py rewritten onto typed graph_io API (queries/update/store/render)
  - _open_graph_conn(workspace) shared helper: read_only_connect + exception→exit-code map
  - graph_tools.py using graph_io.render.render (not graph_io.cli._format)
  - SC#1 satisfied: zero graph_io.cli imports under agents/graph-wiki-agent/src/
  - SC#2 satisfied: no argparse/_build_namespace/_capture_run/redirect_stdout in graph.py

affects:
  - 59-03 (tests — snapshot/exit-code tests now build against real typed API)
  - any future consumer of agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py

tech-stack:
  added: []
  patterns:
    - "_open_graph_conn helper: read_only_connect + except GraphNotInitializedError → typer.Exit(NOT_INITIALIZED), except SchemaMismatchError → typer.Exit(SCHEMA_MISMATCH)"
    - "update.run exception→exit-code map: NotInGitRepoError(5), UpdateInProgressError(6), SchemaMismatchError(4), Exception(1)"
    - "Entry-point disambiguation inline in graph.py (copied from q_describe_entry_point.py), AMBIGUOUS(7) raised via typer.Exit"
    - "Domain extra SQL inline (packages/subdomains) passed to _render.format_domain(desc, packages, subdomains, fmt=human)"

key-files:
  created: []
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py

key-decisions:
  - "_open_graph_conn placed in commands/graph.py (not a shared utility module) — single consumer matches scan.py precedent for co-location"
  - "Domain extra SQL kept inline in graph.py — deferred to future queries.py helper (matches research recommendation)"
  - "Entry-point disambiguation block copied verbatim into graph.py from q_describe_entry_point.py, adapting return→raise typer.Exit and print→typer.echo(err=True)"
  - "graph_tools.py was a second (research-missed) graph_io.cli importer — fixed as part of this plan's scope (AUDIT NOTE confirmed in plan objective)"
  - "Trace write-on-every-path: each describe command writes trace in both the not-found and success branches; query writes in GENERIC and success branches"

patterns-established:
  - "Typed graph_io consumer pattern: _open_graph_conn + try/finally conn.close() + queries.describe_<kind>() + _render.format_<kind>() + typer.echo()"
  - "Exit-code contract via exception mapping: no magic ints, always graph_io.exit_codes.* constants"

requirements-completed: [SC-01, SC-02, SC-04]

duration: 10min
completed: 2026-05-29
---

# Phase 59 Plan 02: Agent Migration to Typed API Summary

**Rewrote commands/graph.py off the argparse/capture shim onto typed graph_io.queries/update/store + graph_io.render, satisfying SC#1 (no graph_io.cli imports) and SC#2 (no Namespace/capture shim) with exact exit-code contract including AMBIGUOUS(7).**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-29T18:00:00Z
- **Completed:** 2026-05-29T18:10:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Deleted `_build_namespace`, `_capture_run`, `_DESCRIBE_DISPATCH` table, and all `graph_io.cli.*` imports from `commands/graph.py`
- Added `_open_graph_conn(workspace)` helper mirroring scan.py:540-558, reused by all 6 describe commands and `graph query`
- `graph build` now calls `update.run()` with typed exception→exit-code mapping (D-06): `NotInGitRepoError(5)`, `UpdateInProgressError(6)`, `SchemaMismatchError(4)`, `Exception(1)`
- 6 describe commands each call direct typed queries + `_render.format_<kind>()` — entry-point includes full disambiguation block with `AMBIGUOUS(7)` (D-05), domain includes inline SQL for packages/subdomains (D-04)
- `graph query` calls `queries.find()` with D-07 `--in-package` no-match → `GENERIC(1)` quirk preserved
- Fixed `graph_tools.py` line 16: `from graph_io.cli._format import render` → `from graph_io.render import render` (the research-missed second importer)
- SC#1 gate passes: `grep -rn "graph_io.cli" agents/graph-wiki-agent/src/` returns only a docstring reference, no actual imports

## Task Commits

1. **Task 1: Rewrite commands/graph.py onto the typed API** - `a71fb1e` (feat)
2. **Task 2: Swap graph_tools.py off graph_io.cli._format** - `18ed06e` (feat)

## Files Created/Modified
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` — full rewrite: shim deleted; typed API + _open_graph_conn + 6 per-kind describe commands + update.run build + queries.find query; trace schema unchanged
- `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py` — line 16 import + docstring reference updated to graph_io.render

## Decisions Made

- `_open_graph_conn` placed in `commands/graph.py` rather than a shared module — single consumer, mirrors scan.py co-location pattern.
- Domain extra SQL (packages/subdomains) kept inline in graph.py as specified — queried before `conn.close()` inside the same `try` block to avoid Pitfall 2.
- Entry-point disambiguation copied verbatim from `q_describe_entry_point.py` with `return exit_codes.AMBIGUOUS` → `raise typer.Exit(code=exit_codes.AMBIGUOUS)` and `print(..., file=sys.stderr)` → `typer.echo(..., err=True)`.
- Trace records written in both success and failure paths for each command (not-found, AMBIGUOUS, and success all write a record when `--trace` is set).

## Deviations from Plan

None — plan executed exactly as written. The `graph_tools.py` second importer was already called out in the plan's AUDIT NOTE and objective; it was part of the plan's scope.

## Issues Encountered

None. Module imports cleanly on first attempt. SC#1 and SC#2 grep gates pass.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- Plan 03 (test rebuild) can proceed: `commands/graph.py` now uses typed API and `graph_io.render`, so tests can use real DB fixtures and syrupy snapshots instead of Namespace/capture mocks
- `_open_graph_conn` signature: `(workspace: Path) -> sqlite3.Connection` — raises `typer.Exit` on store errors; callers use `try/finally: conn.close()`

## Known Stubs

None — all data paths are wired to the typed API.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. `_open_graph_conn` uses the same `read_only_connect` path as `scan.py`. Inline SQL queries use `?` parameterized placeholders (T-59-04 mitigation confirmed).

## Self-Check: PASSED
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` — file exists and imports cleanly
- `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py` — file exists and imports cleanly
- Commit a71fb1e exists: feat(59-02): rewrite commands/graph.py onto typed graph_io API
- Commit 18ed06e exists: feat(59-02): swap graph_tools.py off graph_io.cli._format

---
*Phase: 59-decouple-graph-wiki-agent-from-graph-io-cli-migrate-commands*
*Completed: 2026-05-29*
