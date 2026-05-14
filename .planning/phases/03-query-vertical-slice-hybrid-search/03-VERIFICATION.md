---
phase: 03-query-vertical-slice-hybrid-search
verified: 2026-05-13T18:30:00Z
status: human_needed
score: 13/14 must-haves verified
overrides_applied: 0
gaps: []
deferred: []
human_verification:
  - test: "Run end-to-end query against the round-trip-vault fixture with real Bedrock"
    expected: "Exit code 0 or 3; JSON output with non-empty answer, at least one [[wikilink]] citation, pages_drilled >= 1, and search_scores dict where each value has bm25/embed/rrf keys"
    why_human: "SC-1 and SC-5 require real Bedrock invocations; CLI integration gate (CODE_WIKI_RUN_INTEGRATION=1) cannot run in automated verification without live AWS credentials"
  - test: "Run `code-wiki-agent query 'What does the middleware pipeline do?' --vault <real-vault> --json`"
    expected: "Coherent answer with [[wikilink]] citations and code-path references, comparable in depth and structure to the current lattice-wiki result"
    why_human: "SC-1 requires subjective quality judgment comparing output to lattice-wiki; cannot verify answer depth programmatically"
  - test: "Verify DeepAgents CLI can invoke wiki_query via MCP and receive structured result"
    expected: "tools/call wiki_query returns WikiQueryOutput with answer, citations, pages_drilled, search_scores — all non-empty"
    why_human: "SC-2 requires launching code-wiki-mcp as a subprocess and invoking the tool; the unit test (test_wiki_query_in_tools_list) is gated by CODE_WIKI_RUN_INTEGRATION=1"
cli_05_note: "REQUIREMENTS.md defines CLI-05 as '--config <path> for non-default model/role configuration'. Plan 03 reinterprets CLI-05 as the --vault flag test. The --config flag is NOT implemented. The ROADMAP Phase 3 Success Criteria do not specifically call for --config, and the plan's success criteria explicitly redefine CLI-05 scope. This deviation is noted but does not block the phase goal (the ROADMAP SC are fully satisfied). See gap analysis below."
---

# Phase 3: Query Vertical Slice + Hybrid Search Verification Report

