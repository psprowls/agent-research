---
phase: 53-wiki-filename-cutover
plan: 02
subsystem: wiki-io
tags: [encode_slug, decode_slug, short_filename, frontmatter.uri, link_rewriter, index_generator, entity_writer, cleanup, dead-code]

requires:
  - phase: 52
    provides: short_filename(uri, collision_set, ...) + _compute_collision_set + _kind_list_fns helpers
provides:
  - "Removed dead surface: encode_slug, decode_slug, _ADMITTED_URI_PREFIXES (entity_writer.py)"
  - "Consumers rewritten: link_rewriter.py + index_generator.py + scan.py go through short_filename for forward derivation and frontmatter.uri for reverse lookups"
  - "Legacy slug tests deleted; remaining tests retargeted to short_filename outputs"
  - "Round-trip fixture audit confirmed no long-form filenames remain (no-op closure)"
affects: [53-verification, future-phases]

tech-stack:
  added: []
  patterns:
    - "Single source of truth for entity filenames: short_filename(uri, collision_set, ...)"
    - "Reverse-lookup via frontmatter.uri (eliminates bidirectional-slug round-trip surface)"
    - "Per-consumer collision_set computation mirrors write_entities pre-pass"

key-files:
  created:
    - .planning/phases/53-wiki-filename-cutover/53-02-SUMMARY.md
  modified:
    - packages/wiki-io/src/wiki_io/entity_writer.py
    - packages/wiki-io/src/wiki_io/link_rewriter.py
    - packages/wiki-io/src/wiki_io/index_generator.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
    - packages/wiki-io/tests/test_entity_writer.py
    - packages/wiki-io/tests/test_index_generator.py
    - packages/wiki-io/tests/test_link_rewriter_build_table.py
    - agents/graph-wiki-agent/tests/test_migrate_vault.py

key-decisions:
  - "_ADMITTED_URI_PREFIXES deleted — audit confirmed decode_slug was its only consumer (D-06 default branch)."
  - "link_rewriter.build_rewrite_table builds collision_set list_fns from its own _LIST_FNS, not from entity_writer._kind_list_fns(). This keeps test monkeypatches of _LIST_FNS effective; without it, tests with conn=None hit the live graph_io.queries functions through _kind_list_fns() and crash. Trade-off: collision_set only covers the 5 admitted kinds the rewriter knows about (no repository/app); acceptable for the rewriter's domain (those 5 are the kinds with convention templates)."
  - "index_generator.PlacedEntity grows two optional fields (suite_kind, pkg_for_suite) so test_suite entities can produce kind-aware short filenames (unit_tests_<pkg>) via the same short_filename pre-pass that write_entities uses."
  - "agents/graph-wiki-agent/commands/scan.py inject_narrative path computes a fresh collision_set rather than receiving one from write_entities. Both calls happen inside the same scan_lock-held region, so the graph state is consistent between them; the second compute is a small (~20-50ms for repos this size) cost, but it keeps the narrator block independent and re-runnable if write_entities is monkeypatched in tests."
  - "Fixture closure was a no-op confirmation: 0 long-form filenames in tests/fixtures/round-trip-vault/ (Phase 52 plan-04 or earlier already cleaned it)."
  - "test_integration_gate.py::test_integration_test_files_use_canonical_gate FAILS on a stash-pre-state run; it is pre-existing failure unrelated to Phase 53 scope (the 7 flagged integration test files were not touched by this plan)."

patterns-established:
  - "Forward entity filename derivation: short_filename(uri, collision_set, ...) — single helper for write/index/rewrite paths."
  - "Reverse URI lookup: frontmatter.load(path).metadata['uri'] — no decode function needed."

requirements-completed:
  - WIKI-FN-05  # encode_slug/decode_slug removed + grep-zero gate + consumer rewrites + test pass
  - WIKI-FN-06  # generate_index emits short filenames (verified observation — no Phase 53 code change required; fixture confirmed short-form already)

duration: ~45min
completed: 2026-05-28
---

# Phase 53, Plan 02: Wiki Filename Cutover — Source-Code Cleanup Summary

**The bidirectional-slug machinery in `wiki_io.entity_writer` (`encode_slug`, `decode_slug`, `_ADMITTED_URI_PREFIXES`) is removed; every consumer in `packages/` and `agents/` derives entity filenames through Phase 52's `short_filename` and reads URIs back through `frontmatter.uri`. Phase 52's transitional state (5 long-form call sites in `index_generator.py` + 1 in `link_rewriter.py`) is closed.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 6 completed (1 read-only audit, 4 source-code, 1 final-gate)
- **Files modified:** 8 (3 production source, 1 scan-agent source, 4 test files)
- **LOC delta:** −215 / +47 net (mostly test/strategy removals)

