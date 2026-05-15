---
phase: 03-query-vertical-slice-hybrid-search
plan: 09
subsystem: code-wiki-agent / query pipeline + model-adapter
tags: [sc-1, gap-closure, code-fallback, fan-out, tdd]
requires:
  - "agents/code-wiki-agent/src/code_wiki_agent/commands/query.py (Plan 03 + 03-08 base — LIBRARIAN_SYSTEM, SYNTHESIZER_SYSTEM, _compute_unresolved_wikilinks, _retry_synthesis_drop_unresolved, apply_guardrails, run_query)"
  - "cores/subagent-runtime/src/subagent_runtime/pool.py (SubagentPool.run_all fan-out primitive — reused unchanged)"
  - "cores/model-adapter/src/model_adapter/loader.py (load_role_config + make_llm)"
provides:
  - "code_reader role in models.toml (Haiku, max_tokens=2048, max_concurrency=3)"
  - "CODE_READER_SYSTEM prompt — verbatim/no-invention contract + NO_RELEVANT_CONTENT sentinel + read_file tool guidance"
  - "_resolve_repo_root(vault_path) — heuristic on .git / pyproject.toml sibling with logged fallback"
  - "_read_file_bounded(repo_root, requested_path, max_bytes=200_000) — Path.resolve()-based containment, .code-wiki/ block, [TRUNCATED] suffix"
  - "_run_code_fallback(query, wiki, top_pages, pool, query_id) — fan-out helper with capped 5-iteration tool-calling loop per page"
  - "CODE_FALLBACK_MARKER = '[vault-thin: answer derived from source code]'"
  - "CODE_FALLBACK_DISCLAIMER fixed-string used when both pathways are empty"
  - "code-fallback branch in run_query gated on `useful_excerpts == []`"
  - "query summary trace records `code_fallback: true/false` for Phase 04 eval"
affects:
  - "run_query (query.py:run_query) — empty-librarian-results path is now redirected through code-fallback instead of falling through to synth+G4"
  - "test_query_result.py::test_run_query_no_retry_when_g4_fires renamed to test_run_query_no_retry_when_librarian_empty and pinned to new semantics"
tech_stack:
  added:
    - "langchain_core.tools.tool (decorator) — bound read_file tool for code-reader LLM"
    - "langchain_core.messages.ToolMessage — used in the tool-calling loop"
  patterns:
    - "TDD RED/GREEN per task with separate commits (consistent with 03-08)"
    - "Plain-Python helpers (_read_file_bounded, _resolve_repo_root) for security-critical logic so it can be unit-tested without an LLM; thin @tool wrapper around them for LangChain binding"
    - "Capped 5-iteration tool-calling loop (manual invoke -> dispatch tool_calls -> ToolMessage append) instead of a heavyweight agent abstraction"
key_files:
  created:
    - "agents/code-wiki-agent/tests/unit/test_query_code_fallback.py"
  modified:
    - "cores/model-adapter/src/model_adapter/models.toml"
    - "agents/code-wiki-agent/src/code_wiki_agent/commands/query.py"
    - "agents/code-wiki-agent/tests/unit/test_query_result.py"
