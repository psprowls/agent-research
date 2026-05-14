---
phase: 03-query-vertical-slice-hybrid-search
plan: "01"
subsystem: code-wiki-agent
tags: [scaffold, wave-0, infra, bm25s, asyncio, test-stubs]
dependency_graph:
  requires: []
  provides:
    - bm25s==0.3.8 installed and importable in code-wiki-agent context
    - subagent-runtime workspace dep wired into code-wiki-agent
    - asyncio_mode=auto active for code-wiki-agent pytest
    - code_wiki_agent.commands subpackage
    - Phase 3 test stubs (20 xfail tests across 5 files)
    - fixture_vault_path pytest fixture
  affects:
    - agents/code-wiki-agent/pyproject.toml
    - uv.lock
tech_stack:
  added:
    - bm25s==0.3.8 (hybrid search BM25 engine)
    - subagent-runtime workspace dep (SubagentPool fan-out for query command)
  patterns:
    - asyncio_mode = "auto" for pytest-asyncio (mirrors subagent-runtime pattern)
    - xfail stubs with strict=False for Wave-0 test discovery
    - FIXTURE_VAULT module-level constant for cross-package vault path
    - INTEGRATION_GATE mark for real-Bedrock test gating
key_files:
  created:
    - agents/code-wiki-agent/src/code_wiki_agent/commands/__init__.py
    - agents/code-wiki-agent/tests/commands/__init__.py
    - agents/code-wiki-agent/tests/conftest.py
    - agents/code-wiki-agent/tests/unit/test_query_search.py
    - agents/code-wiki-agent/tests/unit/test_query_result.py
    - agents/code-wiki-agent/tests/unit/test_cli_query.py
    - agents/code-wiki-agent/tests/unit/test_mcp_query_schema.py
    - agents/code-wiki-agent/tests/integration/test_query_e2e.py
  modified:
    - agents/code-wiki-agent/pyproject.toml
    - uv.lock
decisions:
  - "bm25s pinned exactly at ==0.3.8 per D-04 / SEARCH-01 (not a range) to ensure reproducible indexing behavior"
  - "asyncio_mode=auto added to code-wiki-agent pytest config mirroring subagent-runtime; required for Phase 3 async query tests"
  - "fixture_vault_path uses pytest.skip (not assert) when vault missing so CI reports a skip, not a failure"
metrics:
  duration: "~3 minutes"
  completed: "2026-05-14"
  tasks_completed: 3
  tasks_total: 3
  files_created: 8
  files_modified: 2
---

# Phase 03 Plan 01: Wave 0 Scaffolding — bm25s, commands package, test stubs

Wave 0 scaffold: bm25s==0.3.8 + subagent-runtime installed, asyncio_mode=auto enabled, commands/ subpackage declared, 20 xfail Phase 3 test stubs in place.

## Tasks Completed

| Task | Description | Commit | Key Files |
|------|-------------|--------|-----------|
| 1 | Add bm25s, subagent-runtime, asyncio_mode=auto to pyproject.toml | bbc6855 | pyproject.toml, uv.lock |
| 2 | Create commands/ subpackage + conftest fixture_vault_path | b8c7950 | commands/__init__.py, tests/commands/__init__.py, tests/conftest.py |
| 3 | Create 5 Phase 3 test stub files (20 xfail stubs) | 00e5bab | test_query_search.py, test_query_result.py, test_cli_query.py, test_mcp_query_schema.py, test_query_e2e.py |

## Verification Results

```
uv sync  →  clean (83 packages resolved)
import bm25s; from subagent_runtime.pool import SubagentPool; from code_wiki_agent.commands import __name__  →  ok
pytest -m "not integration" -q  →  14 passed, 3 deselected, 18 xfailed  (exit 0)
pytest --collect-only  →  35 tests collected (20 new Phase 3 stubs)
```

## Deviations from Plan

None — plan executed exactly as written.

## Threat Mitigations Applied

| Threat | Mitigation |
|--------|------------|
| T-03-02 (cross-package path tampering) | fixture_vault_path anchors path to `Path(__file__)` with no user input; `pytest.skip` fires immediately if path missing |

## Known Stubs

All 20 Phase 3 test stubs are intentional xfail stubs. They are not implementation gaps — they are the deliverable of this plan. Each stub will be replaced by a real assertion in the plan listed in its `xfail(reason=...)`.

| Stub File | Count | Unblocked by |
|-----------|-------|--------------|
| test_query_search.py | 5 | Plan 02 |
| test_query_result.py | 4 | Plan 03 |
| test_cli_query.py | 6 | Plan 03 |
| test_mcp_query_schema.py | 3 | Plan 04 |
| test_query_e2e.py | 2 | Plan 04 |

## Self-Check: PASSED

All 8 created files found on disk. All 3 task commits verified in git log.
- bbc6855: chore(03-01): add bm25s==0.3.8, subagent-runtime workspace dep, asyncio_mode=auto
- b8c7950: feat(03-01): create commands subpackage and fixture_vault_path conftest fixture
- 00e5bab: feat(03-01): add Phase 3 xfail test stubs for all 20 search/query requirements
