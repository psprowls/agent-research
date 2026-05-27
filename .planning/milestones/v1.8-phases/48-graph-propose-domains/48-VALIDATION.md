---
phase: 48
slug: graph-propose-domains
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-27
---

# Phase 48 — Validation Strategy

> Per-phase validation contract for `graph propose-domains`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `agents/graph-wiki-agent/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run --package graph-wiki-agent pytest tests/test_propose_domains.py -x` |
| **Full suite command** | `uv run --package graph-wiki-agent pytest tests/test_propose_domains.py tests/integration/test_propose_domains_isolation.py tests/integration/test_propose_domains_e2e.py -x` |
| **Estimated runtime** | ~10 seconds (LLM stubbed) |

---

## Sampling Rate

- **After every task commit:** Run quick command.
- **After every plan wave:** Run full suite command.
- **Before `/gsd:verify-work`:** Full suite green.
- **Max feedback latency:** ~10 seconds (no live Bedrock in CI; live-LLM behind `GRAPH_WIKI_LIVE_BEDROCK=1` env flag).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 48-01-01 | 01 | 1 | PROPOSE-06 | T-48-SC | `domain-proposer` role loads with valid model_id | unit | `uv run --package model-adapter pytest tests/test_loader.py::test_domain_proposer_role -x` | ❌ W0 | ⬜ pending |
| 48-02-01 | 02 | 2 | PROPOSE-01, PROPOSE-02, PROPOSE-03, PROPOSE-04 | T-48-01 | Tool-use parsing rejects non-tool responses | unit | `uv run --package graph-wiki-agent pytest tests/test_propose_domains.py::test_tool_call_parsing -x` | ❌ W0 | ⬜ pending |
| 48-02-02 | 02 | 2 | PROPOSE-02 | T-48-01 | Unknown packages stripped + warning logged | unit | `uv run --package graph-wiki-agent pytest tests/test_propose_domains.py::test_grounding_strips_unknown -x` | ❌ W0 | ⬜ pending |
| 48-02-03 | 02 | 2 | PROPOSE-03 | T-48-01 | Cycle-introducing edges stripped deterministically | unit | `uv run --package graph-wiki-agent pytest tests/test_propose_domains.py::test_cycle_strip_deterministic -x` | ❌ W0 | ⬜ pending |
| 48-02-04 | 02 | 2 | PROPOSE-04 | — | Output YAML uses `proposed_domains:` key + metadata block | unit | `uv run --package graph-wiki-agent pytest tests/test_propose_domains.py::test_yaml_schema -x` | ❌ W0 | ⬜ pending |
| 48-03-01 | 03 | 3 | PROPOSE-01, PROPOSE-04, PROPOSE-06 | T-48-01 | End-to-end with stubbed LLM writes valid `domains.proposed.yaml` and trace records | integration | `uv run --package graph-wiki-agent pytest tests/integration/test_propose_domains_e2e.py -x` | ❌ W0 | ⬜ pending |
| 48-03-02 | 03 | 3 | PROPOSE-05 | T-48-02 | `domains.proposed.yaml` produces zero graph edges after `cg update` | integration | `uv run --package graph-wiki-agent pytest tests/integration/test_propose_domains_isolation.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `agents/graph-wiki-agent/tests/test_propose_domains.py` — created by Plan 02 (Task 02-01)
- [x] `agents/graph-wiki-agent/tests/integration/test_propose_domains_isolation.py` — created by Plan 03 (Task 03-02)
- [x] `agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py` — created by Plan 03 (Task 03-01)
- [x] `packages/model-adapter/tests/test_loader.py::test_domain_proposer_role` — created by Plan 01 (Task 01-01)
- pytest + pytest-asyncio already installed via workspace dev-deps; no framework install needed.

*Tests are created in the same plans that implement the code they verify — single-task TDD pattern (test + impl in one task per the planner anti-shallow rules).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Bedrock end-to-end | PROPOSE-01 | Costs real money; not gated in CI | `GRAPH_WIKI_LIVE_BEDROCK=1 uv run --package graph-wiki-agent pytest tests/integration/test_propose_domains_e2e.py::test_live_bedrock -x` (gated by env flag, ~$0.05/run) |
| Human review of `domains.proposed.yaml` contents | PROPOSE-04 | Quality of LLM proposals is subjective | Run command against agent-research itself; open `domains.proposed.yaml`; sanity-check naming + grouping |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (tests are created in the same plans that need them; no separate Wave 0 plan needed)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-27
