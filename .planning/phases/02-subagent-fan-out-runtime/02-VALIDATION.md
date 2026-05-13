---
phase: 2
slug: subagent-fan-out-runtime
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` (workspace root `[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run --package subagent-runtime pytest cores/subagent-runtime/tests/ -x -q` |
| **Full suite command** | `uv run pytest cores/subagent-runtime/tests/ agents/code-wiki-agent/tests/ -v` |
| **Estimated runtime** | ~30 seconds (unit), ~120 seconds (integration with real Bedrock) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package subagent-runtime pytest cores/subagent-runtime/tests/ -x -q`
- **After every plan wave:** Run `uv run pytest cores/subagent-runtime/tests/ agents/code-wiki-agent/tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | SUB-01 | — | N/A | unit | `uv run --package subagent-runtime pytest tests/test_pool.py -x -q` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | SUB-02 | — | N/A | unit | `uv run --package subagent-runtime pytest tests/test_pool.py::test_partial_failure -x -q` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | SUB-03 | — | N/A | unit | `uv run --package subagent-runtime pytest tests/test_pool.py::test_semaphore -x -q` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | BED-02 | — | N/A | unit | `uv run --package subagent-runtime pytest tests/test_registry.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | BED-03 | — | N/A | unit | `uv run --package subagent-runtime pytest tests/test_registry.py::test_role_resolution -x -q` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | OBS-01 | — | N/A | unit | `uv run --package subagent-runtime pytest tests/test_trace.py -x -q` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | OBS-02 | — | N/A | unit | `uv run --package subagent-runtime pytest tests/test_trace.py::test_jsonl_schema -x -q` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 3 | SUB-04 | — | N/A | integration | `uv run pytest tests/integration/test_pool_integration.py -x -q -m integration` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 3 | SUB-05 | — | N/A | integration | `uv run pytest tests/integration/test_recursion.py -x -q -m integration` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `cores/subagent-runtime/tests/__init__.py` — package marker
- [ ] `cores/subagent-runtime/tests/test_pool.py` — unit test stubs for SUB-01, SUB-02, SUB-03
- [ ] `cores/subagent-runtime/tests/test_registry.py` — unit test stubs for BED-02, BED-03
- [ ] `cores/subagent-runtime/tests/test_trace.py` — unit test stubs for OBS-01, OBS-02
- [ ] `cores/subagent-runtime/tests/conftest.py` — shared fixtures (fake Bedrock responses, mock asyncio)
- [ ] `cores/subagent-runtime/tests/integration/test_pool_integration.py` — integration stubs for SUB-04, SUB-05 (marked with `@pytest.mark.integration`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `code-wiki-agent trace <file>` renders JSONL as human-readable timeline | OBS-03 | CLI output formatting is visual | Run `uv run code-wiki-agent trace .code-wiki/traces/test.jsonl` and inspect output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