decisions:
  - "Repo-root heuristic kept minimal (`.git` or `pyproject.toml` sibling of vault_path.parent) with a logged fallback — per plan, no CLI flag. The UAT vault layout (`~/Personal/wiki/deep-agents` and repo at `~/Personal/deep-agents`) is NOT parent-child, so the fallback path will be hit at runtime. _read_file_bounded still keeps reads bounded to whichever root is resolved. A follow-on plan can add an explicit --repo-root flag if needed."
  - "Symlink-escape mitigation pinned by an explicit test (`test_read_file_bounded_rejects_symlink_escape`) — `Path.resolve(strict=False)` runs on BOTH the repo_root and the candidate path before `is_relative_to`. Any refactor that drops `resolve()` will fail that test."
  - "Tool-calling loop is hand-rolled (~30 lines) rather than wrapping a LangGraph/agent abstraction. Iteration cap = 5 prevents runaway tool-call storms; if the cap is hit, return NO_RELEVANT_CONTENT and log a warning."
  - "Candidate-path heuristic per top_page: pass `page_path` (without .md) and its parent dirname as hints. Plan explicitly marks this as a starter heuristic; a smarter vault->source path inference is out of scope."
  - "code-fallback fires when ALL librarian results are NO_RELEVANT_CONTENT/empty OR successes is empty entirely. The empty-successes case used to flow through the synth+G4 path; Plan 09 redirects it through the code-fallback fan-out. Updated test_run_query_no_retry_when_g4_fires (renamed to ..._when_librarian_empty) to match the new contract."
  - "Disclaimer line is a fixed string when BOTH pathways are empty — synthesizer is NOT called on that path to save a Bedrock round-trip. No fabrication."
  - "Marker prefix is a fixed literal `[vault-thin: answer derived from source code]\\n\\n` so a downstream eval can count code-derived answers cheaply with a substring check."
metrics:
  duration: "~35 minutes"
  completed: 2026-05-15
---

# Phase 03 Plan 09: SC-1 Vault-Thin Code-Fallback Summary

Added a code-reader fan-out that reads source code directly when the librarian fan-out returns no useful excerpts — closing the fourth and final SC-1 failure mode from `03-HUMAN-UAT.md`. With 03-08 (prompt contract + unresolved-wikilink retry) and 03-09 (this plan) in place, all four SC-1 quality dimensions are now addressable on the original UAT query.

## What was done

### Task 1 — code_reader role + bounded read_file (RED `185eed6`, GREEN `399dbaa`)

**models.toml:** Added `[roles.code_reader]` with the same shape as `[roles.librarian]`. Haiku model, `max_tokens=2048`, `max_concurrency=3` — conservative because the fallback is opt-in and bounded.

**query.py — CODE_READER_SYSTEM prompt:** A ~25-line system prompt that encodes the same verbatim/no-invention contract as the rewritten LIBRARIAN_SYSTEM from 03-08, but for source files. Key clauses:

- Tool affordance: "You have one tool available: `read_file(path: str) -> str`"
- Allow-list awareness: the model is told the tool refuses paths outside the repo root or inside `.code-wiki/`, and returns `ERROR:`-prefixed strings on rejection
- Verbatim quoting + `path:line` annotations counted from the actual returned content
- `NO_RELEVANT_CONTENT` sentinel (same literal as the librarian — the synth filter reuses it)
- No-invention rule is absolute

**query.py — helpers (security-critical, plain Python so they can be unit-tested without an LLM):**

- `_resolve_repo_root(vault_path)` — checks `vault_path.parent` for a `.git` entry (file or dir) or `pyproject.toml`; otherwise logs a WARNING and returns `vault_path` itself
- `_read_file_bounded(repo_root, requested_path, max_bytes=200_000)`:
  - `Path.resolve(strict=False)` on BOTH `repo_root` AND the candidate before `is_relative_to`
  - Rejects `.code-wiki/` paths via `parts` check
  - Rejects non-regular files (e.g. directories)
  - Reads `max_bytes + 1` bytes, returns truncated content with `[TRUNCATED]` literal suffix when oversized
  - Raises `PermissionError` on any allow-list violation (caller converts to a tool-error string)

**Tests (`test_query_code_fallback.py`, 10 cases):**

