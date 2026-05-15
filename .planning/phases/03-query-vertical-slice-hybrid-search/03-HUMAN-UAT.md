---
status: complete
phase: 03-query-vertical-slice-hybrid-search
source: [03-VERIFICATION.md]
started: 2026-05-14T04:38:39Z
updated: 2026-05-14T21:30:00Z
---

## Current Test

[testing complete]

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

## Summary

total: 3
passed: 2
issues: 1
pending: 0
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
  side_by_side_query: "How does the SubagentPool fan out work to Bedrock and where are the results aggregated?"
  vault: "~/Personal/wiki/deep-agents/"
  baseline_output: "Cited pool.py:115/:121-146/:149/:156-158/:162-210, loader.py:82-107; named real symbols (run_all, _run_one, _GuardedChatBedrockConverse, FanOutResult, PerItemError, BedrockAccessDenied); reproduced models.toml role table; used real wikilink targets [[wiki/cores/subagent-runtime/subagent-runtime]]; explicitly noted vault stubs and code-derived answer."
  actual_output: "Generic prose; fabricated 'src/agents/subagent_pool/aggregator.py' and 'combine_results()'; 4 unresolved citation warnings ([[SubagentPool]] x3, [[Bedrock]]); no line numbers; no acknowledgment that vault pages were stubs."