## Accomplishments

- `encode_slug` and `decode_slug` definitions deleted from `wiki_io.entity_writer`.
- `_ADMITTED_URI_PREFIXES` deleted (D-06 default — no non-decode consumer found in audit).
- `link_rewriter.py`'s `_new_slug` rewritten to `_new_slug_for_node` calling `short_filename` with the test_suite-aware `(suite_kind, pkg_for_suite)` pair; `build_rewrite_table` computes `collision_set` once via `_compute_collision_set`.
- `index_generator.py`'s 4 `encode_slug` call sites consolidated into a single `_entity_wikilink(entity, collision_set)` helper threaded through `_render_domains`, `_render_by_kind`, `_render_domain_section`; `PlacedEntity` carries `suite_kind` + `pkg_for_suite` so the helper has everything it needs in one pass.
- `agents/graph-wiki-agent/commands/scan.py`'s narrator `inject_narrative` path derives entity page paths through `short_filename` (matching `write_entities`) instead of the dead `encode_slug`.
- Legacy `encode_slug` / `decode_slug` test surface deleted from `test_entity_writer.py` (4 test functions + Hypothesis strategies + composite URI generators).
- `test_index_generator.py` (5 assertions) + `test_link_rewriter_build_table.py` (3 assertions + 1 fixture) + `test_migrate_vault.py` (1 assertion) retargeted to short_filename outputs.
- Round-trip fixture confirmed clean: zero long-form filenames at audit time.

## Task Commits

1. **Task 53-02-01: Discovery grep audit** — no commit (read-only).
2. **Task 53-02-02: Rewrite link_rewriter.py, index_generator.py, scan.py** — `3757308` (refactor).
3. **Task 53-02-03: Delete encode_slug, decode_slug, _ADMITTED_URI_PREFIXES** — `cee3482` (refactor).
4. **Task 53-02-04: Delete legacy tests + retarget assertions** — `e71bec2` (test).
5. **Task 53-02-05: Fixture confirmation** — no commit (no-op confirmation).
6. **Task 53-02-06: Final gate + migrate_vault test fix** — `4dff073` (test).

## Files Created/Modified

- `packages/wiki-io/src/wiki_io/entity_writer.py` — Deleted `encode_slug`, `decode_slug`, `_ADMITTED_URI_PREFIXES`. Module docstring rewritten to describe `short_filename` + `_compute_collision_set` contract. `_URI_PREFIX_BY_KIND` comments cleaned of decode_slug references.
- `packages/wiki-io/src/wiki_io/link_rewriter.py` — `_new_slug` → `_new_slug_for_node` (calls `short_filename` with test_suite kind awareness). `build_rewrite_table` computes `collision_set` from `_LIST_FNS` so test monkeypatches stay effective. Module docstring updated.
- `packages/wiki-io/src/wiki_io/index_generator.py` — All 4 `encode_slug` call sites collapsed into `_entity_wikilink(entity, collision_set)` helper. `PlacedEntity` grows `suite_kind` + `pkg_for_suite` fields. `_render` computes `collision_set` once at the top and threads through `_render_domains`, `_render_by_kind`, `_render_domain_section`.
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — Narrator `inject_narrative` block derives entity paths via `short_filename` (with a freshly-computed `collision_set`); no more `encode_slug` import.
- `packages/wiki-io/tests/test_entity_writer.py` — Deleted: `test_slug_encode_examples`, `test_decode_slug_rejects_unknown_kind`, `test_decode_slug_rejects_too_few_segments`, `test_slug_round_trip`, `test_slug_batch_injective`, the Hypothesis strategies they consumed, and the `decode_slug` / `encode_slug` imports. Module docstring updated.
- `packages/wiki-io/tests/test_index_generator.py` — 5 assertions retargeted: `pkg_pkg-a`, `pkg_pkg-cross`, `tests_cross`, `pkg_pkg-solo`, `plugin_graph-wiki`.
- `packages/wiki-io/tests/test_link_rewriter_build_table.py` — Fixture URIs corrected (`dep:` → `dependency:`, `suite:` → `test_suite:` with `suite_kind` + `path` attrs); 3 assertions retargeted (`pkg_graph-io`, `pkg_wiki-io`, `dep_click`).
- `agents/graph-wiki-agent/tests/test_migrate_vault.py` — 1 assertion retargeted to `pkg_graph-io.md`.

## Decisions Made

