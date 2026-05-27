---
phase: 43-entity-writer
plan: 01
subsystem: graph-io
tags: [graph-ingestion, pep508, dependency-graph, plugins, subpackage-fix]

requires:
  - phase: 42-uri-slug-scheme-per-kind-templates
    provides: dependency_uri / plugin_uri / package_family_uri builders; entity-*.md templates
provides:
  - DependencyDescription + PluginDescription dataclasses in graph_io.queries
  - 4 new read-only helpers: describe_dependency / list_dependencies / describe_plugin / list_plugins
  - _VALID_KINDS extended from 10 to 12 (added "dependency", "plugin")
  - packages.refresh ingests [project.dependencies] + [dependency-groups] -> dependency nodes + used_by edges
  - _extract_dep_name PEP 508 bare-name helper
  - new graph_io.plugins module with emit() that reads .graph-wiki.yaml plugins[]
  - update.run wired to call plugins.emit after structural_nodes.emit
  - structural_nodes._walk_subpackages no longer yields the import root (folded todo)
affects: [43-02 (entity_writer mock graph surface), 43-03 (integration tests), 45 (run_scan Step 9a)]

tech-stack:
  added: []
  patterns:
    - "PEP 508 bare-name extraction via anchored regex (no full PEP 503 normalization in v1.8)"
    - "Graph URIs stored in nodes.uri column, not in attrs_json (graph-io v1.6 convention)"
    - "Dependency aggregation across all manifests before emit (one dependency node per (ecosystem, name))"
    - "used_by edges deduped per (consumer, dep) pair"
    - "Tiny per-kind emitter module pattern (plugins.py mirrors domains.py shape)"

key-files:
  created:
    - packages/graph-io/src/graph_io/plugins.py
    - packages/graph-io/tests/test_plugins.py
  modified:
    - packages/graph-io/src/graph_io/queries.py
    - packages/graph-io/src/graph_io/packages.py
    - packages/graph-io/src/graph_io/structural_nodes.py
    - packages/graph-io/src/graph_io/update.py
    - packages/graph-io/tests/test_queries.py
    - packages/graph-io/tests/test_packages.py
    - packages/graph-io/tests/test_structural_nodes.py
    - .planning/todos/resolved/2026-05-26-fix-scanner-treats-import-root-as-subpackage.md (moved from pending/)

key-decisions:
  - "Read graph URI from nodes.uri column (not attrs_json) — graph-io v1.6 convention (upsert pops uri out)"
  - "plugins.emit tolerates RuntimeError from read_manifest (v1 manifests, parse errors) — skips silently rather than breaking cg update"
  - "Dependency name extraction does NOT apply full PEP 503 normalization in v1.8 (only lowercase) — matches RESEARCH.md Open Question Q1"
  - "used_by edges deduped per (consumer_name, dep_name) — a dep listed in both [project.dependencies] and [dependency-groups] produces ONE edge"
  - "package.json deps are NOT ingested as dependency nodes in this plan — only Python manifests (info[\"language\"] == \"python\") emit deps"
  - "plugins.emit's ctx parameter unused for URIs (plugin URIs are concept-level per Phase 42 D-04) but accepted for symmetry with other emitters"

patterns-established:
  - "Per-(ecosystem, name) dependency aggregation: collect across all manifests, then emit once at end of refresh"
  - "Self-referential subpackage fix: _walk_subpackages skips the import root via d.resolve() == import_root_resolved guard"
  - "Tolerant manifest reading: try/except RuntimeError around read_manifest when used by emitters"

requirements-completed: []

duration: 70min
completed: 2026-05-27
---

# Phase 43 Plan 01: graph-io dependency + plugin kinds + folded subpackage fix

**Two new graph kinds (`dependency`, `plugin`) admitted with full ingestion + read surface; folded subpackage bug fix landed in the same pass.**

## What was built

Five tasks in one plan:

1. **Task 1 (queries.py + tests):** Added `dependency` and `plugin` to `_VALID_KINDS` (now 12 kinds), defined `DependencyDescription` and `PluginDescription` dataclasses, implemented `describe_dependency`, `list_dependencies`, `describe_plugin`, `list_plugins`. 6 new tests; all 74 `test_queries.py` tests pass.

2. **Task 2 (packages.py + tests):** Added `_extract_dep_name` (anchored regex `^[A-Za-z0-9_.\-]+`, lowercases, skips URL/relative-path forms). Extended `_read_pyproject` to include a `dep_groups` field for PEP 735 `[dependency-groups]`. Extended `refresh` to accumulate deps across all manifests, emit one `dependency` node per `(ecosystem, name)`, and emit `used_by` edges from each consumer package to each dep (deduped). 9 new tests; all 16 `test_packages.py` tests pass.

