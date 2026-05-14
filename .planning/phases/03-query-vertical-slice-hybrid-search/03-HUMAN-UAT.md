---
status: partial
phase: 03-query-vertical-slice-hybrid-search
source: [03-VERIFICATION.md]
started: 2026-05-14T04:38:39Z
updated: 2026-05-14T04:38:39Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. End-to-End Bedrock Query (ROADMAP SC-1 + SC-5, SEARCH-06)
expected: Exit 0 or 3; JSON output contains `pages_drilled >= 1`, at least one `[[wikilink]]` citation in `answer`, and `search_scores` dict with `bm25`/`embed`/`rrf` keys per page.
result: [pending]

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
result: [pending]

**Run:** Invoke the query command against a real lattice-wiki vault and compare to existing `lattice-wiki` plugin output.

### 3. MCP tools/list Subprocess Test (MCP-07)
expected: `wiki_query` appears in `tools/list` with "hybrid" or "BM25" in its description.
result: [pending]

**Run:**
```bash
CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/integration/test_mcp_stdio.py::test_wiki_query_in_tools_list -m integration -v
```

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
