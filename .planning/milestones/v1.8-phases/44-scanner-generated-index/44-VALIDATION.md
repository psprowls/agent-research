---
phase: 44
slug: scanner-generated-index
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-26
---

# Phase 44 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.3 + syrupy >=4.7 + optional hypothesis >=6.116 (already deps from Phase 42) |
| **Config file** | `pyproject.toml` (root) + `packages/wiki-io/pyproject.toml` |
| **Quick run command (wiki-io)** | `uv run --package wiki-io pytest tests/test_index_generator.py -x` |
| **Quick run command (graph-io regressions)** | `uv run --package graph-io pytest -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | wiki-io ~12s (index_generator tests + existing), graph-io unchanged, full ~60s |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package wiki-io pytest tests/test_index_generator.py -x`
- **After every plan wave:** Run `uv run pytest` (full suite — catches accidental regressions in `update_index.py` callers)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds (per-package) / 60 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 44-01-01 | 01 | 1 | INDEX-01 | — | N/A | unit | `uv run --package wiki-io pytest tests/test_index_generator.py::TestIndexWriteResult -x` | ❌ W0 | ⬜ pending |
| 44-01-02 | 01 | 1 | INDEX-01 | — | N/A | unit | `uv run --package wiki-io pytest tests/test_index_generator.py::TestQualifyingDomains -x` | ❌ W0 | ⬜ pending |
| 44-01-03 | 01 | 1 | INDEX-02 (D-04 single placement) | — | Multi-domain entity routes to By Kind | unit | `uv run --package wiki-io pytest tests/test_index_generator.py::TestPlacement -x` | ❌ W0 | ⬜ pending |
| 44-01-04 | 01 | 1 | INDEX-01, INDEX-02 | — | N/A | unit | `uv run --package wiki-io pytest tests/test_index_generator.py::TestRenderDomainTree -x` | ❌ W0 | ⬜ pending |
| 44-01-05 | 01 | 1 | INDEX-01 (D-09 by-kind order) | — | Hard-coded order (NOT frozenset iteration) | unit | `uv run --package wiki-io pytest tests/test_index_generator.py::TestRenderByKind -x` | ❌ W0 | ⬜ pending |
| 44-01-06 | 01 | 1 | INDEX-05 (curated lanes) | T-44-01-T3 | Frontmatter parse rejects malicious YAML tags via safe_load semantics | unit | `uv run --package wiki-io pytest tests/test_index_generator.py::TestCuratedScan -x` | ❌ W0 | ⬜ pending |
| 44-01-07 | 01 | 1 | INDEX-05 (work lane) | — | N/A | unit | `uv run --package wiki-io pytest tests/test_index_generator.py::TestWorkScan -x` | ❌ W0 | ⬜ pending |
| 44-01-08 | 01 | 1 | INDEX-01 | — | N/A | integration | `uv run --package wiki-io pytest tests/test_index_generator.py::test_generate_index_against_fixture_graph -x` | ❌ W0 | ⬜ pending |
| 44-02-01 | 02 | 1 | INDEX-04 | — | Determinism — byte-identical across permuted insertion order | integration | `uv run --package wiki-io pytest tests/test_index_generator.py::test_determinism_across_permutations -x` | ❌ W0 | ⬜ pending |
| 44-02-02 | 02 | 1 | INDEX-04 | — | Write-if-changed — second call no-op, mtime unchanged | integration | `uv run --package wiki-io pytest tests/test_index_generator.py::test_write_if_changed -x` | ❌ W0 | ⬜ pending |
| 44-02-03 | 02 | 1 | INDEX-03 | — | Cross-cutting package only in By Kind | integration | `uv run --package wiki-io pytest tests/test_index_generator.py::test_cross_cutting_in_by_kind_only -x` | ❌ W0 | ⬜ pending |
| 44-02-04 | 02 | 1 | INDEX-02 (D-04) | — | Multi-domain test_suite in By Kind, not in either domain section | integration | `uv run --package wiki-io pytest tests/test_index_generator.py::test_multi_domain_entity_in_by_kind -x` | ❌ W0 | ⬜ pending |
| 44-02-05 | 02 | 1 | INDEX-01 (D-07) | — | Sub-domain nested under parent | integration | `uv run --package wiki-io pytest tests/test_index_generator.py::test_sub_domain_nesting -x` | ❌ W0 | ⬜ pending |
| 44-02-06 | 02 | 1 | INDEX-01 (D-08) | — | Empty sections omitted | integration | `uv run --package wiki-io pytest tests/test_index_generator.py::test_empty_sections_omitted -x` | ❌ W0 | ⬜ pending |
| 44-02-07 | 02 | 1 | INDEX-05 | — | Curated lanes consolidated into single index | integration | `uv run --package wiki-io pytest tests/test_index_generator.py::test_curated_lanes_consolidated -x` | ❌ W0 | ⬜ pending |
| 44-02-08 | 02 | 1 | INDEX-01 (D-04 plugin) | — | Plugin always in By Kind | integration | `uv run --package wiki-io pytest tests/test_index_generator.py::test_plugin_always_by_kind -x` | ❌ W0 | ⬜ pending |
| 44-02-09 | 02 | 1 | INDEX-05 | — | `wiki/index.md` and `*/index.md` excluded from curated scan | integration | `uv run --package wiki-io pytest tests/test_index_generator.py::test_generated_files_excluded -x` | ❌ W0 | ⬜ pending |
| 44-02-10 | 02 | 1 | INDEX-01..05 | — | Real-graph rendering smoke test (syrupy snapshot of agent-research) | snapshot | `uv run --package wiki-io pytest tests/test_index_generator.py::test_snapshot_against_agent_research -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/wiki-io/tests/test_index_generator.py` — NEW file. Contains all test classes and module-level integration tests above.
- [ ] `packages/wiki-io/tests/conftest.py` — extend with `make_index_fixture_graph(spec)` factory that builds an in-memory sqlite connection from a declarative spec (list of `(kind, name, attrs, edges)` tuples). Reuse Phase 43's connection fixture as the substrate.
- [ ] `packages/wiki-io/tests/fixtures/` — add `make_curated_vault(tmp_path, spec)` helper that creates a temp wiki directory tree with frontmatter-bearing pages for curated-lane scan tests. Optional but recommended for readable tests.

*If existing wiki-io test infrastructure already covers conftest fixtures, reuse; else Wave 0 adds.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual inspection of rendered `wiki/index.md` against `agent-research` | INDEX-01..05 sanity | Output is markdown for humans; final acceptance is "does it read sensibly?" | Run `cd /Users/pat/Personal/agent-research && uv run python -c "import sqlite3; from pathlib import Path; from wiki_io.index_generator import generate_index; conn = sqlite3.connect('.graph-wiki/graph.db'); print(generate_index(conn, Path('.graph-wiki/wiki')))"` (adjust paths to actual workspace); review rendered output for: section ordering matches D-03; domain trees nest correctly; no obvious entity miscategorizations; banner date matches today. |

*If none: "All phase behaviors have automated verification."*

The above manual check is a sanity backstop — the automated snapshot test (44-02-10) covers the same surface deterministically. Manual review is for first-time validation before snapshot baselining.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (`tests/test_index_generator.py` is new — Wave 0 creates it)
- [x] No watch-mode flags
- [x] Feedback latency < 30s (per-package pytest)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending — sign at end of planning iteration when checker confirms
