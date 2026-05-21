---
phase: 25
slug: packages-dir-misclassification-fix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-21
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.3 (asyncio not required for these tests) |
| **Config file** | `packages/vault-io/pyproject.toml` (workspace member) |
| **Quick run command** | `uv run --package vault-io pytest tests/test_detect_containers.py -x` |
| **Full suite command** | `uv run --package vault-io pytest` |
| **Phase gate command** | `uv run pytest` (full workspace) |
| **Estimated runtime** | ~1 second (quick), ~15 seconds (full workspace) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package vault-io pytest tests/test_detect_containers.py -x`
- **After every plan wave:** N/A — single PLAN, single wave
- **Before `/gsd:verify-work`:** `uv run pytest` (full workspace) must be green
- **Max feedback latency:** ~1 second per task

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 25-01-01 | 01 | 1 | PKGCLS-01 | — | N/A | unit | `uv run --package vault-io pytest tests/test_detect_containers.py::test_mixed_manifest_dirs_classify_as_package -x` | ❌ W0 | ⬜ pending |
| 25-01-02 | 01 | 1 | PKGCLS-01 | — | N/A | unit | `uv run --package vault-io pytest tests/test_detect_containers.py::test_loose_md_file_at_container_root_does_not_block_package -x` | ❌ W0 | ⬜ pending |
| 25-01-03 | 01 | 1 | PKGCLS-01 | — | N/A | unit | `uv run --package vault-io pytest tests/test_detect_containers.py::test_empty_dir_falls_back_to_ambiguous -x` | ❌ W0 | ⬜ pending |
| 25-01-04 | 01 | 1 | PKGCLS-01 | — | N/A | unit | `uv run --package vault-io pytest tests/test_detect_containers.py -x` | ✅ existing | ⬜ pending |
| 25-01-05 | 01 | 1 | PKGCLS-02 | — | N/A | smoke | `python -c "from vault_io.detect_containers import main"` | ✅ existing | ⬜ pending |
| 25-01-06 | 01 | 1 | PKGCLS-03 | — | N/A | source | `grep -q "≥1 manifested child" plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md` | ❌ W0 | ⬜ pending |
| 25-01-07 | 01 | 1 | PKGCLS-05 | — | N/A | filesystem | `test -f .planning/todos/resolved/2026-05-20-fix-packages-dir-misclassification.md && ! test -f .planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md` | ✅ existing path | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/vault-io/tests/test_detect_containers.py` — 3 new unit tests (`test_mixed_manifest_dirs_classify_as_package`, `test_loose_md_file_at_container_root_does_not_block_package`, `test_empty_dir_falls_back_to_ambiguous`); existing `conftest.py` already provides `tmp_repo`/`write_file` helpers — no new fixtures needed.
- [ ] `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md` — updated rule text describing the ≥1-manifest permissive heuristic.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `graph-wiki-agent bootstrap` on this repo classifies `packages/` as `package` and emits `wiki/packages/` | PKGCLS-04 | End-to-end CLI invocation against the current repo; not gated in CI for this phase | Run `python -m vault_io.detect_containers --json` from repo root; assert output contains `"packages"` → `"classification": "package"` and `"children_count": 5`. Then run `uv run graph-wiki-agent bootstrap` and confirm `wiki/packages/` is created without manual intervention. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
