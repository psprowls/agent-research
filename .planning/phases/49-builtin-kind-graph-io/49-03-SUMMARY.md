---
phase: 49-builtin-kind-graph-io
plan: "03"
subsystem: graph-io
tags: [builtin-kind, graph-io, cli, queries, integration-test]
dependency_graph:
  requires:
    - 49-01  # _VALID_KINDS "builtin" + builtin_uri already in place
    - 49-02  # builtins.refresh() wired into update.run()
  provides:
    - graph_io.queries.BuiltinDescription dataclass
    - graph_io.queries.describe_builtin(conn, *, language, module_name)
    - graph_io.queries.list_builtins(conn)
    - graph_io.cli.q_list_builtins (cg list-builtins)
    - graph_io.cli.q_describe_builtin (cg describe-builtin <uri>)
    - tests: 4 query tests, 4 describe-builtin CLI tests, 3 list-builtins CLI tests, 5 e2e integration tests
  affects:
    - packages/graph-io
tech_stack:
  added: []
  patterns:
    - describe_builtin mirrors describe_dependency (SQL join, path-based lookup)
    - list_builtins is a one-liner via _list_by_kind (mirrors list_dependencies)
    - q_describe_builtin parses builtin:<lang>/<mod> URI then delegates to queries
    - path=language as upsert key discriminator for cross-language module name collisions
key_files:
  created:
    - packages/graph-io/src/graph_io/cli/q_list_builtins.py
    - packages/graph-io/src/graph_io/cli/q_describe_builtin.py
    - packages/graph-io/tests/integration/test_e2e_builtins.py
  modified:
    - packages/graph-io/src/graph_io/queries.py
    - packages/graph-io/src/graph_io/builtins.py
    - packages/graph-io/src/graph_io/update.py
    - packages/graph-io/src/graph_io/cli/main.py
    - packages/graph-io/tests/test_queries.py
    - packages/graph-io/tests/test_cli_describe.py
    - packages/graph-io/tests/test_cli_smoke.py
decisions:
  - "describe_builtin uses WHERE kind='builtin' AND name=module_name AND path=language — path=language is the upsert key discriminator enabling python/os and javascript/os to coexist"
  - "builtins.py node emission uses path=lang instead of path=None so cross-language collisions are impossible"
  - "update.py DELETE cleanup excludes kind='builtin' alongside kind='package' since builtins use path=language (not a file path) and must not be cleaned up during full rebuilds"
  - "test_e2e_builtins uses mixed_workspace.parent (not .parent/'repo') as the repo root — workspace is child of repo root"
metrics:
  duration: "~12 minutes"
  completed: "2026-05-28"
  tasks_completed: 3
  tasks_total: 3
---

# Phase 49 Plan 03: Builtin CLI Surface Summary

## One-liner

Added `BuiltinDescription` + `describe_builtin()` + `list_builtins()` to queries, two CLI handlers (`cg list-builtins`, `cg describe-builtin <uri>`), registered both in `cli/main._SUBCOMMANDS`, and locked the pipeline with 16 new tests including a 5-test end-to-end integration suite.

## What Was Built

### Task 1: Query layer (queries.py + builtins.py + update.py + test_queries.py)

**`BuiltinDescription` dataclass** added immediately after `DependencyDescription`:
- Fields: `language`, `module_name`, `uri`, `used_by: list[str]`

**`describe_builtin(conn, *, language, module_name)`** added after `describe_dependency`:
- SQL: `WHERE kind='builtin' AND name=? AND path=?` (path=language as discriminator)
- Populates `used_by` via inbound `used_by` edges from `package` nodes (ORDER BY name)
- Returns `None` when not found

**`list_builtins(conn)`** added after `list_dependencies`:
- One-liner: `return _list_by_kind(conn, "builtin")`

**Auto-fix [Rule 1 - Bug] — builtins.py path=lang discriminator:**
- Found that `path=None` for all builtin nodes creates `(kind, name, path)` collisions when two languages use the same module name (e.g., Python's `os` and Node.js's `os`)
- Fixed: `builtins.py` now emits `path=lang` for builtin nodes and `dst=("builtin", module_name, lang)` for edges
- Fixed: `update.py` DELETE cleanup changed to `kind NOT IN ('package', 'builtin')` so builtin nodes with `path=language` (not a file path) survive full-rebuild purges

**4 new test functions in test_queries.py:**
- `test_list_builtins_alphabetical`: 3 nodes, asserts sorted order
- `test_describe_builtin_returns_description`: 1 builtin + 1 package + 1 edge, asserts all fields
- `test_describe_builtin_returns_none_when_missing`: one-liner assertion
- `test_describe_builtin_filters_by_language`: python/os and javascript/os coexist, filter returns correct one

### Task 2: CLI handlers (q_list_builtins.py, q_describe_builtin.py, main.py)

**`q_list_builtins.py`** — mirrors `q_list_packages.py` verbatim:
- Calls `queries.list_builtins(conn)`
- Human: `print(r.name)` per record
- JSON: `dataclasses.asdict` list
- Empty: `"No builtins in graph."` to stderr (human) or `[]` (JSON)

**`q_describe_builtin.py`** — mirrors `q_describe_dependency.py` with URI parse:
- Parses `builtin:<language>/<module_name>` — rejects non-`builtin:` prefix (GENERIC) and missing `/` (GENERIC)
- Calls `queries.describe_builtin(conn, language=language, module_name=module_name)`
- Human: labelled lines for `language`, `module_name`, `uri`, `used_by`
- JSON: `dataclasses.asdict(desc)`

