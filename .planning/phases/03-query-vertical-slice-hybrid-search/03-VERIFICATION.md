---
phase: 03-query-vertical-slice-hybrid-search
verified: 2026-05-15T03:30:00Z
status: passed
score: 20/20 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 19/20
  gaps_closed:
    - "CR-01: G4 guardrail no longer strips citations on the code-fallback path. apply_guardrails now accepts skip_g4: bool = False (query.py:609-615); run_query passes skip_g4=code_fallback_used at the single call site (query.py:982-984). Two new regression tests pin the contract: test_apply_guardrails_skip_g4_preserves_citations_on_empty_successes and test_apply_guardrails_skip_g4_still_runs_g1 (test_query_result.py:134-185)."
    - "SC-1 quality re-scoring (truth 20): Test 4 in 03-HUMAN-UAT.md ran the original side-by-side baseline query against ~/Personal/wiki/deep-agents on live Bedrock. Result: 3 of 4 quality dimensions cleanly improved vs Test 2 baseline; dimension 2 PARTIAL because the librarian returned useful-but-shallow excerpts and code-fallback did not fire (by design — code-fallback runs only when all excerpts are empty/NO_RELEVANT_CONTENT). ≥3 of 4 threshold met."
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "code-path:line citations on useful-but-shallow vault pages (where librarian returns real but thin excerpts and code-fallback does not fire)"
    addressed_in: "Phase 4 (eval-driven model sweep)"
    evidence: "03-HUMAN-UAT Test 4 dim-2 PARTIAL note and 03-09-SUMMARY eval-harness handoff. Phase 4 success criteria include code_fallback flag tracking and quality scoring across model swaps."
  - truth: "WR-04 _resolve_repo_root heuristic falls back to vault_path in sibling vault/repo layouts; resolve_wiki_and_repo's repo tuple is currently discarded"
    addressed_in: "Future enhancement"
    evidence: "Already documented as advisory follow-up in 03-REVIEW.md WR-04 and 03-09-SUMMARY deferred items. Does not block the phase goal — code-fallback was not required to fire to meet the SC-1 acceptance threshold in Test 4."
  - truth: "WR-05 datetime.utcnow() deprecation; WR-01 pages_drilled mis-reports on code-fallback path; WR-02 tool-name verification; WR-03 fence-post in code-reader loop; IN-* informational items"
    addressed_in: "Future cleanup phase"
    evidence: "03-REVIEW.md advisory follow-ups (now non-blocking after CR-01 close). All are quality/observability concerns, not correctness blockers for the phase goal."
---

# Phase 03: Query Vertical Slice + Hybrid Search Verification Report

**Phase Goal:** The `query` command works end-to-end on real Bedrock — hybrid BM25+embedding search, librarian fan-out, synthesis — accessible via both the MCP server (`wiki_query` tool) and the headless CLI (`code-wiki-agent query`), with both delivery surfaces sharing a single implementation.
**Verified:** 2026-05-15T03:30:00Z
**Status:** passed
**Re-verification:** Yes — end-of-phase verdict after CR-01 fix + SC-1 live rescore

## Re-Verification Context

This is the third pass on Phase 03. Prior state (2026-05-14T22:30:00Z) had `status: human_needed`, score 19/20, with one BLOCKER (CR-01) and one UNCERTAIN (SC-1 quality re-scoring). Two updates have since landed:

1. **CR-01 closed (RED/GREEN)** — commit `058912a` adds two failing regression tests; commit `0d5f87b` implements the fix. `apply_guardrails` gained `skip_g4: bool = False`; `run_query` calls it with `skip_g4=code_fallback_used` at query.py:982-984. The G4 branch at query.py:636 now guards on `not skip_g4` before testing fan_result.successes emptiness. Both new tests are green; full unit suite passes 118/118 (excluding test_cli_query.py per documented deferred-items.md).

2. **SC-1 live rescore complete** — commit `4b6076d` reopened 03-HUMAN-UAT.md with Test 4; status subsequently flipped to `complete`. Pat re-ran the original side-by-side baseline query against `~/Personal/wiki/deep-agents` on live Bedrock and scored 3-of-4 cleanly improved + 1 partial (dimension 2: line numbers absent because librarian returned useful-but-shallow excerpts that prevented code-fallback from firing — by design). The ≥3-of-4 acceptance threshold is met; the dim-2 gap on useful-but-shallow pages is properly handed off to Phase 4's eval harness.

