---
phase: 1
slug: infrastructure-vault-io-and-mcp-skeleton
status: approved
nyquist_compliant: true
wave_0_complete: true
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

> Each row maps a PLAN task to its requirement, threat ref, and automated command. Task IDs use the `{plan}/T{n}` shorthand (1-indexed within each plan).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01/T1 | 01-01 | 1 | INFRA-01, INFRA-02, INFRA-04, INFRA-05 | T-1-03 | No credentials in `models.toml`; `.gitignore` covers `.env*` | smoke | `uv sync && test -f uv.lock` | ❌ W0 | ⬜ pending |
| 01-01/T2 | 01-01 | 1 | INFRA-03, INFRA-06 | — | N/A | unit | `uv run --package code-wiki-agent pytest -x -q` | ❌ W0 | ⬜ pending |
| 01-01/T3 | 01-01 | 1 | (docs) | — | N/A | smoke | `grep -q "deep-agents" CLAUDE.md && grep -q "code-wiki-agent" .planning/REQUIREMENTS.md` | ✅ | ⬜ pending |
| 01-02/T1 | 01-02 | 2 | BED-01 | T-1-01 | IAM error includes exact ARN | unit (TDD red) | `uv run --package model-adapter pytest tests/test_loader.py -x -q` | ❌ W0 | ⬜ pending |
| 01-02/T2 | 01-02 | 2 | BED-01 | T-1-01 | IAM error includes exact ARN | integration | `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest tests/integration/test_bedrock_iam.py -x -q` | ❌ W0 | ⬜ pending |
| 01-03/T1 | 01-03 | 2 | VAULT-04, VAULT-05, VAULT-06 | T-1-06, T-1-07 | Truncated frontmatter skipped not crashed; vault round-trip preserved byte-exact | unit (Wave-0 red) | `uv run --package vault-io pytest --collect-only` | ❌ W0 | ⬜ pending |
| 01-03/T2 | 01-03 | 2 | VAULT-01, VAULT-02, VAULT-03, VAULT-04, VAULT-05, VAULT-06 | T-1-06, T-1-07 | Round-trip preserves byte-exact output; truncated frontmatter skipped | unit | `uv run --package vault-io pytest -x -q` | ❌ W0 | ⬜ pending |
| 01-03/T3 | 01-03 | 2 | VAULT-07 | — | N/A | unit | `uv run --package vault-io pytest tests/test_imports.py -x -q` | ❌ W0 | ⬜ pending |
| 01-04/T1 | 01-04 | 3 | MCP-05, MCP-08 | T-1-02 | stdout contains only JSON-RPC; stray print() raises | unit (TDD red) | `uv run --package code-wiki-agent pytest tests/integration/test_mcp_stdio.py --collect-only` | ❌ W0 | ⬜ pending |
| 01-04/T2 | 01-04 | 3 | MCP-05, MCP-08 | T-1-02 | stdout contains only JSON-RPC | integration | `uv run --package code-wiki-agent pytest tests/integration/test_mcp_stdio.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

These test infrastructure files are written RED in Task 1 of each plan and turn GREEN as the corresponding Task 2 implementations land:

- [x] `cores/vault-io/tests/conftest.py` — shared `tmp_path`-based fixtures (01-03/T1)
- [x] `cores/vault-io/tests/fixtures/round-trip-vault/` — copy of real vault (~148 pages from `/Users/pat/Personal/lattice/lattice/wiki/`) (01-03/T1)
- [x] `cores/vault-io/tests/test_round_trip.py` — VAULT-04 gate (01-03/T1)
- [x] `cores/vault-io/tests/test_truncated_frontmatter.py` — VAULT-05 (01-03/T1)
- [x] `cores/vault-io/tests/test_wikilink_predicate.py` — VAULT-06 (01-03/T1)
- [x] `cores/vault-io/tests/test_imports.py` — VAULT-07 (01-03/T3)
- [x] `cores/model-adapter/tests/test_loader.py` — unit tests with mocked Bedrock (01-02/T1)
- [x] `agents/code-wiki-agent/tests/unit/test_cli_help.py` — INFRA-06 (01-01/T2)
- [x] `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py` — BED-01 (01-02/T2)
- [x] `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` — MCP-05 / MCP-08 (01-04/T1)
- [x] `pytest-asyncio==1.3.0`, `syrupy==5.1.0` in workspace dev group (01-01/T1)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Bedrock invocation against Pat's AWS account | BED-01 | Requires live AWS credentials; gated behind `CODE_WIKI_RUN_INTEGRATION=1` env var so CI/cold-clone runs skip it | Set `AWS_PROFILE` (or default creds), then `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest tests/integration/test_bedrock_iam.py` |
| Standalone Bedrock IAM diagnostic | BED-01 | Off-CI exploratory tool for IAM debugging | `uv run python scripts/verify_bedrock_iam.py` — prints the exact ARN missing if access denied |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task in every plan has `<automated>`)
- [x] Wave 0 covers all MISSING references (all 10 test files listed above are created by Task 1 of their owning plan)
- [x] No watch-mode flags (`-x -q` only; no `--watch`)
- [x] Feedback latency < 60s (per-task pytest runs are sub-30s; integration adds 30s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-13
