# Phase 47: `cg domain-clusters` — Research

**Researched:** 2026-05-27
**Status:** Research complete
**Phase requirement IDs:** CLUSTER-01, CLUSTER-02, CLUSTER-03, CLUSTER-04, CLUSTER-05

---

## Summary

Phase 47 adds a single self-contained graph-io feature: a new `cg domain-clusters`
subcommand that computes connected-component clusters over the package-level
`references` adjacency graph, with hub exclusion preprocessing and degenerate-cluster
detection. The shape of the work is overwhelmingly determined by CONTEXT.md
(decisions D-01..D-26). This research grounds those decisions in the actual code
landscape and surfaces the small set of integration details the planner needs.

The phase has zero external runtime dependencies (pure stdlib union-find), no LLM,
no cross-package coupling. It only reads from the existing SQLite graph store and
mirrors the established CLI subcommand pattern.

---

## How `graph-io` is Wired Today

### Module layout (verified)

`packages/graph-io/src/graph_io/`:
- `cli/main.py` — argparse dispatch over `_SUBCOMMANDS` dict; every subcommand
  module exposes `add_arguments(parser)` and `run(args) -> int`.
- `cli/q_cross_cutting.py` — closest analog to the Phase 47 subcommand. Opens
  read-only via `store.read_only_connect`, handles `GraphNotInitializedError`
  and `SchemaMismatchError`, dispatches on `args.fmt`, returns
  `exit_codes.SUCCESS|NOT_INITIALIZED|SCHEMA_MISMATCH`.
- `cli/_format.py::render()` — flat-record renderer (one record per row, aligned
  columns). Designed for tabular `q_*` output. Phase 47's output is hierarchical
  (clusters with member lists + hubs with `connects_clusters` lists) so the
  cluster CLI will render inline like `q_cross_cutting.py` does, **not** through
  `_format.render`. CONTEXT.md D-21 already locks this human format.
- `store.py` — `read_only_connect(db_path)` opens `mode=ro` URI, runs
  `apply_schema`-compatible version check, raises `GraphNotInitializedError`
  or `SchemaMismatchError`.
- `exit_codes.py` — exposes `SUCCESS=0, GENERIC=1, STALE=2, NOT_INITIALIZED=3,
  SCHEMA_MISMATCH=4, NOT_IN_GIT_REPO=5, UPDATE_IN_PROGRESS=6, AMBIGUOUS=7`.
  **There is no `USAGE` code** — D-19's `--hub-threshold` validation will use
  `GENERIC` (1).
- `queries.py::cross_cutting_packages` — confirms the `kind='references'` filter
  semantics. Phase 47's SELECT is similar but does not need the
  cross_cutting-specific aggregation.
- `derived_edges.py::_compute_references_and_depends_on` — produces the
  package-to-package `references` edges that Phase 47 consumes. Already runs as
  part of `cg update`. Not modified by Phase 47.

### Test layout (verified)

`packages/graph-io/tests/`:
- `conftest.py` — exposes `seeded_db` (session-scoped, runs `update.run(..., full=True)`
  against `tests/fixtures/sample_monorepo`) and `empty_db` (function-scoped,
  `:memory:` with bare schema). Phase 47 will reuse these.
- `test_queries.py`, `test_derived_edges.py` — precedent for in-process query
  tests using `seeded_db`.
- `test_cli_smoke.py`, `test_cli_exit_codes.py`, `test_cli_format.py` — precedent
  for CLI tests using `subprocess.run(["cg", ...])`.
- `tests/integration/` — **does not exist yet**. Phase 47 creates it for the
  agent-research-self integration test (D-26).

### Schema (relevant subset)

The `code.db` schema includes:
- `nodes(id INTEGER PK, kind TEXT, name TEXT, uri TEXT, ...)`.
- `edges(src INTEGER, dst INTEGER, kind TEXT, attrs JSON, ...)`.

The `references` edge kind is produced by the derived-edges step and connects
package-kind nodes whose source modules transitively import each other. This is
the only edge kind Phase 47 reads.

---

