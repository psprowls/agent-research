---
phase: 44-scanner-generated-index
plan: 02
status: complete
completed_at: 2026-05-27
---

# Plan 44-02 Summary — Determinism, Write-if-Changed, Edge-Case Acceptance + Snapshot

## Outcome

All 11 acceptance tests landed in `packages/wiki-io/tests/test_index_generator.py`
(co-located with Plan 01's unit tests). Total file: 49 active tests + 1
conditionally-skipped snapshot test.

No production code changed in Plan 02 — every behavior was already implemented
in Plan 01. Plan 02 is a pure verification layer.

## Test Count by Section

| Group | Count | Tests |
|---|---|---|
| Determinism + write-if-changed (Task 1) | 4 | `test_determinism_across_permutations`, `test_write_if_changed`, `test_write_if_changed_writes_when_graph_mutates`, `test_atomic_write_no_tmp_remains` |
| Placement + section structure (Task 2) | 5 | `test_cross_cutting_in_by_kind_only`, `test_multi_domain_entity_in_by_kind`, `test_sub_domain_nesting`, `test_empty_sections_omitted`, `test_plugin_always_by_kind` |
| Curated + generated-files (Task 3) | 2 | `test_curated_lanes_consolidated`, `test_generated_files_excluded` |
| Snapshot (Task 3) | 1 (skipped) | `test_snapshot_against_agent_research` |
| **Plan 02 total** | **12** | (11 active + 1 conditionally skipped) |

## Snapshot Status

`test_snapshot_against_agent_research` SKIPPED — agent-research workspace has
no `.graph-wiki/graph.db` at the time of Plan 02 execution. The test is
correctly guarded by `pytest.mark.skipif` and will activate once a live
graph is built. No snapshot file (`tests/__snapshots__/test_index_generator.ambr`)
was created. This is acceptable per the plan ("never failing").

When the live graph appears (Phase 45 `run_scan` lands), the snapshot can be
recorded with `pytest tests/test_index_generator.py::test_snapshot_against_agent_research --snapshot-update`.

## First-Run Results

- **Determinism**: passed on first run. No non-determinism surfaced in the
  Plan 01 implementation. The hard-coded `BY_KIND_ORDER` tuple + URI-keyed
  sorts inside every bucket eliminated insertion-order dependencies cleanly.
- **Write-if-changed**: passed on first run. The byte-compare against
  `path.read_bytes()` correctly returns `changed=False` on the second
  invocation and `mtime` is unchanged.
- **Atomic write cleanup**: passed on first run. `os.replace` removes the
  temp file by atomicity guarantee on POSIX; no `.tmp` files leak.

## Deviations / Notes

- `test_multi_domain_entity_in_by_kind` uses the full encoded slug substring
  (`test_suite__agent-research__cross__integration`) rather than the bare
  `suite-multi` name, because the URI slug encoding inserts `__cross__` from
  the URI path (`test_suite:agent-research/cross/integration`). This made
  the test more specific and avoids any false-positive matches.
- `test_empty_sections_omitted` uses a fresh `text.find("##", start)` slice
  to extract the active-domain section text; `Test Suites` and `Dependencies`
  sub-bullet labels are confirmed absent.

## File Byte-Identity Verification

- `packages/wiki-io/src/wiki_io/update_index.py` — no `git status` modification
  (D-01 holds).
- `packages/wiki-io/pyproject.toml` — no `git status` modification (D-22 holds).

## Suite Health

`uv run --package wiki-io pytest -x` exits 0:
**1288 passed, 35 skipped, 1 xfailed** (snapshot suite: 19 snapshots passed
elsewhere; index-generator snapshot deferred).

No regressions introduced into:
- `update_index.py` callers (`ingest_work_item.py` still imports cleanly)
- Other wiki-io modules
- `graph-io` queries (Phase 43 surface untouched)

## Phase 46 Follow-Up

The Phase 46 cutover will:
- Delete `wiki/<lane>/index.md` files (per-folder sub-indexes) — the new
  `wiki/index.md` consolidates them as sections.
- Delete `update_index.py` and rewire `ingest_work_item.py` to use
  `generate_index` instead.

When that lands, the deferred snapshot recording in this phase should be
established as the baseline.
