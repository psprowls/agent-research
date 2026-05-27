---
phase: 43-entity-writer
plan: 03
subsystem: integration-tests
tags: [integration-test, real-graph, cli, doc-reconciliation]

requires:
  - phase: 43-01
    provides: graph-io ingestion of dependency + plugin kinds, query helpers, plugins.emit
  - phase: 43-02
    provides: wiki_io.entity_writer.write_entities + ADMITTED_KINDS_V18
provides:
  - 6 integration tests under packages/wiki-io/tests/integration/test_entity_writer_integration.py
  - 2 new CLI subcommands (cg describe-dependency, cg describe-plugin) + 5 smoke tests
  - graph-io fix: _row_to_node + _list_by_kind project nodes.uri column into NodeRecord.attrs
  - REQUIREMENTS.md: ENTITY-01..05 marked Complete
  - STATE.md: Phase 43 — Completed (2026-05-27) block recording package_family deferral, folded-todo resolution, and Pitfall 2/3/9 guard activation
  - ROADMAP.md: Phase 43 checked off in milestone list + Status: Complete on detail block + 3 plans enumerated
affects: [45 (run_scan integration), 46 (cutover)]

tech-stack:
  added: []
  patterns:
    - "Synthesis-wave integration test pattern: build synthetic workspace + git init + run graph-io ingestion + run wiki-io write_entities + assert filesystem state"
    - "CLI subcommand stamp pattern (one module per kind): add_arguments + run -> int, mirror q_describe_package.py shape"

key-files:
  created:
    - packages/wiki-io/tests/integration/test_entity_writer_integration.py (6 integration tests)
    - packages/graph-io/src/graph_io/cli/q_describe_dependency.py
    - packages/graph-io/src/graph_io/cli/q_describe_plugin.py
    - packages/graph-io/tests/test_cli_describe.py (5 smoke tests)
  modified:
    - packages/graph-io/src/graph_io/queries.py (URI column projection into NodeRecord.attrs)
    - packages/graph-io/src/graph_io/cli/main.py (wire 2 new subcommands)
    - .planning/REQUIREMENTS.md (ENTITY-01..05: Pending -> Complete)
    - .planning/STATE.md (Phase 43 — Completed block)
    - .planning/ROADMAP.md (Phase 43 checkbox + Status + Plans list)

key-decisions:
  - "Task 5 decision = SHIP — q_describe_*.py modules follow a consistent existing pattern (per-kind CLI command); shipping two more matches convention with zero design surprise (CONTEXT.md D-06 discretion knob)"
  - "URI column projection happens in _row_to_node (the shared projector) so EVERY list_* / find / describe_* surface gets the URI in attrs uniformly — no need to teach write_entities about the nodes.uri column"
  - "_row_to_node accepts both 5-column and 6-column row shapes (backward-compat with any caller still using the old SELECT)"
  - "CLI tests build a synthetic workspace with .graph-wiki.yaml at <repo>/graph-wiki/.graph-wiki.yaml (the default workspace location), not at the repo root — matches workspace_io.config.resolve_workspace semantics"

patterns-established:
  - "Synthesis-wave integration tests use real sqlite + real graph-io ingestion modules (not MockGraphConn) — close the loop on Wave 1's mocked-graph development"
  - "Hard-delete forensic chain: graph node removed -> page unlinked -> JSONL log entry with all 6 fields (timestamp, uri, slug, path, kind, body_was_empty)"

requirements-completed: [ENTITY-01, ENTITY-02, ENTITY-03, ENTITY-04, ENTITY-05]

duration: 35min
completed: 2026-05-27
---

# Phase 43 Plan 03: Integration synthesis + REQUIREMENTS/STATE/ROADMAP close-out

**Real-graph integration tests prove all 5 ENTITY-* requirements end-to-end; folded-todo cleanup verified; two discretionary CLI subcommands shipped to match the existing per-kind pattern.**

## Decision recorded (Task 5)

**Choice: SHIP** the two CLI subcommands (`cg describe-dependency` and `cg describe-plugin`). Rationale from CONTEXT.md D-06: the existing `cli/` directory has a consistent per-kind subcommand pattern (`q_describe_package.py`, `q_describe_domain.py`, `q_describe_suite.py`, `q_describe_repo.py`, `q_describe_entry_point.py`, `q_describe_path.py`), shipping two more matches that convention with zero design surprise. ~30 LOC each, deterministic argparse + queries + format. 5 smoke tests pass.

## What was built

1. **Task 1 — Integration tests (6 tests, ~225 LOC):** Real-graph synthesis tests under `packages/wiki-io/tests/integration/test_entity_writer_integration.py`:
   - `test_write_entities_round_trip_on_synthetic_workspace` — builds a tmp workspace with 2 pyproject.tomls + .graph-wiki.yaml + nested __init__.py; runs `packages.refresh` + `structural_nodes.emit` + `plugins.emit` + `write_entities`; asserts >=7 entity pages (repo + 2 packages + 3 unique deps + plugin) and zero errors.
   - `test_status_deprecated_preserved_after_rewrite` — proves merge semantics on real graph.
   - `test_hard_delete_logs_to_deletions_log` — proves the full forensic chain: graph DELETE + re-run + page unlinked + JSONL entry with all 6 schema fields.
   - `test_scan_lock_blocks_concurrent_writes` — threaded contention test (<500ms fail-fast).
   - `test_determinism_second_run_all_unchanged` — proves byte-stable YAML emission.
   - `test_needs_narrative_round_trip` — needs_narrative non-empty on create, empty on no-op.