## Algorithm Translation Notes (grounding D-01..D-10)

### Union-find sketch

A minimal disjoint-set with path compression + union-by-rank is ~25–30 lines and
sufficient for v1.8 graph sizes (<1k packages expected even for large monorepos).
No tuning needed.

```
class _UnionFind:
    def __init__(self, items): self.parent = {x: x for x in items}; self.rank = {x: 0 for x in items}
    def find(self, x): ...path compression...
    def union(self, a, b): ...union by rank...
```

### Hub detection ordering

D-04/D-05 mandate hubs are computed and excluded **before** union-find runs.
Order of operations:
1. SELECT names + adjacency from the DB.
2. For each node, `in_degree = sum(1 for src,dst in edges if dst==node)`.
3. `is_hub = in_degree / (n_packages - 1) > hub_threshold`. Strictly greater
   (D-09 verifies the inequality is `>`, not `>=`).
4. Drop hub nodes and any edge touching a hub from the working set.
5. Initialize `_UnionFind` over **remaining** nodes only.
6. For each `(src, dst)` in remaining edges: `uf.union(src, dst)`.

`(n_packages - 1)` denominator: matches ROADMAP "imported by >50% of others"
phrasing — a package can't import itself; the universe of potential importers is
`n - 1`. Edge case: `n_packages == 1` → degenerate before computation; treat as
trivially non-hub (denominator-zero guard at top of `_compute_hubs`).

### `connects_clusters` for hubs (D-08)

After clusters are computed (sorted; IDs assigned), iterate every excluded hub:
- Look at the **original** adjacency: for every edge touching the hub, take the
  other endpoint.
- If the other endpoint is in some cluster `c_id`, collect it.
- Deduplicate, sort ascending. That tuple is `connects_clusters`.

Note: if the other endpoint is also a hub (hub-to-hub edge), it does not belong
to any cluster — skip it. CONTEXT does not specify this, but the natural reading
is that only "would-connect-real-clusters" reports as a connection. Implementation
detail under Claude's discretion.

### Auto-derived cluster name (D-10)

For each cluster: among its members, count incoming references **from other
members of the same cluster** (intra-cluster in-degree); pick the max; tiebreak
alphabetical. Done at result-build time using the already-loaded adjacency. ~10
LOC helper.

### Sort spec invariants (D-09) — critical for CLUSTER-05

The byte-identical determinism guarantee depends on applying all four sorts
explicitly at result-build time:
- `clusters` outer: `key=(-size, members[0])`.
- `members` inner: `sorted(members)`.
- `cross_cutting` outer: `key=name`.
- `connects_clusters` inner: `sorted(...)` ascending integer.
- Cluster IDs are 0,1,2,... assigned **after** the outer sort.

The `name_to_cluster_id` map used in `connects_clusters` computation MUST be built
after the outer sort, so cluster IDs match.

---

## Output Path Decisions (grounding D-20..D-22)

### JSON output

Per D-20, JSON uses `json.dumps(..., indent=2, sort_keys=False)`. The dataclass
field declaration order is the canonical key order (Python 3.7+ guarantees dict
key order; `dataclasses.asdict` preserves field order). To force `hub_threshold`,
`n_packages_total`, `degenerate_warning` first and `clusters` / `cross_cutting`
last as shown in CONTEXT, declare them in that order on `ClusterResult`.

Verified — CONTEXT D-07's field order already matches D-20's example JSON key
order. No re-arrangement needed.

The `imported_by_fraction` field needs 2-decimal truncation for human output but
should be retained at full float precision in JSON (so byte-identical comparison
is deterministic across machines, since the float value is computed
deterministically from integer counts).

Decision: keep full precision in both. CONTEXT D-20 says "truncated to 2 decimals
via formatting (display-only)" — the JSON keeps the underlying float; the human
formatter wraps it with `f"{frac:.0%}"` for `%` display.

### Human output

Per D-21, sections rendered manually (no `_format.render`). Width computed from
longest name in each section; `~80-col` target is advisory. Cross-cutting hubs
printed first.