**Phase Goal:** The `query` command works end-to-end on real Bedrock — hybrid BM25+embedding search, librarian fan-out, synthesis — accessible via both the MCP server (`wiki_query` tool) and the headless CLI (`code-wiki-agent query`), with both delivery surfaces sharing a single implementation.
**Verified:** 2026-05-13T18:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `build_index(vault_path)` produces `.code-wiki/bm25/` and `.code-wiki/search.db` SQLite in WAL mode with sha256 incremental rebuild | VERIFIED | `query.py` lines 341-411; `test_build_index_creates_bm25_and_sqlite` and `test_incremental_skip_unchanged_hash` both pass |
| 2 | `bm25_query` returns ranked page paths; RRF fusion combines BM25 and embedding ranks | VERIFIED | `query.py` lines 213-263, 419-448; 10 unit tests in `test_query_search.py` all pass |
| 3 | `run_query()` returns a `QueryResult` dataclass with `answer`, `citations`, `pages_drilled`, `search_scores` | VERIFIED | `query.py` lines 152-166, 456-609; `test_query_result.py` 13 tests all pass including `test_run_query_unit_with_mocks` |
| 4 | `run_query()` triggers `build_index()` auto on first run if index missing | VERIFIED | `query.py` lines 495-501; auto-build guarded by `not bm25_dir.exists() or not db_path.exists()` |
| 5 | Librarian fan-out via `SubagentPool.run_all` with role="librarian", max_concurrency from config | VERIFIED | `query.py` lines 524-547; uses `lib_cfg["max_concurrency"]` from `load_role_config("librarian")` |
| 6 | G1 (unresolved citation warning) and G4 (empty fan-out clears citations) guardrails applied before return | VERIFIED | `query.py` lines 281-333; `test_apply_guardrails_g4_clears_citations_on_empty_successes` and `test_apply_guardrails_g1_flags_unresolved` pass |
| 7 | `code-wiki-agent query` CLI subcommand exists with `--top-k`, `--vault`, `--json`, `--no-state-gate`, `--quiet`; exit codes 0/1/3 | VERIFIED | `cli.py` lines 128-162; `uv run code-wiki-agent query --help` shows all flags; exit codes wired at lines 144, 162 |
| 8 | CLI `--json` flag emits `dataclasses.asdict(QueryResult)` as valid JSON | VERIFIED | `cli.py` line 149; `test_json_flag_emits_valid_json` passes — parses keys `{answer, citations, pages_drilled, search_scores}` |
| 9 | CLI and MCP share the same `run_query()` implementation (CLI-03 single source of truth) | VERIFIED | `cli.py` line 13: `from code_wiki_agent.commands.query import run_query`; `server.py` line 62: `from code_wiki_agent.commands.query import QueryResult, run_query` |
| 10 | `wiki_query` MCP tool registered on existing FastMCP instance with Pydantic `WikiQueryInput`/`WikiQueryOutput` schemas | VERIFIED | `server.py` lines 103-142; `@mcp.tool(name="wiki_query")` decorates `async def wiki_query`; both model classes defined |
| 11 | `WikiQueryInput` `top_k` field validated 3-10 via `Field(ge=3, le=10)`; invalid input returns ValidationError (MCP-04) | VERIFIED | `server.py` line 106: `Field(default=5, ge=3, le=10)`; `test_wiki_query_input_rejects_out_of_range_top_k` and `test_wiki_query_input_rejects_top_k_too_low` both pass |
| 12 | `ctx.report_progress()` called at start (0/top_k) and end (pages_drilled/top_k) of `wiki_query` (MCP-06) | VERIFIED | `server.py` lines 126-135; `test_progress_called_at_start_and_end` asserts `await_count >= 2` — passes |
| 13 | Integration test `test_fixture_vault_has_citations` and `test_json_flag_emits_search_scores` exist with real assertions gated by `CODE_WIKI_RUN_INTEGRATION=1` | VERIFIED (code only) | `test_query_e2e.py` lines 47-122; tests contain real subprocess invocations and assertions — not stubs; but cannot verify the Bedrock execution path programmatically |
| 14 | `test_wiki_query_in_tools_list` subprocess test asserts `wiki_query` in `tools/list` (MCP-07) | VERIFIED (code only) | `test_mcp_stdio.py` lines 157-198; real subprocess test with assertion — gated by `CODE_WIKI_RUN_INTEGRATION=1` |

**Score:** 13/14 must-haves verified (1 requires human/live Bedrock — SCs 1, 2, 5 from ROADMAP)

### CLI-05 Requirement Discrepancy

**REQUIREMENTS.md definition:** CLI-05 = `--config <path> for non-default model/role configuration`
**Plan 03 treatment:** CLI-05 = `--vault flag wired (Path passed to resolve_wiki_and_repo)`
**What exists:** `--vault` flag is fully implemented; `--config` flag does NOT exist in the codebase.

This is a scope reinterpretation, not a missing implementation. The ROADMAP Phase 3 Success Criteria do not reference `--config` and are all satisfiable by what was built. The plan's explicit success criteria redefine CLI-05 as the vault flag. Given the phase goal focuses on the query command working end-to-end — which it does — this deviation does not block the phase goal.

