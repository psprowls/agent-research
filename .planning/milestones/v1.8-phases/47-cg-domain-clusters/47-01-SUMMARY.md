---
phase: 47-cg-domain-clusters
plan: 01
status: complete
completed: 2026-05-27
---

# Plan 47-01: graph_io.cluster module — SUMMARY

## What was built

A new pure-stdlib `graph_io.cluster` module implementing deterministic
connected-component clustering over package-references edges, plus a 12-test
unit suite covering correctness, determinism, hub-threshold boundaries, and
degenerate-cluster detection.

### Implementation

- **`packages/graph-io/src/graph_io/cluster.py`** — 366 lines
  - Module docstring describing union-find + hub exclusion + sort-at-every-level
    determinism guarantee (D-09)
  - Four named constants: `_DEFAULT_HUB_THRESHOLD=0.5`, `_DEGENERATE_GIANT_RATIO=0.8`,
    `_REFERENCES_KIND="references"`, `_PACKAGE_KIND="package"` (D-23)
  - Three frozen dataclasses: `Cluster`, `CrossCuttingHub`, `ClusterResult`
    (D-07). Collection fields are `tuple[...]` so results are hashable/immutable.
  - `_UnionFind` with union-by-rank + iterative path compression (~30 LOC, D-01)
  - Seven private helpers: `_load_package_names`, `_load_reference_edges`,
    `_compute_hubs`, `_compute_intra_in_degree`, `_pick_cluster_name`,
    `_compute_connects_clusters`, `_detect_degenerate` (D-23)
  - Public `compute_clusters(conn, *, hub_threshold=0.5) -> ClusterResult`
    implementing the 8-step algorithm (D-02)
  - Pure stdlib: only `sqlite3`, `dataclasses`, `collections`, `collections.abc`,
    `__future__` (D-24)

### Tests

- **`packages/graph-io/tests/test_cluster.py`** — 12 test functions
  - `test_union_find_correctness`
  - `test_hub_detection_threshold_boundary` (including strict-greater rational
    case at threshold = 5/9 exactly)
  - `test_known_small_graph` (6 packages + 1 hub, asserts 3 clusters of
    sizes 3/2/1, hub.connects_clusters == (0,1,2))
  - `test_degenerate_giant` (asserts "100% of packages" substring)
  - `test_degenerate_all_singletons` (asserts "every package is its own cluster")
  - `test_determinism_repeated_invocation` (byte-identical JSON)
  - `test_determinism_permuted_insertion` (separate DBs, seeded shuffle)
  - `test_hub_threshold_out_of_range` (0.0, -0.1, 1.001 raise; 1.0 inclusive)
  - `test_empty_graph`
  - `test_singleton_cluster_present_when_isolated`
  - `test_cluster_name_intra_in_degree_picks_central`
  - `test_connects_clusters_skips_hub_to_hub_edges`

## Decisions honored

- D-01..D-15: algorithm, sort spec, dataclass shape, SQL filter, hub formula
- D-09: sort at every level enforces byte-identical determinism (verified by
  two determinism tests)
- D-24: zero new dependencies introduced

## Deviations

None.

## Verification

```
$ uv run --package graph-io pytest tests/test_cluster.py -x -q
............                                                             [100%]
12 passed in 0.10s
```

Stdlib-only check:
```
$ grep -E "^(import|from)" packages/graph-io/src/graph_io/cluster.py \
    | grep -vE "^from __future__|^from collections|^from dataclasses|^import sqlite3"
(no output)
```

## Key files created

- `packages/graph-io/src/graph_io/cluster.py`
- `packages/graph-io/tests/test_cluster.py`

## Commits

- `86bedac` feat(47-01): scaffold graph_io.cluster module
- `34c1417` feat(47-01): implement compute_clusters algorithm
- `a48a751` test(47-01): add unit + determinism + degenerate tests for cluster module

## Self-Check: PASSED

- Verification commands from `<verification>` block all exit 0
- All `<acceptance_criteria>` items satisfied
- No third-party imports
- 12 tests defined; all pass
