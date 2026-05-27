# Phase 47: `cg domain-clusters` - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement deterministic connected-component clustering over the import-adjacency graph as a new CLI subcommand. Pure-Python, no LLM, no third-party dependencies beyond what `graph-io` already uses. Self-contained: testable in isolation, independent of Phases 42–46. Output feeds Phase 48 (`graph propose-domains`) which adds the LLM proposal layer on top.

**Code surface added:**
- `packages/graph-io/src/graph_io/cluster.py` — new module. Public function: `compute_clusters(conn: sqlite3.Connection, *, hub_threshold: float = 0.5) -> ClusterResult`.
- `packages/graph-io/src/graph_io/cli/q_domain_clusters.py` — new CLI subcommand following the `q_cross_cutting.py` pattern.
- `packages/graph-io/src/graph_io/cli/main.py` — register the new subcommand (small edit).
- `packages/graph-io/tests/test_cluster.py` — unit + property tests for clustering algorithm and determinism.
- `packages/graph-io/tests/integration/test_cluster_cli.py` — integration test against the agent-research graph itself.

**Code surface NOT modified:**
- `packages/graph-io/src/graph_io/derived_edges.py` — read-only consumer; no schema changes.
- `packages/graph-io/src/graph_io/import_scan.py` — not called from Phase 47 (clusterer queries the graph, not the filesystem).
- `wiki-io`, `agents/graph-wiki-agent/` — entirely untouched. Phase 47 is graph-io-only.

**Independence guarantee.** Phase 47 has no runtime dependencies on Phases 42–46. It can ship before, during, or after the entity restructure. Its only prerequisite is the existing `references` edges in the graph (already produced by `derived_edges.py` since v1.x).

**Not in scope (Phase 47):**
- LLM domain naming — Phase 48.
- Cycle detection on proposed domains — Phase 48.
- Writing `domains.proposed.yaml` — Phase 48.
- Modifying the `references` edge derivation — out of scope; we consume what's there.
- Modularity-based clustering (Louvain etc.) — explicitly rejected per D-01.
- Hierarchical clustering — not in v1.8.

</domain>

<decisions>
## Implementation Decisions

### Algorithm

- **D-01:** **Undirected weakly-connected components via union-find.** Each `(src_pkg, dst_pkg)` reference edge becomes an undirected edge; cluster = maximal connected subgraph after hub exclusion. Union-find implementation: `parent[]`/`rank[]` arrays, path compression. Pure stdlib. ~30 LOC for the core. Deterministic by construction once input is sorted (see D-05/D-09).

- **D-02:** **Algorithm steps in `compute_clusters`:**
  1. Load all `package` nodes from the graph; build a sorted list of names (alphabetical).
  2. Load all `references` edges where both endpoints are `package` kind; build adjacency.
  3. Compute hub set: packages whose `in_degree / (n_packages - 1) > hub_threshold` (D-04).
  4. Remove hub packages from the working node set; remove all edges touching hubs.
  5. Run union-find over remaining edges.
  6. Group surviving nodes by union-find root → clusters.
  7. For each removed hub: identify the union-find roots its excluded edges would have connected → `connects_clusters` list (D-08).
  8. Apply sort spec (D-09) and emit `ClusterResult`.

- **D-03:** **Singletons are clusters.** A package with no surviving edges after hub exclusion is its own cluster of size 1. Singletons feed into the degenerate-detection check (CLUSTER-02).

### Hub identification

- **D-04:** **Hub = in-degree fraction > `hub_threshold`.** Computation: `imported_by_count / (n_packages - 1)`. Default `hub_threshold = 0.5` per CLUSTER-01 signature. Configurable via `--hub-threshold` flag. Matches ROADMAP's "packages imported by >50% of others" wording exactly. Out-degree is NOT considered (rejected during discussion).

- **D-05:** **Hub detection happens BEFORE cluster computation.** Order matters: hubs are removed from both the node set and the edge set before union-find runs. Otherwise utility libraries would silently merge all clusters into one giant component.