No regressions. No new blockers.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `build_index(vault_path)` produces `.code-wiki/bm25/` and `.code-wiki/search.db` SQLite in WAL mode with sha256 incremental rebuild | VERIFIED | `query.py:681-743`; `_PRAGMA_WAL` applied during build; incremental sha256 skip logic |
| 2 | `bm25_query` returns ranked page paths; RRF fusion combines BM25 and embedding ranks | VERIFIED | `query.py:259-275` (`_rrf_fuse`) + `query.py:751-781` (`bm25_query`); 10 passing tests in `test_query_search.py` |
| 3 | `run_query()` returns a `QueryResult` dataclass with `answer`, `citations`, `pages_drilled`, `search_scores` | VERIFIED | `query.py:198-212` (dataclass), full pipeline at `query.py:789-1000`; 38 tests pass in `test_query_result.py` |
| 4 | `run_query()` triggers `build_index()` auto on first run if index missing | VERIFIED | `query.py:832-838` (auto-build guarded by `not bm25_dir.exists() or not db_path.exists()`) |
| 5 | Librarian fan-out via `SubagentPool.run_all` with role="librarian", max_concurrency from config | VERIFIED | `query.py:861-891`; `pool.run_all` invoked with `role="librarian"` and `max_concurrency=lib_cfg["max_concurrency"]` |
| 6 | G1 (unresolved citation warning) and G4 (empty fan-out clears citations) guardrails applied before return | VERIFIED | `query.py:609-673` (apply_guardrails); G4 conditional on `not skip_g4` (line 636); test_query_result.py covers both branches |
| 7 | `code-wiki-agent query` CLI subcommand exists with `--top-k`, `--vault`, `--json`, `--no-state-gate`, `--quiet`; exit codes 0/1/3 | VERIFIED | `cli.py:147-181`; flags rendered in `--help`; exit codes wired at lines 163 (1) and 181 (3) |
| 8 | CLI `--json` flag emits `dataclasses.asdict(QueryResult)` as valid JSON | VERIFIED | `cli.py:168` (`typer.echo(json.dumps(dataclasses.asdict(result), indent=2))`) |
| 9 | CLI and MCP share the same `run_query()` implementation (CLI-03 single source of truth) | VERIFIED | `cli.py:18` and `server.py:62` both import `run_query` from `code_wiki_agent.commands.query` |
| 10 | `wiki_query` MCP tool registered on existing FastMCP instance with Pydantic `WikiQueryInput`/`WikiQueryOutput` schemas | VERIFIED | `server.py:101-142`; `@mcp.tool(name="wiki_query")` decorates `async def wiki_query`; both schemas defined |
| 11 | `WikiQueryInput` `top_k` field validated 3-10 via `Field(ge=3, le=10)`; invalid input returns ValidationError (MCP-04) | VERIFIED | `server.py:106`; unit tests for boundary validation pass |
| 12 | `ctx.report_progress()` called at start (0/top_k) and end (pages_drilled/top_k) of `wiki_query` (MCP-06) | VERIFIED | `server.py:126, 132`; unit test `test_progress_called_at_start_and_end` passes |
| 13 | Integration test `test_fixture_vault_has_citations` and `test_json_flag_emits_search_scores` run on live Bedrock and pass | VERIFIED | `test_query_e2e.py`; 03-HUMAN-UAT.md Test 1: 2 passed in 35.94s on real Bedrock |
| 14 | `test_wiki_query_in_tools_list` subprocess test asserts `wiki_query` in `tools/list` (MCP-07) | VERIFIED | `test_mcp_stdio.py`; 03-HUMAN-UAT.md Test 3: 1 passed in 0.89s on real Bedrock |
| 15 | Top-level `--config <path>` flag accepts TOML config and rewires `models_path` (CLI-05) | VERIFIED | `cli.py:29-38` (`main_callback` with `--config` Typer option), wires `set_models_path()` from `config.load_config(path)` |
| 16 | `LIBRARIAN_SYSTEM` and `SYNTHESIZER_SYSTEM` prompts encode no-invention, NO_RELEVANT_CONTENT sentinel, full-path wikilink, code-path:line citation, and vault-thin acknowledgment rules (SC-1 dim 1, 2, 3) | VERIFIED | `query.py:137-163`; 5 prompt-contract tests pass |
| 17 | One-shot synthesizer retry runs when answer contains unresolved wikilinks; retry HumanMessage literally embeds each unresolved token (SC-1 dim 3) | VERIFIED | `query.py:561-601` (`_retry_synthesis_drop_unresolved`) + `query.py:929-938` (retry block); test asserts `[[ghost]]` literal in retry call_args |
| 18 | `CODE_READER_SYSTEM` prompt + `_read_file_bounded` allow-listed reader + `_run_code_fallback` fan-out (SC-1 dim 4 — vault-thin handling) | VERIFIED | `query.py:165-179` (prompt), `query.py:354-395` (`_read_file_bounded` with `Path.resolve()` symlink-escape mitigation, `.code-wiki/` reject, truncation), `query.py:403-536` (`_run_code_fallback`); 14 tests in `test_query_code_fallback.py` pass |
| 19 | code-fallback branch triggers ONLY when `useful_excerpts` (non-NO_RELEVANT_CONTENT successes) is empty; trace record includes `code_fallback: true/false` | VERIFIED | `query.py:895-952` (`useful_excerpts` filter gates two branches); `code_fallback` field at line 999 in summary record; tests pin both directions |
| 20 | SC-1 answer-quality matches lattice-wiki baseline (≥3 of 4 dimensions improved on live-Bedrock side-by-side rescore) | VERIFIED | 03-HUMAN-UAT.md Test 4 (live Bedrock 2026-05-15): dim 1 (no fabricated paths) PASS, dim 2 (code-path:line citations) PARTIAL (excerpts useful-but-shallow; code-fallback did not fire by design), dim 3 (zero unresolved wikilinks) PASS, dim 4 (vault-thin acknowledgment) PASS. ≥3 of 4 threshold met. Dim-2 useful-but-shallow gap deferred to Phase 4 eval harness. |