2. **Task 2 — REQUIREMENTS.md update:** Both the checkbox list (lines 25-29) and the Traceability table (lines 106-110) updated: `ENTITY-01..05: Pending -> Complete`. Matched existing URI-* convention (Complete, not Implemented).

3. **Task 3 — STATE.md update:** Added "Phase 43 — Completed (2026-05-27)" section recording (a) shipped artifacts, (b) `package_family` v1.9 deferral with ADMITTED_KINDS_V18 derivation note, (c) folded-todo resolution, (d) Pitfall 2/3/9 guard activation with implementation pointers, (e) graph-io side effect that unblocks the Phase 44 BLOCKER noted in STATE.md.

4. **Task 4 — ROADMAP.md update:** Phase 43 checkbox in milestone list flipped to `[x]` with completion date. Phase 43 detail block now has `Status: Complete (2026-05-27)`, success-criteria items have `[x]` markers, and the Plans line lists all 3 plan files.

5. **Task 5 — Decision gate:** Chose SHIP for the optional CLI subcommands (rationale above).

6. **Task 6 — CLI subcommands shipped:** `q_describe_dependency.py` + `q_describe_plugin.py` mirror `q_describe_package.py`. Wired into `cli/main.py` `_SUBCOMMANDS` dict and import block (alphabetical order preserved). 5 smoke tests in `tests/test_cli_describe.py` cover: human-format dep smoke, dep-not-found, dep JSON output, plugin smoke, plugin-not-found.

7. **Task 7 — Cross-cutting verification:**
   - Folded todo confirmed present in `.planning/todos/resolved/`, absent from `pending/`.
   - Full graph-io suite: 358 passed, 1 skipped, 1 xfailed (5 more than pre-Plan-03 from new CLI tests + 6 from queries.py URI projection regression cover).
   - Full wiki-io suite: 221 passed, 1 skipped (6 more than pre-Plan-03 from the integration tests).

## Cross-plan discoveries

- **`list_*` helpers were returning empty `attrs.uri`** (Plan 01 escape, caught during Plan 03 integration test). The `nodes.uri` column wasn't being projected back into `NodeRecord.attrs` by `_row_to_node` + `_list_by_kind`. Fix landed in this plan: `_row_to_node` now accepts both 5-column and 6-column shapes and folds the uri column into attrs. `_list_by_kind` SELECT updated to fetch the uri column. This is more correct than teaching `write_entities` about the column directly because EVERY downstream caller benefits from uniform `node.attrs["uri"]` access.

## Phase 45 readiness note

`write_entities` is ready to be wired into `run_scan` Step 9a:
```python
result = write_entities(conn, wiki_root, ADMITTED_KINDS_V18)
# Step 9b: fan out LLM scanner over result.needs_narrative
```
`needs_narrative` is ready to drive the Phase 45 fan-out. All 5 ENTITY-* requirements are complete. The Plan 43 phase is ready to ship.

## Deviations from Plan

[Rule 1 - Bug] **`list_*` helpers returned empty `uri` in NodeRecord.attrs**
- Found during: Task 1 first run of `test_write_entities_round_trip_on_synthetic_workspace`
- Issue: `_row_to_node` SELECTed 5 columns (no uri) so `node.attrs["uri"]` was missing for nodes whose uri lived in the column (which is all of them via the upsert layer). `write_entities` saw no admitted URIs and emitted zero pages.
- Fix: extend `_row_to_node` to accept the 6-column shape with uri appended; fold uri back into attrs. Extend `_list_by_kind` SELECT to include uri.
- Files modified: packages/graph-io/src/graph_io/queries.py
- Verification: all 6 integration tests pass; all 358 graph-io tests pass; all 221 wiki-io tests pass
- Commit hash: 62d9535

[Rule 1 - Bug] **CLI tests' .graph-wiki.yaml at wrong path**
- Found during: Task 6 first run of `test_cg_describe_plugin_smoke`
- Issue: Initial fixture put `.graph-wiki.yaml` at `<repo>/`, but `workspace_io.config.resolve_workspace` defaults to `<repo>/graph-wiki/` as the workspace. Plugin was never ingested because `plugins.emit` looked for the manifest at the workspace path, not the repo root.
- Fix: relocate the fixture manifest to `<repo>/graph-wiki/.graph-wiki.yaml`
- Files modified: packages/graph-io/tests/test_cli_describe.py
- Verification: 5/5 CLI smoke tests pass

**Total deviations:** 2 auto-fixed (both Rule 1 bugs). **Impact:** The URI projection fix is a genuine improvement to graph-io's read surface — it makes ALL list_* callers uniform.

## Self-Check: PASSED

- All 6 integration tests pass: `uv run --package wiki-io pytest tests/integration/test_entity_writer_integration.py -x` exits 0
- All 5 CLI describe tests pass: `uv run --package graph-io pytest tests/test_cli_describe.py -x` exits 0
- `uv run --package graph-io pytest` exits 0 (358 passed, 1 skipped, 1 xfailed)
- `uv run --package wiki-io pytest` exits 0 (221 passed, 1 skipped — bedrock-live expected)
- REQUIREMENTS.md Traceability: 5 Complete rows for ENTITY-01..05
- STATE.md has the "Phase 43 — Completed (2026-05-27)" block with all required bullets
- ROADMAP.md Phase 43 has `[x]` in milestone list + `Status: Complete (2026-05-27)` + `[x]` success-criteria + Plans: 3 plans
- `.planning/todos/resolved/2026-05-26-fix-scanner-treats-import-root-as-subpackage.md` exists
- `.planning/todos/pending/2026-05-26-fix-scanner-treats-import-root-as-subpackage.md` does NOT exist