- **D-06:** **`hub_threshold` range validation.** Valid range: `(0.0, 1.0]`. Threshold of 0.0 would exclude everything; threshold of 1.0 means "only packages imported by 100% of others" (almost never matches). CLI rejects out-of-range values with a clear error message. `compute_clusters` raises `ValueError` for the same.

### Output shape

- **D-07:** **`ClusterResult` dataclass + cluster + hub dataclasses:**
  ```python
  @dataclass(frozen=True)
  class Cluster:
      id: int                     # 0-indexed, assigned by sort order
      name: str                   # auto-derived per D-10; advisory only
      members: tuple[str, ...]    # sorted alphabetical
      size: int                   # == len(members)

  @dataclass(frozen=True)
  class CrossCuttingHub:
      name: str
      imported_by_count: int
      imported_by_fraction: float  # for human display
      connects_clusters: tuple[int, ...]  # cluster IDs sorted ascending

  @dataclass(frozen=True)
  class ClusterResult:
      clusters: tuple[Cluster, ...]
      cross_cutting: tuple[CrossCuttingHub, ...]
      hub_threshold: float
      n_packages_total: int
      degenerate_warning: str | None  # populated by D-13
  ```
  Tuples (not lists) so the dataclass is hashable + immutable. Sort order applied at construction time.

- **D-08:** **Hub `connects_clusters` semantics.** For each excluded hub, look at every (hub→other) and (other→hub) edge: collect the union-find root of `other`; map roots back to cluster IDs; deduplicate; sort ascending. This list tells Phase 48 "if you ignore this hub, these N clusters become reachable." Useful signal for downstream LLM proposal.

- **D-09:** **Sort spec (locks byte-identical JSON per CLUSTER-05):**
  - `clusters` outer sort: `key=lambda c: (-c.size, c.members[0])` (size descending, ties by first-member alphabetical).
  - `members` inner sort: alphabetical (`sorted(members)`).
  - `cross_cutting` outer sort: `key=lambda h: h.name` (alphabetical).
  - `connects_clusters` inner sort: ascending integer.
  - Cluster IDs assigned 0, 1, 2, ... AFTER outer sort applied. ID is purely positional in the sorted output.

- **D-10:** **Auto-derived cluster name = highest in-degree within cluster.** Among the cluster's `members`, pick the one with the highest count of incoming `references` edges from other members of the SAME cluster (intra-cluster in-degree). Tiebreak by alphabetical. This identifies the package the rest of the cluster gravitates around — a hint, not a contract. Phase 48 LLM may override. Computation done at result-build time using the already-loaded adjacency.

### Degenerate-cluster detection (CLUSTER-02)

- **D-11:** **Degenerate condition 1 — giant component.** If `max(c.size for c in clusters) / n_packages_total > 0.8` (more than 80% in one cluster). Emit warning to stderr:
  ```
  warning: domain clustering degenerate — cluster '<name>' contains <pct>% of packages.
  Likely cause: hub threshold too high (currently <threshold>), too few packages, or sparse imports.
  Try: cg domain-clusters --hub-threshold 0.3
  ```

- **D-12:** **Degenerate condition 2 — all singletons.** If `len(clusters) == n_packages_total` (every package is its own cluster). Emit:
  ```
  warning: domain clustering degenerate — every package is its own cluster.
  Likely cause: hub threshold too aggressive (currently <threshold>) or no inter-package imports.
  Try: cg domain-clusters --hub-threshold 0.7
  ```

- **D-13:** **Both conditions OR'd; first-matching wins.** Check giant first; if not giant, check all-singletons. Only one warning emitted (whichever fires). `ClusterResult.degenerate_warning` field captures the message (or `None`); the CLI prints it to stderr. Exit code is still 0 — degeneracy is a warning, not an error.

- **D-14:** **Warning suggests an adjusted threshold heuristic.** Giant → suggest `0.3` (more aggressive hub exclusion). All-singletons → suggest `0.7` (less aggressive). These are starting points, not formulae; the user iterates from there.

### Data source

