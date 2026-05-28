---
phase: 52
slug: wiki-filename-slimdown-core
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-05-28
---

# Phase 52 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + hypothesis 6.153.x |
| **Config file** | `packages/wiki-io/pyproject.toml` (pytest section) |
| **Quick run command** | `uv run --package wiki-io pytest packages/wiki-io/tests/test_short_filename.py packages/wiki-io/tests/test_entity_writer.py -x` |
| **Full suite command** | `uv run --package wiki-io pytest packages/wiki-io/tests/ -v` |
| **Estimated runtime** | ~15 seconds (quick), ~45 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run quick command (above) on the just-modified test file
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 52-01-01 | 01 | 1 | WIKI-FN-04 | — | N/A (pure helper, no I/O) | unit + property | `uv run --package wiki-io pytest packages/wiki-io/tests/test_short_filename.py -v` | ❌ W0 (created in plan) | ⬜ pending |
| 52-01-02 | 01 | 1 | WIKI-FN-02 | — | N/A | property | `uv run --package wiki-io pytest packages/wiki-io/tests/test_short_filename.py::test_suite_kind_dispatch -v` | ❌ W0 | ⬜ pending |
| 52-02-01 | 02 | 2 | WIKI-FN-01 | — | N/A | integration | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py::test_write_entities_short_filenames -v` | ❌ W0 | ⬜ pending |
| 52-02-02 | 02 | 2 | WIKI-FN-03 | — | N/A (deterministic suffix; D-04 symmetric semantics) | integration | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py::test_write_entities_cross_org_collision -v` | ❌ W0 | ⬜ pending |
| 52-02-03 | 02 | 2 | WIKI-FN-01 (dep alias) | — | N/A | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py::test_dep_prefix_alias -v` | ❌ W0 | ⬜ pending |
| 52-03-01 | 03 | 2 | WIKI-FN-01 (app rendering) | — | N/A | integration | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py::test_write_entities_renders_app_pages -v` | ❌ W0 | ⬜ pending |
| 52-03-02 | 03 | 2 | (template existence) | — | N/A | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py::test_entity_app_template_exists -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is empty for Phase 52 — pytest + hypothesis are already installed workspace-wide and the
`packages/wiki-io/tests/` directory already exists. The new test file
`packages/wiki-io/tests/test_short_filename.py` is created by Plan 52-01 itself (not a Wave 0
dependency).

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SC#1: real vault produces `pkg_eval-harness.md`, `app_graph-wiki-agent.md`, `dep_langchain-aws.md`, `repo_agent-research.md`, `domain_observability.md` on a fresh scan of this repo | WIKI-FN-01 | The integration tests use synthesized fixtures; running a real `cg scan` confirms behavior against the actual graph. Optional smoke check before verify-phase. | After all plans pass: `rm -rf ~/Personal/graph-wiki/agent-research/wiki/entities/* && uv run cg scan && ls ~/Personal/graph-wiki/agent-research/wiki/entities/ \| sort` — confirm short-form filenames appear. |

All phase behaviors that need to block phase verification have automated coverage. The vault
smoke check is a nice-to-have because it crosses the package boundary (`cg scan` lives in
`agents/graph-wiki-agent`); the integration tests fully cover the `write_entities` contract.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none required)
- [x] No watch-mode flags
- [x] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter (flipped when plans are finalized and reviewed)

**Approval:** pending