### Empty-graph behavior (D-22)

If both `clusters` and `cross_cutting` are empty: JSON emits the canonical shape
with empty arrays; human prints `"No packages with import edges found."` to
stderr; both exit 0. Per D-13, degeneracy is a warning (stderr) but exit 0.

---

## CLI Integration (grounding D-17..D-19)

### Subcommand registration

`cli/main.py::_SUBCOMMANDS` dict has 29 existing entries. Phase 47 adds one line:
```
"domain-clusters": q_domain_clusters,
```
plus the corresponding import at the top of the file. **Mechanical edit; no
behavioral change to existing commands.**

### `--hub-threshold` argument

`add_arguments(parser)` registers:
```
parser.add_argument(
    "--hub-threshold",
    type=float,
    default=0.5,
    help="exclude packages imported by more than this fraction of others (default 0.5)",
)
```

Range validation: D-06 says `(0.0, 1.0]`. `compute_clusters` raises `ValueError`
on out-of-range; CLI catches and translates to a friendly stderr message with
exit code `exit_codes.GENERIC` (CONTEXT D-19 says "EXIT_USAGE or equivalent" —
GENERIC is the equivalent in this codebase). The CLI wraps the call:

```
try:
    result = cluster.compute_clusters(conn, hub_threshold=args.hub_threshold)
except ValueError as exc:
    print(f"error: {exc}", file=sys.stderr)
    return exit_codes.GENERIC
```

### Help text behaviors (CLUSTER-04)

`cg --help` and `cg domain-clusters --help` already exit 0 via argparse's normal
behavior once the subcommand is registered. The tests assert presence in stdout.

---

## Test Strategy (grounding D-25, D-26)

### Unit tests (test_cluster.py — new)

Use `empty_db` for tests that need a real connection with no rows; build
fixtures via direct `INSERT INTO nodes/edges` for small known graphs (avoids the
overhead of running a full `update.run`). Pattern matches `test_queries.py`.

Tests enumerated in D-25:
1. `_UnionFind` correctness — direct unit tests (no DB needed).
2. Hub detection at threshold boundaries (10 packages: 5/9 vs 0.55, 0.5, 0.49).
3. Known small graph — 3 clusters, 1 hub, validated `connects_clusters`.
4. Degenerate giant (>80% in one cluster).
5. Degenerate all-singletons.
6. Determinism — call twice on same DB, byte-identical JSON.
7. Determinism with permuted insert order — seed two random insertion sequences
   for the same graph, byte-identical output. (Pure stdlib `random.Random(seed)`
   suffices; Hypothesis is available as a dev dep but not required.)
8. `hub_threshold` out-of-range raises `ValueError` (0.0 and 1.0+epsilon).
9. Empty graph → empty `ClusterResult`.

### Integration test (test_cluster_cli.py — new directory)

`packages/graph-io/tests/integration/test_cluster_cli.py`:
- Locate the agent-research repo root (the test file's grandparent grandparent
  of grandparent — but more robustly, walk up until we find `.git` + `pyproject.toml`
  with workspace members). The `tests` dir already has conftest patterns; we
  reuse the workspace resolution.
- Skip with `pytest.mark.integration` when the agent-research graph is not
  present. The marker is registered ad-hoc via `pyproject.toml` `tool.pytest.ini_options`
  (already configured for `testpaths = ["tests"]`; we register the marker).
- Assertions: exit 0, JSON parses, contains `>=1` cluster OR degenerate_warning.
- Determinism assertion: run subprocess twice via `subprocess.check_output`,
  compare bytes.
- Help-flag smoke test: `subprocess.run(["cg", "--help"])` contains
  `domain-clusters`; `subprocess.run(["cg", "domain-clusters", "--help"])` contains
  `--hub-threshold`.

`@pytest.mark.integration` registration: add to graph-io `pyproject.toml`
under `[tool.pytest.ini_options]`:
```
markers = ["integration: requires the agent-research workspace graph"]
```
This is a small additional edit and keeps the marker explicit.

---

## Validation Architecture