- **D-15:** **`compute_clusters` queries the `edges` table directly.** Single SELECT:
  ```sql
  SELECT src_node.name, dst_node.name
  FROM edges e
  JOIN nodes src_node ON src_node.id = e.src
  JOIN nodes dst_node ON dst_node.id = e.dst
  WHERE e.kind = 'references'
    AND src_node.kind = 'package'
    AND dst_node.kind = 'package'
  ```
  Filters: both endpoints are `package` kind (excludes domain edges, test_suite edges, dependency edges); edge kind is `references` (the derived package-to-package edge produced by `derived_edges.py::_compute_references_and_depends_on`). Read-only. ~5–10 LOC.

- **D-16:** **No fallback to `scan_package_imports`.** If the graph isn't initialized, `cg domain-clusters` exits with `NOT_INITIALIZED` exit code (mirroring `q_cross_cutting.py` pattern). Filesystem-rebuild is NOT a fallback path — keeps Phase 47 deterministic and graph-snapshot-aligned with Phase 48.

### CLI

- **D-17:** **`packages/graph-io/src/graph_io/cli/q_domain_clusters.py`** follows the `q_cross_cutting.py` pattern exactly:
  - `add_arguments(parser)` — adds `--hub-threshold FLOAT` (default 0.5). `--fmt human|json` is the global flag (already handled at CLI dispatch level).
  - `run(args) -> int` — opens read-only connection via `graph_dir(args.workspace) / "code.db"` and `store.read_only_connect`. Handles `GraphNotInitializedError`, `SchemaMismatchError`. Calls `compute_clusters`. Renders via `_format.render(records, fmt=args.fmt)` OR direct print depending on existing patterns (verify in research). Returns `exit_codes.SUCCESS`.

- **D-18:** **Subcommand registration.** Edit `packages/graph-io/src/graph_io/cli/main.py` to add `domain-clusters` to the subcommand dispatch table. Pattern: same line shape as the other `q_*` subcommands. Mechanical addition.

- **D-19:** **`--hub-threshold` validation at CLI level.** If user passes a value outside `(0.0, 1.0]`, exit with `EXIT_USAGE` (or equivalent) and a clear error message. `compute_clusters` raises `ValueError` for the same, but CLI catches and translates to a friendlier exit.

### Human + JSON output formatting

- **D-20:** **JSON format** (CLUSTER-05 byte-identical):
  ```json
  {
    "hub_threshold": 0.5,
    "n_packages_total": 14,
    "degenerate_warning": null,
    "clusters": [
      {"id": 0, "name": "graph-io", "size": 5, "members": ["core-bedrock", "graph-io", "model-adapter", "subagent-runtime", "wiki-io"]},
      {"id": 1, "name": "workspace-io", "size": 2, "members": ["graph-wiki-agent", "workspace-io"]}
    ],
    "cross_cutting": [
      {"name": "click", "imported_by_count": 8, "imported_by_fraction": 0.57, "connects_clusters": [0, 1]},
      {"name": "pytest", "imported_by_count": 12, "imported_by_fraction": 0.86, "connects_clusters": [0, 1]}
    ]
  }
  ```
  Emit via `json.dumps(..., indent=2, sort_keys=False)` — keys in the order shown (manual ordering inside `dataclasses.asdict` pass). `imported_by_fraction` truncated to 2 decimals via formatting (display-only; the math uses full precision).

- **D-21:** **Human format** (markdown-style sections, cross_cutting first):
  ```
  # cg domain-clusters — agent-research
  
  Hub threshold: 0.5  ·  14 packages total
  
  ## Cross-cutting hubs (2)
    click       — imported by 8/14 (57%) — connects clusters 0, 1
    pytest      — imported by 12/14 (86%) — connects clusters 0, 1
  
  ## Cluster 0: graph-io (5 packages)
    - core-bedrock
    - graph-io
    - model-adapter
    - subagent-runtime
    - wiki-io
  
  ## Cluster 1: workspace-io (2 packages)
    - graph-wiki-agent
    - workspace-io
  ```
  Padding: column widths computed from longest name in section; ~80-column width target. Section ordering: cross_cutting before clusters (actionable signal first).