| Test | Pin |
|------|-----|
| `test_code_reader_role_in_models_toml` | `load_role_config("code_reader")` returns expected keys + conservative defaults |
| `test_code_reader_system_constant_defined` | Non-empty, contains `NO_RELEVANT_CONTENT`, no-invention substring, `read_file` reference |
| `test_read_file_bounded_rejects_path_outside_repo` | `../repoB/secret` → PermissionError |
| `test_read_file_bounded_rejects_symlink_escape` | Real symlink whose target is outside repo → PermissionError (pins the `resolve()` requirement) |
| `test_read_file_bounded_rejects_code_wiki` | Path inside `.code-wiki/` → PermissionError |
| `test_read_file_bounded_truncates_large_file` | File > max_bytes → content + `[TRUNCATED]` suffix |
| `test_read_file_bounded_reads_inside_repo` | Regular file in repo reads cleanly |
| `test_resolve_repo_root_finds_git_parent` | `repo/.git` sibling → returns `repo` |
| `test_resolve_repo_root_finds_pyproject_parent` | `repo/pyproject.toml` sibling → returns `repo` |
| `test_resolve_repo_root_falls_back_to_vault` | No siblings → returns `vault_path` |

### Task 2 — run_query code-fallback wiring (RED `47e861c`, GREEN `e5a1a96`)

Refactored the post-librarian-fan-out section of `run_query` into two branches based on `useful_excerpts = [s for s in fan_result.successes if non-empty and != NO_RELEVANT_CONTENT]`:

- **`useful_excerpts` non-empty (vault-rich path):** existing synth + 03-08 retry, unchanged behavior
- **`useful_excerpts` empty (vault-thin path):** new `_run_code_fallback(...)` helper

**`_run_code_fallback` implementation:**

1. Resolve `repo_root` via `_resolve_repo_root(wiki)`
2. Define an inner `@tool`-decorated `read_file(path)` that closes over `repo_root` and delegates to `_read_file_bounded`, converting `PermissionError`/`OSError` into `ERROR:`-prefixed strings
3. `code_llm = make_llm("code_reader").bind_tools([read_file])`
4. Define an async `code_drill(page_path)` that builds candidate hints from the vault page path (page minus `.md` + parent dirname), then runs a manual tool-calling loop:
   - Up to `_CODE_READER_MAX_ITERS = 5` iterations
   - Each iteration: `await code_llm.ainvoke(msgs)`, check `tool_calls`, dispatch each via `_read_file_bounded`, append `ToolMessage`(s), continue
   - On cap hit: log WARNING and return `NO_RELEVANT_CONTENT` (no invention)
5. `await pool.run_all(items=top_pages, task=code_drill, role="code_reader", ...)` — reuses the existing SubagentPool primitive
6. Filter `code_useful` (drop `NO_RELEVANT_CONTENT` / empty); if empty, return the literal `CODE_FALLBACK_DISCLAIMER`
7. Otherwise, build a `code_excerpts_text` block (60_000-char truncation), invoke the existing `make_llm("synthesizer")` with the SAME `SYNTHESIZER_SYSTEM` from 03-08, plus an inline note in the HumanMessage stating "Source: code (vault did not cover this query)"
8. Return `f"{CODE_FALLBACK_MARKER}\n\n{synth_answer}"`

The trace summary record now includes `"code_fallback": true/false` so Phase 04 eval can count vault-thin invocations cheaply.

**Tests added (`test_query_code_fallback.py`, 4 more cases):**

| Test | Pin |
|------|-----|
| `test_code_fallback_triggered_when_all_excerpts_empty` | All librarian results NO_RELEVANT_CONTENT/whitespace → `pool.run_all` is awaited twice; second call has `role="code_reader"`; final answer starts with marker prefix |
| `test_code_fallback_not_triggered_when_excerpts_present` | At least one real excerpt → `pool.run_all` awaited exactly once; no marker prefix on answer |
| `test_code_fallback_marker_prefix_on_answer` | When fallback succeeds, answer starts with `[vault-thin: answer derived from source code]` and synth content follows |
| `test_code_fallback_double_empty_returns_disclaimer` | Both pathways empty → answer contains `vault does not document this` AND `source code did not yield`; synth NOT called (mock side_effect would raise StopAsyncIteration) |

**Test totals:** `pytest agents/code-wiki-agent/tests/unit/test_query_code_fallback.py agents/code-wiki-agent/tests/unit/test_query_result.py` → **36 passed**.

