---
phase: 55
slug: dependency-classification-fix
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-28
---

# Phase 55 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (graph-io package) |
| **Config file** | `packages/graph-io/conftest.py` (existing) |
| **Quick run command** | `uv run --package graph-io pytest packages/graph-io/tests/test_packages.py` |
| **Full suite command** | `uv run --package graph-io pytest` |
| **Estimated runtime** | ~20 seconds (full); ~5s (quick) |

---

## Sampling Rate

- **After every task commit:** Run the quick command (the test file touched by the task)
- **After every plan wave:** Run `uv run --package graph-io pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 55-01-01 | 01 | 1 | CLASS-01, CLASS-02 | — | N/A | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_packages.py` | ✅ | ⬜ pending |
| 55-01-02 | 01 | 1 | CLASS-01, CLASS-02 | — | N/A | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_packages.py` | ✅ | ⬜ pending |
| 55-02-01 | 02 | 2 | CLASS-02 | — | N/A | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py packages/graph-io/tests/test_cli_describe.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. `test_packages.py`, `test_queries.py`, and `test_cli_describe.py` already exist with the `conn` fixture, `_seed_file_node` helper, and CLI subprocess harness.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none missing)
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-28
