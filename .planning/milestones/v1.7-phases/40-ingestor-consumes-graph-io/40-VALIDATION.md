---
phase: 40
slug: ingestor-consumes-graph-io
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-26
---

# Phase 40 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 1.3 |
| **Config file** | `agents/graph-wiki-agent/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_ingest.py agents/graph-wiki-agent/tests/unit/test_uri_slug.py -q` |
| **Full suite command** | `uv run --package graph-wiki-agent pytest -q` |
| **Estimated runtime** | quick: ~5s · full: ~45s |

---

## Sampling Rate

- **After every task commit:** Run the quick command (scoped to ingest + uri_slug tests).
- **After every plan wave:** Run the full suite for `graph-wiki-agent`.
- **Before `/gsd:verify-work`:** Full suite must be green.
- **Max feedback latency:** 10 seconds (quick scope).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 40-01-01 | 01 | 1 | INGESTOR-01 | — | URI-derived slug-tail derivation never returns empty; raises on empty input | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_uri_slug.py -q` | ❌ W0 | ⬜ pending |
| 40-01-02 | 01 | 1 | INGESTOR-01 | — | Frontmatter rewrite places `entity_uri:` after `target_slug:`; handles null + idempotence | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_ingest.py -k entity_uri_in_body -q` | ❌ W0 | ⬜ pending |
| 40-01-03 | 01 | 2 | INGESTOR-01 | — | Path lookup: file-in-package → URI; outside-repo returns None | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_ingest.py -k lookup_entity_by_path -q` | ❌ W0 | ⬜ pending |
| 40-01-04 | 01 | 2 | INGESTOR-01 | — | Name fallback: single match returns URI; multi-match → no override + stderr warning; entity-kind filter excludes files | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_ingest.py -k lookup_entity_by_name -q` | ❌ W0 | ⬜ pending |
| 40-01-05 | 01 | 3 | INGESTOR-01 | — | End-to-end ingest with graph match: slug overridden, `entity_uri: pkg:...` written, `IngestResult.entity_uri` populated | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_ingest.py -k path_match_overrides_slug -q` | ❌ W0 | ⬜ pending |
| 40-01-06 | 01 | 3 | INGESTOR-01 | — | End-to-end ingest without graph match: LLM slug retained, `entity_uri: null` written | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_ingest.py -k no_match_writes_null -q` | ❌ W0 | ⬜ pending |
| 40-01-07 | 01 | 3 | INGESTOR-02 | — | Missing graph DB → exits with code 3 and writes the D-02 stderr message | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_ingest.py -k not_initialized_exits -q` | ❌ W0 | ⬜ pending |
| 40-01-08 | 01 | 3 | INGESTOR-01 | — | Read-only conn closed on exception during LLM call | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_ingest.py -k closes_conn_on_exception -q` | ❌ W0 | ⬜ pending |
| 40-01-09 | 01 | 3 | INGESTOR-03 | — | Code comment present at lookup site; PLAN.md contains `## v1.8 Reconciliation` section | source-assertion | `grep -q "URI-drift limitation (INGESTOR-03" agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py && grep -q "## v1.8 Reconciliation" .planning/phases/40-ingestor-consumes-graph-io/40-01-PLAN.md` | ❌ W0 | ⬜ pending |
| 40-01-10 | 01 | 4 | INGESTOR-01 | — | MCP `WikiIngestOutput` exposes `entity_uri` field; snapshot updated | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_mcp_schema_forbid_extra.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `agents/graph-wiki-agent/tests/unit/test_uri_slug.py` — stubs for `slug_from_uri` happy / empty-input / no-slash cases
- [ ] `agents/graph-wiki-agent/tests/unit/test_commands_ingest.py` — extended with new tests for path lookup, name lookup, multi-match, NOT_INITIALIZED, conn close, entity_uri frontmatter
- [ ] Fixture extension in `agents/graph-wiki-agent/tests/conftest.py` (or in-test) to seed a tiny `<workspace>/.graph/code.db` for path-match tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end via real Bedrock | INGESTOR-01 | Real LLM cost; skipped in CI | `GRAPH_WIKI_RUN_INTEGRATION=1 uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/ -k ingest -q` (deferred — not required for phase completion) |
| URI-drift behavior on package rename | INGESTOR-03 | Phase 40 explicitly does not solve drift | Documentation only — no manual verification needed |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (verified — every task has an automated command)
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
