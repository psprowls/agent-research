---
phase: 43
slug: entity-writer
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-26
---

# Phase 43 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.3 + pytest-asyncio + hypothesis >=6.116 (added Phase 42) |
| **Config file** | `pyproject.toml` (root) + `packages/wiki-io/pyproject.toml` + `packages/graph-io/pyproject.toml` |
| **Quick run command (wiki-io)** | `uv run --package wiki-io pytest -x` |
| **Quick run command (graph-io)** | `uv run --package graph-io pytest -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | wiki-io ~15s, graph-io ~30s, full ~60s |

---

## Sampling Rate

- **After every task commit:** Run the relevant per-package `pytest -x` (wiki-io or graph-io depending on what was touched)
- **After every plan wave:** Run `uv run pytest` (full suite)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (per-package) / 60 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 43-01-01 | 01 | 1 | (indirect ENTITY-01) | — | N/A | unit | `uv run --package graph-io pytest tests/test_queries.py::test_valid_kinds_includes_dependency_plugin -x` | ❌ W0 | ⬜ pending |
| 43-01-02 | 01 | 1 | (indirect ENTITY-01) | — | N/A | unit | `uv run --package graph-io pytest tests/test_packages.py::test_pep_508_name_extraction -x` | ❌ W0 | ⬜ pending |
| 43-01-03 | 01 | 1 | (indirect ENTITY-01) | — | N/A | integration | `uv run --package graph-io pytest tests/test_packages.py::test_dependency_ingestion_from_workspace -x` | ❌ W0 | ⬜ pending |
| 43-01-04 | 01 | 1 | (indirect ENTITY-01) | — | N/A | integration | `uv run --package graph-io pytest tests/test_plugins.py::test_plugin_ingestion_from_manifest -x` | ❌ W0 | ⬜ pending |
| 43-01-05 | 01 | 1 | (indirect ENTITY-01) | — | N/A | unit | `uv run --package graph-io pytest tests/test_queries.py::test_describe_dependency_returns_dependency_description -x` | ❌ W0 | ⬜ pending |
| 43-01-06 | 01 | 1 | (indirect ENTITY-01) | — | N/A | unit | `uv run --package graph-io pytest tests/test_queries.py::test_describe_plugin_returns_plugin_description -x` | ❌ W0 | ⬜ pending |
| 43-01-07 | 01 | 1 | (folded todo) | — | N/A | regression | `uv run --package graph-io pytest tests/test_structural_nodes.py::test_no_subpackage_node_at_import_root -x` | ❌ W0 | ⬜ pending |
| 43-02-01 | 02 | 1 | ENTITY-04 | — | N/A | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_entity_write_result_shape -x` | ❌ W0 | ⬜ pending |
| 43-02-02 | 02 | 1 | ENTITY-02 | — | Human-authored `status:` survives merge | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_merge_preserves_human_authored_status -x` | ❌ W0 | ⬜ pending |
| 43-02-03 | 02 | 1 | ENTITY-02 | — | Whitelist key disjointness | property | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_merge_property_non_whitelist_preserved -x` | ❌ W0 | ⬜ pending |
| 43-02-04 | 02 | 1 | ENTITY-04 | — | needs_narrative on structural change | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_needs_narrative_on_structural_change -x` | ❌ W0 | ⬜ pending |
| 43-02-05 | 02 | 1 | ENTITY-04 | — | needs_narrative on create | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_needs_narrative_on_create -x` | ❌ W0 | ⬜ pending |
| 43-02-06 | 02 | 1 | ENTITY-01 | — | Determinism on write-if-changed | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_write_if_changed_no_op_on_identical_input -x` | ❌ W0 | ⬜ pending |
| 43-02-07 | 02 | 1 | ENTITY-05 | T-43-01 | scan.lock contention raises WriteLockHeldError | unit (threaded) | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_scan_lock_raises_on_contention -x` | ❌ W0 | ⬜ pending |
| 43-02-08 | 02 | 1 | ENTITY-05 | T-43-01 | scan.lock released on exception path | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_scan_lock_released_on_exception -x` | ❌ W0 | ⬜ pending |
| 43-02-09 | 02 | 1 | ENTITY-03 | — | deletions.log JSONL append | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_append_deletion_writes_jsonl -x` | ❌ W0 | ⬜ pending |
| 43-02-10 | 02 | 1 | ENTITY-03 | — | rotation at 10MB | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_deletions_log_rotates_at_threshold -x` | ❌ W0 | ⬜ pending |
| 43-02-11 | 02 | 1 | ENTITY-01 | — | Partial-failure isolation | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_partial_failure_recorded_in_errors -x` | ❌ W0 | ⬜ pending |
| 43-03-01 | 03 | 2 | ENTITY-01..05 | — | Round-trip on agent-research itself | integration | `uv run --package wiki-io pytest tests/integration/test_entity_writer_integration.py::test_write_entities_round_trip_on_agent_research -x` | ❌ W0 | ⬜ pending |
| 43-03-02 | 03 | 2 | ENTITY-02 | — | Merge preservation under real graph | integration | `uv run --package wiki-io pytest tests/integration/test_entity_writer_integration.py::test_status_deprecated_preserved_after_rewrite -x` | ❌ W0 | ⬜ pending |
| 43-03-03 | 03 | 2 | ENTITY-03 | — | Hard-delete with full log entry | integration | `uv run --package wiki-io pytest tests/integration/test_entity_writer_integration.py::test_hard_delete_logs_to_deletions_log -x` | ❌ W0 | ⬜ pending |
| 43-03-04 | 03 | 2 | ENTITY-04 | — | needs_narrative correct on create + change | integration | `uv run --package wiki-io pytest tests/integration/test_entity_writer_integration.py::test_needs_narrative_round_trip -x` | ❌ W0 | ⬜ pending |
| 43-03-05 | 03 | 2 | ENTITY-05 | T-43-01 | Concurrent write_entities blocked | integration | `uv run --package wiki-io pytest tests/integration/test_entity_writer_integration.py::test_scan_lock_blocks_concurrent_writes -x` | ❌ W0 | ⬜ pending |
| 43-03-06 | 03 | 2 | ENTITY-01 | — | Determinism: two consecutive runs → zero updated | integration | `uv run --package wiki-io pytest tests/integration/test_entity_writer_integration.py::test_determinism_second_run_all_unchanged -x` | ❌ W0 | ⬜ pending |
| 43-03-07 | 03 | 2 | (discretionary D-06) | — | `cg describe dependency` exits 0 | integration | `uv run --package graph-io pytest tests/test_cli_describe.py::test_cg_describe_dependency_smoke -x` | ❌ W0 | ⬜ pending (may slip per D-06) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/wiki-io/tests/test_entity_writer.py` — extended (Phase 42 created the file; Phase 43 adds ENTITY-* unit tests; reuse existing imports + Hypothesis dep)
- [ ] `packages/wiki-io/tests/integration/test_entity_writer_integration.py` — NEW directory + file; needs conftest fixture for "build a temp workspace + run wave-1 ingestion + return (conn, wiki_root)"
- [ ] `packages/wiki-io/tests/conftest.py` — add `mock_graph_conn` fixture if not present (canned `NodeRecord` / `DependencyDescription` / `PluginDescription` returns)
- [ ] `packages/graph-io/tests/test_plugins.py` — NEW file for plugin-ingestion tests
- [ ] `packages/graph-io/tests/test_packages.py` — extend with PEP 508 + dependency ingestion tests
- [ ] `packages/graph-io/tests/test_structural_nodes.py` — add subpackage-import-root regression test
- [ ] `packages/graph-io/tests/test_cli_describe.py` — NEW file IF D-06 stretch goal ships in Plan 03

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `body_was_empty: true` correctness when a page has only the template default | ENTITY-03 | Requires comparing rendered template output for each kind — automated covers it but a one-off inspection of one real deleted page in `.graph-wiki/deletions.log` is a useful sanity check | After Plan 03 ships: pick a fixture node, delete it from graph, run `write_entities`, `cat .graph-wiki/deletions.log` and confirm the JSON line for that URI has `body_was_empty: true`. |
| File mode `0o644` on written entity pages | (convention) | OS-level inspection | After integration test: `ls -l wiki/entities/*.md \| awk '{print $1}' \| sort -u` should show only `-rw-r--r--`. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s (full) / < 30s (per-package)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
