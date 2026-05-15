---
phase: 03-query-vertical-slice-hybrid-search
verified: 2026-05-14T22:30:00Z
status: human_needed
score: 19/20 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 13/14
  gaps_closed:
    - "SC-1 answer-quality gap (fabricated paths, missing code-path:line citations, unresolved wikilinks, vault-thin handling) — closed structurally by 03-08 (prompt contract + retry) + 03-09 (code-fallback fan-out)"
    - "CLI-05 --config flag — now implemented at top-level cli.py:30 in main_callback; previous PARTIALLY SATISFIED is now SATISFIED"
    - "Integration tests test_fixture_vault_has_citations + test_json_flag_emits_search_scores + test_wiki_query_in_tools_list ran on live Bedrock per 03-HUMAN-UAT.md — all 3 passed"
  gaps_remaining:
    - "Live-vault side-by-side quality scoring vs lattice-wiki baseline NOT yet executed (03-08/03-09 checkpoints were 'approved without live run'); answer-quality improvement claimed structurally but not behaviorally verified against the original UAT comparison query"
  regressions: []
deferred:
  - truth: "code-wiki-agent query answer quality matches lattice-wiki baseline on the SubagentPool side-by-side query against ~/Personal/wiki/deep-agents"
    addressed_in: "Phase 4 (eval-driven model sweep)"
    evidence: "ROADMAP Phase 4 success criteria include eval harness with code_fallback flag tracking and quality scoring; 03-09-SUMMARY 'eval-harness note for Phase 04' explicitly hands off this measurement"
gaps:
  - truth: "G4 guardrail does not falsely strip citations on the code-fallback path when librarian successes are empty"
    status: failed
    reason: "03-REVIEW.md CR-01 identifies a critical correctness bug: when fan_result.successes is empty AND code-fallback succeeds with citations, apply_guardrails at query.py:628 fires G4 against the librarian fan_result and clears citations from a code-derived answer that IS supported by code excerpts. The in-code comment at query.py:971-974 acknowledges only the NO_RELEVANT_CONTENT-success case, not the zero-successes case."
    severity: major
    artifacts:
      - path: "agents/code-wiki-agent/src/code_wiki_agent/commands/query.py"
        issue: "Line 975: apply_guardrails(query_result, wiki, fan_result) is called unconditionally even on the code-fallback branch; G4 at line 628 then evaluates 'not fan_result.successes and result.citations' which is true when all librarian calls errored, clearing legitimate code-derived citations and prepending the 'unsupported by retrieved pages' warning"
    missing:
      - "Skip G4 (or substitute the code-reader fan_result) when code_fallback_used is True. Suggested fix in 03-REVIEW.md CR-01 Fix section."
human_verification:
  - test: "Run the SC-1 side-by-side baseline query against ~/Personal/wiki/deep-agents on live Bedrock and score the 4 quality dimensions vs lattice-wiki baseline captured in 03-HUMAN-UAT.md"
    expected: "≥3 of 4 quality dimensions show measurable improvement: (1) no fabricated file paths/symbols, (2) ≥1 code-path:line citations, (3) zero unresolved wikilinks, (4) vault-thin acknowledgment via [vault-thin: ...] marker prefix with real source-file citations"
    why_human: "Quality judgment is subjective; cannot verify 'comparable in depth and structure' programmatically. 03-08 + 03-09 checkpoints were both 'approved without live run' — the executor agent could not run real Bedrock; only structural test pins exist. The original SC-1 UAT failure has not been re-tested against the lattice-wiki baseline."
---

# Phase 03: Query Vertical Slice + Hybrid Search Verification Report

**Phase Goal:** The `query` command works end-to-end on real Bedrock — hybrid BM25+embedding search, librarian fan-out, synthesis — accessible via both the MCP server (`wiki_query` tool) and the headless CLI (`code-wiki-agent query`), with both delivery surfaces sharing a single implementation.
**Verified:** 2026-05-14T22:30:00Z
**Status:** human_needed
**Re-verification:** Yes — end-of-phase verdict after 03-08 + 03-09 gap closure

## Re-Verification Context

