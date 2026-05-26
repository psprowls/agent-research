---
phase: 37-librarian-grounding-tools
status: passed
verified_at: 2026-05-26
verifier: inline (orchestrator, no Agent runtime available)
requirements_checked: [LIBTOOLS-01, LIBTOOLS-02, LIBTOOLS-03, LIBTOOLS-04, LIBTOOLS-05]
must_haves_passed: 21
must_haves_failed: 0
test_suite_pass: true
test_count: 240
test_skipped: 6
packages_suite_pass: true
packages_test_count: 840
human_verification: []
---

# Phase 37 Verification: Librarian Grounding Tools

## Phase Goal

> Give the librarian agent ≤5 `@tool` callables wrapping `graph_io.queries.*` functions, exposed via `build_graph_tools(conn)` closure factory and wired into `commands/query.py` with shared read-only connection + CountTokens pre-flight gate.

**Verdict: PASSED.** All 5 LIBTOOLS requirements are landed, all 21 must_haves across both plans verify clean against the codebase, full agent test suite (240 passed) and packages suite (840 passed) green with zero regressions.

## Requirement Traceability

| Requirement | Plan | Status | Evidence |
|---|---|---|---|
| LIBTOOLS-01 | 37-01 | ✓ Complete | `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py` defines `build_graph_tools(conn) -> list[BaseTool]` returning exactly 5 `@tool` callables (cg_find, cg_describe, cg_callers, cg_callees, cg_imports). Verified by `test_factory_returns_five_named_tools`. |
| LIBTOOLS-02 | 37-01 | ✓ Complete | All 5 tools declare `-> str` return type. All success paths route through `graph_io.cli._format.render(records, fmt="human", cap=_ROW_CAP)` where `_ROW_CAP = 50`. Verified by `grep -c "render(... cap=_ROW_CAP)" graph_tools.py` → 5. |
| LIBTOOLS-03 | 37-01, 37-02 | ✓ Complete | Factory closure captures conn once (Plan 01); `commands/query.py::run_query` opens conn once at command entry, closes in `finally` (Plan 02). Verified by `test_closure_shares_single_connection` (id-equal across tool calls) and `test_single_connection_open_close` (open=1, close=1). |
| LIBTOOLS-04 | 37-02 | ✓ Complete | `run_query` opens `read_only_connect(graph_dir(wiki.parent) / "code.db")`, catches `GraphNotInitializedError`, calls `librarian_llm.bind_tools(graph_tools)` when available. Verified by `test_single_connection_open_close` + `test_not_initialized_fallback`. |
| LIBTOOLS-05 | 37-02 | ✓ Complete | CountTokens pre-flight (`prompt + tool_schemas + per-page input`) at command entry; abort with exit code 3 on overflow. Verified by `test_budget_overflow_hard_aborts` + `test_budget_under_proceeds`. |

## Must-Have Coverage

### Plan 37-01 (11 truths)
- ✓ pyproject.toml has `graph-io` workspace dep + `langchain-aws>=1.4.7`
- ✓ `from graph_wiki_agent.graph_tools import build_graph_tools` imports cleanly
- ✓ Factory returns `list[BaseTool]` length 5 with exact names
- ✓ Every tool has `-> str` return + routes through `render(..., cap=50)`
- ✓ `cg_find.invoke({})` returns the documented error string (test passes)
- ✓ `cg_describe` bad kind returns documented error string (test passes)
- ✓ `_DESCRIBE_DISPATCH` module-level dict dispatches over 6 kinds (test parametrized over 6 kinds passes)
- ✓ Missing-entity returns `error: no <kind> named '...' found in graph` (test passes)
- ✓ Closure-shared conn (id-equal across calls, mock-recorded — test passes)
- ✓ Docstrings concise (single-sentence + Args block; visually inspected)
- ✓ Plan 01 unit suite exits 0 with 13 tests passing

