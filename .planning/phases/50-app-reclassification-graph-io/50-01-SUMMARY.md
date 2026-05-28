---
phase: 50-app-reclassification-graph-io
plan: "01"
subsystem: graph-io
tags: [app-kind, graph-io, classification, manifest-readers, schema-foundation]
requires:
  - phase-49-builtin-kind-graph-io
provides:
  - graph_io.queries._VALID_KINDS admits "app"
  - graph_io.queries._VALID_APP_KINDS frozenset
  - graph_io.uri.app_uri builder
  - graph_io.packages._read_pyproject scripts_present field
  - graph_io.packages._read_package_json bin_present field
  - graph_io.classification.classify pure function
  - graph_io.classification._FRAMEWORK_PRECEDENCE constant
affects:
  - All downstream graph-io callers that iterate _VALID_KINDS or call into manifest readers
tech-stack:
  added: []
  patterns:
    - "pure-function-classification (classify takes info dict + pkg_dir, returns tuple — no I/O)"
    - "frozenset-write-time-gate (_VALID_APP_KINDS rejects malformed app_kind before DB write)"
key-files:
  created:
    - packages/graph-io/src/graph_io/classification.py
    - packages/graph-io/tests/test_classification.py
  modified:
    - packages/graph-io/src/graph_io/queries.py
    - packages/graph-io/src/graph_io/uri.py
    - packages/graph-io/src/graph_io/packages.py
    - packages/graph-io/tests/test_queries.py
    - packages/graph-io/tests/test_uri.py
    - packages/graph-io/tests/test_packages.py
key-decisions:
  - "D-12 honored: SCHEMA_VERSION stays at 2 — admitting a new kind is additive only"
  - "D-04 implemented as both a frozenset (queries._VALID_APP_KINDS) and a runtime ValueError inside classify() so typos surface at the classify call site, not at the DB"
  - "_FRAMEWORK_PRECEDENCE placed in classification.py (not queries.py) — only classify() consumes the order; queries.py only enforces membership"
requirements-completed:
  - APP-01
  - APP-03
  - APP-04
duration: "5 min"
completed: "2026-05-28"
---

# Phase 50 Plan 01: App Schema Foundation Summary

App graph kind admitted (`"app"` in `_VALID_KINDS`), `_VALID_APP_KINDS = frozenset({"cli","expo","nextjs","spa"})` added as the write-time gate, `app_uri(ctx, name)` builder lands next to `pkg_uri`, manifest readers now surface `scripts_present` / `bin_present` presence booleans, and a new pure module `graph_io.classification` ships the `classify(info, pkg_dir) -> (kind, app_kind, app_signals)` function with the documented framework-precedence rule. All foundational primitives Plan 02 and Plan 03 depend on are in place.

## Execution Times

- Start: 2026-05-28T01:59:24Z
- End:   2026-05-28T02:04:02Z
- Duration: 5 min
- Tasks: 3 (Task 1 admit+URI, Task 2 manifest-reader fields, Task 3 classify module)
- Files touched: 8 (3 src modified + 1 src created + 3 tests modified + 1 test created)

## Task-by-Task

### Task 1: Admit "app" kind, add _VALID_APP_KINDS gate, ship app_uri builder

- **RED commit** d30ccc7 — three failing tests (test_valid_kinds_includes_app, test_valid_app_kinds_contents, test_app_uri_shape)
- **GREEN commit** 6854087 — admitted `"app"` to `_VALID_KINDS` with Phase 50 D-12 comment; defined `_VALID_APP_KINDS` immediately below; added `app_uri` directly after `pkg_uri` in `uri.py`
- 106 passed, 1 skipped (test_queries + test_uri together)
- SCHEMA_VERSION unchanged (still `2`)

### Task 2: Surface scripts_present and bin_present on manifest info dicts

