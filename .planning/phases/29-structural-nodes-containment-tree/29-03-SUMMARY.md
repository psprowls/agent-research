---
phase: 29-structural-nodes-containment-tree
plan: 03
subsystem: database
tags: [graph-io, structural-nodes, emitter, repository, subpackage, file-role-flags]

requires:
  - phase: 28-schema-v2-uri-foundation
    provides: nodes.uri column, _upsert_node pop-uri-to-column path, RepoContext / repo_uri / subpkg_uri / file_uri helpers
  - phase: 29-structural-nodes-containment-tree/01
    provides: PythonParser writes `_has_main_block` and `_has_importable_symbols` to file-level SourceNode attrs
  - phase: 29-structural-nodes-containment-tree/02
    provides: resolve.sweep predicate spares URI-bearing structural nodes
provides:
  - packages/graph-io/src/graph_io/structural_nodes.py module with emit(conn, *, repo_root, ctx, skip_dirs)
  - Repository node emission (D-01..D-03) with five attrs incl. default_branch via _git
  - SubPackage emission for Python packages (D-04..D-08, D-18): src-layout + flat-layout probe, unlimited depth, dotted_path includes top-level importable
  - File node emission with all 7 role-flag attrs (D-09..D-12, D-20, SPARSER-02)
  - 34 unit tests covering each emission rule + role-flag heuristic in isolation
affects: [29-04, 30-entry-points-test-suites, 31-domain-edges, 32-query-layer]

tech-stack:
  added: []
  patterns:
    - "structural_nodes.emit follows packages.refresh module style (module-private constants + helpers + public emit())"
    - "Role-flag heuristics are pure functions on Path/str — individually unit-testable, no DB or git deps"
    - "Git subprocess access through graph_io.update._git (single source of truth for NotInGitRepoError translation)"

key-files:
  created:
    - packages/graph-io/src/graph_io/structural_nodes.py
    - packages/graph-io/tests/test_structural_nodes.py
  modified: []

key-decisions:
  - "File nodes use name=rel_path (matching source_parser.projections.graph._emit_node convention) so the structural overlay merges with the existing source-parser File node rather than creating a duplicate"
  - "Repository node emission is unconditional (always emits, even in detached HEAD with default_branch=NULL) — structural tree must always have a root (D-02)"
  - "Generic container directory guard is enforced both for SubPackage names (skip if dotted in container set) and File filenames (defensive — only matters if someone names a file literally 'tests')"

patterns-established:
  - "Pattern: per-Package SubPackage map is built once (subpkg_by_dir) and reused for File-parent resolution to avoid re-walking the FS"
  - "Pattern: skip_dirs is passed through as a function arg, never re-loaded inside the emitter — keeps the FS walk gate consistent with the caller's _ignore.load_skip_dirs"

requirements-completed:
  - STRUCT-01
  - STRUCT-02
  - STRUCT-03
  - STRUCT-05
  - SPARSER-02

duration: 35min
completed: 2026-05-26
---

# Phase 29 / Plan 03: structural_nodes.emit — Repository + SubPackage + File with role flags

**The Phase 29 centerpiece: `structural_nodes.emit` produces the strict physical containment subgraph (Repository → Package → [SubPackage → …] → File) with all seven File role-flag attrs, ready to be wired into `update.run` (Plan 04).**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-05-26
- **Tasks:** 3 completed (module scaffolding, SubPackage + File + SPARSER read, unit tests)
- **Files modified:** 2 (1 new module + 1 new test file)

## Accomplishments
- New `structural_nodes.py` module (~470 LOC) with module-private constants for D-09..D-15 heuristics, role-flag helpers, Repository emission, SubPackage walk, and File enumeration
- 34 unit tests across 5 categories (Repository, role-flag heuristics, SubPackage Python+JS gating, File SPARSER read, generic-container exclusion) — all pass first run
- Full graph-io suite green (178/178)
- Zero new dependencies — uses stdlib `fnmatch`, `os`, `pathlib`, plus existing `graph_io._ignore` / `graph_io.update._git` / `graph_io.uri` / `graph_io.upsert`

