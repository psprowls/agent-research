---
phase: 54
slug: debt-clearance
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-28
---

# Phase 54 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.3 (uv workspace) |
| **Config file** | root `pyproject.toml` (`[tool.pytest.ini_options]`) — already present |
| **Quick run command** | `uv run pytest tests/test_integration_gate.py` |
| **Full suite command** | `uv run pytest tests/test_integration_gate.py && grep -n "deepagents\|lattice-wiki" .planning/PROJECT.md` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run that task's `<automated>` verify command
- **After every plan wave:** Run the gate test + the scoped PROJECT.md grep
- **Before `/gsd:verify-work`:** Gate test green AND no stale strings in the three corrected sections
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 54-01-01 | 01 | 1 | DEBT-01 | — | N/A (comment-only annotation) | gate | `uv run pytest tests/test_integration_gate.py` | ✅ | ⬜ pending |
| 54-01-02 | 01 | 1 | DEBT-01 | — | N/A (collection unaffected by comments) | unit | `uv run pytest --collect-only agents/graph-wiki-agent/tests/integration packages/graph-io/tests/integration packages/wiki-io/tests/integration` | ✅ | ⬜ pending |
| 54-01-03 | 01 | 1 | DEBT-02 | — | N/A (planning-doc edit) | grep | `grep -c "deepagents\|lattice-wiki" .planning/PROJECT.md` (scoped check in task) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. pytest and the gate test already exist; the 7 target test files and PROJECT.md already exist. No new test infrastructure, fixtures, or framework install needed.

---

## Manual-Only Verifications

All phase behaviors have automated verification. The "preserve historical/host-product references" constraint (D-06/D-07) is verified by the scoped grep distinguishing the three corrected sections from the rest of the file.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — existing infra)
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-28