- **D-06 default taken** — `_ADMITTED_URI_PREFIXES` deleted (only consumer was `decode_slug`).
- **Per-consumer `_compute_collision_set` calls** — `link_rewriter` and `index_generator` and the `scan.py` narrator each compute their own collision_set rather than receiving one from `write_entities`. Reads SQLite in a read-only fashion; the redundancy is small and keeps each entry point independent.
- **link_rewriter's collision-set list_fns comes from `_LIST_FNS`** — not from `entity_writer._kind_list_fns()`. This is the single non-obvious design choice in this plan and is documented inline so future readers (or refactors) understand why.

## Deviations from Plan

None of substance. Two refinements made during execution:

1. **link_rewriter `build_rewrite_table` collision_set source.** Discovered while running tests: using `entity_writer._kind_list_fns()` for the collision pass broke `test_link_rewriter_build_table.py` because its fixture monkeypatches only `link_rewriter._LIST_FNS`. The fix uses `_LIST_FNS` directly. Documented in the commit message (`3757308` was followed by the fix in `e71bec2`).
2. **test_migrate_vault.py also needed a retarget** (not flagged by the audit because it lives outside `packages/wiki-io/tests/`). Caught by the workspace test gate; fixed in `4dff073`.

## Verification — Final Gates (task 53-02-06)

1. **Symbol-removal grep:** `grep -rn "encode_slug\|decode_slug" packages/ agents/ --include="*.py"` → **0 hits.** ✓
2. **Negative import — encode_slug:** `python -c "from wiki_io.entity_writer import encode_slug"` → ImportError. ✓
3. **Negative import — decode_slug:** `python -c "from wiki_io.entity_writer import decode_slug"` → ImportError. ✓
4. **Positive import (Phase 52 survivors):** `from wiki_io.entity_writer import short_filename, _compute_collision_set, _URI_PREFIX_BY_KIND, _FILENAME_PREFIX_BY_URI_PREFIX, scanner_frontmatter_for_node, write_entities` → exits 0. ✓
5. **wiki-io test suite:** `uv run --package wiki-io pytest packages/wiki-io/tests/` → **356 passed, 2 skipped, 1 xfailed.** ✓
6. **Full workspace test suite:** `uv run pytest` → **1526 passed, 1 failed, 38 skipped, 2 xfailed.** The single failure is `tests/test_integration_gate.py::test_integration_test_files_use_canonical_gate`, which is a **pre-existing failure** unrelated to Phase 53 scope (the 7 flagged integration test files were never touched by this plan; verified by running the same test against the pre-Phase-53 working tree). ⚠ Pre-existing
7. **Planning artifact sanity (expected non-zero):** `grep -F "encode_slug" .planning/REQUIREMENTS.md` returns 1 hit (the new WIKI-FN-05 verification text from plan 53-01); `grep -F "encode_slug" .planning/ROADMAP.md` returns 2 hits (the new SC #1 + Scope reshape sentence in §Phase 53). ✓

## Issues Encountered

**Pre-existing failure surfaced by Gate 5 (workspace test suite):**

`tests/test_integration_gate.py::test_integration_test_files_use_canonical_gate` fails — but the failure predates Phase 53. The gate complains that 7 integration test files (`agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py`, `..._isolation.py`, `..._scan_entity_integration.py`, `packages/graph-io/tests/integration/test_cluster_cli.py`, `..._test_e2e_apps.py`, `..._test_e2e_builtins.py`, `packages/wiki-io/tests/integration/test_link_rewriter_integration.py`) do not match the canonical `GRAPH_WIKI_RUN_INTEGRATION` skipif pattern documented in `docs/testing.md`. None of these files were modified by Phase 53; the failure is identical on a pre-Phase-53 working tree.

Per Karpathy §3 (surgical changes — clean only your own mess) this is out of scope for Phase 53. Recorded here so it shows up in audit-uat / progress.

## Next Phase Readiness

Phase 53 source-code cleanup is complete. The two remaining gates per `53-CONTEXT.md` `<next_steps>` are:

1. **Manual vault regen (D-08; WIKI-FN-06 UAT)** — Pat runs `cg update --full` + `graph-wiki-agent scan` against `~/Personal/graph-wiki/agent-research`, inspects `wiki/index.md`, records findings in `53-UAT.md`. Phase 52's `write_entities` already emits short filenames; this UAT verifies the regen produces no `pkg__org__repo__name`-style files in practice.
2. **Phase verification** — automated `verify-phase` agent (next step in execute-phase) cross-checks must_haves against the codebase.

## Self-Check: PASSED
