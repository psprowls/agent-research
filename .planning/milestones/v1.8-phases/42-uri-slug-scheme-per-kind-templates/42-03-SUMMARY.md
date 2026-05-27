---
phase: 42
plan: 03
subsystem: wiki-io, .planning
tags: [vault-bootstrap, cross-cutting-test, doc-reconciliation]
requires:
  - wiki_io.entity_writer.ADMITTED_KINDS (42-01)
  - 7 entity-*.md templates (42-02)
provides:
  - wiki/entities/ lane in init_wiki bootstrap
  - test_entity_templates.py cross-cutting validator
  - REQUIREMENTS.md / ROADMAP.md aligned with CONTEXT.md
affects:
  - packages/wiki-io/src/wiki_io/init_vault.py
  - packages/wiki-io/tests/test_init_vault.py
  - packages/wiki-io/tests/test_entity_templates.py
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
tech-stack: {}
key-files:
  created:
    - packages/wiki-io/tests/test_entity_templates.py
  modified:
    - packages/wiki-io/src/wiki_io/init_vault.py
    - packages/wiki-io/tests/test_init_vault.py
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
key-decisions:
  - Test 2 used the monkeypatched pattern (matching test_init_wiki_creates_section_index_stubs) — stubs out _workspace_init + _resolve_pinned_containers so the test exercises only the directory-creation + sentinel-write path. End-to-end (no-monkeypatch) approach not needed; the monkeypatched form is the established convention in this test file.
requirements-completed:
  - URI-04
  - URI-03 (drift-reconciled)
duration: ~15 min
completed: 2026-05-27
---

# Phase 42 Plan 03: Vault Wire-Up + Cross-Cutting Validator + Doc Reconciliation

Finalized Phase 42's foundation by wiring `wiki/entities/` into vault bootstrap, adding the cross-cutting template validator that locks Plan 01's `ADMITTED_KINDS` and Plan 02's 7 templates together, and reconciling the two documentation-drift spots in REQUIREMENTS.md / ROADMAP.md against the CONTEXT.md locked decisions.

## What was built

- `packages/wiki-io/src/wiki_io/init_vault.py`:
  - `FIXED_VAULT_DIRS` gains `"entities"` (one-line addition, no removals).
  - `init_wiki` writes `wiki/entities/_index.md` sentinel comment idempotently (after `installed_files = []`, with `if not entities_index.exists()` guard).
- `packages/wiki-io/tests/test_init_vault.py`: 2 new test functions appended.
  - `test_entities_in_fixed_vault_dirs` — constant-shape regression guard.
  - `test_entities_dir_bootstrapped_after_init_wiki` — end-to-end exercise via monkeypatch.
- `packages/wiki-io/tests/test_entity_templates.py` (NEW): 4 named tests producing 16 sub-tests via `pytest.mark.parametrize` over the 7 entity templates. Locks ADMITTED_KINDS ↔ template kind ↔ `## Narrative` H2 invariants.
- `.planning/REQUIREMENTS.md` URI-03 + `.planning/ROADMAP.md` Phase 42 success criterion #3: path reconciled (`templates/entities/` → `assets/page-templates/`); narrative marker reconciled (`sentinel comment` → `## Narrative` H2). 2 line changes per file.

## Test-approach decision (Q3 from RESEARCH.md)

The end-to-end vs. monkeypatched debate is resolved by following the existing convention in `test_init_vault.py`: the prior `test_init_wiki_creates_section_index_stubs` test already uses `monkeypatch.setattr(init_vault, "_workspace_init", lambda *a, **k: None)`. Plan 03's Task 2 mirrors that pattern verbatim — no fixture invention, no full-stack git init / workspace bootstrap exercise. The monkeypatched form gives the test stable behavior and isolates the unit under test (sentinel write).

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `'entities' in FIXED_VAULT_DIRS`.
- [x] `init_wiki` produces `wiki/entities/_index.md` containing the sentinel comment.
- [x] Cross-cutting test asserts the 7 templates' `kind:` values equal `ADMITTED_KINDS` exactly (16 sub-tests pass).
- [x] REQUIREMENTS.md URI-03 + ROADMAP.md success criterion #3 reference `assets/page-templates/` and `## Narrative` H2.
- [x] Strings `wiki_io/templates/entities/` and `prose sentinel comment` no longer appear in either file.
- [x] Full wiki-io test suite: 183 passed, 1 skipped (integration). No regressions; +18 tests from the phase.

## Phase 42 attestation

**Phase 42 contracts locked; ready for Phase 43 entity-writer implementation.**

All 5 Phase 42 success criteria satisfied:
1. Property test of ≥1,000 URIs passes (Plan 01).
2. Round-trip stable (Plan 01).
3. 7 templates exist with `kind:` + `## Narrative` (Plan 02 + Plan 03 validator).
4. Fresh vault contains `wiki/entities/_index.md` (Plan 03 Tasks 1 + 2).
5. Frozenset constants present and disjoint from human keys (Plan 01).
