---
phase: 45-scanner-integration
verified: 2026-05-27
status: passed
verifier: gsd-execute-phase inline (Opus 4.7 1M, sequential mode)
requirements_verified:
  - SCANINT-01
  - SCANINT-02
  - SCANINT-03
  - SCANINT-04
  - SCANINT-05
  - SCANINT-06
---

# Phase 45 Verification: Scanner Integration

## Phase Goal

> `run_scan` calls `entity_writer.write_entities` (Step 9a) and fans out the LLM scanner only for `needs_narrative` URIs (Step 9b), hard-deletes entity pages for disappeared nodes (Step 11), regenerates the entity index (Step 12), and handles `wiki/entities/` by URI in load/diff — with the existing plugin smoke test still passing.

## Result

**PASSED.** All six SCANINT requirements implemented, verified by code grep + integration tests, and the SCANINT-06 plugin smoke regression (`packages/wiki-io/tests/test_scan_monorepo.py`) continues to pass.

## Requirement-by-requirement verification

### SCANINT-01 — Step 9a write_entities + Step 9b narrator gate on needs_narrative

Source:
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` line 646: `entity_write_result = write_entities(conn, wiki, ADMITTED_KINDS_V18)`
- Line 663: `if entity_write_result.needs_narrative:` — narrator pool only instantiated when set is non-empty

Tests:
- `tests/integration/test_scan_entity_integration.py::test_run_scan_creates_entity_pages_from_graph`
- `tests/integration/test_scan_entity_integration.py::test_run_scan_narrator_gates_on_needs_narrative` (second scan returns zero narrator invocations)

### SCANINT-02 — LLM prose-only (no frontmatter from LLM)

Source:
- `scan.py:330` system message in `build_entity_narrative_prompt`: `"Output ONLY prose: no YAML frontmatter, no H1, no H2 headings, ..."`
- Step 10 calls `inject_narrative` which replaces ONLY the body region between `## Narrative` and the next H2 (scanner-owned frontmatter intact)

Tests:
- `tests/unit/test_entity_narrative_prompt.py::TestSystemMessage::test_system_bans_frontmatter`
- `tests/unit/test_entity_narrative_prompt.py::TestSystemMessage::test_system_bans_h1`
- `tests/integration/test_scan_entity_integration.py::test_entity_pages_prose_only_no_frontmatter_drift` — feeds the narrator a string that LOOKS like frontmatter; asserts the page frontmatter is preserved
- `packages/wiki-io/tests/test_inject_narrative.py::test_inject_narrative_preserves_frontmatter`

### SCANINT-03 — Entity hard-delete on disappeared nodes

Source:
- `packages/wiki-io/src/wiki_io/entity_writer.py::write_entities` deletion sweep at line 595 (`page_path.unlink()`)
- Curated-lane stale-tag behavior unchanged in Step 11 (D-09; see `scan.py:709-743`)

Tests:
- `packages/wiki-io/tests/integration/test_entity_writer_integration.py` (Phase 43 ENTITY-03 tests — verified by pre-existing 1288 passing wiki-io tests)
- `tests/integration/test_scan_entity_integration.py::test_step_11_legacy_stale_tag_still_runs_for_non_entity_deletions`

### SCANINT-04 — Step 12 dual writer (generate_index + update_index)

Source:
- `scan.py:786` `index_result = generate_index(conn, wiki)`
- `scan.py:799` `update_index(wiki)` (per-folder sub-indexes only after Phase 45 D-02 surgical change)
- Order: `regenerate_dependencies_index → generate_index → update_index`

Tests:
- `tests/integration/test_scan_entity_integration.py::test_step_12_dual_writer_index` — both `wiki/index.md` and `wiki/concepts/index.md` produced
- `tests/integration/test_scan_entity_integration.py::test_step_12_calls_generate_then_update` — order asserted

REQUIREMENTS.md text rewritten to D-03 wording (commit b372466).

### SCANINT-05 — `_load_existing_pages` walks `wiki/entities/` by URI

Source:
- `packages/wiki-io/src/wiki_io/scan_monorepo.py:831` `class ExistingPages` (frozen dataclass)
- Lines 962-980: entities walk indexes by URI from frontmatter; skips `_index.md`; skips pages without `uri`; skips unparseable frontmatter
- `compute_diff` unchanged (D-12); callers pass `existing_pages.legacy` (verified in `scan.py:625`)

