---
phase: 11
slug: workspace-io-port-m1
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-17
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (workspace root) |
| **Config file** | `pyproject.toml` (workspace), per-package `pyproject.toml` |
| **Quick run command** | `uv run --package workspace-io pytest -x` |
| **Full suite command** | `uv run --package workspace-io pytest && uv run --package wiki-io pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package workspace-io pytest -x`
- **After every plan wave:** Run the full suite (workspace-io + wiki-io)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Populated by the planner. Every task in every PLAN.md must have an automated verify command pointing at one of the entries below OR list a Wave 0 dependency.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | WS-01 | — | uv sync resolves workspace-io member | smoke | `uv sync && uv run --package workspace-io python -c 'import workspace_io'` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `packages/workspace-io/pyproject.toml` — uv workspace member scaffold
- [ ] `packages/workspace-io/src/workspace_io/__init__.py` — package init
- [ ] `packages/workspace-io/tests/conftest.py` — shared fixtures (tmp `.graph-wiki.yaml` workspace)
- [ ] Workspace root `pyproject.toml` updated with new member entry

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PROJECT.md Key Decisions records `.graph-wiki.yaml` vs `wiki-config.toml` answer | WS-10 | Documentation, not code | Open `PROJECT.md`, grep for `wiki-config.toml`; ensure a Key Decision entry exists naming the two surfaces as distinct (or describes the migration script if reversed). |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