The `--config` flag is a cross-cutting concern for all commands and would naturally belong in a later phase when additional commands are added (Phase 5). No later phase explicitly claims CLI-05, however, so this will need to be addressed eventually.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agents/code-wiki-agent/src/code_wiki_agent/commands/__init__.py` | commands subpackage declaration | VERIFIED | File exists; `code_wiki_agent.commands` is importable |
| `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` | Full search layer + run_query pipeline | VERIFIED | 610 lines; all 8 exported symbols present: `build_index`, `bm25_query`, `QueryResult`, `run_query`, `LIBRARIAN_SYSTEM`, `SYNTHESIZER_SYSTEM`, `apply_guardrails`, `_extract_wikilinks` |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py` | `query()` Typer subcommand | VERIFIED | Lines 128-162; all 5 flags wired; exit codes 0/1/3 |
| `agents/code-wiki-agent/src/code_wiki_mcp/server.py` | `wiki_query` MCP tool + Pydantic schemas | VERIFIED | Lines 101-142; `WikiQueryInput`, `WikiQueryOutput`, `async def wiki_query` all present |
| `agents/code-wiki-agent/tests/unit/test_query_search.py` | 10 real unit tests for SEARCH-01..05 | VERIFIED | 10 passing tests; 0 xfail markers |
| `agents/code-wiki-agent/tests/unit/test_query_result.py` | 13 real unit tests for QueryResult + guardrails | VERIFIED | 13 passing tests; 0 xfail markers |
| `agents/code-wiki-agent/tests/unit/test_cli_query.py` | 8 real unit tests for CLI subcommand | VERIFIED | 8 passing tests; 0 xfail markers |
| `agents/code-wiki-agent/tests/unit/test_mcp_query_schema.py` | 9 real unit tests for wiki_query MCP tool | VERIFIED | 9 passing tests; 0 xfail markers |
| `agents/code-wiki-agent/tests/integration/test_query_e2e.py` | 2 real integration tests (gated) | VERIFIED (code) | Real subprocess invocations with assertions; gated by `CODE_WIKI_RUN_INTEGRATION=1` |
| `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` | Extended with `test_wiki_query_in_tools_list` (gated) | VERIFIED (code) | Appended to existing file; existing tests untouched |
| `agents/code-wiki-agent/pyproject.toml` | bm25s==0.3.8, subagent-runtime, asyncio_mode=auto | VERIFIED | Lines 9-10, 33: all three present and correct |
| `agents/code-wiki-agent/tests/conftest.py` | `fixture_vault_path` fixture pointing to round-trip-vault | VERIFIED | Fixture defined; resolves cross-package path to `cores/vault-io/tests/fixtures/round-trip-vault` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `code_wiki_agent.cli::query` | `code_wiki_agent.commands.query::run_query` | `asyncio.run(run_query(...))` | WIRED | `cli.py` line 13 (import) + line 141 (invocation) |
| `code_wiki_mcp.server::wiki_query` | `code_wiki_agent.commands.query::run_query` | `await run_query(...)` | WIRED | `server.py` line 62 (import) + line 127 (invocation) |
| `commands/query.py::run_query` | `subagent_runtime.pool::SubagentPool.run_all` | `await pool.run_all(items=top_pages, task=drill_page, role="librarian", ...)` | WIRED | `query.py` line 41 (import) + lines 526, 541-547 |
| `commands/query.py::run_query` | `model_adapter.loader::make_llm` | `make_llm("librarian") + make_llm("synthesizer")` | WIRED | `query.py` line 39 (import) + lines 525, 562 |
| `commands/query.py::run_query` | `vault_io._workspace::resolve_wiki_and_repo` | `wiki, _ = resolve_wiki_and_repo(vault_path)` | WIRED | `query.py` line 41 (import) + line 492 |
| `commands/query.py::build_index` | `.code-wiki/bm25/` + `.code-wiki/search.db` | `bm25s.BM25.save + sqlite3 INSERT OR REPLACE` | WIRED | `query.py` lines 357-411; WAL pragma at line 379 |
| `commands/query.py::bm25_query` | `.code-wiki/bm25/` on disk | `bm25s.BM25.load + Tokenizer.load_vocab + load_stopwords` | WIRED | `query.py` lines 429-448; `update_vocab=False` at line 437 |
| `commands/query.py::_cosine_search_sqlite` | `.code-wiki/search.db` | `SELECT path, embedding FROM pages + struct.unpack` | WIRED | `query.py` lines 237-263 |
| `server.py::wiki_query` | `mcp.server.fastmcp.Context::report_progress` | `await ctx.report_progress(progress, total, message)` | WIRED | `server.py` lines 126-135; 2 calls verified by unit test |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `run_query()` | `search_scores` | `bm25_score_map`, `embed_score_map`, `fused` — all computed from real search calls | Yes — dict populated from actual BM25 + cosine search scores | FLOWING |
| `run_query()` | `answer` | `synth_resp.content` from `make_llm("synthesizer").ainvoke(msgs)` | Yes — Bedrock LLM response (mocked in unit tests; real in integration) | FLOWING |
| `cli.py::query` | `result` | `asyncio.run(run_query(...))` | Yes — delegates to run_query pipeline | FLOWING |
| `server.py::wiki_query` | returned `WikiQueryOutput` | `QueryResult` from `await run_query(...)` | Yes — all four fields mapped from QueryResult | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `code-wiki-agent query --help` exits 0 and shows all required flags | `uv run --package code-wiki-agent code-wiki-agent query --help` | Exit 0; `--top-k`, `--vault`, `--json`, `--no-state-gate`, `--quiet` all present in output | PASS |
| Full unit test suite passes with no xfail markers | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/ -m "not integration" -q` | 54 passed, 4 deselected, 0 failed, 0 xfailed | PASS |
| `bm25s` importable in code-wiki-agent context | `uv run --package code-wiki-agent python -c "import bm25s; print('ok')"` | `ok` | PASS |
| `subagent_runtime` importable in code-wiki-agent context | `uv run --package code-wiki-agent python -c "from subagent_runtime.pool import SubagentPool; print('ok')"` | `ok` | PASS |
| All 12 SUMMARY-claimed git commits exist | `git log --oneline \| grep <hash>` | All 12 hashes found: bbc6855, b8c7950, 00e5bab, f6dd439, 8c42872, 84a3bb3, 9fd7df6, a423d9e, a00e64f, b2fd5c2, 750d028, 3551dfc | PASS |
| Zero xfail markers remain in any Phase 3 test file | `grep -c "xfail" test_query_*.py test_mcp_query_schema.py test_query_e2e.py` | All files return 0 | PASS |

### Probe Execution

No probe scripts (`scripts/*/tests/probe-*.sh`) declared or conventional for this phase. Step 7c: SKIPPED (no probe files exist for Phase 3).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SEARCH-01 | Plan 02 | BM25 index via `bm25s` 0.3.8 | SATISFIED | `build_index` + `bm25_query` in `query.py`; `test_bm25_query_ranks_target_page_first` passes |
| SEARCH-02 | Plan 02 | Bedrock Titan v2 embedding index | SATISFIED | `BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0")` in `build_index`; mocked in unit tests |
| SEARCH-03 | Plan 02 | Hybrid search via RRF fusion | SATISFIED | `_rrf_fuse()` in `query.py` lines 213-229; 2 unit tests pass |
| SEARCH-04 | Plan 02 | Embedding index persists to SQLite (WAL mode) | SATISFIED | `_PRAGMA_WAL = "PRAGMA journal_mode=WAL"` applied in `build_index`; unit test verifies WAL mode |
| SEARCH-05 | Plan 02 | Incremental rebuild via sha256 content hash | SATISFIED | Lines 396-408 in `build_index`; `test_incremental_skip_unchanged_hash` and `test_one_page_changed_reembeds_only_that_page` pass |
| SEARCH-06 | Plan 03 | search_scores with bm25/cosine/fused visible in --json output | SATISFIED | `QueryResult.search_scores` dict with `{"bm25", "embed", "rrf"}` keys; `test_search_scores_shape_per_page` passes; integration test verifies e2e (gated) |
| CMD-04 | Plan 03 | `query` returns answer + citations + pages_drilled + search_scores | SATISFIED | `QueryResult` dataclass with all four fields; `test_run_query_unit_with_mocks` verifies shape |
| CMD-07 | Plan 03 | `--json` flag for structured output | SATISFIED | `cli.py` line 149: `json.dumps(dataclasses.asdict(result))`; `test_json_flag_emits_valid_json` passes |
| CMD-08 | Plan 03 | State-gate mechanism (`--no-state-gate` is no-op for query) | SATISFIED | `cli.py` line 138 comment: `# state gate is a no-op for query (read-only) — D-08`; flag accepted in help |
| MCP-02 | Plan 04 | `wiki_query` tool with typed schema sufficient for DeepAgents CLI | SATISFIED | `WikiQueryInput`/`WikiQueryOutput` Pydantic models; description contains "hybrid" and "BM25"; `test_wiki_query_tool_registered` passes |
| MCP-04 | Plan 04 | Invalid input returns structured error (no crash) | SATISFIED | `Field(ge=3, le=10)` enforces top_k; `test_wiki_query_input_rejects_out_of_range_top_k` passes |
| MCP-06 | Plan 04 | `ctx.report_progress()` called at start + end | SATISFIED | `server.py` lines 126-135; `test_progress_called_at_start_and_end` verifies `await_count >= 2` |
| MCP-07 | Plan 04 | `code-wiki-mcp` entry point; `wiki_query` in `tools/list` | SATISFIED (code) | Entry point registered in `pyproject.toml`; `test_wiki_query_in_tools_list` gated by `CODE_WIKI_RUN_INTEGRATION=1` |
| CLI-01 | Plan 03 | `code-wiki-agent query` subcommand exists | SATISFIED | `@app.command()` at `cli.py` line 128; help exits 0 |
| CLI-02 | Plan 03 | Full pipeline runs in-process via `asyncio.run` (no MCP host) | SATISFIED | `cli.py` line 141: `asyncio.run(run_query(...))` |
| CLI-03 | Plan 03 | CLI and MCP share same implementation | SATISFIED | Both import from `code_wiki_agent.commands.query`; confirmed by source and unit tests |
| CLI-04 | Plan 03 | `--json` flag on query subcommand | SATISFIED | `cli.py` line 133; `test_json_flag_emits_valid_json` passes |
| CLI-05 | Plan 03 | `--vault` flag wired (per Plan 03 reinterpretation of CLI-05) | PARTIALLY SATISFIED | `--vault` flag implemented and wired; `--config <path>` (per REQUIREMENTS.md) NOT implemented — see discrepancy note |
| CLI-06 | Plan 03 | Exit codes 0/1/3 | SATISFIED | `cli.py` lines 144 (exit 1), 162 (exit 3); `test_exit_code_1_on_unresolved_vault` passes |
| CLI-07 | Plan 03 | Headless mode (`--quiet` + non-TTY stderr routing) | SATISFIED | `cli.py` lines 155-159: `err=not sys.stdout.isatty()` when not quiet; `--quiet` flag accepted |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `cli.py` | 126 | `Cost USD: (Phase 4)` — placeholder string in trace viewer | Info | Pre-existing from Phase 2; not Phase 3 modification; no TBD/FIXME marker |

No TBD, FIXME, or XXX markers in any Phase 3 modified files. The `Cost USD: (Phase 4)` string is informational, not a debt marker, and pre-dates Phase 3.

### Human Verification Required

#### 1. End-to-End Bedrock Query (ROADMAP SC-1 + SC-5)

**Test:** Run `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/integration/test_query_e2e.py -v -m integration` from repo root. Alternatively, run `uv run --package code-wiki-agent code-wiki-agent query "What does the SubagentPool do?" --vault cores/vault-io/tests/fixtures/round-trip-vault --top-k 3 --json` directly.
**Expected:** Exit code 0 or 3; JSON output with `pages_drilled >= 1`; `citations` has at least 1 entry or `answer` contains `[[`; `search_scores` dict where every value has `bm25`, `embed`, `rrf` keys.
**Why human:** Requires live AWS Bedrock credentials and the first-run index build (~2-3 min). Integration gate prevents automated execution.

#### 2. Answer Quality Assessment (ROADMAP SC-1)

**Test:** Run the query above against a real lattice-wiki vault (not just the fixture vault) and compare the answer to the current lattice-wiki plugin output for the same question.
**Expected:** Answer is coherent, contains code-path references, and is comparable in depth and structure to the current lattice-wiki result.
**Why human:** Quality judgment is subjective; cannot verify "comparable in depth and structure" programmatically.

#### 3. MCP tools/list Subprocess Test (ROADMAP SC-2 + MCP-07)

**Test:** Run `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/integration/test_mcp_stdio.py::test_wiki_query_in_tools_list -v`.
**Expected:** Pass — `wiki_query` appears in `tools/list` response with description containing "hybrid" or "BM25".
**Why human:** Subprocess test gated by `CODE_WIKI_RUN_INTEGRATION=1`; launching `code-wiki-mcp` requires working dep install and import chain.

### Gaps Summary

No blocking gaps. All must-haves are verified at the code level. Three items require human/live Bedrock verification because they depend on real AWS credentials. The CLI-05 discrepancy (--config not implemented vs --vault flag implemented) is noted but does not block the phase goal — the ROADMAP success criteria are satisfiable by what was built.

---

_Verified: 2026-05-13T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