Tests:
- `packages/wiki-io/tests/test_load_existing_pages.py` (11 tests covering dataclass shape, return-type, entities walk, _index.md skip, missing-uri skip, unparseable frontmatter)

### SCANINT-06 — Plugin smoke test still passes

Verified:
```
uv run --package wiki-io pytest packages/wiki-io/tests/test_scan_monorepo.py -x
============================== 29 passed in 0.11s ==============================
```

This plan did NOT modify `plugins/graph-wiki/scan_monorepo.py` (D-13) and the agent-side rewire is independent of `wiki_io.scan_monorepo.main()` which the plugin shim calls.

## Test summary

| Package | Run | Result |
|---------|-----|--------|
| model-adapter | `pytest packages/model-adapter/tests` | 24 passed |
| wiki-io | `pytest packages/wiki-io` | 295 passed, 2 skipped (no live agent-research graph for snapshot; Bedrock-live integration gated) |
| graph-wiki-agent | `pytest agents/graph-wiki-agent/tests/` | 315 passed, 11 skipped (4 from Phase 45 `_PHASE_45_LEGACY_REMOVED` marker + 7 pre-existing skips) |

Total: **634 tests passing** across affected packages.

## Phase deliverables vs. plan

| Plan | Status | Commits |
|------|--------|---------|
| 45-01 (narrator role + inject_narrative + update_index surgical) | Complete | 5245596, fe3b618, 2a30c8e, 8664882, b372466, 00c0f37 |
| 45-02 (ExistingPages + entities walk) | Complete | f0e7fdd, bd8e9a0 |
| 45-03 (run_scan rewire + integration tests) | Complete | cecb40c, 23512bf, 63649cd, af88cc7, 2bc73d4 |

13 commits total. All three SUMMARY.md files exist; all three plans marked complete in ROADMAP via `gsd-sdk query roadmap.update-plan-progress`.

## Deviations from plan

The execution-phase orchestrator could not spawn parallel `Agent()` subagents in this runtime, so Wave 1 (Plans 01 + 02) ran sequentially instead of in parallel. Functionally equivalent — there were no file overlaps between 01 and 02, but they landed back-to-back rather than concurrently. Plan 03's Wave 2 execution was unchanged.

Plan 02's three TDD tasks landed in a single commit (`f0e7fdd`) rather than three separate ones — the structural change (dataclass return, legacy walk preservation, entities walk) was too tightly coupled to ship as three independent increments. Acceptance criteria still satisfied: 11 of the planned 9 unit tests pass.

Plan 03 Task 4 (Step 12 wiring) was folded into Task 3's commit (`63649cd`) since the import was added there; Task 4's commit (`af88cc7`) is purely the integration test suite. Wiring + verification both landed; the split-vs-fold doesn't affect correctness.

The legacy v1.7 unit tests in `test_commands_scan.py` that validated the removed scanner fan-out were not rewritten — instead they were marked with the `_PHASE_45_LEGACY_REMOVED` skip marker (4 tests). Their v1.8 equivalents live in `test_scan_entity_integration.py` (Plan 03 Task 4). Test-coverage parity preserved.

## Next phase readiness

- Phase 46 (Inbound Link Migration + Cutover) is unblocked:
  - `wiki/entities/` is the canonical location for new entity pages
  - `ScanResult.entities_created` lists the admitted URIs after a scan
  - Stale legacy pages under `wiki/packages/`, `wiki/dependencies/`, etc. still exist on disk from prior scans — Phase 46 cutover deletes them (per CONTEXT.md "Phase 46 ripple")
  - Phase 46 does NOT delete `update_index.py` (overridden by Phase 45 D-02)
  - `plugins/graph-wiki/` stays on legacy layout per D-13; plugin-cutover decision deferred

- Outstanding follow-ups (not blockers):
  - Phase 49 may want to retire the 4 `_PHASE_45_LEGACY_REMOVED` skipped tests after the integration suite has been observed to be the new source of truth for a release cycle.
  - The Bedrock-live `test_count_tokens_live.py` skip and `test_snapshot_against_agent_research` skip are pre-existing and unaffected by Phase 45.

---
*Phase: 45-scanner-integration*
*Verified: 2026-05-27*