- **D-22:** **Empty case.** If `clusters` is empty AND `cross_cutting` is empty (no packages, or only orphan packages): JSON output is the same shape with empty arrays. Human output prints `No packages with import edges found.` to stderr, returns SUCCESS exit code.

### Module structure

- **D-23:** **`packages/graph-io/src/graph_io/cluster.py` contents:**
  - Module docstring describing algorithm + determinism guarantees.
  - Constants: `_DEFAULT_HUB_THRESHOLD = 0.5`, `_DEGENERATE_GIANT_RATIO = 0.8`, `_REFERENCES_KIND = "references"`, `_PACKAGE_KIND = "package"`.
  - Dataclasses: `Cluster`, `CrossCuttingHub`, `ClusterResult` (D-07).
  - Private union-find: `class _UnionFind` with `find()`, `union()` — ~30 LOC.
  - Private helpers: `_load_package_names(conn)`, `_load_reference_edges(conn)`, `_compute_hubs(adj, names, threshold)`, `_run_union_find(remaining_nodes, remaining_edges)`, `_build_cluster_records(roots, intra_cluster_in_degree)`, `_compute_connects_clusters(hub, original_adj, name_to_cluster_id)`, `_detect_degenerate(clusters, n_total, threshold)`.
  - Public function: `compute_clusters(conn, *, hub_threshold=0.5) -> ClusterResult`.

- **D-24:** **No new third-party dependencies.** Pure stdlib: `sqlite3`, `dataclasses`, `collections`. No `networkx`, no `python-louvain`.

### Tests

- **D-25:** **Unit tests in `packages/graph-io/tests/test_cluster.py`:**
  - `_UnionFind` correctness (find/union/path-compression).
  - Hub detection at threshold boundaries (0.499, 0.5, 0.501 with `n_packages=10`).
  - Connected-components on a known small graph (3 clusters of 2+3+1 nodes).
  - Degenerate giant condition.
  - Degenerate all-singletons condition.
  - Determinism: same graph, two `compute_clusters` calls → byte-identical `json.dumps(asdict(result), sort_keys=False)`.
  - Determinism with permuted node insertion order (fixed seed) → byte-identical output.
  - `hub_threshold` out-of-range raises `ValueError`.
  - Empty graph → empty `ClusterResult`.

- **D-26:** **Integration test in `packages/graph-io/tests/integration/test_cluster_cli.py`:**
  - Run `cg domain-clusters` (via subprocess or click test runner) against the actual `agent-research` `code.db`.
  - Assert: exit code 0, JSON parses, contains at least one cluster OR a degenerate-warning.
  - Assert: second invocation produces byte-identical stdout (`subprocess.check_output` × 2).
  - Mark as `@pytest.mark.integration` to skip in non-agent-research workspaces.

### Claude's discretion

