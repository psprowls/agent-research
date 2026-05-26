---
phase: 37-librarian-grounding-tools
plan: 02
subsystem: librarian-tools
tags: [langchain-aws, bind_tools, count_tokens, graph-io, sqlite, agentic-loop]

requires:
  - phase: 37-librarian-grounding-tools
    provides: build_graph_tools(conn) closure factory from Plan 37-01
  - phase: 36-cg-find-parser-ergonomics
    provides: _format.render(*, cap=) + queries.find(*, name=, kind=, in_package=)
provides:
  - Single read-only sqlite3.Connection lifecycle in commands/query.py::run_query
  - CountTokens pre-flight budget gate (BUDGET_EXCEEDED_EXIT_CODE=3)
  - NOT_INITIALIZED graceful fallback (no tools, addendum, one-shot stderr line)
  - Agentic tool-call loop inside drill_page (bounded by _LIBRARIAN_MAX_ITERS=5)
  - 7 unit tests covering all four wiring concerns
affects:
  - Future phases that ship grounding tools (the same closure-factory + gate pattern is reusable)
  - Phase 38 (cg find filter ergonomics) — same code-graph surface, no contract change

tech-stack:
  added: []
  patterns:
    - "Single-conn-per-command lifecycle: open at command entry → bind into tool factory → close in finally (LIBTOOLS-03)"
    - "CountTokens pre-flight gate before any LLM call — hard-exits with documented code before fan-out begins"
    - "NOT_INITIALIZED graceful degradation: no exception raised to user; librarian runs vault-thin with a prompt addendum, one stderr line per command, zero tools bound"
    - "Agentic tool-call loop with explicit iteration cap and NO_RELEVANT_CONTENT exit on cap — mirrors the established _run_code_fallback pattern at query.py:461-489"

key-files:
  created:
    - agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py

key-decisions:
  - "Workspace resolution uses wiki.parent under the standard layout (.graph and wiki both live in the workspace root). resolve_wiki_and_repo's first return is the wiki dir, not the workspace — parent is correct."
  - "Pre-read of top_pages for CountTokens is defensive: missing files (e.g., when tests mock the search but never write the pages) are skipped from the gate calculation; drill_page falls back to re-reading at fan-out time. Preserves the pre-Phase-37 testability of run_query."
  - "CountTokens API failures are permissive: an exception during the gate sets measured=0 (treat as 'under budget') rather than aborting. RESEARCH.md §2 — gate is a guardrail against runaway cost, not a hard correctness invariant."
  - "Tool-call dispatch shadows: the @tool import at module scope and the per-call lookup variable collide; renamed the lookup to tool_obj. No semantic change."

patterns-established:
  - "Module-level greppable stderr literals (_GRAPH_UNAVAILABLE_STDERR, _BUDGET_EXCEEDED_TEMPLATE) — operators can locate the emit site without reading code"
  - "tool_obj = next((t for t in graph_tools if t.name == call_name), None) — clean name-based dispatch with explicit unknown-tool error string (T-37-06 mitigation)"

requirements-completed:
  - LIBTOOLS-04
  - LIBTOOLS-05

duration: ~30 min
completed: 2026-05-26
---

# Phase 37 Plan 02: Librarian Grounding Tools Wiring Summary

**Librarian fan-out now opens one read-only graph conn at command entry, runs a CountTokens budget gate, binds 5 grounding tools onto the LLM (or gracefully degrades to vault-thin with a one-shot stderr signal when the graph is missing), drives an agentic tool-call loop bounded at 5 iterations per page, and closes the conn in `finally`.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-05-26T17:48Z
- **Completed:** 2026-05-26T18:12Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- One read-only conn opened via `read_only_connect(graph_dir(wiki.parent) / "code.db")`, passed into `build_graph_tools(conn)`, closed in `finally` (LIBTOOLS-03 lifetime).
- CountTokens pre-flight totals `LIBRARIAN_SYSTEM + addendum` + tool schemas + per-page input; on overflow, writes the documented stderr line and `sys.exit(BUDGET_EXCEEDED_EXIT_CODE=3)` BEFORE any subagent fan-out (D-04..D-06).
- NOT_INITIALIZED fallback path: catches `GraphNotInitializedError`, emits `_GRAPH_UNAVAILABLE_STDERR` exactly once per `run_query` call (D-08), appends `_LIBRARIAN_FALLBACK_ADDENDUM` to `LIBRARIAN_SYSTEM` at runtime (D-07 — no edit to `prompts/librarian.py`), runs the librarian with zero bound tools.
- `bind_tools(graph_tools)` called only when the graph is available; the agentic loop inside `drill_page` mirrors `_run_code_fallback`'s loop (query.py:461-489) bounded by `_LIBRARIAN_MAX_ITERS=5` with `NO_RELEVANT_CONTENT` exit on cap.
- 7 unit tests cover: single open/close, NOT_INITIALIZED fallback (stderr count + addendum in SystemMessage + no bind_tools), budget overflow (SystemExit + stderr + no fan-out), budget under (proceeds + run_all called once), tool-call loop (two ainvokes + tool.invoke + ToolMessage in second turn), iter cap (5 ainvokes + NO_RELEVANT_CONTENT result), and the Plan 01 pyproject sanity check.

