---
phase: 37-librarian-grounding-tools
plan: 01
subsystem: librarian-tools
tags: [langchain-aws, langchain-core, sqlite, graph-io, tool-binding]

requires:
  - phase: 36-cg-find-parser-ergonomics
    provides: _format.render(records, fmt=..., cap=..., on_truncate=...) with cap kwarg, queries.find(*, name=, kind=, in_package=)
provides:
  - build_graph_tools(conn) closure factory returning 5 @tool callables (cg_find, cg_describe, cg_callers, cg_callees, cg_imports)
  - seeded_graph_conn pytest fixture (session-scoped) reusing packages/graph-io's sample_monorepo
  - graph-io workspace dependency on the graph-wiki-agent package
  - langchain-aws>=1.4.7 floor (strip-invalid-tool_use-block fix)
affects:
  - 37-02-PLAN.md (commands/query.py wiring — consumes build_graph_tools)
  - downstream phases that bind grounding tools to librarian LLM

tech-stack:
  added: []
  patterns:
    - "Closure-factory @tool pattern (build_X(conn) returning list[BaseTool]) — extends the existing read_file closure in commands/query.py"
    - "Per-kind kwarg dispatch inside a single uniform (kind, identifier) tool API — keeps the LLM-facing surface flat while honoring each queries.describe_* signature"

key-files:
  created:
    - agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py
    - agents/graph-wiki-agent/tests/unit/test_graph_tools.py
  modified:
    - agents/graph-wiki-agent/pyproject.toml
    - agents/graph-wiki-agent/tests/conftest.py

key-decisions:
  - "Map uniform (kind, identifier) cg_describe API onto the actual queries.describe_* kwarg shapes inside the tool body (test_suite → suite_name=, entry_point → package_name=+entry_name=) — keeps the LLM-facing schema flat per D-10 even though queries.py is non-uniform"
  - "entry_point identifier accepts 'package:entry' shape; missing colon returns the standard 'error: no entry_point named ...' string instead of raising, preserving D-12's error-as-string contract"

patterns-established:
  - "Closure-shared sqlite3.Connection: factory captures conn once, all 5 tools share id(conn) — verified by test_closure_shares_single_connection"
  - "Error-as-string for every tool path (validation, dispatch, not-found) — D-12 contract proven by 3 dedicated tests"

requirements-completed:
  - LIBTOOLS-01
  - LIBTOOLS-02
  - LIBTOOLS-03

duration: ~25 min
completed: 2026-05-26
---

# Phase 37 Plan 01: Librarian Grounding Tools Factory Summary

**5 closure-bound `@tool` callables wrapping `graph_io.queries` with a shared read-only conn, 50-row render cap, and never-raise error contract — ready for `commands/query.py` to bind in Plan 02.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-26T17:40:40Z
- **Completed:** 2026-05-26T17:48Z
- **Tasks:** 4
- **Files modified:** 4

## Accomplishments

- `build_graph_tools(conn)` factory returns exactly 5 named tools (`cg_find`, `cg_describe`, `cg_callers`, `cg_callees`, `cg_imports`), each closing over the same conn (LIBTOOLS-03).
- All 5 tools return `str` on every code path (success, empty, validation error, missing entity) per LIBTOOLS-02 and D-12; success paths render through `_format.render(records, fmt="human", cap=50)` per LIBTOOLS-02.
- `cg_describe` dispatches via a module-level `_DESCRIBE_DISPATCH` dict over 6 valid kinds (D-02, D-10).
- Workspace dep wired (`graph-io = { workspace = true }`), `langchain-aws>=1.4.7` pinned (RESEARCH.md: strip-invalid-tool_use-block fix), `uv sync` resolves cleanly.
- Session-scoped `seeded_graph_conn` fixture reuses `packages/graph-io/tests/fixtures/sample_monorepo` with no duplication (D-14-style fixture reuse).
- 13 unit tests pass (8 unique + 5 parametrize expansions for `cg_describe` dispatch); full graph-wiki-agent suite stays green (233 passed, 6 integration skipped).

## Task Commits

1. **Task 1: Wire graph-io dep + bump langchain-aws** — `21ab2ff` (chore)
2. **Task 2: Add seeded_graph_conn fixture** — `971f63a` (test)
3. **Task 3: Create build_graph_tools factory + 5 @tool callables** — `f356e29` (feat)
4. **Task 4: Unit tests for graph_tools (incl. cg_describe kwarg fix)** — `b79b68f` (test)

## Files Created/Modified