This phase's behaviors are largely property-based; the validation strategy is
table-driven.

| Behavior                                          | Source-of-truth verification                              |
|---------------------------------------------------|-----------------------------------------------------------|
| Connected-components correctness                  | Hand-built small graph; assert exact membership           |
| Hub exclusion at threshold                        | Boundary tests at 0.499 / 0.5 / 0.501 with `n=10`         |
| Singletons are clusters of size 1                 | Hand-built graph with isolated nodes                      |
| `connects_clusters` semantics                     | Hand-built graph with hub spanning known clusters         |
| Degenerate giant detection                        | Synthesized graph with one >80% cluster                   |
| Degenerate all-singletons detection               | Empty-edges graph with N package nodes                    |
| Determinism guarantee (CLUSTER-05)                | Twice-invocation byte-identical comparison                |
| Determinism under permuted node insertion         | `random.Random(seed)` permutation, byte-identical compare |
| `--hub-threshold` range validation                | 0.0 and 1.001 → ValueError; CLI exits non-zero            |
| Empty graph → empty result + degenerate warning   | `empty_db` fixture with zero edges                        |
| `cg --help` lists `domain-clusters` (CLUSTER-04)  | Subprocess help-text contains substring                   |
| `cg domain-clusters --help` exit 0 (CLUSTER-04)   | Subprocess exit code == 0                                 |
| Integration on agent-research graph (CLUSTER-04)  | Run against real `code.db`; exit 0; meaningful output     |
| `NOT_INITIALIZED` exit code path (D-16)           | CLI against missing `code.db`; exit code == 3             |

Each row maps to at least one test in D-25 or D-26.

---

## Risks / Open Questions

- **`tests/integration/` location and discovery.** `pyproject.toml` has
  `testpaths = ["tests"]` which already covers subdirectories. No change needed.
- **`integration` marker registration.** Need to add to `pyproject.toml`. Mentioned
  above; treated as a small edit inside the test plan.
- **Agent-research graph freshness.** The integration test runs against the
  current `code.db` which may need `cg update` to be fresh. If the test runs in CI
  without prior `cg update`, it will hit `NOT_INITIALIZED` (exit 3) — this is
  expected behavior, and the test must guard via skip-if-not-initialized.
  Concretely: the integration test attempts `read_only_connect`; on
  `GraphNotInitializedError`, the test calls `pytest.skip(...)` with a message
  pointing to `cg update`. Avoids false-failures in environments where the graph
  isn't built.
- **Hub-to-hub edges in `connects_clusters`.** If two excluded hubs share an
  edge, neither is in any cluster — the edge is ignored when computing
  `connects_clusters`. This is the natural reading of D-08 ("connects clusters"
  literally only counts cluster-membership endpoints). Implementation handles
  via filter; documented in module docstring.
- **`Cluster.name` field for clusters with 0 intra-edges.** If a cluster has no
  intra-edges (e.g., a 2-node cluster with one inbound edge from outside),
  intra-cluster in-degree is 0 for both members → tiebreak is alphabetical
  (first member). Handled by D-10 spec.

---

## File-by-File Plan-Input Summary

| File                                                                              | Action  | Lines | Tests touched   |
|-----------------------------------------------------------------------------------|---------|-------|-----------------|
| `packages/graph-io/src/graph_io/cluster.py`                                       | CREATE  | ~250  | test_cluster.py |
| `packages/graph-io/src/graph_io/cli/q_domain_clusters.py`                         | CREATE  | ~110  | integration     |
| `packages/graph-io/src/graph_io/cli/main.py`                                      | EDIT    | +2    | smoke           |
| `packages/graph-io/tests/test_cluster.py`                                         | CREATE  | ~250  | unit            |
| `packages/graph-io/tests/integration/__init__.py`                                 | CREATE  | 0     | (boilerplate)   |
| `packages/graph-io/tests/integration/test_cluster_cli.py`                         | CREATE  | ~120  | integration     |
| `packages/graph-io/pyproject.toml`                                                | EDIT    | +2    | (marker reg)    |

---

## RESEARCH COMPLETE