### Plan 37-02 (10 truths)
- ✓ `run_query` opens ONE read-only conn via `read_only_connect(graph_dir(wiki.parent)/"code.db")`
- ✓ Conn passed once into `build_graph_tools(conn)` and closed in `finally`
- ✓ CountTokens pre-flight totals `LIBRARIAN_SYSTEM+addendum + tool_schemas + per-page input`, compared to `int(LIBRARIAN_CONTEXT_WINDOW*LIBRARIAN_BUDGET_FRACTION)`
- ✓ Budget overflow → stderr line + `sys.exit(3)` (BUDGET_EXCEEDED_EXIT_CODE)
- ✓ NOT_INITIALIZED → librarian still runs with no tools bound (verified by `test_not_initialized_fallback`)
- ✓ NOT_INITIALIZED path's system prompt is `LIBRARIAN_SYSTEM + _LIBRARIAN_FALLBACK_ADDENDUM` (no edit to `prompts/librarian.py`)
- ✓ Stderr line `[graph unavailable: ...]` emitted EXACTLY once per run_query (grep count = 1; test asserts count == 1)
- ✓ `bind_tools(build_graph_tools(conn))` called once when graph is present
- ✓ `drill_page` runs agentic tool-call loop bounded by `_LIBRARIAN_MAX_ITERS = 5`
- ✓ Plan 02 wiring suite exits 0 with 7 tests passing

## Cross-Phase Coupling (Phase 36 dependency)

- Phase 36 (`cg-find-parser-ergonomics`) provided `_format.render(records, fmt=..., cap=..., on_truncate=...)` and `queries.find(*, name=, kind=, in_package=)`. Both are consumed by Phase 37's `graph_tools.py` without modification. Verified by direct test exercise (cg_find with kind/name/in_package args, render with cap=50).

## Decision Honor Check (37-CONTEXT.md D-01..D-12)

| Decision | Honored? | Evidence |
|---|---|---|
| D-01: 5 tools, fixed names | ✓ | `test_factory_returns_five_named_tools` asserts exact name set |
| D-02: `_DESCRIBE_DISPATCH` module dict | ✓ | Defined as module-level constant in `graph_tools.py` |
| D-03: Concise docstrings (single-line + Args) | ✓ | Visually verified; no multi-line examples |
| D-04: `BUDGET_EXCEEDED_EXIT_CODE = 3` | ✓ | Module constant; verified by `test_budget_overflow_hard_aborts` |
| D-05: `LIBRARIAN_BUDGET_FRACTION = 0.90` | ✓ | Module constant in `query.py` |
| D-06: Gate aborts BEFORE fan-out | ✓ | `test_budget_overflow_hard_aborts` asserts `pool.run_all.await_count == 0` |
| D-07: Addendum is runtime concatenation, no edit to `prompts/librarian.py` | ✓ | `git diff prompts/librarian.py` empty; SystemMessage built with `+ addendum` at runtime |
| D-08: One-shot stderr per `run_query` | ✓ | `grep -c "sys.stderr.write(_GRAPH_UNAVAILABLE_STDERR" query.py` → 1; test asserts count == 1 |
| D-09: Tool names exactly cg_find/cg_describe/cg_callers/cg_callees/cg_imports | ✓ | Test asserts exact set equality |
| D-10: 6-kind enum + invalid-kind error string | ✓ | `test_cg_describe_kind_enum` asserts both literal substrings |
| D-11: cg_callers/cg_callees with depth default 3 | ✓ | Plan 01 spec + visual inspection of `graph_tools.py` |
| D-12: Error-as-string for all validation paths (never raise) | ✓ | 3 dedicated tests cover the sentinel cases |

## Test Suite Results

```
agents/graph-wiki-agent/tests/        : 240 passed, 6 skipped (integration, GRAPH_WIKI_RUN_INTEGRATION not set)
packages/                              : 840 passed, 27 skipped, 1 xfailed
```

Pre-Phase-37 baseline: 233 passed (agent) + 833 passed (packages). Net: +7 new wiring tests (Plan 02) + 13 new graph_tools tests (Plan 01) – 6 tests already counted elsewhere. No regressions, all gains.

## Phase 35 Territory Check

- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — `git diff HEAD~N` empty (untouched).
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` — `git diff HEAD~N` empty (untouched).
- Phase 35's in-flight work (cli + init) is fully isolated from Phase 37's territory (graph_tools + commands/query.py).

## Gaps Found

None.

## Human Verification

None required. All behavior is unit-verifiable; the integration test surface in `tests/integration/` exists and remains skipped under `GRAPH_WIKI_RUN_INTEGRATION=1` for opt-in real-Bedrock smoke checks. Phase 38 will be the first to exercise the wiring end-to-end against a real graph DB.

## Final Verdict

**Phase 37 PASSED verification.** All 5 LIBTOOLS requirements complete, all 21 must_haves green, both plans' test suites pass, no regressions in 840-test packages suite, all 12 D-NN decisions from 37-CONTEXT.md honored.

Ready to mark Phase 37 complete and advance to Phase 38.