## Task Commits

1. **Task 1: Module constants + helpers + imports** — `e583200` (feat) — additive only, no behavior change.
2. **Task 2: Integrate conn lifecycle + gate + bind + agentic loop** — `f44791a` (feat) — 237 inserts / 148 deletes in `commands/query.py`.
3. **Task 3: Wiring tests** — `b6bec1b` (test) — 7 tests, 428 lines.

## Files Created/Modified

- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` (modified, +237/-148):
  - Imports: `sys`, `graph_io.store.{GraphNotInitializedError,read_only_connect}`, `wiki_io.update_tokens.count_tokens`, `workspace_io.paths.graph_dir`, `graph_wiki_agent.graph_tools.build_graph_tools`.
  - Constants: `_LIBRARIAN_MAX_ITERS=5`, `LIBRARIAN_CONTEXT_WINDOW=200_000`, `LIBRARIAN_BUDGET_FRACTION=0.90`, `BUDGET_EXCEEDED_EXIT_CODE=3`, plus three greppable stderr literals.
  - Helper: `_estimate_tool_schema_tokens(tools)` — returns the CountTokens count of all bound-tool schemas concatenated, or 0 on empty/error.
  - Inside `run_query`: open-conn block + CountTokens gate + bind_tools + drill_page agentic loop + try/finally wrapping the rest of the function body.
- `agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py` (new, 428 lines): 7 async wiring tests under `pytest-asyncio` auto mode.

## Decisions Made

- **Workspace location**: `wiki.parent` gives the workspace root under the standard layout (`workspace/wiki/`, `workspace/.graph/`). Confirmed against `packages/workspace-io/src/workspace_io/paths.py:graph_dir`.
- **Defensive page pre-read**: missing files are silently skipped from the CountTokens calculation; drill_page handles re-reading at fan-out time. This preserves the testability contract of `run_query` (existing tests mock `bm25_query` + `_cosine_search_sqlite` to return page names that never exist on disk).
- **Permissive CountTokens failure**: wrapped the gate in try/except; an API failure sets `measured=0` (gate stays under budget). The gate is a guardrail against runaway cost, not a correctness invariant.
- **Tool dispatch name `tool_obj`**: `from langchain_core.tools import tool` shadows the natural local name. Using `tool_obj` is a non-semantic rename. The plan's `tool.invoke(call_args)` literal is honored in behavior; only the variable name differs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Bug] Pre-reading top_pages at command entry broke 15 pre-existing tests**
- **Found during:** Task 2 (running full test suite after the run_query body edit)
- **Issue:** The plan said to "pre-read each page once" for the CountTokens gate, then re-use the text in `drill_page`. But existing tests in `test_query_result.py`, `test_query_trace_unit.py`, `test_command_overrides.py`, `test_query_code_fallback.py` mock the search layer to return page names that don't exist on disk (since `pool.run_all` is also mocked). The unconditional pre-read raised `FileNotFoundError` at command entry.
- **Fix:** Made the pre-read defensive — `try: text = (wiki/p).read_text(...) except OSError: continue`. Missing pages are skipped from the gate calculation; `drill_page` falls back to `(wiki/page).read_text(...)` at fan-out time when the cache miss is hit. Pre-Phase-37 behavior preserved exactly.
- **Files modified:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` (inside the CountTokens gate block).
- **Verification:** `pytest agents/graph-wiki-agent/tests/ -q` → 240 passed, 6 skipped (was 233 before Phase 37). The defensive change restored all 15 originally-failing tests.
- **Committed in:** `f44791a` (Task 2 commit, alongside the run_query body edit).

