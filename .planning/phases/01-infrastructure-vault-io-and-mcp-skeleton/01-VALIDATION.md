---
phase: 1
slug: infrastructure-vault-io-and-mcp-skeleton
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥ 8.3 |
| **Config file** | Per-member `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run --package <member> pytest -x -q` |
| **Full suite command** | `uv run pytest` |
| **Integration command** | `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest -m integration` |
| **Estimated runtime** | ~30 seconds unit; ~60 seconds with integration |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package <member> pytest -x -q`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd-verify-work`:** Full suite + integration suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Populated by gsd-planner from RESEARCH.md "Phase Requirements → Test Map". Each PLAN.md task must map to a row here. See RESEARCH.md §Validation Architecture for the authoritative mapping.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 0 | INFRA-01 | — | N/A | smoke | `uv sync && uv run --package vault-io pytest --collect-only` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | INFRA-02 | — | N/A | smoke | `uv sync && ls uv.lock` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | INFRA-03 | — | N/A | smoke | `uv run --package vault-io pytest --collect-only 2>&1 \| grep -v code_wiki` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | INFRA-06 | — | N/A | unit | `uv run --package code-wiki-agent pytest tests/unit/test_cli_help.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | BED-01 | T-1-01 | IAM error includes exact ARN | integration | `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest tests/integration/test_bedrock_iam.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | VAULT-04 | — | N/A | unit | `uv run --package vault-io pytest tests/test_round_trip.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | VAULT-05 | — | Truncated frontmatter skipped, not crashed | unit | `uv run --package vault-io pytest tests/test_truncated_frontmatter.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | VAULT-06 | — | N/A | unit | `uv run --package vault-io pytest tests/test_wikilink_predicate.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | MCP-05 / MCP-08 | T-1-02 | stdout contains only JSON-RPC | integration | `uv run --package code-wiki-agent pytest tests/integration/test_mcp_stdio.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `cores/vault-io/tests/conftest.py` — shared `tmp_path`-based fixtures
- [ ] `cores/vault-io/tests/fixtures/round-trip-vault/` — copy of real vault (~148 pages from `/Users/pat/Personal/lattice/lattice/wiki/`)
- [ ] `cores/vault-io/tests/test_round_trip.py` — VAULT-04 gate
- [ ] `cores/vault-io/tests/test_truncated_frontmatter.py` — VAULT-05
- [ ] `cores/vault-io/tests/test_wikilink_predicate.py` — VAULT-06
- [ ] `cores/model-adapter/tests/test_loader.py` — unit tests with mocked Bedrock
- [ ] `agents/code-wiki-agent/tests/unit/test_cli_help.py` — INFRA-06
- [ ] `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py` — BED-01
- [ ] `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` — MCP-05 / MCP-08
- [ ] `pytest-asyncio==1.3.0`, `syrupy==5.1.0` added to workspace dev group via `uv add --group dev`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Bedrock invocation against Pat's AWS account | BED-01 | Requires live AWS credentials; gated behind `CODE_WIKI_RUN_INTEGRATION=1` env var so CI/cold-clone runs skip it | Set `AWS_PROFILE` (or default creds), then `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest tests/integration/test_bedrock_iam.py` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