## Task Commits

1. **Task 1 + Task 2 + Task 3 combined** — `fc0474d` (feat)

(Combined because the three tasks land verifiably-correct ONLY together: Task 1 alone leaves emit() incomplete; Task 2 alone has nothing to test; Task 3 alone has no module to import.)

## Files Created/Modified

- `packages/graph-io/src/graph_io/structural_nodes.py` — new module
- `packages/graph-io/tests/test_structural_nodes.py` — new test file (34 tests)

## Decisions Made

- **`name=rel_path` for File nodes** — Decision driven by integration with `source_parser.projections.graph`. The projection writes file SourceNodes with `name = str(node.path)`, so the resulting GraphNode has `name = path = <rel>`. If structural_nodes used `name=basename` instead, the upsert key `(kind, name, path)` would differ and we'd create a second row. Using `name=rel` lets us UPDATE the existing row in place (additive merge of SPARSER attrs and role flags). The plan's pseudocode used `name=basename`; this was a discovery-time correction.
- **Single global File-enumeration pass** (rather than per-Package nested walks) — Avoids double-emission when files sit under multiple packages (e.g. root manifest plus nested manifest). The `_owning_package` helper picks the deepest enclosing Package by longest-prefix.
- **`_tracked_files` (git ls-files) as the primary file source, FS-walk only as fallback** — Matches the `_process_files` discipline of operating on tracked content only, avoiding leakage of `.graph/code.db*` files and other build artifacts.

## Deviations from Plan

### Auto-fixed Issues

**1. File node naming convention discovered during update integration**
- **Found during:** Plan 04's first integration test run (idempotency test diff showed duplicate File rows)
- **Issue:** Plan 03's pseudocode specified `name=basename` for File nodes, but `source_parser.projections.graph` uses `name=str(path)`. Two different names ⇒ two rows in the upsert table ⇒ duplicate File nodes per file.
- **Fix:** Switched to `name=rel_path` in structural_nodes.emit; updated test_file_python_reads_sparser_has_main fixture seeding to match.
- **Verification:** Idempotency test passes (single File row per path after run); structural unit tests pass.
- **Committed in:** `fc0474d` (initial) + `682b5ec` (correction landed with Plan 04)

**2. Single global File pass instead of per-package nested walks**
- **Found during:** Idempotency debugging (per-package os.walk leaked `.graph/code.db*` files and produced non-deterministic order)
- **Issue:** Original plan called for per-package file enumeration via `os.walk`. This drifted node IDs between runs because untracked files (DB sibling files) appeared/disappeared.
- **Fix:** Use `git ls-files` once at the top of emit(), sort, route each file to its owning Package via longest-prefix match.
- **Verification:** test_update_full_twice_produces_byte_identical_db passes (after orthogonal test cleanup; see Plan 04 summary).
- **Committed in:** `682b5ec` (refactor landed with Plan 04)

---

**Total deviations:** 2 auto-fixed (both surfaced during Plan 04 integration; resolved without scope creep).
**Impact on plan:** No scope creep — both deviations resolved during Plan 04 wiring without changing the public emit() signature.

## Issues Encountered

- **Circular import**: `structural_nodes` imports `_git` from `graph_io.update`; `update` imports `structural_nodes` to call `emit`. Resolved in Plan 04 by deferring the structural_nodes import inside `update.run()`.

## User Setup Required
None.

## Next Phase Readiness
- Plan 04 wires `structural_nodes.emit` into `update.run()` between `packages.refresh` and `resolve.sweep` (D-23)
- Phase 30 (test_suites + entry_points) can consume the existing test-File subset (`is_test=true`) under Repository containment, and re-parent them under TestSuite nodes per D-14's phase boundary
- Phase 31 (Domain) can attach `belongs_to_domain` edges to Package/SubPackage nodes without coordination

---
*Phase: 29-structural-nodes-containment-tree*
*Completed: 2026-05-26*