**Score:** 20/20 truths verified. No blockers, no regressions, no human verification items remaining.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` | Full search layer + run_query pipeline + 03-08 prompts/retry + 03-09 code-fallback + CR-01 skip_g4 | VERIFIED | ~1000 lines; all 03-08 + 03-09 symbols present; `apply_guardrails(... , *, skip_g4: bool = False)` at line 609-615; call site at 982-984 passes `skip_g4=code_fallback_used` |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py` | `query()` Typer subcommand + top-level `--config` callback | VERIFIED | Lines 28-38 (main_callback w/ --config), 147-181 (query subcommand); 6 flags wired |
| `agents/code-wiki-agent/src/code_wiki_agent/config.py` | WikiConfig + load_config to back --config | VERIFIED | Module exists; consumed by cli.main_callback and mcp.main |
| `agents/code-wiki-agent/src/code_wiki_mcp/server.py` | `wiki_query` MCP tool + Pydantic schemas | VERIFIED | Lines 101-142 |
| `agents/code-wiki-agent/tests/unit/test_query_search.py` | 10 unit tests for SEARCH-01..05 | VERIFIED | 10 passing |
| `agents/code-wiki-agent/tests/unit/test_query_result.py` | Tests for QueryResult + guardrails + prompts + retry + CR-01 skip_g4 regression | VERIFIED | 38 passing tests including the two new CR-01 regression tests: `test_apply_guardrails_skip_g4_preserves_citations_on_empty_successes` (line 134) and `test_apply_guardrails_skip_g4_still_runs_g1` (line 167) |
| `agents/code-wiki-agent/tests/unit/test_query_code_fallback.py` | 14 unit tests for 03-09 code-fallback path | VERIFIED | 14 passing tests covering role config, prompt constant, `_read_file_bounded` allow-list (incl. symlink escape), `_resolve_repo_root`, fallback trigger/no-trigger, marker prefix, double-empty disclaimer |
| `agents/code-wiki-agent/tests/unit/test_cli_query.py` | Real unit tests for CLI subcommand | PARTIAL (deferred) | 5 passing; 3 fail due to ANSI escape sequences in Typer rich help. Pre-existing per phase `deferred-items.md`; flags demonstrably present in `--help` output (Behavioral Spot-Checks). Excluded from this verification run per task instructions. |
| `agents/code-wiki-agent/tests/unit/test_mcp_query_schema.py` | Unit tests for wiki_query MCP tool | VERIFIED | 9 passing |
| `agents/code-wiki-agent/tests/integration/test_query_e2e.py` | Integration tests against real Bedrock | VERIFIED | 2 tests passed live on Bedrock per 03-HUMAN-UAT.md Test 1 (35.94s) |
| `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` | Extended with `test_wiki_query_in_tools_list` | VERIFIED | Passed live on Bedrock per 03-HUMAN-UAT.md Test 3 (0.89s) |
| `cores/model-adapter/src/model_adapter/models.toml` | code_reader role config | VERIFIED | `[roles.code_reader]` with model_id, region, max_tokens, max_concurrency |
| `agents/code-wiki-agent/pyproject.toml` | bm25s==0.3.8, subagent-runtime, asyncio_mode=auto | VERIFIED | All three confirmed |
| `agents/code-wiki-agent/tests/conftest.py` | `fixture_vault_path` fixture pointing to round-trip-vault | VERIFIED | Confirmed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `cli.py::query` | `commands.query::run_query` | `asyncio.run(run_query(...))` | WIRED | cli.py:18 (import) + cli.py:160 (invocation) |
| `cli.py::main_callback` | `model_adapter.loader::set_models_path` | `set_models_path(_active_config.models_path)` | WIRED | cli.py:35-38 |
| `server.py::wiki_query` | `commands.query::run_query` | `await run_query(...)` | WIRED | server.py:62 + server.py:127 |
| `commands.query::run_query` | `subagent_runtime.pool::SubagentPool.run_all` | `await pool.run_all(items, task, role, model_id, max_concurrency)` | WIRED | query.py:45 (import) + query.py:885-891 (librarian) + query.py:496-502 (code_reader) |
| `commands.query::run_query` | `model_adapter.loader::make_llm` | `make_llm("librarian")` + `make_llm("synthesizer")` + `make_llm("code_reader")` | WIRED | query.py imports + invocations at the librarian/synth/code-reader call sites |
| `commands.query::run_query` | `_run_code_fallback` | `await _run_code_fallback(query, wiki, top_pages, pool, query_id)` | WIRED | query.py:946-952 (gated on empty useful_excerpts) |
| `commands.query::run_query` | `_retry_synthesis_drop_unresolved` | `await _retry_synthesis_drop_unresolved(synth_llm, query, excerpts_text, unresolved)` | WIRED | query.py:929-938 (gated on G1 unresolved) |
| `commands.query::_run_code_fallback` | `_read_file_bounded` | bound `read_file` LangChain tool closure + direct dispatch | WIRED | query.py:422-436 (`@tool` schema-only wrapper), query.py:478-486 (direct dispatch in tool-call loop) |
| `commands.query::run_query` | `apply_guardrails` | `apply_guardrails(query_result, wiki, fan_result, skip_g4=code_fallback_used)` | WIRED | query.py:982-984. **CR-01 fix:** skip_g4 keyword now suppresses G4 on the code-fallback path while preserving G1's unresolved-wikilink check. |
| `server.py::wiki_query` | `mcp.server.fastmcp.Context::report_progress` | 2x `await ctx.report_progress(...)` | WIRED | server.py:126, 132 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `run_query()` | `search_scores` | computed from real BM25 + cosine scores via `_rrf_fuse` | Yes | FLOWING |
| `run_query()` | `answer` (vault-rich path) | `synth_llm.ainvoke()` content | Yes (real Bedrock per Test 1 + Test 4 UAT) | FLOWING |
| `run_query()` | `answer` (vault-thin path) | `_run_code_fallback` → `code_llm.ainvoke()` + `synth_llm.ainvoke()` with CODE_FALLBACK_MARKER prefix | Yes (mocked in unit tests; live Bedrock path exists and exercised structurally) | FLOWING |
| `run_query()` | `citations` (code-fallback path) | `_extract_wikilinks(answer)` then preserved via `apply_guardrails(skip_g4=True)` | Yes — CR-01 fix prevents false stripping | FLOWING |
| `cli.py::query` | `result` | `asyncio.run(run_query(...))` | Yes | FLOWING |
| `server.py::wiki_query` | returned `WikiQueryOutput` | `QueryResult` from `await run_query(...)` | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unit suite (excl. test_cli_query.py per deferred-items.md) | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit --ignore=agents/code-wiki-agent/tests/unit/test_cli_query.py -q` | **118 passed in 4.56s** | PASS |
| CR-01 regression tests present and green | grep + run on `test_query_result.py:134, 167` | Both tests run, both green; test names: `test_apply_guardrails_skip_g4_preserves_citations_on_empty_successes`, `test_apply_guardrails_skip_g4_still_runs_g1` | PASS |
| `code-wiki-agent query --help` exits 0 and shows all 5 flags | `uv run code-wiki-agent query --help` | Exit 0; flags --top-k, --vault, --json, --no-state-gate, --quiet visible | PASS (from prior verification, unchanged) |
| `code-wiki-agent --help` shows top-level --config flag | `uv run code-wiki-agent --help` | Exit 0; `--config PATH` visible | PASS (from prior verification, unchanged) |
| Integration tests passed live on Bedrock per UAT | `CODE_WIKI_RUN_INTEGRATION=1 pytest tests/integration/...` (run by Pat) | test_query_e2e.py: 2 passed in 35.94s; test_mcp_stdio.py::test_wiki_query_in_tools_list: 1 passed in 0.89s | PASS |
| SC-1 side-by-side live rescore | 03-HUMAN-UAT.md Test 4 (Pat ran on live Bedrock 2026-05-15) | 3 dims PASS + 1 dim PARTIAL (by design — code-fallback did not fire because excerpts were useful-but-shallow); ≥3-of-4 threshold met | PASS |

### Probe Execution

No probe scripts (`scripts/*/tests/probe-*.sh`) declared or conventional for this phase. Step 7c: SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SEARCH-01 | Plan 02 | BM25 index via `bm25s` 0.3.8 | SATISFIED | `query.py:681-703` + `query.py:751-781`; `test_query_search.py` passes |
| SEARCH-02 | Plan 02 | Bedrock Titan v2 embedding index | SATISFIED | `query.py:715-740` (BedrockEmbeddings titan-embed-text-v2:0) |
| SEARCH-03 | Plan 02 | Hybrid search via RRF fusion | SATISFIED | `query.py:259-275` (`_rrf_fuse`); tests pass |
| SEARCH-04 | Plan 02 | Embedding index persists to SQLite (WAL mode) | SATISFIED | `_PRAGMA_WAL` applied during build_index; tests confirm WAL mode |
| SEARCH-05 | Plan 02 | Incremental rebuild via sha256 content hash | SATISFIED | `query.py:728-733` skip-on-hash-match logic |
| SEARCH-06 | Plan 02 | search_scores with bm25/cosine/fused visible in --json output | SATISFIED | `QueryResult.search_scores` populated at `query.py:967-974`; integration test verified live on Bedrock |
| CMD-04 | Plan 03 | `query` returns answer + citations + pages_drilled + search_scores | SATISFIED | `QueryResult` dataclass with all 4 fields; tests pass |
| CMD-07 | Plan 03 | `--json` flag for structured output | SATISFIED | `cli.py:152, 167-168` |
| CMD-08 | Plan 03 | State-gate mechanism (`--no-state-gate` is no-op for query) | SATISFIED | `cli.py:153, 157` |
| MCP-02 | Plan 04 | `wiki_query` tool with typed schema sufficient for DeepAgents CLI | SATISFIED | `WikiQueryInput`/`WikiQueryOutput` Pydantic schemas |
| MCP-04 | Plan 04 | Invalid input returns structured error | SATISFIED | `Field(ge=3, le=10)` enforces top_k; Pydantic ValidationError surfaces as MCP error |
| MCP-06 | Plan 04 | `ctx.report_progress()` called at start + end | SATISFIED | `server.py:126, 132` |
| MCP-07 | Plan 04 | `code-wiki-mcp` entry point; `wiki_query` in `tools/list` | SATISFIED | Confirmed live on Bedrock by UAT Test 3 |
| CLI-01 | Plan 03 | `code-wiki-agent query` subcommand exists | SATISFIED | `cli.py:147` |
| CLI-02 | Plan 03 | Full pipeline runs in-process via `asyncio.run` (no MCP host) | SATISFIED | `cli.py:160` |
| CLI-03 | Plan 03 | CLI and MCP share same implementation | SATISFIED | Both import run_query from `code_wiki_agent.commands.query` |
| CLI-04 | Plan 03 | `--json` flag on query subcommand | SATISFIED | `cli.py:152` |
| CLI-05 | (post-prior) | `--config <path>` for non-default model/role configuration | SATISFIED | `cli.py:30` (`main_callback`), wired to `set_models_path()` via `config.load_config()` |
| CLI-06 | Plan 03 | Exit codes 0/1/3 | SATISFIED | `cli.py:163` (1), `cli.py:181` (3) |
| CLI-07 | Plan 03 | Headless mode (`--quiet` + non-TTY stderr routing) | SATISFIED | `cli.py:154, 173-178` |

**All 20 requirement IDs from the phase's stated requirement set are SATISFIED.** No ORPHANED requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `query.py` | 826, 987 | `datetime.datetime.utcnow()` deprecated in Python 3.12+ | INFO (deferred) | 03-REVIEW.md WR-05. Will emit DeprecationWarning when project floor advances past 3.11. Not a Phase 3 blocker. |
| `query.py` | 467-486 | Tool-call dispatch unconditionally calls `_read_file_bounded` regardless of `call.name` | INFO (deferred) | 03-REVIEW.md WR-02. Containment preserved by `_read_file_bounded`. Advisory follow-up. |
| `query.py` | 468-494 | Last iteration of code-reader loop discards final tool reads (fence-post) | INFO (deferred) | 03-REVIEW.md WR-03. Advisory follow-up. |
| `query.py` | 327-351 | `_resolve_repo_root` silently degrades to `vault_path` in sibling layouts | INFO (deferred) | 03-REVIEW.md WR-04. Test 4 met SC-1 threshold without code-fallback firing — so the WR-04 limitation didn't block the phase goal. |
| `query.py` | 422-436, 478-483 | `@tool`-decorated `read_file` schema-only; direct dispatch duplicates error-handling | INFO (deferred) | 03-REVIEW.md IN-01 |
| `query.py` | 514-518 | Code-fallback excerpts truncated to 60_000 chars without log or marker | INFO (deferred) | 03-REVIEW.md IN-03 |
| `query.py` | 539-558, 642-650 | `_compute_unresolved_wikilinks` duplicates G1 resolution logic | INFO (deferred) | 03-REVIEW.md IN-04 |
| `query.py` | 954-967 | `pages_drilled=len(fan_result.successes)` counts librarian successes on code-fallback path | INFO (deferred) | 03-REVIEW.md WR-01. Observability concern, not correctness. |

No TBD / FIXME / XXX debt markers in Phase 3 modified files. The `Cost USD: (Phase 4)` placeholder in `cli.py:144` is informational and references the trace command, not the query path.

### Human Verification Required

None. All previously human-gated items are now resolved:
- Test 1 (integration tests on live Bedrock) — passed on 2026-05-14.
- Test 3 (MCP tools/list subprocess on live Bedrock) — passed on 2026-05-14.
- Test 4 (SC-1 side-by-side baseline rescore on live Bedrock) — passed on 2026-05-15 with 3-of-4 dimensions cleanly improved and 1 partial deferred to Phase 4.

### Gaps Summary

**No blockers. No warnings requiring action this phase.**

Prior verification's BLOCKER (CR-01: G4 strips citations on code-fallback path) is closed structurally and behaviorally:
- `apply_guardrails(..., *, skip_g4: bool = False)` adds the suppression switch.
- `run_query` passes `skip_g4=code_fallback_used` at the unique call site.
- Two regression tests pin the behavior in both directions (preserves citations when skipped; G1 still fires when skipped).
- Full unit suite 118/118 green.

Prior verification's UNCERTAIN (SC-1 quality re-scoring) is closed:
- Pat re-ran the original side-by-side baseline query on live Bedrock (Test 4 in 03-HUMAN-UAT.md).
- 3 of 4 dimensions cleanly improved (no fabricated paths/symbols; zero unresolved wikilinks; vault-thin acknowledgment).
- 1 dimension partial (code-path:line citations absent because librarian returned useful-but-shallow excerpts that prevented code-fallback from firing — by design). This is the correct outcome under the current threshold and is properly deferred to Phase 4's eval harness for systematic measurement across model swaps.

**Deferred items (informational):** code-path:line citations on useful-but-shallow vault pages (Phase 4 eval harness); WR-04 repo-root heuristic in sibling layouts; WR-01/02/03/05 + IN-* advisory follow-ups from 03-REVIEW.md. None of these block the phase goal.

**Phase goal is achieved.** The `query` command works end-to-end on real Bedrock with hybrid BM25+embedding search, librarian fan-out, and synthesis, and is accessible via both the MCP `wiki_query` tool and the headless `code-wiki-agent query` CLI, with both surfaces sharing a single `run_query()` implementation. SC-1 quality threshold is met.

---

_Verified: 2026-05-15T03:30:00Z_
_Verifier: Claude (gsd-verifier)_