- Exact union-find implementation (rank vs size optimization — equivalent for v1.8 sizes).
- Whether to memoize `_compute_hubs` adjacency reads (unnecessary at v1.8 scale).
- Internal helper signatures may consolidate (D-23 list is a sketch).
- Whether human-format padding handles unicode-wide characters (defer to v1.9; v1.8 vault names are ASCII).
- Whether to log clustering stats (n_hubs_excluded, n_edges_after_exclusion) — lean: no, keep output focused.
- Whether the CLI subcommand name is `domain-clusters` (canonical, per CLUSTER-03) or also accepts an alias (`clusters`, `cluster`) — lean: canonical only.
- Whether `Cluster.name` is `None`-able for empty clusters (cluster size 0 shouldn't happen, but defensive).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Direct predecessors
- (none) — Phase 47 is independent of Phases 42–46 per ROADMAP. Reads only the existing graph state.

### Milestone-level
- `.planning/REQUIREMENTS.md` §CLUSTER — CLUSTER-01..CLUSTER-05.
- `.planning/ROADMAP.md` Phase 47 — Goal + 5 success criteria.
- `.planning/STATE.md` — Pitfall 6 (degenerate clusters): hub-exclusion preprocessing + degenerate-cluster warning required in Phase 47 initial implementation (addressed by D-04..D-06 and D-11..D-14).

### Existing code (must be read by planner/researcher)
- `packages/graph-io/src/graph_io/cli/q_cross_cutting.py` — Template for the new CLI subcommand. Same connection-open / error-handling / dual-format-render shape.
- `packages/graph-io/src/graph_io/cli/main.py` — Subcommand registration pattern.
- `packages/graph-io/src/graph_io/cli/_format.py` — `render(records, fmt="human")` helper if used by other queries. Phase 47 may or may not use it depending on the existing convention (research confirms).
- `packages/graph-io/src/graph_io/queries.py::cross_cutting_packages` — Precedent for the "zero qualifying domain" query pattern; informs how to filter `(package, package)` reference edges.
- `packages/graph-io/src/graph_io/derived_edges.py` — Source of `references` edges. NOT modified by Phase 47; consumed read-only.
- `packages/graph-io/src/graph_io/store.py::read_only_connect` + `exit_codes.NOT_INITIALIZED` + `exit_codes.SCHEMA_MISMATCH` — Standard error-handling primitives.
- `packages/workspace_io/src/workspace_io/paths.py::graph_dir` — Workspace → code.db path resolution.

### Research baseline
- `.planning/research/ARCHITECTURE.md` §graph-io module map.
- `.planning/research/PITFALLS.md` Pitfall 6 (degenerate clusters — addressed by D-11..D-14).
- `.planning/research/FEATURES.md` §F9 (domain-clusters command) if present.

### Tests (where new Phase 47 tests land)
- `packages/graph-io/tests/test_cluster.py` (new) — unit + determinism + edge cases.
- `packages/graph-io/tests/integration/test_cluster_cli.py` (new) — CLI integration against agent-research graph.
- `packages/graph-io/tests/cli/test_cli_help.py` (if exists) — extend with `cg domain-clusters --help` exit-0 check (CLUSTER-04).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`q_cross_cutting.py` CLI structure** — direct template: connection open with `store.read_only_connect`; error mapping to `exit_codes`; dual JSON/human output. Phase 47 mirrors it.
- **`derived_edges.py::_compute_references_and_depends_on`** — produces the `references` edges Phase 47 queries. Already runs as part of `ops_update.run`. No new derivation needed.
- **`store.read_only_connect`** — opens code.db in WAL/read-only mode; raises `GraphNotInitializedError` if absent. Phase 47 follows the same pattern.
- **`exit_codes`** module — already defines NOT_INITIALIZED, SCHEMA_MISMATCH, SUCCESS, USAGE (verify exact set in research). Phase 47 reuses these.

### Established Patterns
- **CLAUDE.md §1 — uv workspace member packages.** `graph-io` is a leaf package; new `cluster.py` lands in its source tree, tests in `packages/graph-io/tests/`.
- **CLAUDE.md §8 — pytest + Hypothesis.** Hypothesis used in Phase 42's slug round-trip and Phase 43's frontmatter merge. Phase 47 may use it for clustering determinism with permuted inputs (D-25).
- **Frozen dataclasses with tuple collection fields** — Phase 43 `EntityWriteResult`, Phase 44 `IndexWriteResult` precedent. Phase 47's `Cluster`/`CrossCuttingHub`/`ClusterResult` follow the same shape.
- **Atomic CLI subcommand registration in `cli/main.py`** — adding a new line per the existing pattern (research confirms exact location).
- **JSON output via `json.dumps(asdict(result), ...)`** — Phase 43/44 precedent; key ordering controlled by the dataclass field declaration order plus explicit `sort_keys=False`.

### Integration Points
- **Phase 48 consumes `ClusterResult`.** The JSON output shape (D-20) IS the Phase 48 input contract. Phase 48 reads `cg domain-clusters --fmt json` output, fans clusters to LLM, validates names, writes `domains.proposed.yaml`. Phase 47's JSON is the IPC boundary.
- **No wiki-io or agent-graph-wiki integration.** Phase 47 lives entirely in graph-io.
- **`graph_dir(workspace) / "code.db"`** is the data source path — same as every other `q_*` subcommand.
- **`derived_edges.py` produces `references` edges as a derived-on-update step.** As long as `cg update` has run recently, Phase 47 has up-to-date data. No new "are derived edges fresh?" check in Phase 47.

</code_context>

<specifics>
## Specific Ideas

- **Hypothesis-based determinism test (D-25):** Hypothesis generates a random package graph (list of edges); compute_clusters runs twice with permuted input order via a fixed seed; assert `json.dumps(asdict(r1)) == json.dumps(asdict(r2))`. Concrete bug-finder for any "set iteration leaked into output" mistakes.
- **Known-graph fixture:** hand-build a small fixture graph with 6 packages: A,B,C form one cluster (A→B, B→C); D,E form another (D→E); F is a singleton; X is a hub imported by 5/6 packages. Assert: 3 clusters (sizes 3, 2, 1), 1 hub (X), connects_clusters for X = [0, 1, 2].
- **Threshold-boundary test:** with n_packages=10, package P imported_by 5 others. At hub_threshold=0.55 (5/9 = 0.555 — just under) → P is NOT a hub. At hub_threshold=0.50 → P IS a hub. Verify the inequality is strictly `>`.
- **Run against agent-research itself (CLUSTER-04):** the v1.7 graph already exists. Run `cg domain-clusters` from the integration test; capture output; verify it produces SOMETHING (cluster or warning), not crash. Snapshot the JSON for the current vault state (will need re-baselining as packages are added).
- **`cg domain-clusters --help` smoke test (CLUSTER-04):** subprocess invocation; assert exit code 0; assert `--hub-threshold` appears in stderr/stdout help text.
- **`cg --help` listing test:** subprocess `cg --help`; assert `domain-clusters` appears in the subcommand list.
- **Empty graph test:** read_only_connect to a fresh db with `package` nodes but zero `references` edges; assert n_packages_total > 0, clusters all size 1 (singletons), degenerate_warning triggers all-singletons message.

</specifics>

<deferred>
## Deferred Ideas

- **Louvain / modularity clustering** — D-01 explicitly rejected. Revisit if connected-components are too coarse for actual repo-scale domain proposals (v1.9 if needed).
- **Hierarchical clustering** — multi-level cluster trees (e.g., agglomerative). Out of scope for v1.8; the flat-clusters output is enough for Phase 48 LLM proposal.
- **Per-cluster cohesion scoring** — could emit `Cluster.cohesion: float` (intra-cluster-edge-density). Phase 48 could use it. Not load-bearing in v1.8; deferred.
- **Edge weighting by usage_count** — `references` edges have a `usage_count` attribute. Phase 47 ignores it (treats all edges as unit). Weighted clustering would allow finer separation but adds complexity. Defer to v1.9.
- **Configurable degenerate-detection thresholds** — D-11 (>80% giant) and D-12 (all-singletons) are constants. Could expose as flags (`--giant-ratio`, `--singleton-threshold`). v1.8 hard-codes; tune later if needed.
- **Output `Cluster.cohesion` and `connects_clusters` strength** — see above; cohesion deferred. Hub connect-strength (how many edges hub had to each cluster) could be useful for Phase 48 but is not in v1.8 output.
- **Cycle detection** — Phase 48 strips cycle-introducing edges (PROPOSE spec). Phase 47 does NOT pre-detect cycles in clusters because connected components don't have cycles in the partition sense — that's Phase 48's job on proposed domain edges.
- **Reading from `--graph-snapshot FILE` instead of workspace** — could let `cg domain-clusters --graph-snapshot path/to/db` cluster against an arbitrary db file. Useful for analysis tools. Not in v1.8 scope; standard workspace flow is sufficient.

</deferred>

---

*Phase: 47-`cg domain-clusters`*
*Context gathered: 2026-05-27*
