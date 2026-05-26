---
phase: 31-domain-layer-derived-edges
plan: 02
subsystem: graph-io
tags: [graph-io, import-scan, shared-helper, phase-30-back-port]
requires:
  - 31-01
provides:
  - graph_io.import_scan module (scan_package_imports, scan_files_imports)
  - shared regex constants + _build_pkg_index + _build_importable_maps helpers
  - test_suites.emit back-ported to consume the shared scanner (D-10)
affects:
  - Phase 31 Plan 31-04 derived_edges.compute will consume scan_package_imports
  - Phase 30 test_suites.py simplified — single regex source-of-truth
tech-stack:
  added:
    - "packages/graph-io/src/graph_io/import_scan.py (new module)"
  patterns:
    - "Shared scanner pattern: scan_package_imports(conn, ...) for connection-aware callers; scan_files_imports(repo_root, file_paths, pkg_rows) for connection-free callers"
key-files:
  created:
    - packages/graph-io/src/graph_io/import_scan.py
    - packages/graph-io/tests/test_import_scan.py
  modified:
    - packages/graph-io/src/graph_io/test_suites.py
key-decisions:
  - "Two public functions instead of one: scan_files_imports takes a precomputed file list, scan_package_imports queries the DB. Preserves Phase 30's per-suite file-list semantics without forcing the caller to re-query."
  - "_REPOSITORY_EDGE_THRESHOLD remains owned by test_suites.py (D-12 is semantically a TestSuite concept, not a scanner concept)"
  - "_build_pkg_index stays in test_suites.py because _discover_test_roots still needs it for config-driven pyproject testpaths resolution (independent of the scanner)"
requirements-completed:
  - DERIVED-01
  - DERIVED-02
duration: "20 min"
completed: 2026-05-26
---

# Phase 31 Plan 02: Extract import_scan.py + Back-Port test_suites.emit Summary

Phase 30 inlined an import-graph scanner inside `_emit_tests_edges`.
CONTEXT.md D-10 forbids two parallel scanners — Phase 31's
`derived_edges.compute` (Plan 31-04) must call the same code path for
production-code references / depends_on derivation. This plan extracts
the scanner into a shared `graph_io.import_scan` module and back-ports
Phase 30's `test_suites.py` to consume it.

**Tasks:** 4 (skeleton → public surface → tests → back-port)
**Files created:** 2 (import_scan.py, test_import_scan.py)
**Files modified:** 1 (test_suites.py — net -71 lines)
**Duration:** ~20 min
**Test result:** 223 passed, 1 skipped (up from 215 — net +8 new
test_import_scan tests, no Phase 30 regressions)

## Task Outcomes

| # | Task | Commit | Result |
|---|------|--------|--------|
| 1 | Scaffold import_scan module (regex + helpers) | ea2b908 | Module imports cleanly; 6 AC pass |
| 2 | Add scan_package_imports + scan_files_imports | b240eb8 | Both callables; 7 AC pass |
| 3 | 8 unit tests in test_import_scan.py | fcbf814 | 8/8 pass first run; 7 AC pass |
| 4 | Back-port test_suites.emit to call scan_files_imports | 3a9059f | Phase 30 tests still 21 pass / 1 skip; 6 AC pass |

## Public Surface (new)

```python
from graph_io.import_scan import scan_package_imports, scan_files_imports

# Phase 31 path:
imports = scan_package_imports(
    conn, repo_root, "pkg-a", "packages/pkg-a",
    include_test_files=False,  # D-11 default — production-code only
)
# -> set[tuple[pkg_name, pkg_rel | None]]

# Phase 30 path (now used by test_suites.emit):
imports = scan_files_imports(repo_root, file_paths, pkg_rows)
# -> set[tuple[pkg_name, pkg_rel | None]]
```

## Test Coverage

`test_import_scan.py` covers all 8 must_haves cases:

| Test | Behaviour |
|------|-----------|
| `test_scan_package_imports_python` | Python `from pkg_b import bar` resolves via py_importable_to_pkg |
| `test_scan_js_bare_spec_resolved` | JS bare specifier `import "jspkg-b"` → js_name_to_pkg lookup |
| `test_scan_js_relative_import_resolved` | JS `../../jspkg-b/src/foo` → _owning_package via pkg_index |
| `test_scan_js_scoped_package` | `@scope/foo` → first-two-segment lookup |
| `test_scan_excludes_test_files_by_default` | D-11: is_test files skipped when include_test_files=False |
| `test_scan_includes_test_files_when_flag_set` | Same fixture; include_test_files=True picks up the test-file imports |
| `test_scan_unreadable_file_silently_skipped` | OSError on missing file → continue, other files still processed |
| `test_scan_stdlib_imports_ignored` | `import json` / `import typing` not in py_map → not in result |

## Deviations from Plan

None — plan executed exactly as written.

**Total deviations:** 0
**Impact:** None.

## Self-Check: PASSED

- Key files exist on disk: `import_scan.py`, `test_import_scan.py`, updated `test_suites.py`
- `git log --oneline --grep="31-02"` returns 4 commits
- All `<acceptance_criteria>` re-run: PASS (26 individual assertions across 4 tasks)
- Plan-level `<verification>` (full graph-io suite): PASS — 223 passed, 1 skipped

## Next Steps

Ready for Wave 1's other plan (31-03) and Wave 2 (31-04). Plan 31-04
will import `scan_package_imports` from `graph_io.import_scan` and use
it to derive `references` edges between Packages.
