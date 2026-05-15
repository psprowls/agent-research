---
status: partial
phase: 03-query-vertical-slice-hybrid-search
source: [03-VERIFICATION.md]
started: 2026-05-14T04:38:39Z
updated: 2026-05-15T02:45:00Z
reopened_reason: "Test 4 added after 03-08 + 03-09 + CR-01 fix — SC-1 quality must be re-scored against the lattice-wiki baseline now that structural fixes are in place"
---

## Current Test

4 — pending

## Tests

### 1. End-to-End Bedrock Query (ROADMAP SC-1 + SC-5, SEARCH-06)
expected: Exit 0 or 3; JSON output contains `pages_drilled >= 1`, at least one `[[wikilink]]` citation in `answer`, and `search_scores` dict with `bm25`/`embed`/`rrf` keys per page.
result: pass
evidence: |
  `CODE_WIKI_RUN_INTEGRATION=1 pytest tests/integration/test_query_e2e.py -m integration -v` → 2 passed in 35.94s against live Bedrock. test_fixture_vault_has_citations (wikilinks present in answer) and test_json_flag_emits_search_scores (bm25/embed/rrf keys in search_scores) both green.

**Run:**
```bash
CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/integration/test_query_e2e.py -m integration -v
```
or manually:
```bash
uv run code-wiki-agent query "What does the SubagentPool do?" \
  --vault cores/vault-io/tests/fixtures/round-trip-vault \
  --top-k 3 --json
```

### 2. Answer Quality Assessment (ROADMAP SC-1)
expected: Answer is coherent, includes code-path references, and wikilink citation structure is comparable to lattice-wiki's librarian output depth.
result: issue
reported: "answer hallucinates file paths, no code-path citations, unresolved wikilinks, no code-fallback when vault is thin...maybe needs skill content"
severity: major

**Run:** Invoke the query command against a real lattice-wiki vault and compare to existing `lattice-wiki` plugin output.

**Comparison evidence:**

Query: "How does the SubagentPool fan out work to Bedrock and where are the results aggregated?" — same vault (`~/Personal/wiki/deep-agents/`), same question.

| Dimension | lattice-wiki librarian | code-wiki-agent |
|-----------|------------------------|-----------------|
| Code-path:line citations | Yes — `pool.py:115`, `:121-146`, `:149`, `:156-158`, `:162-210`, `loader.py:82-107` | None |
| Real symbol names | `run_all`, `_run_one`, `_GuardedChatBedrockConverse`, `FanOutResult.successes/.errors`, `PerItemError`, `RunnableConfig`, `BedrockAccessDenied` | None (guessed `combine_results()`, fabricated `aggregator.py`) |
| Wikilinks resolve | `[[wiki/cores/subagent-runtime/subagent-runtime]]` (real page paths) | 4 unresolved — `[[SubagentPool]]`, `[[Bedrock]]` (slug-only, no path) |
| Vault-thin handling | Read code directly when pages were TODO stubs; explicitly noted the limitation | Stayed in vault, fabricated specifics |
| Real concrete content | `models.toml` role/model/max_concurrency table reproduced; explained Semaphore-in-`run_all` event-loop rationale and `return_exceptions=True` deepagents-bug context | Generic plausible-sounding prose |

### 3. MCP tools/list Subprocess Test (MCP-07)
expected: `wiki_query` appears in `tools/list` with "hybrid" or "BM25" in its description.
result: pass
evidence: |
  `CODE_WIKI_RUN_INTEGRATION=1 pytest tests/integration/test_mcp_stdio.py::test_wiki_query_in_tools_list -m integration -v` → 1 passed in 0.89s.

**Run:**
```bash
CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/integration/test_mcp_stdio.py::test_wiki_query_in_tools_list -m integration -v
```

### 4. SC-1 Answer-Quality Re-Scoring after 03-08 + 03-09 + CR-01 fix (ROADMAP SC-1)
expected: |
  Run the same baseline query against the same vault on live Bedrock. Score ≥3 of 4 dimensions
  improving vs the Test 2 baseline:
    (1) No fabricated file paths or symbols
    (2) ≥1 `code-path:line` style citation when excerpts contain them
    (3) Zero unresolved wikilinks (the new G1 retry should strip them)
    (4) When vault pages are TODO stubs, the answer is prefixed with
        `[vault-thin: answer derived from source code]` and cites real source files

  The fourth dimension is the new code-fallback path (03-09); the first three are the
  prompt-contract + retry path (03-08).

