---
phase: 56-entity-templates-scan-time-population
plan: 03
subsystem: wiki-io
tags: [cleanup, legacy-templates, dead-links]
requires:
  - "Plan 02 migration (content moved into entity-<kind>.md before deletion)"
provides:
  - "legacy package/domain/plugin/app template dirs removed"
  - "wiki-io test suite fully green (4 pre-existing failures resolved)"
affects:
  - packages/wiki-io/src/wiki_io/assets/page-templates/
tech-stack:
  added: []
  patterns: []
key-files:
  created: []
  modified: []
  deleted:
    - packages/wiki-io/src/wiki_io/assets/page-templates/package/overview.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/domain/overview.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/plugin/overview.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/app/overview.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/app/testing.md
    - packages/wiki-io/tests/test_overview_template_wikilinks.py
key-decisions:
  - "Both git rm operations (legacy dirs + obsolete test) committed together as the plan's deletion unit"
  - "No init_vault.py change (D-14) — rglob copy is path-agnostic"
  - "No new dead-link regression test (D-16) — grep verification only"
requirements-completed: [ENTITY-03]
duration: 6 min
completed: 2026-05-28
---

# Phase 56 Plan 03: Delete Legacy Template Dirs Summary

Deleted the legacy directory-style template assets and the 4 obsolete wikilink tests now that
Plan 02 migrated their content into the `entity-<kind>.md` templates (ENTITY-03).

**Duration:** ~6 min | **Tasks:** 3 | **Files:** 6 deleted

## What was built (removed)

- **Task 1** — Pre-deletion grep gate (D-14): confirmed no live `.py` reference to the legacy dir
  paths (the only matches were in the to-be-deleted test file), and confirmed `init_vault.py`'s
  copy is path-agnostic (`src_tmpl.rglob("*")` at init_vault.py:254). Then `git rm -r` the four
  legacy subdirs: `page-templates/{package,domain,plugin,app}/` (the latter included both
  `overview.md` and `app/testing.md`). The 7 `entity-<kind>.md` templates and the other top-level
  `page-templates/*.md` (adr, architecture, concept*, dependency, index, source, work) all remain.
  `init_vault.py` unchanged (D-14).
- **Task 2** — `git rm packages/wiki-io/tests/test_overview_template_wikilinks.py` (D-15). All 4 of
  its test functions loaded `ASSETS/"package"/"overview.md"`, `ASSETS/"domain"/"overview.md"`, and a
  package/context template — every one now deleted. No replacement test added (coverage lives in
  `test_entity_templates.py` and `test_entity_writer.py`).
- **Task 3** — Dead-link grep verification (D-16, no new test): repo grep shows zero live `.py`
  reference to the deleted dirs. The remaining `[[...]]` links in the entity templates are all
  authoring-guidance placeholders carrying `<...>` instruction segments (e.g. `[[concepts/<concept>]]`,
  `[[packages/<pkg>]]`, `[[domains/<domain>]]`) — intentional per D-01/D-11, not dead links to
  deleted pages.

## Verification evidence

- Pre-deletion grep (live `.py` refs to legacy dirs, excluding the deleted test): **NONE**.
- `test ! -d` for all four legacy subdirs: **all pass** (gone).
- `uv run --package wiki-io pytest packages/wiki-io/tests -q`: **371 passed, 2 skipped, 1 xfailed,
  0 failed** — the 4 pre-existing FileNotFoundError failures are resolved by removal (D-15).
- Post-deletion grep (`page-templates/{package,domain,plugin,app}`, `app/testing` in `*.py`): **NONE**.
- `init_vault.py` diff: **unchanged** (D-14).
- No new test file created (D-16).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

Phase 56 is now fully complete (4/4 plans). The wiki-io suite is green for the first time since the
4 legacy-template failures were flagged in Phase 54. Phase 57 (index polish, IDX-03 inline
summaries) can build on the populated `summary:` field and the filled entity templates.

## Self-Check: PASSED

- All four legacy subdirs absent; 7 entity templates + other top-level templates remain
- `test_overview_template_wikilinks.py` deleted
- `uv run --package wiki-io pytest packages/wiki-io/tests -q` → 371 passed, 0 failed
- No live `.py` reference to deleted dirs; `init_vault.py` unchanged
- Commit present: `git log --grep="56-03"` → 1 deletion commit (feat)
