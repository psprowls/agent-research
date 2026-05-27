---
phase: 47
slug: cg-domain-clusters
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-27
---

# Phase 47 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `packages/graph-io/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run --package graph-io pytest tests/test_cluster.py -x` |
| **Full suite command** | `uv run --package graph-io pytest` |
| **Estimated runtime** | ~15 seconds (unit) · ~30 seconds (full, incl. integration) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package graph-io pytest tests/test_cluster.py -x`
- **After every plan wave:** Run `uv run --package graph-io pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 47-01-01 | 01 | 1 | CLUSTER-01 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_union_find_correctness -x` | ❌ W0 | ⬜ pending |
| 47-01-02 | 01 | 1 | CLUSTER-01 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_hub_detection_threshold_boundary -x` | ❌ W0 | ⬜ pending |
| 47-01-03 | 01 | 1 | CLUSTER-01 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_known_small_graph -x` | ❌ W0 | ⬜ pending |
| 47-01-04 | 01 | 1 | CLUSTER-02 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_degenerate_giant -x` | ❌ W0 | ⬜ pending |
| 47-01-05 | 01 | 1 | CLUSTER-02 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_degenerate_all_singletons -x` | ❌ W0 | ⬜ pending |
| 47-01-06 | 01 | 1 | CLUSTER-05 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_determinism_repeated_invocation -x` | ❌ W0 | ⬜ pending |
| 47-01-07 | 01 | 1 | CLUSTER-05 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_determinism_permuted_insertion -x` | ❌ W0 | ⬜ pending |
| 47-01-08 | 01 | 1 | CLUSTER-01 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_hub_threshold_out_of_range -x` | ❌ W0 | ⬜ pending |
| 47-01-09 | 01 | 1 | CLUSTER-02 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_empty_graph -x` | ❌ W0 | ⬜ pending |
| 47-02-01 | 02 | 2 | CLUSTER-03 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_cli_subcommand_registered -x` | ❌ W0 | ⬜ pending |
| 47-02-02 | 02 | 2 | CLUSTER-03 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_cli_human_format -x` | ❌ W0 | ⬜ pending |
| 47-02-03 | 02 | 2 | CLUSTER-03 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_cli_json_format -x` | ❌ W0 | ⬜ pending |
| 47-02-04 | 02 | 2 | CLUSTER-03 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_cli_hub_threshold_validation -x` | ❌ W0 | ⬜ pending |
| 47-02-05 | 02 | 2 | CLUSTER-03 | — | N/A | unit | `uv run --package graph-io pytest tests/test_cluster.py::test_cli_not_initialized -x` | ❌ W0 | ⬜ pending |
| 47-03-01 | 03 | 3 | CLUSTER-04 | — | N/A | integration | `uv run --package graph-io pytest tests/integration/test_cluster_cli.py::test_cg_help_lists_command -x` | ❌ W0 | ⬜ pending |
| 47-03-02 | 03 | 3 | CLUSTER-04 | — | N/A | integration | `uv run --package graph-io pytest tests/integration/test_cluster_cli.py::test_subcommand_help_exit_zero -x` | ❌ W0 | ⬜ pending |
| 47-03-03 | 03 | 3 | CLUSTER-04 | — | N/A | integration | `uv run --package graph-io pytest tests/integration/test_cluster_cli.py::test_run_against_agent_research_graph -x` | ❌ W0 | ⬜ pending |
| 47-03-04 | 03 | 3 | CLUSTER-05 | — | N/A | integration | `uv run --package graph-io pytest tests/integration/test_cluster_cli.py::test_byte_identical_repeated_invocation -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/graph-io/tests/test_cluster.py` — stubs for CLUSTER-01..05 unit/CLI tests (created in Plan 01 alongside `cluster.py`)
- [ ] `packages/graph-io/tests/integration/__init__.py` — package marker for new integration subdirectory (Plan 03)
- [ ] `packages/graph-io/tests/integration/test_cluster_cli.py` — stubs for CLUSTER-04 integration tests (Plan 03)
- [ ] `packages/graph-io/pyproject.toml` — register `integration` pytest marker (Plan 03)

*Existing infrastructure (`conftest.py::seeded_db`, `empty_db`) covers fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual review of clusters against agent-research vault | CLUSTER-04 | Subjective coherence judgment (clusters look "right") | Run `uv run cg domain-clusters` in the repo root; visually inspect that clusters group related packages. |

---

## Validation Sign-Off

- [x] All tasks have automated verify (unit + integration)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (new files written in their owning plan)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-27
