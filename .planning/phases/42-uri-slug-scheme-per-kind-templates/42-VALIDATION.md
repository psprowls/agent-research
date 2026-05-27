---
phase: 42
slug: uri-slug-scheme-per-kind-templates
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-26
---

# Phase 42 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+, hypothesis 6.x (Wave 0 installs), pytest-asyncio 1.3.0 |
| **Config file** | workspace root `pyproject.toml` + `packages/wiki-io/pyproject.toml` |
| **Quick run command** | `uv run --package wiki-io pytest tests/test_entity_writer.py -x` |
| **Full suite command** | `uv run --package wiki-io pytest && uv run --package graph-io pytest` |
| **Estimated runtime** | ~5-8 seconds (Hypothesis 1000 examples runs in ~1-2s for pure string ops) |

---

## Sampling Rate

- **After every task commit:** Run quick command (the test file scoped to the task)
- **After every plan wave:** Run full suite command (both wiki-io and graph-io)
- **Before `/gsd:verify-work`:** Full suite must be green across both packages
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 42-01-01 | 01 | 1 | (infra) | T-42-01, T-42-SC | `hypothesis` install verified | checkpoint | `uv run python -c "import hypothesis; print(hypothesis.__version__)"` | ✅ after install | ⬜ pending |
| 42-01-02 | 01 | 1 | URI-05, URI-06 | — | `ADMITTED_KINDS`, `SCANNER_OWNED_KEYS` are correct frozensets disjoint from human-owned keys | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_admitted_kinds_shape tests/test_entity_writer.py::test_scanner_owned_keys_disjoint_from_human -x` | ❌ W0 | ⬜ pending |
| 42-01-03 | 01 | 1 | URI-01, URI-02 | — | `encode_slug`/`decode_slug` round-trip and batch-injective for ≥1000 URIs across 7 kinds | property | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_slug_round_trip tests/test_entity_writer.py::test_slug_batch_injective -x` | ❌ W0 | ⬜ pending |
| 42-02-01 | 02 | 1 | URI-04 (graph-io side) | — | 3 new URI builders produce correctly-shaped strings | unit | `uv run --package graph-io pytest tests/test_uri.py -x` | ❌ W0 (extend or create) | ⬜ pending |
| 42-02-02 | 02 | 1 | URI-03 | — | 7 entity templates exist, each declares `kind:` ∈ ADMITTED_KINDS, each has `## Narrative` H2 | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_entity_templates_valid -x` | ❌ W0 | ⬜ pending |
| 42-03-01 | 03 | 2 | URI-04 | — | `wiki/entities/` and `_index.md` created by `init_wiki` | unit + integration | `uv run --package wiki-io pytest tests/test_init_vault.py::test_entities_dir_bootstrapped tests/test_init_vault.py::test_entities_in_fixed_vault_dirs -x` | ❌ W0 (extend existing file) | ⬜ pending |
| 42-03-02 | 03 | 2 | (reconciliation) | — | REQUIREMENTS.md URI-03 + ROADMAP success criterion #3 text updated to match locked CONTEXT.md decisions (path: `assets/page-templates/`; marker: `## Narrative` H2) | grep | `grep -q "assets/page-templates" .planning/REQUIREMENTS.md && grep -q "Narrative" .planning/REQUIREMENTS.md` | ✅ after edit | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `hypothesis` added to workspace-root `[dependency-groups].dev` via `uv add --group dev hypothesis`
- [ ] `packages/wiki-io/tests/test_entity_writer.py` — new file covering URI-01, URI-02, URI-03, URI-05, URI-06
- [ ] `packages/graph-io/tests/test_uri.py` — extend if exists, create otherwise; covers 3 new URI builders
- [ ] `packages/wiki-io/tests/test_init_vault.py` — add 2 test cases (`test_entities_in_fixed_vault_dirs`, `test_entities_dir_bootstrapped`) for URI-04

*Existing infrastructure (pytest, pytest-asyncio, uv workspace) covers everything else.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `hypothesis` package legitimacy | T-42-01, T-42-SC | slopcheck unavailable at research time → fallback policy requires one human-verify glance at `pypi.org/project/hypothesis/` before install | Visit https://pypi.org/project/hypothesis/, confirm: (1) maintainer is `HypothesisWorks`, (2) first release ≥2013, (3) latest stable in 6.x line. Type "approved" to proceed with `uv add --group dev hypothesis`. |

*One manual checkpoint; per the fallback protocol — Hypothesis is universally legitimate, this is a formality.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
