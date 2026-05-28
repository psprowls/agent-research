---
phase: 50-app-reclassification-graph-io
plan: "03"
subsystem: graph-io
tags: [app-kind, graph-io, cli, queries, integration-test]
requires:
  - 50-01-app-schema-foundation
  - 50-02-classify-wiring-and-kind-flip
provides:
  - queries.AppDescription dataclass
  - queries.list_apps + queries.describe_app
  - cli/q_list_apps.py + cli/q_describe_app.py
  - cli/main.py registers 'list-apps' and 'describe-app' subcommands
  - End-to-end integration tests covering every ROADMAP success criterion
affects:
  - User-facing cg CLI surface (two new subcommands)
  - Live agent-research workspace now classifies graph-wiki-agent and graph-io as kind='app'
tech-stack:
  added: []
  patterns:
    - "describe_app SQL mirror of describe_package with kind='app' substituted; consumer-side used_by JOINs broadened to kind IN ('package','app') per RESEARCH Pitfall 7"
key-files:
  created:
    - packages/graph-io/src/graph_io/cli/q_list_apps.py
    - packages/graph-io/src/graph_io/cli/q_describe_app.py
    - packages/graph-io/tests/integration/test_e2e_apps.py
  modified:
    - packages/graph-io/src/graph_io/queries.py
    - packages/graph-io/src/graph_io/cli/main.py
    - packages/graph-io/tests/test_queries.py
    - packages/graph-io/tests/test_cli_describe.py
    - packages/graph-io/tests/test_cli_smoke.py
key-decisions:
  - "describe_app entry_points JOIN broadens to pkg.kind IN ('package','app') per RESEARCH Pitfall 7 even though the row-side WHERE strictly filters kind='app'; the broadening is for any downstream consumer-style usage that mirrors describe_package's used_by pattern"
  - "describe-app human output mirrors describe-builtin's labelled-line style (not describe-package's terse two-column style) so app_kind / signals lines are visually distinct"
  - "CLI smoke tests use the existing _cg helper + _git_repo fixture pattern from Phase 49 — no new test infrastructure"
requirements-completed:
  - APP-02
  - APP-04
  - APP-05
  - APP-06
duration: "7 min"
completed: "2026-05-28"
---

# Phase 50 Plan 03: query layer + CLI handlers + end-to-end integration Summary

