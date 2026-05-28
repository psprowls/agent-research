---
phase: 51-package-family-removal-divergence-rule-cleanup
plan: 01
subsystem: graph-io
tags: [graph-io, schema-cleanup, package-family-removal, kind-admission-set]
requires: []
provides:
  - "_VALID_KINDS frozenset locked without package_family (regression-tested)"
  - "graph_io.uri surface free of package_family_uri builder"
  - "CLI _SUBCOMMANDS registry guarded against future package_family revival"
affects: [graph_io.queries, graph_io.uri, graph_io.cli.main]
tech_stack:
  added: []
  patterns: [negative-assertion-tests, retirement-marker-comments]
key_files:
  created:
    - packages/graph-io/tests/test_cli_main.py
  modified:
    - packages/graph-io/src/graph_io/uri.py
    - packages/graph-io/tests/test_uri.py
decisions:
  - "D-02 honored: no SCHEMA_VERSION bump, no pre-flight migration scan, no stale-row migration command. Users rebuild via `cg update --full`."
  - "Task 01 source-removal step was a no-op: `package_family` was already absent from `_VALID_KINDS` in graph_io.queries at execution time (likely removed in a prior phase). The plan still produced its durable artifact — a negative-assertion test — so any future re-introduction regresses CI."
  - "Added optional belt-and-suspenders test `tests/test_cli_main.py` for PKGFAM-04 despite the plan marking it optional, because the cost (~14 LOC) is trivial and the test pins a registry-level invariant that grep alone cannot enforce at runtime."
  - "Retained intentional `package_family` mentions only in (a) negative-assertion tests and (b) a single retirement-marker comment in uri.py for future code-archaeology."
metrics:
  duration: ~15min
  tasks_completed: 3
  files_modified: 3
  completed: 2026-05-28
---

# Phase 51 Plan 01: graph-io package_family removal Summary

Removed `package_family_uri` from `graph_io.uri` and locked the absence of `package_family` from the `_VALID_KINDS` admission set + CLI subcommand registry via negative-assertion tests; verified PKGFAM-04 (CLI) and PKGFAM-05 (domain layer untouched) by inspection and a clean 453-pass regression run.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 51-01-01 | Assert `package_family` absent from `_VALID_KINDS` | `5e7166a` | `tests/test_uri.py` |
| 51-01-02 | Delete `package_family_uri` builder + its test | `248aec5` | `src/graph_io/uri.py`, `tests/test_uri.py` |
| 51-01-03 | Add CLI subcommand absence guard; full regression | `c271d8f` | `tests/test_cli_main.py` (new) |

## Verification

- `uv run --package graph-io pytest packages/graph-io/tests/ -x` → **453 passed, 3 skipped, 1 xfailed** (xfailed/skips pre-existed and are unrelated to this plan).
- `grep -rn "package_family" packages/graph-io/ --include="*.py"` → only the new negative-assertion tests and the single retirement-marker comment in `uri.py`. No live code paths.
- `grep -nE 'describe-package-family|list-package-families' packages/graph-io/src/graph_io/cli/` → zero hits.
- `git diff HEAD~3 HEAD -- packages/graph-io/src/graph_io/ | grep -i SCHEMA_VERSION` → empty (D-02 honored).
- `python -c "from graph_io.uri import package_family_uri"` → `ImportError` (deletion confirmed at runtime).

## Deviations from Plan

### 1. Task 01 source removal was a no-op (`_VALID_KINDS` already cleaned)

- **Found during:** Task 01 (pre-edit verification).
- **Issue:** `RESEARCH.md` directed deletion of `"package_family"` from `_VALID_KINDS` at `queries.py:9-29`. At execution time, the literal was already absent — likely removed in a prior phase before the planner ran their snapshot.
- **Fix:** None required for the source. Added the durable artifact the task was really about — a negative-assertion test (`test_valid_kinds_excludes_package_family`) — so any future re-introduction of `package_family` regresses CI.
- **Files modified:** `packages/graph-io/tests/test_uri.py` only.
- **Commit:** `5e7166a`.
- **Rule:** None (Rule 3 wasn't needed; the absence pre-existed). Documented here for traceability of the source-of-truth drift between `RESEARCH.md` snapshot and HEAD at execution time.

### 2. Added optional belt-and-suspenders test (Task 03)

- **Found during:** Task 03.
- **Why:** Plan marked `tests/test_cli_main.py` as optional; chose to add it because the cost (~14 LOC) is trivial and it pins a runtime invariant (`"describe-package-family" not in _SUBCOMMANDS`) that the grep gate cannot enforce dynamically.
- **Files modified:** `packages/graph-io/tests/test_cli_main.py` (new).
- **Commit:** `c271d8f`.

## Decisions Made

1. **D-02 (no SCHEMA_VERSION bump) honored** — confirmed by diff over the plan range; no schema field touched.
2. **Comment cleanup in `uri.py`** — replaced the deleted function body with a single retirement-marker comment (`# Phase 51 PKGFAM-02: package_family entity kind retired; builder removed.`) rather than removing all trace, so future readers see why the slot is empty.
3. **Test naming** — `test_valid_kinds_excludes_package_family` and `test_no_package_family_subcommand` chosen for grep-discoverability against the PKGFAM-XX requirement IDs.

## Known Stubs

None.

## Threat Flags

None — this plan deletes surface, it does not add any.

## Self-Check: PASSED

- Files created: `packages/graph-io/tests/test_cli_main.py` — FOUND.
- Files modified: `packages/graph-io/src/graph_io/uri.py`, `packages/graph-io/tests/test_uri.py` — both modified per `git diff --stat`.
- Commits: `5e7166a`, `248aec5`, `c271d8f` — all found via `git log`.
- Full regression: 453 passed (graph-io suite).