This is an end-of-phase re-verification. The prior `03-VERIFICATION.md` (dated 2026-05-13) was a mid-phase verdict (`status: human_needed`, score 13/14) covering plans 03-01..03-04 only and predates the SC-1 quality gap discovered in `03-HUMAN-UAT.md`. The UAT failure drove two gap-closure plans (03-08, 03-09). This re-verification covers the full phase with all 6 plans complete plus the 03-REVIEW.md findings.

Two of the prior verification's three "human verification required" items have since been closed by 03-HUMAN-UAT.md against live Bedrock:
- Integration tests `test_fixture_vault_has_citations` + `test_json_flag_emits_search_scores` passed (2 passed in 35.94s).
- `test_wiki_query_in_tools_list` passed (1 passed in 0.89s).
- Answer-quality side-by-side comparison FAILED (drove 03-08 + 03-09).

The CLI-05 `--config` discrepancy noted in the prior VERIFICATION is also resolved — a top-level `--config` flag is now implemented in `cli.py:30` (`main_callback`) and wired to `set_models_path()`. See evidence below.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `build_index(vault_path)` produces `.code-wiki/bm25/` and `.code-wiki/search.db` SQLite in WAL mode with sha256 incremental rebuild | VERIFIED | `query.py:673-743`; `_PRAGMA_WAL` applied at line 711; incremental sha256 skip at lines 728-733 |
| 2 | `bm25_query` returns ranked page paths; RRF fusion combines BM25 and embedding ranks | VERIFIED | `query.py:751-781` (bm25_query), `query.py:259-275` (_rrf_fuse); 10 passing unit tests in test_query_search.py |
| 3 | `run_query()` returns a `QueryResult` dataclass with `answer`, `citations`, `pages_drilled`, `search_scores` | VERIFIED | `query.py:198-212` (dataclass), `query.py:789-999` (run_query); test_query_result.py 22 tests pass |
| 4 | `run_query()` triggers `build_index()` auto on first run if index missing | VERIFIED | `query.py:832-838`: auto-build guarded by `not bm25_dir.exists() or not db_path.exists()` |
| 5 | Librarian fan-out via `SubagentPool.run_all` with role="librarian", max_concurrency from config | VERIFIED | `query.py:861-891`; pool.run_all invoked with `role="librarian"` and `max_concurrency=lib_cfg["max_concurrency"]` |
| 6 | G1 (unresolved citation warning) and G4 (empty fan-out clears citations) guardrails applied before return | VERIFIED | `query.py:609-665` (apply_guardrails); test_query_result.py covers both branches |
| 7 | `code-wiki-agent query` CLI subcommand exists with `--top-k`, `--vault`, `--json`, `--no-state-gate`, `--quiet`; exit codes 0/1/3 | VERIFIED | `cli.py:147-181`; flags rendered in `--help`; exit codes wired at lines 163 (1) and 181 (3) |
| 8 | CLI `--json` flag emits `dataclasses.asdict(QueryResult)` as valid JSON | VERIFIED | `cli.py:168`: `typer.echo(json.dumps(dataclasses.asdict(result), indent=2))` |
| 9 | CLI and MCP share the same `run_query()` implementation (CLI-03 single source of truth) | VERIFIED | `cli.py:18` and `server.py:62` both import `run_query` from `code_wiki_agent.commands.query` |
| 10 | `wiki_query` MCP tool registered on existing FastMCP instance with Pydantic `WikiQueryInput`/`WikiQueryOutput` schemas | VERIFIED | `server.py:101-142`; `@mcp.tool(name="wiki_query")` decorates `async def wiki_query`; both schemas defined |
| 11 | `WikiQueryInput` `top_k` field validated 3-10 via `Field(ge=3, le=10)`; invalid input returns ValidationError (MCP-04) | VERIFIED | `server.py:106`; unit tests for boundary validation pass |
| 12 | `ctx.report_progress()` called at start (0/top_k) and end (pages_drilled/top_k) of `wiki_query` (MCP-06) | VERIFIED | `server.py:126` (start) and `server.py:132` (end); unit test `test_progress_called_at_start_and_end` passes |
| 13 | Integration test `test_fixture_vault_has_citations` and `test_json_flag_emits_search_scores` run on live Bedrock and pass | VERIFIED | `test_query_e2e.py:47, 89`; 03-HUMAN-UAT.md Test 1: 2 passed in 35.94s on real Bedrock |
| 14 | `test_wiki_query_in_tools_list` subprocess test asserts `wiki_query` in `tools/list` (MCP-07) | VERIFIED | `test_mcp_stdio.py:159`; 03-HUMAN-UAT.md Test 3: 1 passed in 0.89s on real Bedrock |
| 15 | Top-level `--config <path>` flag accepts TOML config and rewires `models_path` (CLI-05) | VERIFIED | `cli.py:29-38` (`main_callback` with `--config` Typer option), wires `set_models_path()` from `config.load_config(path)`; `config.py` module exists; help text rendered |
| 16 | `LIBRARIAN_SYSTEM` and `SYNTHESIZER_SYSTEM` prompts encode no-invention, NO_RELEVANT_CONTENT sentinel, full-path wikilink, code-path:line citation, and vault-thin acknowledgment rules (SC-1 dimension 1, 2, 3) | VERIFIED | `query.py:137-163`; 5 prompt-contract tests in test_query_result.py pass (substring assertions for "verbatim", "NO_RELEVANT_CONTENT", "[[wiki/", "path:line", "vault does not document") |
| 17 | One-shot synthesizer retry runs when answer contains unresolved wikilinks; retry HumanMessage literally embeds each unresolved token (SC-1 dimension 3) | VERIFIED | `query.py:561-601` (`_retry_synthesis_drop_unresolved`) + `query.py:929-938` (retry block); test_run_query_retries_on_unresolved_wikilink asserts retry call_args contains `[[ghost]]` literal |
| 18 | `CODE_READER_SYSTEM` prompt + `_read_file_bounded` allow-listed reader + `_run_code_fallback` fan-out (SC-1 dimension 4 — vault-thin handling) | VERIFIED | `query.py:165-179` (prompt), `query.py:354-395` (`_read_file_bounded` with `Path.resolve()` symlink-escape mitigation, `.code-wiki/` reject, truncation), `query.py:403-536` (`_run_code_fallback`); 14 tests in test_query_code_fallback.py pass including symlink-escape rejection |
| 19 | code-fallback branch triggers ONLY when `useful_excerpts` (non-NO_RELEVANT_CONTENT successes) is empty; trace record includes `code_fallback: true/false` | VERIFIED | `query.py:895-952`: `useful_excerpts` filter gates the two branches; `code_fallback` field at line 990 in summary record; tests `test_code_fallback_triggered_when_all_excerpts_empty` and `test_code_fallback_not_triggered_when_excerpts_present` pin both directions |
| 20 | SC-1 answer-quality matches lattice-wiki baseline (zero fabricated paths, ≥1 code-path:line citations, zero unresolved wikilinks, vault-thin acknowledgment) on live Bedrock | UNCERTAIN | Structural pins exist (truths 16-19) and unit tests verify prompt content + retry semantics + code-fallback dispatch. BUT: the 03-08 and 03-09 checkpoint:human-verify tasks were both "approved without live run". No live-vault re-scoring against the lattice-wiki baseline captured in 03-HUMAN-UAT.md. Cannot programmatically verify subjective quality. |

