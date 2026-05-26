---
phase: 31
slug: domain-layer-derived-edges
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-25
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `packages/graph-io/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run --package graph-io pytest packages/graph-io/tests/test_domains.py packages/graph-io/tests/test_derived_edges.py packages/graph-io/tests/test_import_scan.py -q` |
| **Full suite command** | `uv run --package graph-io pytest packages/graph-io/tests/ -q` |
| **Estimated runtime** | ~12 seconds (quick), ~25 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run quick command (scoped to phase-touched tests).
- **After every plan wave:** Run full suite (catches Phase 29/30 regressions).
- **Before `/gsd:verify-work`:** Full suite must be green.
- **Max feedback latency:** 25 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 01 | 0 | DOMAIN-03 (SC#2 wording) | — | N/A — docs amendment | regex assertion | `grep -F 'skip ONLY the cycle-participating containment edges' .planning/ROADMAP.md` | ❌ W0 | ⬜ pending |
| 31-01-02 | 01 | 0 | DOMAIN-01 | — | N/A | dep check | `uv run --package graph-io python -c "import yaml; print(yaml.__version__)"` | ❌ W0 | ⬜ pending |
| 31-01-03 | 01 | 0 | DOMAIN-01 | — | N/A — URI shape | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_uri.py::test_domain_uri_with_ctx -q` | ❌ W0 | ⬜ pending |
| 31-02-01 | 02 | 1 | DERIVED-01, DERIVED-02 | — | YAML safe_load only (D-06) | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_import_scan.py -q` | ❌ W0 | ⬜ pending |
| 31-02-02 | 02 | 1 | DERIVED-01, DERIVED-02 | — | No regression on Phase 30 | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_test_suites.py -q` | ❌ W0 (after Phase 30) | ⬜ pending |
| 31-03-01 | 03 | 1 | DOMAIN-01, DOMAIN-02 | — | `yaml.safe_load` only (D-06) | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_domains.py::test_emit_domain_nodes -q` | ❌ W0 | ⬜ pending |
| 31-03-02 | 03 | 1 | DOMAIN-02 | — | Multi-domain membership | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_domains.py::test_multi_domain_membership -q` | ❌ W0 | ⬜ pending |
| 31-03-03 | 03 | 1 | DOMAIN-03 | — | Cycle-only edge skip | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_domains.py::test_cycle_skip_only_intra_scc -q` | ❌ W0 | ⬜ pending |
| 31-03-04 | 03 | 1 | DOMAIN-03 | — | Self-loop edge skip | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_domains.py::test_self_loop_skip -q` | ❌ W0 | ⬜ pending |
| 31-03-05 | 03 | 1 | DOMAIN-04 | — | Missing yaml = zero-domain | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_domains.py::test_missing_yaml_zero_domain -q` | ❌ W0 | ⬜ pending |
| 31-03-06 | 03 | 1 | DOMAIN-04 | — | Unknown package warns + known list | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_domains.py::test_unknown_package_warns_with_known_list -q` | ❌ W0 | ⬜ pending |
| 31-03-07 | 03 | 1 | DOMAIN-05 | — | No convention inference (SC#5) | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_domains.py::test_no_convention_inference_from_test_dir -q` | ❌ W0 | ⬜ pending |
| 31-04-01 | 04 | 2 | DERIVED-01 | — | references = D→P cross-domain only | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_derived_edges.py::test_references_emitted -q` | ❌ W0 | ⬜ pending |
| 31-04-02 | 04 | 2 | DERIVED-02 | — | depends_on = A→B per-pair | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_derived_edges.py::test_depends_on_emitted -q` | ❌ W0 | ⬜ pending |
| 31-04-03 | 04 | 2 | DERIVED-03 | — | Idempotent re-run (delete-then-recompute) | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_derived_edges.py::test_idempotency -q` | ❌ W0 | ⬜ pending |
| 31-04-04 | 04 | 2 | DERIVED-04 | — | No transitive storage | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_derived_edges.py::test_no_transitive_storage -q` | ❌ W0 | ⬜ pending |
| 31-04-05 | 04 | 2 | DERIVED-01 (Phase 30 D-13) | — | TestSuite→Domain when all in same domain | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_derived_edges.py::test_testsuite_domain_emitted -q` | ❌ W0 | ⬜ pending |
| 31-04-06 | 04 | 2 | DERIVED-01 (Phase 30 D-13) | — | No TestSuite→Domain on multi-domain spans | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_derived_edges.py::test_testsuite_no_domain_on_multi_domain_span -q` | ❌ W0 | ⬜ pending |
| 31-04-07 | 04 | 2 | DOMAIN-01..05 + DERIVED-01..04 | — | End-to-end: cg update on fixture | integration | `uv run --package graph-io pytest packages/graph-io/tests/test_derived_edges.py::test_update_run_end_to_end -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/graph-io/pyproject.toml` — add `pyyaml>=6.0` to dependencies
- [ ] `packages/graph-io/tests/test_uri.py` — add one test for the amended `domain_uri(ctx, name)` shape
- [ ] `.planning/ROADMAP.md` — amend SC#2 wording per D-15

*Test files for Wave 1/2 plans are created BY those plans; no Wave 0 stub
files are required beyond the three above.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `cg list-domains` CLI shim (if landed) | SC#1 | Phase 33 CLI; Phase 31 may verify via raw SQL instead | Not applicable — verified via `SELECT * FROM nodes WHERE kind='domain'` in `test_derived_edges.py::test_update_run_end_to_end` |

*All other phase behaviors have automated verification (see Per-Task
Verification Map above).*

---

## Sampling Continuity Check

Wave 1 plans (31-02, 31-03) and Wave 2 plan (31-04) each ship with their own
test files (`test_import_scan.py`, `test_domains.py`, `test_derived_edges.py`).
No three consecutive tasks lack automated verification — the longest streak
without a unit-test verify command is 0 tasks (every task in plans 02/03/04
has an associated test assertion).

Wave 0 (plan 31-01) has three tasks, two of which are docs/dep edits with
grep-based verification (acceptable per gates.md — assertion-grade
verification commands count toward the sampling rate).

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags (every command is one-shot `pytest -q`)
- [x] Feedback latency < 25s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
