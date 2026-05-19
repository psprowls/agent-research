---
phase: 17-vault-io-bug-fixes
plan: 01
subsystem: vault-io
tags: [python, scan, companion-folding, workflow_hints, pytest]

# Dependency graph
requires:
  - phase: 16-carry-forward-debt-cleanup
    provides: "vault-io lint module including workflow_hints._parse_workflow_hints reused for companion discovery"
provides:
  - "scan_monorepo._load_existing_pages folds companion files (api/context/patterns/work stems) into parent slug"
  - "4 unit tests in test_scan_companion_fold.py covering SCAN-01 and SCAN-02"
affects: [17-02, 17-03, 17-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-page workflow_hints frontmatter (not layout block) is the authoritative companion source"
    - "Two-pass pattern: first pass discovers companion stems from parent overviews; second pass skips them"
    - "Reuse vault_io.lint.workflow_hints._parse_workflow_hints across modules in same package"

key-files:
  created:
    - packages/vault-io/tests/test_scan_companion_fold.py
  modified:
    - packages/vault-io/src/vault_io/scan_monorepo.py

key-decisions:
  - "D-02 reconciled: workflow_hints lives in per-page frontmatter, not wiki/CLAUDE.md layout block; use _parse_workflow_hints not read_layout() for companion discovery"
  - "Two-pass approach inside _collect(): first pass builds companions_by_dir dict; second pass skips by md.stem"
  - "fold_companions=False default preserves backward compatibility for all call sites; only packages/ and layout-pinned package containers opt in"
  - "Test CLAUDE.md requires graph-wiki sentinel HTML comments (<!-- graph-wiki:layout:start -->) for read_layout() to parse it"

patterns-established:
  - "Companion fold pattern: md.stem in companions_by_dir.get(md.parent, set()) as the skip predicate"
  - "TDD RED/GREEN: write failing tests first, then implement to make them pass"

requirements-completed: [SCAN-01, SCAN-02]

# Metrics
duration: 25min
completed: 2026-05-19
---

# Phase 17 Plan 01: Companion-Fold Filter in scan_monorepo Summary

**Two-pass companion-fold filter added to `_load_existing_pages._collect()` eliminating 28+ phantom deleted entries from scan diff by reading per-page `workflow_hints` frontmatter via `_parse_workflow_hints`.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-19
- **Completed:** 2026-05-19
- **Tasks:** 2 (TDD: RED + GREEN across both tasks)
- **Files modified:** 2

## Accomplishments
- Added `from vault_io.lint.workflow_hints import _parse_workflow_hints` import to `scan_monorepo.py`
- Modified `_collect()` signature to `_collect(root, default_category, fold_companions=False)` with two-pass companion discovery logic
- Updated 3 call sites: `packages/` gets `fold_companions=True`, `apps/` unchanged, layout-pinned containers get `fold_companions=(classification == "package")`
- Applied same two-pass logic to the `domains_dir` inline block for `wiki/domains/<d>/packages/` paths
- Created 4 passing unit tests in `test_scan_companion_fold.py` covering all 4 required behavior cases

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Add failing tests for companion-fold filter** - `b38cfd2` (test)
2. **Task 1+2 GREEN: Companion-fold filter implementation + test fixture fix** - `cebb7ee` (feat)

_TDD: RED commit (b38cfd2) establishes failing tests; GREEN commit (cebb7ee) implements the filter and corrects test CLAUDE.md sentinel format._

## Files Created/Modified
- `packages/vault-io/src/vault_io/scan_monorepo.py` - Added `_parse_workflow_hints` import; companion-fold two-pass logic in `_collect()` and `domains_dir` block
- `packages/vault-io/tests/test_scan_companion_fold.py` - New: 4 unit tests for companion fold, layout-pinned packages, apps-not-filtered, compute_diff phantom deletes

## Decisions Made
- **D-02 reconciliation applied:** CONTEXT.md claimed `workflow_hints` lives in the layout block accessible via `read_layout()`. Research verified it lives in per-page frontmatter. Implementation reads per-page frontmatter using `_parse_workflow_hints` from the existing lint module.
- **Test CLAUDE.md format corrected:** Initial test used bare fenced code block; `read_layout()` requires sentinel HTML comments `<!-- graph-wiki:layout:start -->` / `<!-- graph-wiki:layout:end -->` to detect the layout block.
- **Parent overview detection:** `md.stem == md.parent.name` convention (e.g. `vault-io/vault-io.md`) identifies parent overviews without reading frontmatter in the first pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test CLAUDE.md used wrong layout block format**
- **Found during:** Task 2 (test_layout_pinned_package_skips_companions failing)
- **Issue:** Initial `_LAYOUT_CLAUDE_MD` used a bare fenced code block; `layout_io.read_layout()` requires `<!-- graph-wiki:layout:start -->` / `<!-- graph-wiki:layout:end -->` sentinel comments to detect the layout block.
- **Fix:** Updated `_LAYOUT_CLAUDE_MD` constant in test file to use correct sentinel comments.
- **Files modified:** `packages/vault-io/tests/test_scan_companion_fold.py`
- **Verification:** `test_layout_pinned_package_skips_companions` passes after fix.
- **Committed in:** `cebb7ee` (GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test fixture format)
**Impact on plan:** Necessary correction; test was not exercising the right code path.

## Issues Encountered
- `test_load_existing_skips_companions` initially passed in RED phase (no filter yet) because I first checked for key "api" which doesn't exist (real keys are "lattice-curator-core — API" etc.). Fixed test to check vault_path stems instead of page title keys, which correctly reproduced the bug.

## User Setup Required
None - no external service configuration required.

## TDD Gate Compliance

- **RED gate:** `b38cfd2` — `test(17-01): add failing tests for companion-fold filter (RED)` — 4 tests fail
- **GREEN gate:** `cebb7ee` — `feat(17-01): companion-fold filter in _load_existing_pages (SCAN-01, SCAN-02)` — all 4 tests pass

## Self-Check

Files created/modified:
- `packages/vault-io/src/vault_io/scan_monorepo.py` — MODIFIED (implementation)
- `packages/vault-io/tests/test_scan_companion_fold.py` — CREATED (tests)

## Known Stubs
None.

## Threat Flags
None — no new network endpoints, auth paths, file access patterns, or schema changes. The companion filter is read-only path manipulation on the existing wiki filesystem walk.

## Next Phase Readiness
- SCAN-01 and SCAN-02 requirements complete; vault-io scan diff is no longer polluted by 28 phantom companion deletions
- Ready for Phase 17 Plan 02 (TOK fix) and Plan 03 (WSRES fix) — independent modules with no overlap

---
*Phase: 17-vault-io-bug-fixes*
*Completed: 2026-05-19*
