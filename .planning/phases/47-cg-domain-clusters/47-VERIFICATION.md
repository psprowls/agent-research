---
phase: 47-cg-domain-clusters
status: passed
verifier: gsd-execute-phase (inline — runtime lacks gsd-verifier subagent)
verified_at: 2026-05-27
phase_req_ids: [CLUSTER-01, CLUSTER-02, CLUSTER-03, CLUSTER-04, CLUSTER-05]
---

# Phase 47 Verification

## Goal

`cg domain-clusters` produces deterministic connected-component clusters from
the import adjacency graph with hub-node exclusion preprocessing,
degenerate-cluster warnings, and `--fmt human|json` output — independently
testable with no LLM dependency and exercised against the `agent-research`
monorepo itself.

## Must-have check

| # | Criterion | Verified by | Status |
|---|-----------|-------------|--------|
| 1 | `compute_clusters(conn, *, hub_threshold=0.5) -> ClusterResult` exists, returns frozen dataclasses with tuple collection fields, runs end-to-end on a non-trivial DB | `test_known_small_graph` (3 clusters + 1 hub, asserts sizes and connects_clusters) + module-level introspection (`dataclasses.is_dataclass`, `__dataclass_params__.frozen`) | PASS |
| 2 | Hub exclusion preprocessing runs BEFORE union-find (D-04, D-05); degenerate-cluster warnings fire when giant >80% or all-singletons | `test_hub_detection_threshold_boundary` (strict-greater at exact rational 5/9) + `test_degenerate_giant` ("100% of packages") + `test_degenerate_all_singletons` ("every package is its own cluster") | PASS |
| 3 | `cg domain-clusters` registered as subcommand; both `--fmt human` and `--fmt json` produce well-formed output; correct exit codes on error paths | `test_cli_subcommand_registered` + `test_cli_human_format` + `test_cli_json_format` (D-20 key order locked) + `test_cli_hub_threshold_validation` + `test_cli_not_initialized` (exit 3) | PASS |
| 4 | Integration test exercises `cg domain-clusters` against the real agent-research code.db | `test_run_against_agent_research_graph` (passed against live workspace graph, returncode 0, JSON has locked key order, ≥1 cluster present) | PASS |
| 5 | Byte-identical determinism guarantee at both in-process and subprocess granularity | `test_determinism_repeated_invocation` (json.dumps identical) + `test_determinism_permuted_insertion` (separate DBs, shuffled insertion order, identical JSON) + `test_byte_identical_repeated_invocation` (subprocess.check_output × 2 identical) | PASS |

## Requirement traceability

| Requirement | Description | Verified by | Status |
|-------------|-------------|-------------|--------|
| CLUSTER-01 | `compute_clusters(conn, *, hub_threshold=0.5)` returns `ClusterResult` | Plan 01 `cluster.py` + Plan 01 unit tests | Complete |
| CLUSTER-02 | Hub-exclusion preprocessing + degenerate-cluster warnings | D-04..D-06 + D-11..D-14 implemented; `test_degenerate_giant` + `test_degenerate_all_singletons` | Complete |
| CLUSTER-03 | CLI subcommand with `--fmt human|json` and `--hub-threshold` | Plan 02 `q_domain_clusters.py` + `cli/main.py` registration + 6 CLI tests | Complete |
| CLUSTER-04 | Integration test against agent-research repo's own graph | Plan 03 `tests/integration/test_cluster_cli.py` (4 tests, all pass live) | Complete |
| CLUSTER-05 | Byte-identical determinism for `--fmt json` | Plan 01 in-process JSON tests + Plan 03 subprocess byte-identity test | Complete |

## Test suite snapshot

- `uv run --package graph-io pytest -x -q`: 380 passed, 1 skipped (pre-existing), 1 xfailed (pre-existing)
- Phase 47 contributions: 18 unit + CLI tests in `test_cluster.py`, 4 integration tests in `tests/integration/test_cluster_cli.py`
- Integration tests ran live (not skipped) against the agent-research workspace graph
- No `PytestUnknownMarkWarning` (integration marker registered)
- Cross-package regression: `uv run pytest packages/ --ignore=packages/graph-io`: 662 passed, 27 skipped (pre-existing) — no regressions

## Key decisions honored

- D-09 sort spec at every level → byte-identical determinism verified twice
- D-21 hierarchical custom rendering (no `_format.render`) → confirmed by absence of `_format` import in `q_domain_clusters.py`
- D-24 pure stdlib → confirmed by grep over imports
- Planner note on `exit_codes.GENERIC` for `--hub-threshold` validation (since no USAGE constant exists) → honored in `q_domain_clusters.py`

## Deviations

None. Plan 03's Task 3 `cg update` recommendation was a no-op because the agent-research graph DB was already initialized in this environment, so integration tests ran in their real-data path.

## Human verification

None required — phase is fully validated by automated tests against the live agent-research workspace.
