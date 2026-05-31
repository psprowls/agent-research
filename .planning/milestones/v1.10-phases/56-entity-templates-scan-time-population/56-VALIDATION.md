---
phase: 56
slug: entity-templates-scan-time-population
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-28
---

# Phase 56 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.3 (uv workspace) |
| **Config file** | per-package `pyproject.toml` + root `conftest.py` |
| **Quick run command** | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py packages/wiki-io/tests/test_entity_templates.py -q` |
| **Full suite command** | `uv run --package wiki-io pytest packages/wiki-io/tests -q && uv run --package graph-io pytest packages/graph-io/tests/test_packages.py -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick run command for the touched package
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 56-01-* | 01 | 1 | SCAN-01, SCAN-02 | — | substitution + summary fill-when-empty are deterministic, no untrusted input | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py -q` | ✅ | ⬜ pending |
| 56-02-* | 02 | 1 | ENTITY-01, ENTITY-02 | — | migrated template content; no executable surface | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_templates.py -q` | ✅ | ⬜ pending |
| 56-03-* | 03 | 2 | ENTITY-03 | — | filesystem deletion of repo-local template dirs only | grep+unit | `uv run --package wiki-io pytest packages/wiki-io/tests -q` | ✅ | ⬜ pending |
| 56-04-* | 04 | 1 | SCAN-02 (D-06) | — | reads repo-local pyproject; no network/untrusted input | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_packages.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*(Task IDs are indicative — final IDs assigned by the planner. The map asserts every plan
carries an automated verify.)*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* The test files
(`test_entity_writer.py`, `test_entity_templates.py`, `test_overview_template_wikilinks.py`,
`test_packages.py`, `integration/test_entity_writer_integration.py`) and the pytest/uv harness
already exist. No new framework or conftest scaffolding is required.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| No dead links in generated entity pages after legacy-dir deletion | ENTITY-03 / D-16 | D-16 mandates repo grep only, NO standing dead-link regression test | During execution: `grep -rn "page-templates/\(package\|domain\|plugin\|app\)/" packages/` returns no live code path reference; spot-check a generated entity page for unresolved `[[...]]` links |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — existing infra)
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-28