**2. [Rule 1 - Bug] `tool` is a shadowed name; dispatch uses `tool_obj`**
- **Found during:** Task 2 implementation
- **Issue:** Plan's sketch used `tool = next(...)` for the per-call tool lookup. But `from langchain_core.tools import tool` at module scope shadows that name (it's the @tool decorator).
- **Fix:** Renamed the lookup to `tool_obj` and `tool_obj.invoke(call_args)`. No semantic change; the acceptance criterion "tool.invoke(call_args) is present" is satisfied behaviorally (the dispatch by name + invoke pattern is intact); only the variable name differs from the plan's sketch.
- **Files modified:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` (inside `drill_page`).
- **Verification:** `pytest agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py::test_librarian_tool_call_loop` passes — proves the dispatch + invoke flow works correctly.
- **Committed in:** `f44791a` (Task 2 commit).

**3. [Rule 1 - Plan ambiguity] `test_librarian_loop_iter_cap` needed `_run_code_fallback` patched**
- **Found during:** Task 3 (initial test run)
- **Issue:** When the iter-cap test forces `drill_page` to return `NO_RELEVANT_CONTENT` for every page, the empty-excerpt path in `run_query` triggers `_run_code_fallback`, which tries to `code_llm.ainvoke(...)` against an unmocked LLM and crashes. The plan's `<behavior>` block didn't mention the downstream code-fallback path.
- **Fix:** Patched `_run_code_fallback` in the test to return `("fallback answer", 0, 0)`. Scope-limited; doesn't affect other tests.
- **Files modified:** `agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py`.
- **Verification:** Test passes; `librarian_llm.ainvoke.await_count == _LIBRARIAN_MAX_ITERS` and the NO_RELEVANT_CONTENT sentinel is observed in the captured results.
- **Committed in:** `b6bec1b` (Task 3 commit).

---

**Total deviations:** 3 auto-fixed (2 Rule-1 bugs in plan specifics, 1 Rule-3 bug in plan's pre-read step that would have broken existing tests).
**Impact on plan:** Zero scope change. All four behavioral guarantees from `<success_criteria>` are honored as written; only implementation details deviated. The Rule-3 fix is load-bearing — without it the plan would have shipped a regression in 15 existing tests; with it, the full agent test suite is green (240 passed, 6 skipped).

## Issues Encountered

- None beyond the three deviations above. Phase 38's parallel `discuss-phase` work (commits `7864167`, `0e06ac2`) landed mid-execution but is fully isolated to `.planning/phases/38-...`; no merge conflict, no test interaction.

## User Setup Required

None — no external service configuration. The CountTokens gate uses Bedrock CountTokens which requires AWS credentials, but the gate is permissive on API failure so even an unconfigured environment runs (the budget just won't be enforced).

## Verification Gates (PLAN.md `<verification>` block)

1. `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -q` → **240 passed, 6 skipped** (integration tests requiring `GRAPH_WIKI_RUN_INTEGRATION=1`).
2. `git diff agents/graph-wiki-agent/src/graph_wiki_agent/prompts/librarian.py` → **empty** (D-07 honored: addendum is runtime concatenation, no file edit).
3. `git diff agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` → **empty** (Phase 35 territory).
4. `git diff agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` → **empty** (Phase 35 territory).
5. Only files changed by this plan: `commands/query.py` and `tests/unit/test_query_graph_tools_wiring.py` — confirmed via `git diff --stat HEAD~3 HEAD`.
6. `grep -c "sys.stderr.write(_GRAPH_UNAVAILABLE_STDERR" commands/query.py` → **1** (D-08 emit-once site is in exactly one place).

## Self-Check: PASSED

- All 3 task `<acceptance_criteria>` blocks satisfied (verified individually).
- All 6 `<verification>` items pass.
- All 5 `<success_criteria>` met: vault-rich + populated-graph path works (verified by `test_single_connection_open_close` + `test_budget_under_proceeds`), vault-only + no-graph path works (verified by `test_not_initialized_fallback`), CountTokens overflow aborts with code 3 before fan-out (verified by `test_budget_overflow_hard_aborts`), `prompts/librarian.py`/`cli.py`/`init.py` all untouched (verified by `git diff`), full agent test suite green with no regressions.
- Integration smoke against real Bedrock: NOT executed (running in headless mode without `GRAPH_WIKI_RUN_INTEGRATION=1`); the integration test surface in `tests/integration/` is unchanged by this plan and the 6 skipped tests remain skipped under the same gate.

## Next Phase Readiness

- Phase 37 is now COMPLETE: all 5 LIBTOOLS requirements (LIBTOOLS-01..05) are landed and verified.
- Phase 38 (cg find filter ergonomics — context just landed) can proceed: it operates on the same `queries.find` surface but does not change the public API the librarian's tools depend on. No contract impedance.
- Open question for Phase 38 to consider: should `cg_describe`'s docstring be expanded to advertise the `"package:entry"` identifier shape for `entry_point` kind? Plan 37-01's deviation surfaced this; Plan 37-02 didn't touch the docstring (LLM-facing API only changes when prompt engineering says so).

---
*Phase: 37-librarian-grounding-tools*
*Completed: 2026-05-26*
