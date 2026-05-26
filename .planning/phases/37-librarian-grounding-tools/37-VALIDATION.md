---
phase: 37
slug: librarian-grounding-tools
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-26
---

# Phase 37 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (asyncio_mode=auto) |
| **Config file** | `agents/graph-wiki-agent/pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_graph_tools.py agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py -q` |
| **Full suite command** | `uv run --package graph-wiki-agent pytest -q` |
| **Estimated runtime** | quick ~5s, full ~30s (excluding `integration` marker which is skipped by default) |

---

## Sampling Rate

- **After every task commit:** Run quick command above
- **After every plan wave:** Run `uv run --package graph-wiki-agent pytest -q` (excludes `integration` marker by default — see pyproject markers config)
- **Before `/gsd:verify-work`:** Full suite + a `uv sync` check
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 37-01-01 | 01 | 1 | LIBTOOLS-01 | — | `build_graph_tools(conn)` returns exactly 5 `@tool` callables named `{cg_find, cg_describe, cg_callers, cg_callees, cg_imports}` | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_graph_tools.py::test_factory_returns_five_named_tools -q` | ✅ W0 | ⬜ pending |
| 37-01-02 | 01 | 1 | LIBTOOLS-02 | — | every tool returns `str`; results pass through `_format.render(records, fmt="human", cap=50)`; row cap produces truncation notice on >50-row results | unit | `pytest agents/graph-wiki-agent/tests/unit/test_graph_tools.py::test_tools_return_string_with_row_cap -q` | ✅ W0 | ⬜ pending |
| 37-01-03 | 01 | 1 | LIBTOOLS-03 | — | factory closure captures single conn; every tool sees the same conn object across multiple invocations | unit | `pytest agents/graph-wiki-agent/tests/unit/test_graph_tools.py::test_closure_shares_single_connection -q` | ✅ W0 | ⬜ pending |
| 37-01-04 | 01 | 1 | LIBTOOLS-01 (D-12) | — | `cg_find()` with no args returns the error string `"error: at least one of name, kind, in_package required"` (NOT an exception) | unit | `pytest agents/graph-wiki-agent/tests/unit/test_graph_tools.py::test_cg_find_no_args_returns_error_string -q` | ✅ W0 | ⬜ pending |
| 37-01-05 | 01 | 1 | LIBTOOLS-01 (D-10) | — | `cg_describe(kind="bogus", ...)` returns `error: invalid kind 'bogus'; valid: package, path, repository, domain, entry_point, test_suite` | unit | `pytest agents/graph-wiki-agent/tests/unit/test_graph_tools.py::test_cg_describe_kind_enum -q` | ✅ W0 | ⬜ pending |
| 37-01-06 | 01 | 1 | LIBTOOLS-01 (D-02) | — | `cg_describe(kind, identifier)` parametrized over all 6 kinds dispatches to the matching `describe_*` query function | unit | `pytest agents/graph-wiki-agent/tests/unit/test_graph_tools.py::test_cg_describe_dispatch -q` | ✅ W0 | ⬜ pending |
| 37-01-07 | 01 | 1 | LIBTOOLS-02 | — | `cg_describe(kind, identifier)` on a non-existent identifier returns `"error: no <kind> named '<identifier>' found in graph"` (`None` from `describe_*` never crosses the tool boundary) | unit | `pytest agents/graph-wiki-agent/tests/unit/test_graph_tools.py::test_cg_describe_missing_entity_returns_error_string -q` | ✅ W0 | ⬜ pending |
| 37-02-01 | 02 | 2 | LIBTOOLS-04 | — | `commands/query.py` opens `read_only_connect(graph_dir(workspace) / "code.db")` at command entry and closes it in `finally` (single open, single close) | unit | `pytest agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py::test_single_connection_open_close -q` | ✅ W0 | ⬜ pending |
| 37-02-02 | 02 | 2 | LIBTOOLS-04 (D-07/D-08) | — | when graph DB is absent: librarian still runs with NO bound tools, system prompt addendum is concatenated, stderr line `[graph unavailable: run 'cg update' to enable code-graph grounding tools]` emitted exactly once | unit | `pytest agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py::test_not_initialized_fallback -q` | ✅ W0 | ⬜ pending |
| 37-02-03 | 02 | 2 | LIBTOOLS-05 (D-04) | — | CountTokens pre-flight: when total > budget, process exits non-zero with stderr `librarian: token budget exceeded (X of Y tokens). Reduce vault scope or use a larger-context model.` | unit | `pytest agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py::test_budget_overflow_hard_aborts -q` | ✅ W0 | ⬜ pending |
| 37-02-04 | 02 | 2 | LIBTOOLS-05 (D-05/D-06) | — | gate runs at command entry BEFORE `pool.run_all`; when under budget, fan-out proceeds normally | unit | `pytest agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py::test_budget_under_proceeds -q` | ✅ W0 | ⬜ pending |
| 37-02-05 | 02 | 2 | LIBTOOLS-04 | — | librarian agentic tool-call loop: when `ainvoke` returns `tool_calls`, the loop dispatches the named tool, appends `ToolMessage`, re-invokes; terminates on empty `tool_calls` or iteration cap | unit | `pytest agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py::test_librarian_tool_call_loop -q` | ✅ W0 | ⬜ pending |
| 37-02-06 | 02 | 2 | LIBTOOLS-04 | — | `pyproject.toml` of graph-wiki-agent contains `graph-io` dependency + workspace source + `langchain-aws>=1.4.7` | unit | `grep -q '"graph-io"' agents/graph-wiki-agent/pyproject.toml && grep -q 'langchain-aws>=1.4.7' agents/graph-wiki-agent/pyproject.toml` | ✅ W0 | ⬜ pending |
| 37-02-07 | 02 | 2 | LIBTOOLS-04 (integration) | — | end-to-end smoke: against a seeded sample monorepo DB, a real librarian fan-out invokes at least one graph tool and synthesis succeeds | integration | `uv run --package graph-wiki-agent pytest -q -m integration agents/graph-wiki-agent/tests/integration/test_librarian_graph_tools_smoke.py` (skipped in CI; gated on AWS creds) | ✅ W0 | ⬜ pending |

---

## Wave 0 Requirements

Wave 0 = pre-existing test infrastructure that's already on the branch when Phase 37 starts executing.

- [x] `pytest` + `pytest-asyncio` installed (workspace dev deps, already configured)
- [x] `agents/graph-wiki-agent/tests/unit/` directory exists with conftest pattern
- [x] `packages/graph-io/tests/conftest.py` `seeded_db` fixture exists (template for cross-package fixture mirror)
- [x] `graph_io.update.run()` available for building a test DB
- [x] `_format.render(records, fmt, cap=...)` will be available after Phase 36 merges (HARD DEPENDENCY — see Risk Register)
- [x] `graph_io.queries.find(..., in_package=...)` will be available after Phase 36 merges (HARD DEPENDENCY)

New fixture work in Plan 37-01 (functionally Wave 0 for Phase 37's own tests):

- [ ] `agents/graph-wiki-agent/tests/conftest.py` — add `seeded_graph_conn` fixture that mirrors `packages/graph-io/tests/conftest.py::seeded_db` (copy sample_monorepo into tmp, `git init`, `graph_io.update.run(..., full=True)`, yield `read_only_connect()` conn)
- [ ] `agents/graph-wiki-agent/tests/fixtures/sample_monorepo/` — symlink or copy from `packages/graph-io/tests/fixtures/sample_monorepo`. Recommendation: import the existing fixture path via `Path` rather than duplicating files (`fixture_src = Path(graph_io.__file__).parent.parent.parent / "tests" / "fixtures" / "sample_monorepo"` — verify path exists in conftest's setup, skip the test if absent).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end run against a real wiki + real Bedrock with graph tools | LIBTOOLS-04 (smoke) | Requires live AWS credentials, real wiki vault, ≥10s wallclock cost | 1. Ensure `cg update --full` has populated `<workspace>/.graph/code.db`. 2. Run `uv run --package graph-wiki-agent graph-wiki-agent query "what packages depend on workspace-io"` against a workspace with a real wiki. 3. Verify librarian trace JSONL under `<wiki>/.graph-wiki/traces/` shows at least one `tool_calls` entry for `cg_*` tools. 4. Confirm final answer cites graph data (e.g., paths to importer files). |
| CountTokens API graceful degradation when Bedrock CountTokens is unavailable | LIBTOOLS-05 | Requires region/credential setup with CountTokens blocked or quota exceeded — not reproducible in unit tests beyond a mocked stub | Block egress to `bedrock-runtime` or revoke `bedrock:CountTokens` IAM permission; rerun a query; confirm process emits warning + proceeds (does NOT abort). |
| stderr line emitted exactly once across 5 concurrent librarians | LIBTOOLS-04 (D-08) | Race condition — only observable with real parallel pool execution and a missing graph DB | Run `graph-wiki-agent query "..."` against a workspace with no `.graph/code.db`; capture stderr; grep for the literal "[graph unavailable" line and confirm count is 1 (not 5). |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify (single integration test gated by `integration` marker; all others are unit)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task has an automated command)
- [x] Wave 0 covers all MISSING references (graph-io seeded_db, _format.cap parameter — both pre-existing on the branch via Phase 36)
- [x] No watch-mode flags (all `pytest -q`, no `--watch`)
- [x] Feedback latency < 30s (unit tests run in ~5s; full suite ~30s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending — sign at execute-phase completion
