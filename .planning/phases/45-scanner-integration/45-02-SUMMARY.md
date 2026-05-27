---
phase: 45-scanner-integration
plan: 02
subsystem: scanner-integration
tags: [scan_monorepo, ExistingPages, dataclass, entities, frontmatter, uri-keyed]

requires:
  - phase: 43-entity-writer
    provides: "entity-page filesystem convention (wiki/entities/<encode_slug(uri)>.md, skip `_index.md`)"

provides:
  - "ExistingPages frozen dataclass (legacy / entities sub-dicts)"
  - "_load_existing_pages(wiki) returns ExistingPages; entities walk indexes by URI"
  - "scan_monorepo.main() updated to dataclass shape; compute_diff stays legacy-only"

affects: [45-03, 46-inbound-link-migration-cutover]

tech-stack:
  added: []
  patterns:
    - "Frozen dataclass envelope for backward-compat + new-feature return values"
    - "Local-import pattern for python-frontmatter inside the entities walk (avoids slowing the legacy walk's import cost)"

key-files:
  created:
    - packages/wiki-io/tests/test_load_existing_pages.py
  modified:
    - packages/wiki-io/src/wiki_io/scan_monorepo.py
    - packages/wiki-io/tests/test_scan_companion_fold.py

key-decisions:
  - "Adopted the 2-variable caller form (existing_pages + existing_legacy) over the 1-line form, matching the plan's <interfaces> example. Cleaner read site; identical runtime cost."
  - "Pre-existing test_scan_companion_fold.py tests treated _load_existing_pages as a dict and were updated to index via .legacy. Per Task 2 acceptance criterion: 'fix that test by indexing through .legacy instead. Do NOT add a shim'."

patterns-established:
  - "Entities walk filters: (1) skip `_index.md`; (2) catch frontmatter parse errors silently; (3) skip pages without a `uri` field"

requirements-completed:
  - SCANINT-05
  - SCANINT-06

duration: ~6min
completed: 2026-05-27
---

# Plan 45-02: ExistingPages dataclass + URI-keyed entities walk Summary

**`_load_existing_pages` now returns an ExistingPages dataclass with legacy (name-keyed, unchanged) and entities (URI-keyed, new) sub-dicts — feeds Plan 03's run_scan without re-walking the filesystem.**

## Performance

- **Duration:** ~6 minutes
- **Started:** 2026-05-27T14:53Z
- **Completed:** 2026-05-27T14:59Z
- **Tasks:** 3 (landed as one commit — TDD progression executed inline)
- **Files modified:** 3 (1 src + 2 tests)

## Accomplishments

- Frozen `ExistingPages` dataclass introduced in `scan_monorepo.py` (D-11).
- Entities walk: `wiki/entities/*.md` indexed by URI; `_index.md` skipped; pages without a `uri` skipped; unparseable frontmatter skipped silently.
- `_load_existing_pages(None)` and `_load_existing_pages(<nonexistent>)` return `ExistingPages(legacy={}, entities={})` (defensive shape parity).
- `scan_monorepo.main()` updated: `existing_pages = _load_existing_pages(wiki) ...`; downstream consumers receive `existing_pages.legacy` (one call site touched).
- `compute_diff` unchanged (D-12) — verified by 4 pre-existing `test_scan_companion_fold.py` tests that now index through `.legacy` and continue to pass.
- 11 new tests in `test_load_existing_pages.py`. Full wiki-io suite: 295 passed (no regression, +9 tests overall).

## Task Commits

1. **Tasks 1+2+3 combined: ExistingPages + entities walk** — `f0e7fdd` (feat)

   The plan declared 3 separate TDD tasks (RED → GREEN → entities walk). Executed inline as a single landing because the structural change is tightly coupled — the dataclass, the return-type change, and the entities walk are not independently shippable (Task 2 alone would leave `entities` always `{}`; Task 1 alone would leave callers broken). Self-check confirmed the full 11-test suite passes.

## Files Created/Modified

- `packages/wiki-io/src/wiki_io/scan_monorepo.py` — added `dataclass` import + `ExistingPages` class; renamed local `pages` → `legacy_pages`; appended entities walk; updated `main()` call site
- `packages/wiki-io/tests/test_load_existing_pages.py` — 11 new tests across 3 classes (shape, return-type, entities walk)
- `packages/wiki-io/tests/test_scan_companion_fold.py` — 4 test sites updated to index via `.legacy`

## Decisions Made

- Combined TDD tasks into one landing because the partial shape (return-type changed but entities empty) has no independent caller value — Plan 03 needs both halves. The plan's verification criterion (`pytest packages/wiki-io/tests/test_load_existing_pages.py -x` → 9 tests) is satisfied (actually 11 tests; superset).
- Followed the 2-variable caller form from the plan's `<interfaces>` block over the 1-line variant in the acceptance grep.

## Deviations from Plan

- Acceptance grep `_load_existing_pages\(wiki\).legacy if wiki.exists() else` returns 0 because the 2-variable form lives across two lines. Functionally equivalent — the dataclass return is consumed and `.legacy` is unpacked at the same point. No correctness impact.
- Plan declared 3 commits; landed as 1 (rationale above).

## Issues Encountered

- Pre-existing `test_scan_companion_fold.py` failed on first run with `AttributeError` because it accessed `pages.items()` on the dataclass. Fix: updated 4 call sites to `_load_existing_pages(...).legacy` per the plan's Task 2 acceptance criterion ("fix that test by indexing through `.legacy` instead. Do NOT add a shim — the dataclass IS the new return type per D-11").

## Self-Check: PASSED

```text
uv run --package wiki-io pytest packages/wiki-io/tests/test_load_existing_pages.py -x   → 11 passed
uv run --package wiki-io pytest packages/wiki-io/tests/test_scan_monorepo.py -x         → 29 passed (SCANINT-06)
uv run --package wiki-io pytest packages/wiki-io                                        → 295 passed, 2 skipped
uv run python -c "from wiki_io.scan_monorepo import ExistingPages, _load_existing_pages, compute_diff; print('ok')"
```

## Next Phase Readiness

`ExistingPages` is importable; Plan 03 (Wave 2) consumes:

- `existing_pages.legacy` → passed to `compute_diff` + `attach_changed_files` + Step 11's `existing.get(...)` calls
- `existing_pages.entities` → informational (Phase 45 D-11/D-12); available if Step 9a wants to log entity counts, but `write_entities` reads the filesystem directly and does not need this view

Note: between Plan 02 landing and Plan 03 landing, `commands/scan.py::run_scan` still calls `_load_existing_pages(wiki)` expecting a dict; agent-side tests in `agents/graph-wiki-agent/tests/` may temporarily fail. That's expected per the plan's "All callers" truth — Plan 03 fixes those call sites.

---
*Phase: 45-scanner-integration*
*Completed: 2026-05-27*