- **RED commit** 9752be6 — six failing tests covering all Python+JS presence-boolean cases
- **GREEN commit** 1cc5316 — `_read_pyproject` derives `scripts = project.get("scripts") or {}` then appends `scripts_present: bool(scripts)`; `_read_package_json` derives `bin_present` from the JS bin field (truthy when non-empty string OR dict with any truthy value); legacy keys preserved in both readers
- 22 passed (full `test_packages.py`)
- Raw `bin` payload intentionally NOT exposed — only the boolean signal (per PATTERNS.md "only the boolean")

### Task 3: Add classification.py pure module + 8 unit tests

- **RED commit** f1bc032 — 8 failing tests (every signal type + precedence rule)
- **GREEN commit** 60f6b99 — created `graph_io/classification.py` (83 lines) with `_FRAMEWORK_PRECEDENCE = ("nextjs", "expo", "spa")` and the pure `classify()` implementation
- Purity gate verified: `grep -cE "import sqlite3|import subprocess|store\.|conn\."` returns 0
- 8 tests pass; spa test writes `tmp_path / "index.html"` to exercise the filesystem check

## Verification Results

- `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py packages/graph-io/tests/test_uri.py packages/graph-io/tests/test_packages.py packages/graph-io/tests/test_classification.py -x -q` → **136 passed, 1 skipped** (baseline 119 + 17 new tests)
- `uv run --package graph-io pytest packages/graph-io/tests/ -x -q` → **426 passed, 1 skipped, 1 xfailed** — no regressions across the full graph-io test suite
- Smoke import: `from graph_io.queries import _VALID_KINDS, _VALID_APP_KINDS; from graph_io.uri import app_uri; from graph_io.classification import classify; print('ok')` → `ok`
- `grep -n "SCHEMA_VERSION" packages/graph-io/src/graph_io/schema.py` → `SCHEMA_VERSION = 2` (no bump)
- Acceptance-criteria smoke: `classify({'language':'python','scripts_present':True}, Path('/tmp'))` → `('app', 'cli', ['cli'])`; `classify({'language':'javascript','dependencies':['next','react'],'bin_present':True}, Path('/tmp'))` → `('app', 'nextjs', ['cli', 'nextjs'])`

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0.
**Impact:** None.

## Key Decisions

- **classify() write-time gate is both static and runtime.** The plan asked for an assertion confirming the derived `app_kind` is in `_VALID_APP_KINDS`. Implemented as an explicit `if app_kind not in _VALID_APP_KINDS: raise ValueError(...)` rather than a bare `assert` so the check survives `python -O`. This matches the wording "explicit if/raise ValueError" in the plan's action block.
- **`_FRAMEWORK_PRECEDENCE` lives in `classification.py`, not `queries.py`.** Only `classify()` consumes the order. `queries.py` only needs membership (`_VALID_APP_KINDS`). Keeping them split mirrors how `builtins.py` owns Python/JS builtin module sets while `queries.py` only owns the kind membership.
- **`scripts_present` / `bin_present` are booleans only — no raw payload.** RESEARCH.md §"Manifest Reader Extension" and PATTERNS.md both prescribe boolean-only. Avoids enlarging the manifest-info surface unnecessarily.

## Self-Check: PASSED

- [x] All 3 tasks executed
- [x] Each task committed atomically (RED test commit + GREEN code commit per task)
- [x] Plan-level verification (`<verification>` block) all green
- [x] All `<acceptance_criteria>` from every task verified
- [x] SCHEMA_VERSION unchanged at 2 (D-12 honored)
- [x] No regressions in 426-test graph-io baseline

## Issues Encountered

None.

## Next Phase Readiness

Plan 02 (emit-loop wiring + D-06 kind-flip) is unblocked. All five primitives it needs (`_VALID_KINDS` admits `"app"`, `_VALID_APP_KINDS` frozenset, `app_uri()`, `scripts_present`/`bin_present` on info dicts, `classify()` pure function) are live and tested.

Ready for `50-02`.