The App graph kind is now fully inspectable through the `cg` CLI. `queries.list_apps` and `queries.describe_app` (with the `AppDescription` dataclass) ship the read-only query layer; `cg list-apps` and `cg describe-app` expose it on the command line. Five end-to-end integration tests verify every ROADMAP success criterion (SC #1..#5) by running the full manifest → classify → emit → SQL → query → CLI pipeline against real-shaped repos. Live smoke against the agent-research workspace confirms `graph-wiki-agent` (and `graph-io` — both have `[project.scripts]`) reclassify to `kind='app'` with `app_kind='cli'`.

## Execution Times

- Start: 2026-05-28T02:34:53Z
- End:   2026-05-28T02:41:53Z
- Duration: 7 min
- Tasks: 3
- Files touched: 8 (5 src/test modified + 3 created)

## Task-by-Task

### Task 1: AppDescription + list_apps + describe_app in queries.py

- **RED commit** 7c83813 — four failing tests (alphabetical list, full AppDescription shape, not-found returns None, scope invariant excludes kind='package' rows with the same name)
- **GREEN commit** 3a8c88c — `AppDescription` frozen dataclass added after `PackageDescription`; `describe_app` is a clone of `describe_package`'s SQL block with `kind='app'` substituted in node-side filters and `kind IN ('package','app')` broadened in entry-points consumer JOIN per RESEARCH Pitfall 7; `list_apps` is a one-liner over `_list_by_kind(conn, "app")` placed adjacent to `list_builtins`
- 86 passed, 1 skipped (full test_queries.py)
- `grep -cE "kind\\s+IN\\s+\\('package',\\s*'app'\\)" packages/graph-io/src/graph_io/queries.py` → 3 matches (includes other broadened sites from plan 50-02 deviation work)

### Task 2: CLI handlers + main.py registration

- **Commit** 025a627 — created `cli/q_list_apps.py` and `cli/q_describe_app.py` (verbatim PATTERNS.md templates); registered both in `cli/main.py` import block and `_SUBCOMMANDS` dict at the alphabetically correct positions ("describe-app" before "describe-builtin"; "list-apps" before "list-builtins")
- Six new CLI tests pass (3 smoke + 3 describe): smoke covers happy path, JSON shape, empty-graph fallback; describe covers happy path, not-found GENERIC, full JSON field set
- `cg --help` lists both new subcommands

### Task 3: End-to-end integration tests

- **Commit** e18d1ab — created `tests/integration/test_e2e_apps.py` with five tests covering ROADMAP SC #1..#5 plus APP-06 round-trip
- One footgun avoided: `capsys.readouterr()` returns `out`/`err`, not `stdout`/`stderr` (caught via initial RED run)
- All 5 E2E tests pass

## Verification Results

- `uv run --package graph-io pytest packages/graph-io/tests/ -q` → **454 passed, 1 skipped, 1 xfailed** (up from 423 pre-Phase-50 baseline; Phase 50 contributed 31 new tests across the three plans)
- `uv run cg --help 2>&1 | grep -cE "list-apps|describe-app"` → 2 (both subcommands registered)
- **Live smoke against /Users/pat/Personal/agent-research:**
  - `uv run cg update && uv run cg list-apps` → outputs `graph-io` and `graph-wiki-agent`
  - `uv run cg describe-app graph-wiki-agent` → prints `app_kind: cli`, `signals: ['cli']`, files=93, counts {'class': 35, 'function': 600, 'method': 19}
  - Direct SQL probe against the live DB: `("SELECT kind, uri FROM nodes WHERE name='graph-wiki-agent'")` returns `('app', 'app:psprowls/agent-research/graph-wiki-agent')`
- `grep -n "SCHEMA_VERSION" packages/graph-io/src/graph_io/schema.py` → `SCHEMA_VERSION = 2` (no bump, D-12 honored)

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0.
**Impact:** None. The substantial deviation work from Plan 50-02 (downstream emitter broadening) had already paved the way for this plan to land cleanly.

## Key Decisions

- **describe_app SQL mirrors describe_package** with `kind='app'` substituted in node-side filters and `kind IN ('package','app')` broadened in the entry-points consumer JOIN. Per RESEARCH Pitfall 7, App nodes that are themselves consumers (via used_by-style joins) must remain discoverable from the App's `declares_entry_point` graph.
- **CLI handler human output styles diverge slightly.** `describe-app` uses labelled lines (`app:`, `language:`, `version:`, `app_kind:`, `signals:`, `files:`, `counts:`) rather than `describe-package`'s terser two-column format. This makes the `app_kind` / `signals` lines visually distinct without forcing a column-alignment change to the existing package handler.
- **End-to-end test file lives under `tests/integration/`**, mirroring Phase 49's `test_e2e_builtins.py` placement. The integration directory is gated by the global `tests/conftest.py` collector but no `GRAPH_WIKI_RUN_INTEGRATION` env-var gate — these run as ordinary pytest tests (the env-var gate is for live-Bedrock tests only).

## Self-Check: PASSED

- [x] All 3 tasks executed
- [x] Each task committed atomically (RED test commit + GREEN code commit per task; Task 3 is test-only so single commit)
- [x] Plan-level verification (`<verification>` block) all green
- [x] All `<acceptance_criteria>` from every task verified
- [x] Live smoke against /Users/pat/Personal/agent-research workspace passes
- [x] No regressions: 454-test graph-io baseline holds; SCHEMA_VERSION unchanged

## Issues Encountered

None.

## Next Phase Readiness

Phase 50 is complete. All six APP-* requirements (APP-01..APP-06) are satisfied; all five ROADMAP success criteria are verified through automated tests plus live smoke. The graph-io schema, emit pipeline, downstream emitters, query layer, and CLI surface all honor the package/app distinction consistently.

Ready for Phase 51 (`package-family Removal + Divergence Rule Cleanup`). Phase 51's dependency on Phase 50 is satisfied: `_VALID_KINDS` is clean, `app` is admitted, and the wiki-io boundary is untouched (D-14 honored — Phase 50 made no changes outside graph-io).
