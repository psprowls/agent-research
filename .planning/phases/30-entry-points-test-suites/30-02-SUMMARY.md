---
phase: 30-entry-points-test-suites
plan: 02
subsystem: graph-io
tags:
  - graph-io
  - entry-points
  - emitter
  - manifest-parsing

requires:
  - phase: 28-graph-io-foundation
    provides: "entry_point_uri helper, RepoContext, GraphRecords upsert"
  - phase: 29-structural-nodes-containment-tree
    provides: "Package rows (packages.refresh) + _resolve_import_root for Python import-root probing"
  - phase: 30-entry-points-test-suites
    provides: "Module-level _resolve_import_root (already module-level from Phase 29) callable from this emitter"

provides:
  - "entry_points.emit(conn, *, repo_root, ctx, skip_dirs) — manifest-driven EntryPoint emitter (ENTRY-01..05)"
  - "pyproject.toml [project.scripts] + [project.entry-points.<group>] support"
  - "package.json main / module / bin (string + object) / exports (recursive, conditional, wildcard) support"
  - "Strict path-qualified implemented_by resolution (D-05) with stderr warning + NULL on miss (D-06)"

affects:
  - 30-04-update-orchestration
  - 32-query-layer

tech-stack:
  added: []
  patterns:
    - "Per-manifest emitter modules that consume Package rows + emit derived nodes/edges via the shared upsert pipeline"
    - "Recursive package.json exports walker with condition-key set + key-path accumulator"
    - "Upsert-key disambiguation via the path slot (path='condition:<key>') when name+kind collide"

key-files:
  created:
    - packages/graph-io/src/graph_io/entry_points.py
    - packages/graph-io/tests/test_entry_points.py
  modified: []

key-decisions:
  - "EntryPoint node uses 'entry_kind' attribute (not 'kind') to avoid colliding with the node-kind column ('entry_point' is the node kind)"
  - "Conditional exports sharing an export key (e.g. '.' with import vs require) are emitted as separate rows by encoding the condition in the upsert path slot as 'condition:<key>' while keeping the display name = export key"
  - "callable attribute stores the post-':' function name even when implemented_by cannot be resolved — preserves the declaration record for downstream queries"
  - "Wildcard exports never resolve to a File (path expansion deferred to a future phase); is_wildcard=True + path_pattern set"
  - "_walk_exports lives at module level so it can be referenced/tested in isolation, but the emit-side closure (_emit_entry) is local to _emit_packagejson_entries for nodes/edges accumulation"

patterns-established:
  - "Defensive manifest parse: TOMLDecodeError / JSONDecodeError yield a stderr warning and an empty result, never raise"
  - "Stderr warnings for unresolved implemented_by always include the manifest path, Package name, entry name, and raw value — full debugging context"

requirements-completed:
  - ENTRY-01
  - ENTRY-02
  - ENTRY-03
  - ENTRY-04
  - ENTRY-05

duration: 5min
completed: 2026-05-26
---

# Phase 30 Plan 02: Entry-Points Emitter Summary