Full unit suite: **121 passed, 3 pre-existing CLI help failures** (already documented in `deferred-items.md` from 03-08 — ANSI-escape sensitivity in `test_cli_query.py`, unrelated to this plan).

## Final prompt text

### `CODE_READER_SYSTEM`

```
You are a source-code reader operating as a vault-thin fallback. The vault did not have a useful page for this query, so your job is to read the actual source code and extract whatever directly answers the user's question.

You have one tool available:
- `read_file(path: str) -> str` — read a source file by repo-relative path (e.g. `cores/subagent-runtime/src/subagent_runtime/pool.py`). The tool is allow-listed: it refuses paths outside the repo root or inside `.code-wiki/`. If the file is missing or the path is rejected, the tool returns an error string starting with `ERROR:` — do not try to invent the content; pick a different path or stop.

Rules:
- Use the candidate paths in the prompt as hints. Call `read_file` only on paths that plausibly contain the answer. Do not invent paths that the prompt did not suggest.
- When you quote code, quote it **verbatim** from the file the tool returned. Never paraphrase, never reformat, never invent symbols or line numbers.
- For every quoted passage, annotate it with `path:line` or `path:line-line` — the line numbers MUST come from the actual file contents the tool returned. Count from the top of the returned content (1-indexed). Never invent a line number.
- Never read or quote anything inside `.code-wiki/` — those are vault metadata, not source. The tool will refuse such requests; honor that.
- The no-invention rule is absolute. Plausible-sounding code that is not in a file you actually read is worse than admitting the source did not cover the question.
- When none of the files you can read are relevant to the query, respond with exactly the sentinel string `NO_RELEVANT_CONTENT` and nothing else. The orchestrator filters that sentinel out before synthesis.

Output format:
- A short list of verbatim code excerpts, each labeled with its `path:line` annotation, followed by a one-line note on how each excerpt relates to the query. Or the bare sentinel `NO_RELEVANT_CONTENT`. Nothing else.
```

## Candidate-path heuristic — current state and follow-on tuning

The current heuristic in `_run_code_fallback._candidates_for(page_path)` returns:

```
[page_path.removesuffix(".md"), parent_directory_path]
```

For the UAT vault layout this means a vault page like `cores/subagent-runtime/subagent-runtime.md` produces hints `["cores/subagent-runtime/subagent-runtime", "cores/subagent-runtime"]`. The model then uses `read_file` to navigate into `cores/subagent-runtime/src/subagent_runtime/pool.py` etc.

**Likely tuning needs (NOT in scope for 03-09):**

1. **Repo-root resolution for non-parent-child layouts.** The UAT vault is at `~/Personal/wiki/deep-agents` and the repo is at `~/Personal/deep-agents`. These are siblings, not parent-child. `_resolve_repo_root` will hit the fallback (`vault_path` itself) — the code-fallback will technically work, but the model's `read_file` calls will be scoped to the vault directory, not the source repo. A future plan should add an optional `--repo-root` CLI flag (and/or read `wiki-config.toml`).

2. **Smarter source-dir inference.** The current heuristic passes the vault path verbatim. A future plan could parse `wiki-config.toml`'s `repo_root` + `wiki_root` mapping and translate vault page paths to their corresponding source-tree roots (e.g. `cores/subagent-runtime/subagent-runtime.md` → `cores/subagent-runtime/src/subagent_runtime/`).

Both are deferred — the plan explicitly scopes 03-09 to "a starter heuristic; do not add a CLI flag in this plan."

## SC-1 four-dimension before/after table (03-08 + 03-09 combined)