result: pending
why_human: |
  Both 03-08 and 03-09 had `checkpoint:human-verify` Task 3s that were "approved without
  live run" because executor agents have no live Bedrock session. The structural contract
  is pinned by 38 unit tests (22 in test_query_result.py + 14 in test_query_code_fallback.py
  + 2 added for CR-01 fix), but the behavioral quality vs baseline has not been measured.

**Run:**
```bash
uv run code-wiki-agent query "How does the SubagentPool fan out work to Bedrock and where are the results aggregated?" \
  --vault ~/Personal/wiki/deep-agents \
  --top-k 5 --json
```

**Compare against** the Test 2 baseline table above. Mark `pass` if ≥3 of 4 dimensions
clearly improve; mark `issue` and capture which dimension regressed otherwise.

## Summary

total: 4
passed: 2
issues: 1
pending: 1
skipped: 0
blocked: 0

## Gaps

- truth: "code-wiki-agent query returns answers as good as lattice-wiki librarian — coherent, code-path-cited, resolved wikilinks, drills into code when vault pages are stubs (ROADMAP SC-1)"
  status: failed
  reason: "User reported: answer hallucinates file paths, no code-path citations, unresolved wikilinks, no code-fallback when vault is thin...maybe needs skill content"
  severity: major
  test: 2
  artifacts: []
  missing: []
  hypothesis: "Librarian benefits from rich skill/prompt scaffolding (`agents/librarian.md`, `references/query-workflow.md`). Code-wiki-agent's librarian role prompt may be too thin — missing instructions to (a) emit code-path:line citations, (b) format wikilinks as full page paths not slugs, (c) drill into source code via filesystem tools when vault pages are TODO stubs, (d) acknowledge vault-thinness limitations rather than fabricate."
  root_cause: |
    The code-wiki-agent librarian is a bare single-shot LLM call over a single pre-loaded vault page with a ~60-word system prompt — no filesystem/code-reading tools, no code-path:line citation contract, no wikilink-format spec, no fallback-to-source-code rule. The reference lattice-wiki librarian is a Claude-Code sub-agent with `tools: [Read, Write, Edit, Bash, Grep, Glob]` and a multi-step contract (read index.md → drill 3-10 pages → follow wikilinks → fall back to code → cite `[[wiki/cat/page]]` + `path:line` → "if vault doesn't know, say so"). The port collapsed all of this into one SystemMessage. This single architectural gap produces all four observed failure modes.
  affected_files:
    - "agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:131-143 (LIBRARIAN_SYSTEM + SYNTHESIZER_SYSTEM prompts)"
    - "agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:543-554 (drill_page sees one page text, no tools)"
    - "agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:280-336 (apply_guardrails G1 warns on unresolved wikilinks but doesn't retry)"
  baseline_reference_files:
    - "~/.claude/plugins/cache/lattice/lattice-wiki/1.3.3/agents/librarian.md"
    - "~/.claude/plugins/cache/lattice/lattice-wiki/1.3.3/skills/lattice-wiki/references/query-workflow.md"
  scope_estimate: |
    Small (~30 lines): rewrite both prompt constants with wikilink format spec, code-citation contract, "no invention" rule, "NO_RELEVANT_CONTENT" stub-detect rule. Likely fixes fabrication + bad-wikilink symptoms alone.
    Medium (~150-300 lines): add a code-reader role + read_file tool + fallback fan-out when all drilled pages are stubs. Closes the "no code-fallback when vault is thin" gap from user's report.
  recommendation: "Start small (prompts only), re-query, measure delta vs baseline. Lattice-wiki baseline's strength is mostly the workflow contract in the prompt; tools are the safety net for stub vaults."
  side_by_side_query: "How does the SubagentPool fan out work to Bedrock and where are the results aggregated?"
  vault: "~/Personal/wiki/deep-agents/"
  baseline_output: "Cited pool.py:115/:121-146/:149/:156-158/:162-210, loader.py:82-107; named real symbols (run_all, _run_one, _GuardedChatBedrockConverse, FanOutResult, PerItemError, BedrockAccessDenied); reproduced models.toml role table; used real wikilink targets [[wiki/cores/subagent-runtime/subagent-runtime]]; explicitly noted vault stubs and code-derived answer."
  actual_output: "Generic prose; fabricated 'src/agents/subagent_pool/aggregator.py' and 'combine_results()'; 4 unresolved citation warnings ([[SubagentPool]] x3, [[Bedrock]]); no line numbers; no acknowledgment that vault pages were stubs."
