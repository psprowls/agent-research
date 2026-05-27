# Phase 47: `cg domain-clusters` - Discussion Log

**Date:** 2026-05-27
**Phase:** 47 — `cg domain-clusters`

This log captures the conversation that produced `47-CONTEXT.md`. For audit / retrospective use only — not consumed by downstream agents.

---

## Gray Area Selection

User selected all four offered areas:

1. Clustering algorithm + edge interpretation
2. Hub identification + re-attachment shape
3. JSON output schema (CLUSTER-05 byte-identical determinism)
4. Data source: query graph vs scan_package_imports directly

---

## Area 1: Clustering algorithm + edge interpretation

**Question:** What clustering algorithm + edge interpretation?

**Options presented:**
1. Undirected weakly-connected components (Recommended)  ← chosen
2. Strongly-connected (mutual) components
3. Louvain modularity-based clustering

**User chose:** Option 1 — undirected weakly-connected components via union-find. Pure stdlib (~30 LOC). Best fit for v1.8 domain-proposal use case.

→ Captured as D-01..D-03 (algorithm, steps, singletons-as-clusters).

---

## Area 2: Hub identification + re-attachment shape

**Q1 — Hub metric:**

Options:
1. In-degree fraction only (imported-by ratio) (Recommended)  ← chosen
2. Out-degree fraction (imports-many ratio)
3. Either in or out exceeds threshold

**User chose:** Option 1 — in-degree fraction only. Matches ROADMAP's "packages imported by >50% of others" wording. Out-degree not considered.

→ Captured as D-04..D-06 (formula, ordering, threshold validation).

**Q2 — Hub output shape:**

Options:
1. Separate `cross_cutting` array; each hub lists which clusters it connects  ← chosen
2. Separate `cross_cutting` array; just name + score
3. Annotated per-cluster: each cluster lists its `imported_hubs`

**User chose:** Option 1 — separate top-level `cross_cutting` array with `connects_clusters` field per hub. Most informative for Phase 48 LLM consumption.

→ Captured as D-07 (ClusterResult dataclass shape), D-08 (connects_clusters semantics).

---

## Area 3: JSON output schema + determinism

**Q1 — Cluster naming/IDs:**

Options:
1. Numeric IDs assigned by deterministic order (Recommended)
2. Auto-derived names from largest/most-central member  ← chosen
3. No IDs — cluster identity = sorted members tuple

**User chose:** Option 2 — auto-derived `name` plus numeric `id`. Highest in-degree within cluster wins (tiebreak alphabetical).

→ Captured as D-10. Note: name is advisory only (Phase 48 LLM may override).

**Q2 — Sort spec:**

Options:
1. Clusters by size desc, ties by alphabetical first-member; members alphabetical (Recommended)  ← chosen
2. Clusters alphabetical by first-member only

**User chose:** Option 1. Byte-identical determinism via full sort spec at every level.

→ Captured as D-09.

**Q3 — Human format:**

Options:
1. Markdown-like sections; cross_cutting at top, then clusters by size (Recommended)  ← chosen
2. Compact: one line per cluster, members comma-separated

**User chose:** Option 1 — markdown-like, cross_cutting first (actionable signal for Phase 48).

→ Captured as D-21.

---

## Area 4: Data source

**Question:** Where does `compute_clusters` get its import edges?

**Options presented:**
1. Query `edges` table directly (kind='references' for package→package)  (Recommended)  ← chosen
2. Call `import_scan.scan_package_imports(repo_root)` directly
3. Read `derived_edges.py` adjacency dict if exposed publicly, else fall back to (a)

**User chose:** Option 1 — single sqlite SELECT against the graph. Read-only. Same data source Phase 48 will consume — keeps Phase 47/48 aligned on a single graph snapshot.

→ Captured as D-15, D-16 (no filesystem fallback).

---

## Side Decisions Captured

The discussion also pinned:

- **D-11..D-14: Degenerate-cluster detection.** Two conditions OR'd, first-matching wins. Giant (>80% in one cluster) suggests `--hub-threshold 0.3`; all-singletons suggests `0.7`. Warning to stderr; exit 0.
- **D-17..D-19: CLI surface.** Mirrors `q_cross_cutting.py` structure; `--hub-threshold` flag added; validation at CLI catches out-of-range and translates to friendly exit.
- **D-20: JSON shape locked.** `{hub_threshold, n_packages_total, degenerate_warning, clusters:[...], cross_cutting:[...]}` with explicit key ordering via dataclass field order + `sort_keys=False`.
- **D-22: Empty case.** Empty arrays in JSON; stderr message in human format; SUCCESS exit code.
- **D-23..D-24: Module structure.** `packages/graph-io/src/graph_io/cluster.py`. Pure stdlib. No new third-party deps.
- **D-25..D-26: Tests.** Unit + Hypothesis determinism + integration against agent-research graph.

---

## Deferred Ideas

Captured in `47-CONTEXT.md` `<deferred>` section. Key items:

- Louvain / modularity clustering — explicitly rejected for v1.8 (revisit if connected-components too coarse).
- Edge weighting by `usage_count` — ignored in v1.8; potentially v1.9.
- Per-cluster cohesion scoring — Phase 48 may want; deferred.
- Hierarchical clustering — out of scope.
- Configurable degenerate-detection thresholds — hard-coded in v1.8.
- Cycle detection on clusters — Phase 48's job, not Phase 47's.

---

## Claude's Discretion

Items left to the planner's judgment (documented in `<decisions>` Claude's discretion block):

- Union-find variant (rank vs size — equivalent for v1.8 sizes).
- Internal helper signatures (D-23 list is a sketch).
- Whether human-format padding handles unicode-wide names (defer).
- Whether to log clustering stats inline (lean: no, keep output focused).
- Whether the CLI accepts a `clusters` alias for `domain-clusters` (lean: canonical only).

---

*Discussion concluded: 2026-05-27*