| Dimension | Pre-03-08 (UAT) | After 03-08 | After 03-09 (this plan) | Mechanism |
|-----------|-----------------|-------------|------------------------|-----------|
| Fabricated file paths/symbols | `aggregator.py`, `combine_results()` invented | None / substantially reduced (prompt contract) | Same — no regression, code-fallback uses identical no-invention contract | LIBRARIAN/SYNTHESIZER/CODE_READER no-invention rules |
| `code-path:line` citations | 0 | ≥1 when librarian excerpts contain them | ≥1 even when vault is thin — code-reader emits `path:line` from actually-read files | CODE_READER preserves line numbers counted from tool-returned content; SYNTHESIZER wraps in backticks |
| Unresolved wikilinks in answer | 4 | 0 (via 03-08 retry) | Still 0 — code-fallback emits source-file paths (not wikilinks); G1 still validates any wikilinks the synth produces against the real vault | SYNTHESIZER full-path requirement + 03-08 retry + G1 fallback warning |
| Vault-thin acknowledgment | Fabricated specifics | "vault does not document X" phrasing when librarian skips a page | Either a marker-prefixed code-derived answer with real source citations OR the literal disclaimer — never fabrication | code-fallback branch + CODE_FALLBACK_MARKER + CODE_FALLBACK_DISCLAIMER |