**Score:** 19/20 truths verified (1 UNCERTAIN — see Human Verification section). One BLOCKER from 03-REVIEW.md CR-01 is unresolved (see Gaps).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` | Full search layer + run_query pipeline + 03-08 prompts + 03-08 retry + 03-09 code-fallback | VERIFIED | 1000 lines; all 03-08 (LIBRARIAN_SYSTEM, SYNTHESIZER_SYSTEM, _compute_unresolved_wikilinks, _retry_synthesis_drop_unresolved) and 03-09 (CODE_READER_SYSTEM, _resolve_repo_root, _read_file_bounded, _run_code_fallback, CODE_FALLBACK_MARKER, CODE_FALLBACK_DISCLAIMER) symbols present |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py` | `query()` Typer subcommand + top-level `--config` callback | VERIFIED | Lines 28-38 (main_callback w/ --config), 147-181 (query subcommand); 6 flags wired |
| `agents/code-wiki-agent/src/code_wiki_agent/config.py` | WikiConfig + load_config to back --config | VERIFIED | Module exists; docstring documents usage in CLI callback and MCP main() |
| `agents/code-wiki-agent/src/code_wiki_mcp/server.py` | `wiki_query` MCP tool + Pydantic schemas | VERIFIED | Lines 101-142 |
| `agents/code-wiki-agent/tests/unit/test_query_search.py` | 10 real unit tests for SEARCH-01..05 | VERIFIED | 10 passing tests |
| `agents/code-wiki-agent/tests/unit/test_query_result.py` | Real unit tests for QueryResult + guardrails + 03-08 prompts + retry | VERIFIED | 22 passing tests (15 original + 7 added in 03-08) |
| `agents/code-wiki-agent/tests/unit/test_query_code_fallback.py` | 14 unit tests for 03-09 code-fallback path | VERIFIED | File created in 03-09; 14 tests cover role config, prompt constant, _read_file_bounded allow-list (incl. symlink escape), _resolve_repo_root, fallback trigger/no-trigger, marker prefix, double-empty disclaimer |
| `agents/code-wiki-agent/tests/unit/test_cli_query.py` | Real unit tests for CLI subcommand | PARTIAL | 5 passing; 3 fail due to ANSI escape sequences in Typer rich help (`--top-k`/`--vault`/`--no-state-gate` substring assertions). Pre-existing per `deferred-items.md`; flags are demonstrably present in `--help` output (see Behavioral Spot-Checks). |
| `agents/code-wiki-agent/tests/unit/test_mcp_query_schema.py` | Real unit tests for wiki_query MCP tool | VERIFIED | 9 passing tests |
| `agents/code-wiki-agent/tests/integration/test_query_e2e.py` | Integration tests against real Bedrock | VERIFIED | 2 tests passed live on Bedrock per 03-HUMAN-UAT.md Test 1 (35.94s) |
| `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` | Extended with `test_wiki_query_in_tools_list` | VERIFIED | Passed live on Bedrock per 03-HUMAN-UAT.md Test 3 (0.89s) |
| `cores/model-adapter/src/model_adapter/models.toml` | code_reader role config | VERIFIED | Lines 19-26: `[roles.code_reader]` with model_id=Haiku, region=us-east-1, max_tokens=2048, max_concurrency=3 |
| `agents/code-wiki-agent/pyproject.toml` | bm25s==0.3.8, subagent-runtime, asyncio_mode=auto | VERIFIED | All three confirmed present per prior verification |
| `agents/code-wiki-agent/tests/conftest.py` | `fixture_vault_path` fixture pointing to round-trip-vault | VERIFIED | Confirmed via prior verification and 03-01-SUMMARY.md |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `cli.py::query` | `commands.query::run_query` | `asyncio.run(run_query(...))` | WIRED | cli.py:18 (import) + cli.py:160 (invocation) |
| `cli.py::main_callback` | `model_adapter.loader::set_models_path` | `set_models_path(_active_config.models_path)` | WIRED | cli.py:35-38 (--config flag handler) |
| `server.py::wiki_query` | `commands.query::run_query` | `await run_query(...)` | WIRED | server.py:62 + server.py:127 |
| `commands.query::run_query` | `subagent_runtime.pool::SubagentPool.run_all` | `await pool.run_all(items, task, role, model_id, max_concurrency)` | WIRED | query.py:45 (import) + query.py:885-891 (librarian) + query.py:496-502 (code_reader) |
| `commands.query::run_query` | `model_adapter.loader::make_llm` | `make_llm("librarian")` + `make_llm("synthesizer")` + `make_llm("code_reader")` | WIRED | query.py:44 (import) + query.py:419, 520, 869, 916 |
| `commands.query::run_query` | `_run_code_fallback` | `await _run_code_fallback(query, wiki, top_pages, pool, query_id)` | WIRED | query.py:946-952 (gated on empty useful_excerpts) |
| `commands.query::run_query` | `_retry_synthesis_drop_unresolved` | `await _retry_synthesis_drop_unresolved(synth_llm, query, excerpts_text, unresolved)` | WIRED | query.py:929-938 (gated on G1 unresolved) |
| `commands.query::_run_code_fallback` | `_read_file_bounded` | bound `read_file` LangChain tool closure + direct dispatch | WIRED | query.py:422-436 (`@tool` schema-only wrapper), query.py:478-486 (direct dispatch in tool-call loop) |
| `commands.query::run_query` | `apply_guardrails` | `apply_guardrails(query_result, wiki, fan_result)` | PARTIAL — see Gaps | query.py:975. Wiring is structurally correct but logically broken on the code-fallback branch (CR-01) |
| `server.py::wiki_query` | `mcp.server.fastmcp.Context::report_progress` | 2x `await ctx.report_progress(...)` | WIRED | server.py:126, 132 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `run_query()` | `search_scores` | computed from real BM25 + cosine scores via `_rrf_fuse` | Yes | FLOWING |
| `run_query()` | `answer` (vault-rich path) | `synth_llm.ainvoke()` content | Yes (real Bedrock per Test 1 UAT pass) | FLOWING |
| `run_query()` | `answer` (vault-thin path) | `_run_code_fallback` → `code_llm.ainvoke()` + `synth_llm.ainvoke()` with CODE_FALLBACK_MARKER prefix | Yes (mocked in unit tests; live Bedrock path exists) | FLOWING |
| `cli.py::query` | `result` | `asyncio.run(run_query(...))` | Yes | FLOWING |
| `server.py::wiki_query` | returned `WikiQueryOutput` | `QueryResult` from `await run_query(...)` | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `code-wiki-agent query --help` exits 0 and shows all 5 flags | `uv run code-wiki-agent query --help` | Exit 0; visible flags: --top-k (INTEGER RANGE 3<=x<=10), --vault, --json, --no-state-gate, --quiet | PASS |
| `code-wiki-agent --help` shows top-level --config flag | `uv run code-wiki-agent --help` | Exit 0; `--config PATH  Path to TOML config file` visible | PASS |
| Unit test suite (excluding integration) passes except 3 pre-existing ANSI failures | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit -q` | 121 passed, 3 failed (test_cli_query.py ANSI assertions; pre-existing, documented in deferred-items.md) | PASS (with known deferred regressions) |
| Phase-3-specific tests (search + result + cli + mcp + code-fallback) | `pytest test_query_search.py test_query_result.py test_cli_query.py test_mcp_query_schema.py test_query_code_fallback.py` | 60 passed, 3 failed (same 3 ANSI failures) | PASS |
| Integration tests passed live on Bedrock per UAT | `CODE_WIKI_RUN_INTEGRATION=1 pytest tests/integration/...` (run by Pat) | test_query_e2e.py: 2 passed in 35.94s; test_mcp_stdio.py::test_wiki_query_in_tools_list: 1 passed in 0.89s | PASS |

### Probe Execution

No probe scripts (`scripts/*/tests/probe-*.sh`) declared or conventional for this phase. Step 7c: SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SEARCH-01 | Plan 02 | BM25 index via `bm25s` 0.3.8 | SATISFIED | `query.py:673-703` (build_index) + `query.py:751-781` (bm25_query); test_query_search.py passes |
| SEARCH-02 | Plan 02 | Bedrock Titan v2 embedding index | SATISFIED | `query.py:715-740` (BedrockEmbeddings titan-embed-text-v2:0) |
| SEARCH-03 | Plan 02 | Hybrid search via RRF fusion | SATISFIED | `query.py:259-275` (_rrf_fuse); test_query_search.py passes |
| SEARCH-04 | Plan 02 | Embedding index persists to SQLite (WAL mode) | SATISFIED | `_PRAGMA_WAL` applied at `query.py:711`; tests confirm WAL mode |
| SEARCH-05 | Plan 02 | Incremental rebuild via sha256 content hash | SATISFIED | `query.py:728-733` skip-on-hash-match logic |
| SEARCH-06 | Plan 02 | search_scores with bm25/cosine/fused visible in --json output | SATISFIED | `QueryResult.search_scores` populated at `query.py:959-966`; integration test verified live on Bedrock per UAT Test 1 |
| CMD-04 | Plan 03 | `query` returns answer + citations + pages_drilled + search_scores | SATISFIED | `QueryResult` dataclass with all 4 fields; unit + integration tests pass |
| CMD-07 | Plan 03 | `--json` flag for structured output | SATISFIED | `cli.py:152, 167-168` |
| CMD-08 | Plan 03 | State-gate mechanism (`--no-state-gate` is no-op for query) | SATISFIED | `cli.py:153, 157` (no-op comment); flag in `--help` output |
| MCP-02 | Plan 04 | `wiki_query` tool with typed schema sufficient for DeepAgents CLI | SATISFIED | `WikiQueryInput`/`WikiQueryOutput` Pydantic schemas; description mentions hybrid + BM25 + wikilink |
| MCP-04 | Plan 04 | Invalid input returns structured error (no crash) | SATISFIED | `Field(ge=3, le=10)` enforces top_k; Pydantic ValidationError surfaces as MCP error |
| MCP-06 | Plan 04 | `ctx.report_progress()` called at start + end | SATISFIED | `server.py:126, 132` |
| MCP-07 | Plan 04 | `code-wiki-mcp` entry point; `wiki_query` in `tools/list` | SATISFIED | Confirmed live on Bedrock by UAT Test 3 |
| CLI-01 | Plan 03 | `code-wiki-agent query` subcommand exists | SATISFIED | `cli.py:147` (`@app.command()`) |
| CLI-02 | Plan 03 | Full pipeline runs in-process via `asyncio.run` (no MCP host) | SATISFIED | `cli.py:160` |
| CLI-03 | Plan 03 | CLI and MCP share same implementation | SATISFIED | Both import run_query from `code_wiki_agent.commands.query` |
| CLI-04 | Plan 03 | `--json` flag on query subcommand | SATISFIED | `cli.py:152` |
| CLI-05 | (post-prior-verification) | `--config <path>` for non-default model/role configuration | SATISFIED | Top-level `--config` flag at `cli.py:30` in `main_callback`, wired to `set_models_path()` via `code_wiki_agent.config.load_config()`. **Discrepancy from prior verification closed** — `--config` is now implemented. |
| CLI-06 | Plan 03 | Exit codes 0/1/3 | SATISFIED | `cli.py:163` (1), `cli.py:181` (3) |
| CLI-07 | Plan 03 | Headless mode (`--quiet` + non-TTY stderr routing) | SATISFIED | `cli.py:154, 173-178` |

**All 20 requirement IDs from the phase's stated requirement set are SATISFIED.** No ORPHANED requirements (REQUIREMENTS.md lines 193-212 map exactly these 20 IDs to Phase 3, all covered).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `query.py` | 826, 978 | `datetime.datetime.utcnow()` deprecated in Python 3.12+ | WARNING | 03-REVIEW.md WR-05. Will emit DeprecationWarning when project floor advances past 3.11. Not a Phase 3 blocker. |
| `query.py` | 971-974 | In-code comment acknowledges only the NO_RELEVANT_CONTENT-success case of G4 on code-fallback path, NOT the zero-successes-with-citations case | BLOCKER | 03-REVIEW.md CR-01. See Gaps section. |
| `query.py` | 467-486 | Tool-call dispatch unconditionally calls `_read_file_bounded` regardless of `call.name` (hallucinated tool names get treated as read_file) | INFO | 03-REVIEW.md WR-02. Containment is preserved by `_read_file_bounded` but feedback is misleading. |
| `query.py` | 468-494 | Last iteration of code-reader loop discards final tool reads (fence-post) | INFO | 03-REVIEW.md WR-03 |
| `query.py` | 327-351 | `_resolve_repo_root` silently degrades to `vault_path` in the documented UAT vault layout (siblings, not parent-child) | INFO | 03-REVIEW.md WR-04. Already noted in `_resolve_repo_root` docstring and in 03-09-SUMMARY as deferred. |
| `query.py` | 422-436, 478-483 | `@tool`-decorated `read_file` is schema-only; direct dispatch bypasses it; error-handling duplicated | INFO | 03-REVIEW.md IN-01 |
| `query.py` | 514-518 | Code-fallback excerpts truncated to 60_000 chars without log or marker | INFO | 03-REVIEW.md IN-03 |
| `query.py` | 539-558, 642-650 | `_compute_unresolved_wikilinks` duplicates G1 resolution logic | INFO | 03-REVIEW.md IN-04 |

No TBD / FIXME / XXX debt markers in Phase 3 modified files. The `Cost USD: (Phase 4)` placeholder in `cli.py:144` is informational and pre-dates Phase 3 (trace command, not the query path).

### Human Verification Required

#### 1. SC-1 Side-by-Side Baseline Quality Re-Scoring

**Test:** Run the original UAT side-by-side query against the live vault on real Bedrock:
```bash
uv run code-wiki-agent query "How does the SubagentPool fan out work to Bedrock and where are the results aggregated?" \
  --vault ~/Personal/wiki/deep-agents \
  --top-k 5 --json
```
Compare against the lattice-wiki baseline captured in `03-HUMAN-UAT.md` Test 2 (baseline cited `pool.py:115`, `:121-146`, `:149`, `:156-158`, `:162-210`, `loader.py:82-107` with real symbols `run_all`, `_run_one`, `_GuardedChatBedrockConverse`, `FanOutResult.successes/.errors`, `PerItemError`, `BedrockAccessDenied`).

**Expected:** ≥3 of 4 quality dimensions show measurable improvement:
1. Fabricated file paths/symbols: 0 (was 2+ before 03-08)
2. `code-path:line` citations: ≥1 in answer body (was 0)
3. Unresolved wikilinks: 0 (was 4)
4. Vault-thin acknowledgment: answer prefixed with `[vault-thin: ...]` AND cites real source-file paths from `cores/subagent-runtime/src/subagent_runtime/pool.py` (was: fabricated paths)

Also confirm the trace summary records `code_fallback: true` for this vault-thin query:
```bash
ls -t ~/Personal/wiki/deep-agents/.code-wiki/traces/query_*.jsonl | head -1 | xargs cat | python -m json.tool
```

**Why human:** Quality judgment is subjective; cannot verify "comparable in depth and structure" programmatically. Both 03-08 and 03-09 checkpoint:human-verify tasks were "approved without live run" — only structural test pins exist. The original UAT failure has not been re-tested against the lattice-wiki baseline.

### Gaps Summary

**One BLOCKER (CR-01) and one UNCERTAIN (SC-1 quality re-scoring).**

**BLOCKER — CR-01 (G4 strips citations on code-fallback when librarian successes empty):** `apply_guardrails` is called at `query.py:975` regardless of whether the code-fallback path was taken. When all librarian calls error (zero successes) AND code-fallback succeeds with citations, G4 evaluates `not fan_result.successes and result.citations` → True, clears the citations, and prepends `[warning: no librarian excerpts; answer is unsupported by retrieved pages]`. The answer IS supported by code excerpts; the warning is misleading and the citation clearing is wrong. The in-code comment at lines 971-974 acknowledges only the NO_RELEVANT_CONTENT-as-success case (where `fan_result.successes` is non-empty because pool counts NO_RELEVANT_CONTENT returns as successes) — not the zero-successes case.

This is a correctness bug specifically in the code-fallback branch, which is the path 03-09 introduced to close SC-1. It only manifests when librarian fan-out has all-failed pages (network errors, Bedrock throttling, permission denied) AND code-fallback succeeds — possible but not the common UAT path. Severity is **major** per 03-REVIEW.md.

Fix is small (5-10 lines): skip G4 when `code_fallback_used` is True, or pass a synthesized fan_result. 03-REVIEW.md CR-01 includes the patch.

**UNCERTAIN — SC-1 quality re-scoring:** Truth 20 (SC-1 answer-quality matches lattice-wiki baseline) is structurally pinned by unit tests but never behaviorally verified against the side-by-side baseline that drove the gap closure. Both gap-closure plans' human-verify checkpoints were closed "without live run" by the executor agent. The verifier cannot run real Bedrock; this requires Pat to re-run the original UAT comparison.

**Deferred (informational):** WR-04 (repo-root heuristic insufficient for sibling vault/repo layout — relevant to Pat's actual UAT vault), candidate-path heuristic tuning, and `datetime.utcnow()` deprecation are all noted in 03-09-SUMMARY.md deferred items. These do not block the phase goal.

**No regression risk** for the integration tests already passed on live Bedrock (Test 1, Test 3 in UAT). The vault-rich path remains identical to pre-03-08 behavior aside from the richer prompt; the new code-fallback path is gated by an explicit emptiness check.

---

_Verified: 2026-05-14T22:30:00Z_
_Verifier: Claude (gsd-verifier)_