- `agents/graph-wiki-agent/pyproject.toml` — added `graph-io` workspace dep, bumped `langchain-aws>=1.4.7`, added `[tool.uv.sources]` entry (38 lines total).
- `agents/graph-wiki-agent/tests/conftest.py` — added `seeded_graph_conn` session fixture + `_resolve_sample_monorepo_fixture()` (128 lines total).
- `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py` — NEW; module docstring, `_DESCRIBE_KINDS`/`_DESCRIBE_DISPATCH`, `_ROW_CAP`, `build_graph_tools(conn)` with 5 `@tool` closures (135 lines).
- `agents/graph-wiki-agent/tests/unit/test_graph_tools.py` — NEW; 8 unit tests covering factory shape, error-as-string contracts, dispatch parametrize, row-cap, closure-shared conn, and relationship-tool smoke (107 lines).

## Decisions Made

- **Closure layout**: 5 `@tool` definitions live INSIDE `build_graph_tools` so each call creates a fresh conn closure — matches the existing `read_file` analog in `commands/query.py:415-429`.
- **Uniform LLM-facing API vs. non-uniform queries.py**: `cg_describe(kind, identifier)` adapts the single `identifier` arg to each `describe_*` function's actual kwargs (`name=`, `path=`, `suite_name=`, `package_name=+entry_name=`). Kept a flat LLM tool schema (D-10) without changing `graph_io/queries.py`.
- **entry_point identifier shape**: accepts `"<package>:<entry>"`; bare identifiers without `:` return the standard `error: no entry_point named ...` string (D-12, no raise).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan `<interfaces>` block listed wrong describe_* signatures**
- **Found during:** Task 4 (running unit tests against seeded fixture)
- **Issue:** The plan's `<interfaces>` block declared `describe_entry_point(conn, *, name: str)` and `describe_test_suite(conn, *, name: str)`. The real signatures (in `packages/graph-io/src/graph_io/queries.py`) are `describe_entry_point(conn, *, package_name: str, entry_name: str)` and `describe_test_suite(conn, *, suite_name: str)`. The initial `cg_describe` body called both with `name=`, which raised `TypeError` on the parametrized test sweep over the 6 valid kinds.
- **Fix:** In `cg_describe`, switched from a single `fn(conn, name=identifier)` fallthrough to a per-kind kwarg adapter:
  - `test_suite` → `fn(conn, suite_name=identifier)`
  - `entry_point` → `fn(conn, package_name=..., entry_name=...)` after splitting `identifier` on `:`; bad shape returns the standard not-found error string instead of raising (preserves D-12).
- **Files modified:** `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py`
- **Verification:** `pytest agents/graph-wiki-agent/tests/unit/test_graph_tools.py -q` → 13 passed; `pytest agents/graph-wiki-agent/tests/ -q` → 233 passed, 6 integration skipped (no regressions).
- **Committed in:** `b79b68f` (Task 4 commit, alongside the new tests that surfaced it).

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in plan's pre-extracted interface signatures).
**Impact on plan:** Zero scope change; the LLM-facing `(kind, identifier)` tool API is preserved exactly as D-10 requires. The fix is local to `cg_describe` — no `graph_io/queries.py` modification (Phase 35's territory remains untouched).

## Issues Encountered

- None beyond the Rule 1 deviation above.

## User Setup Required

None — no external service configuration.

## Next Phase Readiness

- Plan 02 can now `from graph_wiki_agent.graph_tools import build_graph_tools` and bind the returned list onto the librarian LLM via `bind_tools(...)`.
- The factory's conn-lifetime contract is documented in its docstring: open via `graph_io.store.read_only_connect(...)` at command entry, close in `finally`.
- One ambiguity for Plan 02 to consider: should `cg_describe` advertise the `"package:entry"` identifier shape in its docstring? Currently the per-kind kwarg adapter handles it but the LLM-facing docstring just says "identifier: string; ignored when kind=repository." Plan 02's prompt-engineering work may want to clarify per-kind identifier shapes in the system-prompt addendum.

## Self-Check: PASSED

- All 4 task verifies pass (`uv sync`, factory import smoke, pytest unit, pytest full suite).
- All `<verification>` block items from PLAN.md pass:
  1. `uv sync` exits 0 with graph-io resolved.
  2. `python -c "from graph_wiki_agent.graph_tools import build_graph_tools; print('ok')"` prints `ok`.
  3. `pytest agents/graph-wiki-agent/tests/unit/test_graph_tools.py -q` → 13 passed.
  4. `pytest agents/graph-wiki-agent/tests/ -q` → 233 passed (no regressions).
  5. `grep -E "def cg_(find|describe|callers|callees|imports)" agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py | wc -l` → `5`.
  6. `grep -c "render(rows, fmt=.human., cap=_ROW_CAP)\|render(\[result\], fmt=.human., cap=_ROW_CAP)"` → `5`.
- All `<success_criteria>` met: 5-tool factory importable, all `str` returns, all routed through `_format.render(..., cap=50)`, closure-shared conn (verified by id-equality test), error-as-string for all 3 sentinel cases, `pyproject.toml` is the only top-level pkg metadata touched, Phase 35's territory (`commands/init.py`, `cli.py`) untouched.

---
*Phase: 37-librarian-grounding-tools*
*Completed: 2026-05-26*