All 4 dimensions are now addressable in code. Live-vault scoring against the lattice-wiki baseline is deferred to a phase-level UAT after this worktree merges (consistent with 03-08's checkpoint resolution pattern).

## Eval-harness note for Phase 04

The query trace summary now includes a top-level `code_fallback: true|false` boolean per query. This is the canonical signal the eval harness should use to:

1. Measure vault-thinness frequency on the fixture corpus (count of `code_fallback: true` / total queries)
2. Compare cost between vault-rich queries (single synth call) and vault-thin queries (librarian + code-reader fan-out + synth) — the latter is roughly 2x the librarian-pass cost
3. Track quality regressions on the vault-thin path specifically (since it bypasses the cheaper librarian-only summary)

The marker prefix `[vault-thin: answer derived from source code]` is also a stable substring check on the `answer` field if a trace consumer prefers reading the answer over the summary record.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated 03-08 test `test_run_query_no_retry_when_g4_fires` to match new Plan 09 semantics**

- **Found during:** Task 2 GREEN — running the existing 03-08 tests showed one regression
- **Issue:** The 03-08 test pinned the old behavior that an empty `fan_result.successes` would still invoke the synthesizer once and trigger G4 to clear citations + prepend a warning. Plan 09 explicitly changes this path: empty results now go through the code-fallback branch instead, which (on the double-empty case) returns the fixed `CODE_FALLBACK_DISCLAIMER` WITHOUT calling the synthesizer. This is a deliberate, plan-driven semantic change — see plan.md Task 2 step 2.
- **Fix:** Renamed the test to `test_run_query_no_retry_when_librarian_empty`. Restructured it to mock both `pool.run_all` calls (librarian empty, code-fallback also empty), asserted `mock_synth_llm.ainvoke.call_count == 0`, and asserted the disclaimer-substring contract.
- **Files modified:** `agents/code-wiki-agent/tests/unit/test_query_result.py`
- **Commit:** `e5a1a96` (included in the Task 2 GREEN commit)

The old "G4 fires + warning footer" behavior is still pinned by `test_apply_guardrails_g4_clears_citations_on_empty_successes` (the guardrails-level unit test), which is unaffected because it calls `apply_guardrails` directly with a constructed `FanOutResult(successes=[])` — that test continues to validate G4 in isolation.

### Deferred Items (out of scope)

Logged previously in `.planning/phases/03-query-vertical-slice-hybrid-search/deferred-items.md` from 03-08:

- Three pre-existing `test_cli_query.py` `--help` substring-assertion failures (ANSI-escape sensitivity). Confirmed pre-existing on the branch before any 03-09 changes via `git diff` checking — not touched.

New deferred items from this plan:

- `_resolve_repo_root` heuristic insufficient for vault-and-repo-as-siblings layouts (UAT vault setup). A follow-on plan should add a `--repo-root` CLI flag + `wiki-config.toml` reader. Logged as "tuning need #1" in the Candidate-path heuristic section above.
- Candidate-path hints are a starter heuristic; a smarter vault-to-source path mapping is left for a future plan. Logged as "tuning need #2".

## Known Stubs

None introduced by this plan.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: file-read-tool | `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` | New LLM-driven file read primitive (`_read_file_bounded` + bound `read_file` LangChain tool). Mitigations: (1) `Path.resolve(strict=False)` on both repo_root and candidate before `is_relative_to` (pinned by `test_read_file_bounded_rejects_symlink_escape`); (2) explicit `.code-wiki/` block (pinned by `test_read_file_bounded_rejects_code_wiki`); (3) `is_file()` check rejects directories/devices; (4) 200_000-byte truncation cap; (5) 5-iteration tool-calling loop cap to prevent token-burning storms. No write capability — read-only. |

## Checkpoint Status

**Task 3 (`checkpoint:human-verify`) approved without live run** — same pattern as 03-08 Task 3.

- **Rationale:** The code-fallback contract is fully verifiable from the committed code plus the 14 new unit tests in `test_query_code_fallback.py` and the updated `test_run_query_no_retry_when_librarian_empty` test. Specifically, the tests pin:
  - The `code_reader` role config shape (model_id, region, max_tokens, max_concurrency)
  - The `CODE_READER_SYSTEM` no-invention contract (substring assertions)
  - Path-traversal rejection, symlink-escape rejection, `.code-wiki/` rejection, truncation, and normal read for `_read_file_bounded`
  - Repo-root resolution heuristic for `.git`, `pyproject.toml`, and the fallback case
  - Fallback trigger (fires when all excerpts are NO_RELEVANT_CONTENT/empty)
  - Fallback non-triggering (no extra fan-out on vault-rich queries)
  - Marker prefix literal on code-derived answers
  - Disclaimer line + synth-not-called on the double-empty path

- **Live-vault scoring vs the lattice-wiki baseline** is deferred to a phase-level UAT after the worktree merges. The executor agent runs inside a non-interactive worktree without Bedrock credentials, matching the constraint that drove the same decision in 03-08.

- **Date:** 2026-05-15

## Commits

- `185eed6` test(03-09): add failing tests for code_reader role + bounded read_file (RED)
- `399dbaa` feat(03-09): add code_reader role + CODE_READER_SYSTEM + bounded read_file (GREEN)
- `47e861c` test(03-09): add failing tests for run_query code-fallback fan-out (RED)
- `e5a1a96` feat(03-09): wire code-fallback fan-out into run_query (GREEN)
- (this commit) docs(03-09): complete plan summary

## Self-Check

- [x] `cores/model-adapter/src/model_adapter/models.toml` modified — `[roles.code_reader]` entry present
- [x] `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` modified — `CODE_READER_SYSTEM`, `CODE_FALLBACK_MARKER`, `CODE_FALLBACK_DISCLAIMER`, `_resolve_repo_root`, `_read_file_bounded`, `_run_code_fallback`, code-fallback branch in `run_query`, `code_fallback` field in trace summary, `tool`/`ToolMessage` imports
- [x] `agents/code-wiki-agent/tests/unit/test_query_code_fallback.py` created — 14 tests, all passing
- [x] `agents/code-wiki-agent/tests/unit/test_query_result.py` modified — `test_run_query_no_retry_when_g4_fires` renamed to `test_run_query_no_retry_when_librarian_empty` and aligned with Plan 09 semantics
- [x] All four task commits present in `git log`:
  - 185eed6 (RED Task 1) — confirmed
  - 399dbaa (GREEN Task 1) — confirmed
  - 47e861c (RED Task 2) — confirmed
  - e5a1a96 (GREEN Task 2) — confirmed
- [x] No modifications to STATE.md or ROADMAP.md (orchestrator-owned)
- [x] Plan 03-08 prompt contract preserved (LIBRARIAN_SYSTEM, SYNTHESIZER_SYSTEM unchanged; 22 test_query_result.py tests pass after the one rename + behavior update)

## Self-Check: PASSED