**`cli/main.py`** registration:
- `q_describe_builtin` imported alphabetically before `q_describe_dependency`
- `q_list_builtins` imported alphabetically before `q_list_domains`
- `"describe-builtin"` inserted before `"describe-dependency"` in `_SUBCOMMANDS`
- `"list-builtins"` inserted before `"list-packages"` in `_SUBCOMMANDS`

### Task 3: Tests (test_cli_describe.py, test_cli_smoke.py, integration/test_e2e_builtins.py)

**test_cli_describe.py** — added `workspace_with_builtins` fixture + 4 tests:
- `test_cg_describe_builtin_smoke`: human output fields verified
- `test_cg_describe_builtin_not_found`: GENERIC + stderr `"error: builtin not found:"`
- `test_cg_describe_builtin_json`: JSON keys + types verified
- `test_cg_describe_builtin_malformed_uri`: two malformed URIs, two assertions

**test_cli_smoke.py** — added `builtin_repo` fixture + 3 tests via subprocess:
- `test_cg_list_builtins_smoke`: exit 0, `pathlib` and `os` in output lines
- `test_cg_list_builtins_json`: exit 0, `kind="builtin"` in all entries
- `test_cg_list_builtins_empty`: exit 0, human → stderr warning, json → `[]`

**integration/test_e2e_builtins.py** — 5 end-to-end tests via direct API calls:
- `test_e2e_python_and_node_builtins_emitted`: `pathlib` + `os` in list; `fs`/`path` conditional on Node
- `test_e2e_describe_python_builtin_shows_used_by`: `language:`, `pathlib`, `demo` in output
- `test_e2e_npm_dependency_classification_unchanged`: `boto3` stays as dependency
- `test_e2e_express_remains_dependency_not_builtin`: `builtin:javascript/express` → GENERIC
- `test_e2e_idempotency`: two incremental updates yield same Builtin node count

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `0aaa6f8` | feat(49-03): add BuiltinDescription, describe_builtin(), list_builtins() to queries.py |
| 2 | `347542c` | feat(49-03): add q_list_builtins.py + q_describe_builtin.py CLI handlers, register in main.py |
| 3 | `dbf6ca0` | test(49-03): add CLI tests for list-builtins and describe-builtin, plus e2e integration test |

## Verification

- `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -x -q` → 80 passed, 1 skipped
- `uv run --package graph-io pytest packages/graph-io/tests/test_cli_describe.py -x -q` → 9 passed
- `uv run --package graph-io pytest packages/graph-io/tests/test_cli_smoke.py -x -q` → 23 passed
- `uv run --package graph-io pytest packages/graph-io/tests/integration/test_e2e_builtins.py -x -q` → 5 passed
- `uv run pytest packages/graph-io/tests/ packages/wiki-io/tests/test_entity_templates.py -x -q` → 423 passed, 3 skipped, 1 xfailed
- `uv run cg --help 2>&1 | grep -c "list-builtins\|describe-builtin"` → 2

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed builtin node upsert collision when two languages share a module name**
- **Found during:** Task 1 test execution (`test_describe_builtin_filters_by_language` failed)
- **Issue:** `builtins.py` used `path=None` for all builtin nodes, so `("builtin", "os", None)` is the same upsert key for both Python's `os` and Node.js's `os` — the second upsert would silently overwrite the first
- **Fix:** Changed `builtins.py` to use `path=lang` as the upsert key discriminator; updated edge dst to `("builtin", module_name, lang)`; updated `describe_builtin` SQL to use `WHERE name=? AND path=?` (path=language) instead of `json_extract`; updated `update.py` DELETE to exclude `kind='builtin'` from full-rebuild cleanup (since `path=language` is not a file path)
- **Files modified:** `packages/graph-io/src/graph_io/builtins.py`, `packages/graph-io/src/graph_io/queries.py`, `packages/graph-io/src/graph_io/update.py`
- **Commit:** `0aaa6f8`

**2. [Rule 1 - Bug] Fixed path construction in test_e2e_idempotency**
- **Found during:** Task 3 integration test execution
- **Issue:** The plan's fixture used `mixed_workspace.parent / "repo"` but `mixed_workspace` is `tmp_path/repo/graph-wiki`, making `.parent` already `tmp_path/repo` (the repo root) — adding `/"repo"` produced a nonexistent path
- **Fix:** Changed to `repo = mixed_workspace.parent` (no `/"repo"` suffix)
- **Files modified:** `packages/graph-io/tests/integration/test_e2e_builtins.py`
- **Commit:** `dbf6ca0`

## Known Stubs

None — all functionality is implemented and exercised by tests.

## Threat Flags

None — threat model mitigations from the plan's STRIDE register are implemented:
- T-49-03-T: `args.uri` parsed via `startswith` + `split("/", 1)`; resulting language + module_name bound as SQL parameters `?` — no string concatenation into SQL
- T-49-03-I: accepted (repo source is the trust boundary)
- T-49-03-D: accepted (read-only; bounded by stdlib module count)

## Self-Check: PASSED

- `packages/graph-io/src/graph_io/queries.py` — FOUND (contains `class BuiltinDescription`, `def describe_builtin`, `def list_builtins`)
- `packages/graph-io/src/graph_io/cli/q_list_builtins.py` — FOUND
- `packages/graph-io/src/graph_io/cli/q_describe_builtin.py` — FOUND
- `packages/graph-io/src/graph_io/cli/main.py` — FOUND (contains `"describe-builtin"` and `"list-builtins"`)
- `packages/graph-io/tests/integration/test_e2e_builtins.py` — FOUND (5 test functions)
- Commits `0aaa6f8`, `347542c`, `dbf6ca0` — all verified in git log
- Full test suite: 423 passed, 3 skipped, 1 xfailed