3. **Task 3 (plugins.py + update wiring + tests):** New 67-LOC `graph_io.plugins` module with `emit(conn, *, workspace_root, ctx)` that reads `.graph-wiki.yaml` `plugins[]` and emits one `kind:plugin` node per entry with attrs `{uri, ecosystem: "claude-code", name, installed_version?, applied_version?}`. Wired into `update.run` after `structural_nodes.emit`. 5 new tests; tolerates v1 manifests + parse errors silently (RuntimeError).

4. **Task 4 (folded todo, _walk_subpackages fix):** Modified `_walk_subpackages` to skip yielding the import root itself while still descending into its children. Re-baselined 6 existing tests for new (correct) counts and parent assignments. Added 2 regression tests (`test_no_subpackage_node_at_import_root`, `test_no_subpackages_when_only_import_root`). Moved `2026-05-26-fix-scanner-treats-import-root-as-subpackage.md` from `pending/` to `resolved/` via `git mv`.

5. **Task 5 (full graph-io suite green):** `uv run --package graph-io pytest` exits 0 — 353 passed, 1 skipped, 1 xfailed. Caught and patched a regression in `test_cli_sync_wiki.py` (fixture uses a v1 manifest; fixed `plugins.emit` to skip on `RuntimeError` from `read_manifest`).

## Specific numbers for downstream

- **`_VALID_KINDS` element count:** 12 (10 original + `dependency` + `plugin`)
- **Subpackage rebaselines:** `test_subpackage_python_src_layout` 3 -> 2; `test_subpackage_python_flat_layout` 1 -> 0; `test_physically_contains_is_strict_tree` `n_subpkgs >= 3` -> `n_subpkgs >= 2`; `test_subpackage_parent_is_package_for_top_level` rewritten to assert nested-sub parent (the import root is no longer a subpackage); `test_subpackage_parent_is_enclosing_subpackage_for_nested` rewritten to use doubly-nested subpackage; `test_non_test_python_file_parented_by_subpackage` rewritten — file directly under import root is now parented by `package`, file in nested subpackage stays parented by that subpackage.
- **PEP 508 edge cases:** `git+...` URL deps return None and are skipped silently. The 7 parametrized cases all pass (`boto3>=1.38` -> `boto3`, `langchain-aws[bedrock]>=1.4.6` -> `langchain-aws`, env markers, lowercase normalization, empty -> None, URL -> None).
- **`update.py` workspace_root threading:** Already threaded — `workspace` was already in scope inside `update.run` (resolved at the top via `resolve_workspace`). Just needed to pass `workspace_root=workspace` to `plugins.emit`.

## Dependency node count (real workspace)

Not measured during this plan (no integration test against real workspace yet — that's Plan 43-03 Task 1). The plan's `must_haves.truths` includes "real workspace fixture" assertions that will be verified in 43-03.

## Deviations from Plan

[Rule 1 - Bug] **Graph URI stored in nodes.uri column, not attrs_json**
- Found during: Task 1 test_describe_dependency_returns_dependency_description initial run
- Issue: First implementation read URI from `attrs.get("uri", "")` but the URI returned empty string because graph-io's upsert layer pops `uri` out of attrs and stores it in the dedicated `nodes.uri` column
- Fix: Select `uri` from the column directly (`SELECT id, name, attrs_json, uri FROM nodes ...`) for both describe_dependency and describe_plugin
- Files modified: packages/graph-io/src/graph_io/queries.py
- Verification: re-ran failing test; passed
- Commit hash: aa1b07d

[Rule 1 - Bug] **plugins.emit broke cg update on v1 manifests**
- Found during: Task 5 full-suite run
- Issue: `read_manifest` raises `RuntimeError` for v1 .graph-wiki.yaml files; test_cli_sync_wiki.py's fixture uses v1 format, and my new `plugins.emit` was now called inside `update.run`, propagating the error and breaking the cli test
- Fix: Wrap `read_manifest` call in try/except RuntimeError and return silently
- Files modified: packages/graph-io/src/graph_io/plugins.py
- Verification: test_cli_sync_wiki tests now pass; plugin tests still pass
- Commit hash: 21bfd12

**Total deviations:** 2 auto-fixed (both Rule 1 bugs). **Impact:** None — both fixes match the spirit of the plan (URI handling matches existing queries.py patterns; plugins.emit's "silently tolerates missing manifest" intent extends naturally to "silently tolerates unreadable manifest").

## Self-Check: PASSED

- `from graph_io.queries import DependencyDescription, PluginDescription, describe_dependency, list_dependencies, describe_plugin, list_plugins` — OK
- `from graph_io.plugins import emit` — OK
- `_VALID_KINDS` has 12 elements
- `update.py` calls `plugins.emit` after `structural_nodes.emit` (line 304)
- `_walk_subpackages` does not yield import root (verified by `test_no_subpackage_node_at_import_root`)
- Folded todo moved to `.planning/todos/resolved/2026-05-26-fix-scanner-treats-import-root-as-subpackage.md`
- `uv run --package graph-io pytest` — 353 passed, 1 skipped, 1 xfailed