**Manifest-driven `entry_points.emit` emits EntryPoint + declares_entry_point + implemented_by edges from pyproject.toml and package.json with strict path-qualified resolution and graceful degradation on miss.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-26T02:38:39Z
- **Completed:** 2026-05-26T02:43:32Z
- **Tasks:** 4 completed (Task 4's tests were added incrementally alongside Tasks 1-3)
- **Files modified:** 2 (1 created module + 1 created test file)

## Accomplishments
- New module `packages/graph-io/src/graph_io/entry_points.py` (≈350 lines) exposes a single public `emit()` plus two private per-language helpers and a `_walk_exports` recursive helper.
- Per-manifest dispatch by Package `language` attribute (Python -> `_emit_pyproject_entries`; JS/TS -> `_emit_packagejson_entries`).
- pyproject support: `[project.scripts]` (executable), `[project.entry-points.<group>]` (executable when `group == 'console_scripts'`, library otherwise). Implemented_by resolution walks the dotted module prefix against `_resolve_import_root` and prefers `<foo>.py` over `<foo>/__init__.py`.
- package.json support: `main` / `module` (library), `bin` string form (one executable named after the Package) and object form (one per key), full recursive `exports` walk that distinguishes condition selectors (`import`, `require`, `default`, `node`, `browser`, `types`, `deno`, `worker`) from sub-path keys (`./...`), with wildcard awareness (`is_wildcard` + `path_pattern`; no implemented_by edge on wildcards).
- D-06 graceful degradation: every unresolvable declaration still emits the EntryPoint + declares_entry_point edge, suppressing the implemented_by edge and printing a `[entry_points] warning: cannot resolve implemented_by ...` line to stderr with manifest + Package + entry + value.
- 12 unit tests cover every manifest shape plus parse-failure and shebang anti-tests. All 197 graph-io tests pass (modulo Phase 30 net-add).

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: skeleton import test** — `2d47a85` (test)
2. **Task 1 GREEN: module skeleton + emit dispatch** — `03f20b8` (feat)
3. **Task 2 RED: pyproject + miss + malformed tests** — `d16ef79` (test)
4. **Task 2 GREEN: `_emit_pyproject_entries` (ENTRY-01, D-03..D-06)** — `638fba5` (feat)
5. **Task 3 RED: package.json bin/main/module/exports/edge/shebang tests** — `a7f78f3` (test)
6. **Task 3 GREEN: `_emit_packagejson_entries` + `_walk_exports` (D-07, D-08)** — `30f2eb9` (feat)

(Task 4 added no new commits — its required tests were added incrementally alongside Tasks 1-3.)

## Files Created/Modified
- `packages/graph-io/src/graph_io/entry_points.py` — new module; emit + two private per-language helpers + recursive exports walker.
- `packages/graph-io/tests/test_entry_points.py` — new test file; 12 tests covering all 11 named cases from the plan's behavior list plus the skeleton-import RED test.

## Decisions Made
- **`entry_kind` attribute name.** Stored as `entry_kind` (not `kind`) so the per-EntryPoint executable-vs-library distinction is queryable without colliding with the node-kind column.
- **Conditional-export disambiguation via path slot.** Two EntryPoint rows sharing an export key (`"."` with `import` vs `require`) are kept distinct in the SQLite `(kind, name, path)` upsert key by encoding the condition as `path='condition:<cond>'`. The display name remains the export key; the condition lives in attrs and the path slot.
- **Wildcards: no implemented_by.** Wildcard patterns (`"./helpers/*"`) cannot be resolved to a single File without path expansion — deferred. `is_wildcard=True` + `path_pattern=<value>` are queryable signals for any future expander.
- **`callable` preserved on miss.** The post-`:` function name is recorded in attrs even when the file cannot be resolved, so the declaration record is preserved for downstream queries (D-04).
- **Shebang scripts excluded.** A trailing comment in the module makes ENTRY-05 explicit: shebang scripts ride on `File.is_executable` from Phase 29, never the EntryPoint emitter.

## Deviations from Plan

- **Inlined Task 4 into Tasks 1–3.** Plan's Task 4 enumerated 11 named tests to add. Following TDD, each Task 1/2/3 RED step already wrote its tests inline; Task 4 became a verification pass (no new code). All 11 named test functions are present (verified by `grep -cE 'def test_(...|...)'` → 11).
- **Path-slot disambiguation for conditional exports** (Rule 1 - Bug). The plan's behavior spec implied two separate EntryPoint rows sharing a name; the initial implementation collided in the upsert key `(kind, name, path)`. Fix: encode `condition` in the path slot (`path='condition:<key>'`) so both rows survive. Stored in commit `30f2eb9`.
- **`_resolve_import_root` import.** Plan referenced `_resolve_import_root` from `graph_io.structural_nodes`; that helper has been module-level since Phase 29, so no Plan 30-01 dependency was needed (the hoist in 30-01 was for `_owning_package`, not `_resolve_import_root`).

**Total deviations:** 1 Rule-1 auto-fixed (path-slot disambiguation). **Impact:** None on the plan's contract — both conditional EntryPoints are emitted and queryable as the plan requires; the path-slot encoding is an implementation detail behind the upsert layer.

## Verification Results

- `uv run --package graph-io pytest packages/graph-io/tests/test_entry_points.py -v` → **12 passed** in 0.09s.
- `uv run --package graph-io pytest packages/graph-io/tests/ -q` → **197 passed** in 10.12s (full graph-io suite, no regressions).
- `uv run --package graph-io python -c "from graph_io.entry_points import emit; print('ok')"` → **ok**.
- `grep -c 'kind="entry_point"' packages/graph-io/src/graph_io/entry_points.py` → **2**.
- `grep -c 'declares_entry_point' packages/graph-io/src/graph_io/entry_points.py` → **4**.
- No new external deps: `grep -E '^(import|from)' .../entry_points.py | grep -vE 'allowed'` → **0**.

## Self-Check: PASSED

- File `packages/graph-io/src/graph_io/entry_points.py` exists and imports cleanly.
- File `packages/graph-io/tests/test_entry_points.py` exists with 12 tests.
- All 11 named test functions from the plan present.
- emit + _emit_pyproject_entries + _emit_packagejson_entries + _walk_exports + _EXPORT_CONDITION_KEYS confirmed via grep.
- Full graph-io suite: 197 passed.
- Commit hashes verified via `git log`.

## Next Plan Readiness

Plan 30-03 (`test_suites.emit`) can reuse `_owning_package` (hoisted in 30-01) and the same upsert / GraphRecords pattern. Plan 30-04 will wire `entry_points.emit` into `update.run()` and exercise it on the Phase 29-04 sample-monorepo fixture (which already contains a `pyproject.toml` with `[project.scripts]` and a `package.json` with `bin`).
