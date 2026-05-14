---
phase: 03-query-vertical-slice-hybrid-search
plan: "03"
subsystem: query
tags: [query, cli, librarian-fan-out, synthesizer, guardrails, typer, asyncio, dataclass]

requires:
  - phase: 03-02
    provides: "build_index, bm25_query, _cosine_search_sqlite, _rrf_fuse — search helpers already wired"
  - phase: 02-subagent-fan-out-runtime
    provides: "SubagentPool.run_all, FanOutResult, PerItemError — fan-out primitive"
  - phase: 01-infrastructure-vault-io-and-mcp-skeleton
    provides: "resolve_wiki_and_repo, make_llm, load_role_config — vault resolution and model adapter"

provides:
  - "QueryResult @dataclass: answer, citations, pages_drilled, search_scores"
  - "run_query() async pipeline: resolve -> auto-build -> BM25 -> embed -> RRF -> librarian fan-out -> synthesizer -> guardrails"
  - "LIBRARIAN_SYSTEM and SYNTHESIZER_SYSTEM prompt constants"
  - "apply_guardrails(): G1 (citation resolution) + G4 (empty-result safety)"
  - "_extract_wikilinks(): [[wikilink]] regex extractor"
  - "code-wiki-agent query CLI subcommand with --top-k, --vault, --json, --no-state-gate, --quiet"
  - "Exit codes: 0 success, 1 user error, 3 partial success"

affects:
  - "03-04-MCP tool (wiki_query) will import run_query from commands/query.py"
  - "Phase 4 eval harness will test QueryResult shape and citation accuracy"

tech-stack:
  added: []
  patterns:
    - "asyncio.run() bridges sync Typer CLI to async run_query() pipeline"
    - "Guardrails run after synthesis: G4 clears citations on empty fan-out, G1 checks each [[wikilink]] against vault filesystem"
    - "Query summary JSONL written directly to traces/ (not via SubagentPool) — per RESEARCH Open Question 1 recommendation"
    - "CliRunner tests use monkeypatch on code_wiki_agent.cli.run_query for isolation"

key-files:
  created:
    - "agents/code-wiki-agent/tests/unit/test_query_result.py — 13 tests for QueryResult, guardrails, run_query mock"
    - "agents/code-wiki-agent/tests/unit/test_cli_query.py — 8 tests for CLI subcommand flags, exit codes, JSON output"
  modified:
    - "agents/code-wiki-agent/src/code_wiki_agent/commands/query.py — added QueryResult, LIBRARIAN_SYSTEM, SYNTHESIZER_SYSTEM, run_query, apply_guardrails, _extract_wikilinks"
    - "agents/code-wiki-agent/src/code_wiki_agent/cli.py — added query() Typer subcommand, imports asyncio/dataclasses/sys/run_query"

key-decisions:
  - "Typer CliRunner does not support mix_stderr kwarg — tests use CliRunner() and check result.output"
  - "test_run_query_unit_with_mocks checks answer contains synthesizer text (not strict equality) because G1 guardrail appends warnings for unresolved citations in mock vault"
  - "Query summary JSONL written directly from run_query() to traces/query_<id>.jsonl — avoids changing SubagentPool API in Phase 3"

patterns-established:
  - "TDD RED-GREEN per task: failing test committed first, then implementation committed"
  - "All worktree commits use git -C <worktree-path> to avoid main-branch drift (#3097)"
  - "CliRunner tests monkeypatch code_wiki_agent.cli.run_query (module attribute) not the module function"

requirements-completed: [CMD-04, CMD-07, CMD-08, CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06, CLI-07]

duration: 9min
completed: 2026-05-14
---

# Phase 03 Plan 03: MVP Query Command — run_query Pipeline + CLI Summary

**QueryResult dataclass and run_query() async pipeline wired with G1+G4 guardrails; `code-wiki-agent query` CLI subcommand delivers the first user-facing end-to-end query entry point**

## Performance

- **Duration:** 9 min
- **Started:** 2026-05-14T04:13:15Z
- **Completed:** 2026-05-14T04:22:40Z
- **Tasks:** 2 (each with RED + GREEN TDD commits)
- **Files modified:** 4

## Accomplishments

- `QueryResult` dataclass defined with `answer`, `citations`, `pages_drilled`, `search_scores` fields — `dataclasses.asdict()` serializes cleanly to JSON
- `run_query()` async pipeline: resolve vault -> auto-build index on first run -> BM25 + embedding search (over-retrieve 3x) -> RRF fusion -> librarian fan-out (SubagentPool) -> synthesizer (Sonnet) -> apply guardrails
- G4 guardrail: clears citations and prepends warning when librarian fan-out returns zero successes
- G1 guardrail: appends `[warning: N citation(s) did not resolve: ...]` for each `[[wikilink]]` not found in the vault filesystem
- `code-wiki-agent query` Typer subcommand: `--top-k`, `--vault`, `--json`, `--no-state-gate`, `--quiet` all wired; exit codes 0/1/3; non-TTY routes "Pages drilled:" to stderr
- 21 new unit tests (13 for query pipeline, 8 for CLI subcommand); zero xfail markers in plan 03 test files

