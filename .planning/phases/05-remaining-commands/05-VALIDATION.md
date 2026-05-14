---
phase: 5
slug: remaining-commands
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-14
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.3, pytest-asyncio 1.3.0, syrupy 5.1.0 |
| **Config file** | Each package has its own `pyproject.toml` with `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit -x` |
| **Full suite command** | `uv run pytest cores/vault-io/tests agents/code-wiki-agent/tests -x` |
| **Estimated runtime** | ~30 seconds (unit only), ~90 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit -x -q`
- **After every plan wave:** Run `uv run pytest cores/vault-io/tests agents/code-wiki-agent/tests/unit -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-W1-log | TBD | 1 | CMD-06 | unit | `pytest agents/code-wiki-agent/tests/unit/test_commands_log.py -x` | No — Wave 0 | ⬜ pending |
| 05-W1-init | TBD | 1 | CMD-01 | unit | `pytest agents/code-wiki-agent/tests/unit/test_commands_init.py -x` | No — Wave 0 | ⬜ pending |
| 05-W1-config | TBD | 1 | CLI-05 | unit | `pytest agents/code-wiki-agent/tests/unit/test_config.py -x` | No — Wave 0 | ⬜ pending |
| 05-W2-lint-modules | TBD | 2 | CMD-05 | unit | `pytest cores/vault-io/tests/test_lint_modules.py -x` | No — Wave 0 | ⬜ pending |
| 05-W2-placeholder | TBD | 2 | CMD-05 | unit | `pytest cores/vault-io/tests/test_wikilink_predicate.py -x` | YES | ⬜ pending |
| 05-W3-ingest-source | TBD | 3 | CMD-03 | unit | `pytest cores/vault-io/tests/test_ingest_source.py -x` | No — Wave 0 | ⬜ pending |
| 05-W3-ingest-wi | TBD | 3 | CMD-03 | unit | `pytest cores/vault-io/tests/test_ingest_work_item.py -x` | No — Wave 0 | ⬜ pending |
| 05-W4-scan | TBD | 4 | CMD-02 | unit | `pytest agents/code-wiki-agent/tests/unit/test_commands_scan.py -x` | No — Wave 0 | ⬜ pending |
| 05-W4-ingest-cmd | TBD | 4 | CMD-03 | unit | `pytest agents/code-wiki-agent/tests/unit/test_commands_ingest.py -x` | No — Wave 0 | ⬜ pending |
| 05-W5-lint-cmd | TBD | 5 | CMD-05 | unit | `pytest agents/code-wiki-agent/tests/unit/test_commands_lint.py -x` | No — Wave 0 | ⬜ pending |
| 05-W5-mcp-tools | TBD | 5 | MCP-01,MCP-03 | unit | `pytest agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py -x` | No — Wave 0 | ⬜ pending |
| 05-W6-parity-scan | TBD | 6 | CMD-02 | integration | `pytest agents/code-wiki-agent/tests/commands/test_scan_parity.py -x` | No — Wave 0 | ⬜ pending |
| 05-W6-parity-lint | TBD | 6 | CMD-05 | integration | `pytest agents/code-wiki-agent/tests/commands/test_lint_parity.py -x` | No — Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `agents/code-wiki-agent/tests/unit/test_commands_log.py` — stubs for CMD-06
- [ ] `agents/code-wiki-agent/tests/unit/test_commands_init.py` — stubs for CMD-01
- [ ] `agents/code-wiki-agent/tests/unit/test_commands_scan.py` — stubs for CMD-02
- [ ] `agents/code-wiki-agent/tests/unit/test_commands_ingest.py` — stubs for CMD-03
- [ ] `agents/code-wiki-agent/tests/unit/test_commands_lint.py` — stubs for CMD-05
- [ ] `agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py` — stubs for MCP-01, MCP-03
- [ ] `cores/vault-io/tests/test_ingest_source.py` — stubs for CMD-03 ingest_source port
- [ ] `cores/vault-io/tests/test_ingest_work_item.py` — stubs for CMD-03 ingest_work_item port
- [ ] `cores/vault-io/tests/test_lint_modules.py` — stubs for CMD-05 mechanical lint modules
- [ ] `agents/code-wiki-agent/tests/commands/test_scan_parity.py` — parity test for scan
- [ ] `agents/code-wiki-agent/tests/commands/test_lint_parity.py` — parity test for lint

*Note: `cores/vault-io/tests/test_wikilink_predicate.py` (placeholder filter) already exists from Phase 1.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `wiki_scan` progress notifications reach MCP host | MCP-03 | Requires real DeepAgents CLI MCP session | Run `code-wiki-mcp` via DeepAgents CLI, invoke `wiki_scan`, observe progress events |
| Scanner stub quality on real vault | CMD-02 | LLM output quality is subjective | Run `code-wiki-agent scan` on a real lattice-wiki vault; manually inspect 3 generated stubs |
| MCP stdio session survives lint error | MCP-01 | Requires subprocess crash test | Invoke `wiki_lint` with intentionally broken vault; confirm server stays alive |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
