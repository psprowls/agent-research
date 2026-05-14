---
phase: 3
slug: query-vertical-slice-hybrid-search
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ + pytest-asyncio 1.3.0 |
| **Config file** | `agents/code-wiki-agent/pyproject.toml` (Wave 0 adds `asyncio_mode = "auto"`) |
| **Quick run command** | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/ -x -q -m "not integration"` |
| **Full suite command** | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/ -v -m "not integration"` |
| **Integration test** | `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/ -m integration -v` |
| **Estimated runtime** | ~3s (unit); ~30s (integration, requires Bedrock) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/ -x -q -m "not integration"`
- **After every plan wave:** Run full suite (unit + vault-io integration where applicable)
- **Before `/gsd-verify-work`:** Full suite must be green; integration test must pass on real Bedrock
- **Max feedback latency:** ~3 seconds (unit suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| 03-xx-01 | 01 | 0 | INFRA | asyncio_mode=auto in pyproject.toml; bm25s dep added | unit | `uv run --package code-wiki-agent python -c "import bm25s"` | ⬜ pending |
| 03-xx-02 | search | 1 | SEARCH-01 | BM25 index builds from vault pages; tokenizer replicates TOKEN_RE | unit | `pytest -k test_bm25_index -m "not integration"` | ⬜ pending |
| 03-xx-03 | search | 1 | SEARCH-04,05 | SQLite search.db created; incremental rebuild skips unchanged pages | unit | `pytest -k test_embedding_index -m "not integration"` | ⬜ pending |
| 03-xx-04 | search | 1 | SEARCH-03,06 | RRF fuse returns ranked dict with bm25/embed/rrf keys | unit | `pytest -k test_rrf_fuse -m "not integration"` | ⬜ pending |
| 03-xx-05 | query | 2 | CMD-04 | run_query() returns QueryResult with answer, citations, pages_drilled, search_scores | unit (mock LLM) | `pytest -k test_run_query_unit -m "not integration"` | ⬜ pending |
| 03-xx-06 | query | 2 | CLI-01,02,04 | query subcommand exists; --json emits valid QueryResult JSON | unit | `pytest -k test_cli_query -m "not integration"` | ⬜ pending |
| 03-xx-07 | query | 2 | CMD-08 | --no-state-gate flag present; gate always passes (read-only) | unit | `pytest -k test_state_gate -m "not integration"` | ⬜ pending |
| 03-xx-08 | mcp | 3 | MCP-02,04,07 | wiki_query tool registered; Pydantic input/output schema valid; errors return structured MCP response | unit | `pytest -k test_wiki_query_tool -m "not integration"` | ⬜ pending |
| 03-xx-09 | e2e | 4 | CMD-04 (success criterion 5) | headless CLI query against fixture vault returns answer with >=1 [[wikilink]] citation | integration | `CODE_WIKI_RUN_INTEGRATION=1 pytest -k test_query_e2e -m integration` | ⬜ pending |
| 03-xx-10 | e2e | 4 | SEARCH-06 | --json output contains search_scores with bm25/embed/rrf keys per page | integration | `CODE_WIKI_RUN_INTEGRATION=1 pytest -k test_query_json_scores -m integration` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `agents/code-wiki-agent/pyproject.toml` — add `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`
- [ ] `uv add --package code-wiki-agent bm25s==0.3.8` — new dependency
- [ ] `agents/code-wiki-agent/src/code_wiki_agent/commands/__init__.py` — new subpackage stub
- [ ] `agents/code-wiki-agent/tests/commands/test_search.py` — stubs for SEARCH-01..06 (bm25 index, embedding index, RRF)
- [ ] `agents/code-wiki-agent/tests/commands/test_query.py` — stubs for CMD-04, CLI-01..07
- [ ] `agents/code-wiki-agent/tests/mcp/test_wiki_query.py` — stubs for MCP-02, MCP-04
- [ ] `agents/code-wiki-agent/tests/conftest.py` — `@pytest.fixture` for `fixture_vault_path` pointing to `cores/vault-io/tests/fixtures/round-trip-vault/`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Answer quality vs lattice-wiki baseline | CMD-04 success criterion 1 | Requires human judgment to compare answer depth, citation structure, and accuracy against existing lattice-wiki output | Run `code-wiki-agent query "What does the middleware pipeline do?"` against real vault; compare to current lattice-wiki output manually |
| MCP tool invokable from DeepAgents CLI | MCP-02, MCP-07 | Requires DeepAgents CLI running against live MCP subprocess | Launch `uv run code-wiki-mcp` as stdio subprocess; invoke `wiki_query` through DeepAgents CLI and confirm structured result received |
| MCP progress notifications emitted | MCP-06 | Depends on client sending progressToken; hard to assert in unit test | Use MCP Inspector or a test client that sends progressToken; confirm progress events arrive during fan-out |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s (unit suite)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