## Task Commits

Each task was committed atomically with RED then GREEN:

1. **Task 1 RED: Failing tests for QueryResult, guardrails, run_query** - `84a3bb3` (test)
2. **Task 1 GREEN: Implement QueryResult, run_query, guardrails** - `9fd7df6` (feat)
3. **Task 2 RED: Failing tests for CLI query subcommand** - `a423d9e` (test)
4. **Task 2 GREEN: Add query Typer subcommand + updated tests** - `a00e64f` (feat)

## Files Created/Modified

- `/agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` — Extended with QueryResult, LIBRARIAN_SYSTEM, SYNTHESIZER_SYSTEM, _extract_wikilinks, apply_guardrails, run_query
- `/agents/code-wiki-agent/src/code_wiki_agent/cli.py` — Added query() subcommand + imports (asyncio, dataclasses, sys, run_query)
- `/agents/code-wiki-agent/tests/unit/test_query_result.py` — 13 unit tests replacing stubs
- `/agents/code-wiki-agent/tests/unit/test_cli_query.py` — 8 unit tests replacing stubs

## Decisions Made

- `Typer CliRunner` does not accept `mix_stderr=False` kwarg (undocumented limitation) — tests use `CliRunner()` and check `result.output` which mixes stdout+stderr; headless routing is verified by subprocess test
- `test_run_query_unit_with_mocks` uses `in` containment check for answer (not strict equality) because the G1 guardrail appends a resolution warning when FakePage.md does not exist in the mock tmp_path vault
- Query summary JSONL record written directly from `run_query()` to `traces/query_<id>.jsonl` rather than adding `correlation_id` kwarg to SubagentPool (simpler, zero API change, per RESEARCH Open Question 1 recommendation)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_run_query_unit_with_mocks answer assertion too strict**
- **Found during:** Task 1 GREEN phase run
- **Issue:** Test asserted `result.answer == "Answer about [[FakePage]]."` but the G1 guardrail correctly appends `[warning: 1 citation(s) did not resolve: ['FakePage']]` because FakePage.md doesn't exist in the mock vault (tmp_path). This is correct behavior, not a bug.
- **Fix:** Changed assertion to `assert "Answer about [[FakePage]]." in result.answer`
- **Files modified:** `tests/unit/test_query_result.py`
- **Committed in:** `9fd7df6` (Task 1 feat commit, test updated inline)

**2. [Rule 1 - Bug] CliRunner does not support mix_stderr kwarg**
- **Found during:** Task 2 GREEN phase run
- **Issue:** `typer.testing.CliRunner(mix_stderr=False)` raises `TypeError: CliRunner.__init__() got an unexpected keyword argument 'mix_stderr'`
- **Fix:** Removed `mix_stderr=False` from all CliRunner instantiations; adjusted `test_headless_mode_progress_to_stderr` to check `result.output` instead of `result.stdout`
- **Files modified:** `tests/unit/test_cli_query.py`
- **Committed in:** `a00e64f` (Task 2 feat commit, test updated inline)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — test assertion corrections discovered during GREEN phase)
**Impact on plan:** Both fixes were minor test adjustments; no implementation scope change.

## Issues Encountered

- Worktree cwd-drift (#3097): first RED commit accidentally landed on `main` branch because `cd /Users/pat/Personal/deep-agents` put the shell in the main repo context. Recovered by `git reset --hard` on main and re-committing from worktree path `git -C <worktree>`. All subsequent commits used `git -C "$WT"` pattern.

## Known Stubs

None — `commands/query.py` fully implements the pipeline. All stubs replaced with real tests.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns beyond what was planned in the threat model. `drill_page` reads only paths from the BM25 corpus (vault-rooted, not user-supplied), and the 24000-char truncation guard (T-03-10) is implemented.

## Next Phase Readiness

- `run_query()` is importable and tested; Plan 04 (MCP `wiki_query` tool) can immediately import and await it
- `QueryResult` shape is stable; MCP wrapper will use `dataclasses.asdict()` to serialize
- Unit test suite: 42 passed, 3 xfailed (MCP stubs for Plan 04) — clean baseline

## Self-Check: PASSED

- `commands/query.py` exists: FOUND
- `cli.py` has `def query(`: FOUND
- Commits `84a3bb3`, `9fd7df6`, `a423d9e`, `a00e64f` exist: CONFIRMED via git log
- pytest unit suite: 42 passed, 3 xfailed

---
*Phase: 03-query-vertical-slice-hybrid-search*
*Completed: 2026-05-14*
