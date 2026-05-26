# Phase 31: Domain Layer + Derived Edges - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

After Phase 31, `cg update` reads a single `<repo_root>/domains.yaml` (missing file = zero-domain mode, not an error) and lands two new emitters in `graph-io`:

1. **`domains.emit`** — Parses `domains.yaml`, emits `Domain` nodes, `belongs_to_domain` (Package → Domain) edges, and `domain_contains_domain` (Domain → Domain, tree) edges. Cycle detection skips cycle-participating containment edges (surgical recovery, per the SC#2 amendment in D-15) and prints a warning identifying the cycle. Unknown package names in `domains.yaml` print a warning with the full alphabetised list of known packages; `cg update` exits 0 (graceful degradation per DOMAIN-04).

2. **`derived_edges.compute`** — Runs AFTER `resolve.sweep` and AFTER the Phase 30 strict-tree invariant check. In a single transaction: `DELETE FROM edges WHERE kind IN ('references', 'depends_on', 'tests' AND child_id targets a Domain)` then recompute three derived edge classes from production-code imports + domain membership:
   - `references` (Domain → Package) for every (D, P) pair where D contains a Package that imports P and P ∉ D, with `usage_count` = number of distinct packages directly in D that import P (no transitive walks at compute time — DERIVED-04).
   - `depends_on` (Domain A → Domain B) for every (A, B) pair where a package in A imports a package in B, with `usage_count` = number of distinct (importing_pkg_in_A, imported_pkg_in_B) pairs.
   - `tests` (TestSuite → Domain) for every TestSuite whose `TestSuite → Package` edges (from Phase 30 D-09) all land in the SAME single Domain (≥2 packages required; multi-domain spans get NO Domain edge — multi-Package edges from Phase 30 already capture cross-cutting).

The import scan for the derived passes is shared with Phase 30 — `import_scan.scan_package_imports(pkg) → list[Package]` is refactored out of Phase 30's `test_suites.emit` into a shared helper. Test files (`is_test=true`) are EXCLUDED from `references` / `depends_on` derivation — test imports are captured by Phase 30's `TestSuite → Package` edges instead.

**Strictly NOT in this phase:**
- CLI surface adds (`cg list-domains`, `cg describe-domain`, `cg domain-refs`, `cg domain-deps`) → Phase 33 (success criteria's `cg list-domains` reference is one of the few SC-required CLI checks; Phase 31 may land a thin shim if the SC verification needs it, or Phase 33 includes the helper and Phase 31 ships only what's needed for SQL-level verification)
- `queries.py` helpers (`describe_domain`, `domain_refs`, `domain_deps`, `cross_cutting_packages`) → Phase 32
- Convention-based domain inference, import-graph clustering, LLM-proposed groupings → v1.7+ (DOMAIN-05, decision logged 2026-05-25)
- Transitive-membership storage for nested domains → never (DERIVED-04 forbids; queries walk `domain_contains_domain` at read time)
- "Shared" / "Common" domain — ontology spec §5 rejects this; cross-cutting packages have zero `belongs_to_domain` edges by design
- Brand sweep → Phase 34

Requirements addressed: DOMAIN-01, DOMAIN-02, DOMAIN-03, DOMAIN-04, DOMAIN-05, DERIVED-01, DERIVED-02, DERIVED-03, DERIVED-04.

**Cross-phase amendment:** SC#2 in ROADMAP.md needs a wording update before Phase 31 plans (see D-15). The planner must edit ROADMAP.md as a Wave 0 / pre-plan task.

</domain>

<decisions>
## Implementation Decisions

### `domains.yaml` schema (DOMAIN-01)

- **D-01:** **Flat map with explicit parent** as the schema shape. Top-level keys are domain names. Each domain entry is an object with fields:
  - `packages: [<name>, ...]` — REQUIRED. List of Package names (matching `Package.name`, e.g. `graph-io`, `billing-service`). Empty list is allowed (a domain with no direct package members but with subdomains via parent-pointer).
  - `parent: <domain-name>` — OPTIONAL. String. Names another top-level domain; produces a `domain_contains_domain` (parent → self) edge. Tree constraint enforced via cycle detection (DOMAIN-03).
  - `description: <string>` — OPTIONAL. Stored as `Domain.description` attr.
  - `owner: <string>` — OPTIONAL. Stored as `Domain.owner` attr (string for now; future schemas can extend).
  - **Unknown keys**: logged at WARNING level (`"domains.yaml: domain '<name>' has unknown key '<key>' — ignored"`) but do not fail the parse. Forward-compatible.

  Example:
  ```yaml
  billing:
    packages: [billing-service, billing-models]
    description: "Invoice generation and dunning"
  payments:
    packages: [payments-api]
    parent: financial
  financial:
    packages: []
    description: "Top-level financial domain"
  ```

- **D-02:** **Multi-domain membership is expressed by listing the same package name under multiple domain entries**. Example: `billing-service` appears under both `billing.packages` and `reporting.packages` → two `belongs_to_domain` edges. Aggregation happens at edge-emit time. No warning for intentional double-listing (Pat's call — DOMAIN-02 explicitly supports 0..N).

- **D-03:** **Fixed file location**: `<repo_root>/domains.yaml`. No CLI flag, no env var override, no multi-path probing. Missing file = zero-domain mode (DOMAIN-04): `domains.emit` is a no-op (no Domain nodes, no edges), `cg update` exits 0. The planner should still write a fixture under `tests/fixtures/sample_monorepo/domains.yaml` for Phase 31's tests.

- **D-04:** **Package-name validation**: any name in `<domain>.packages` that doesn't match a `Package.name` in the DB prints a warning: `"domains.yaml: package '<name>' (in domain '<dom>') is not a known package. Known packages: <alphabetised list of ALL Package.name values>"`. SC#4 requires the full list — print all, sorted, comma-separated. `cg update` does NOT fail; the offending entry is silently skipped (no edge emitted). The Domain node itself still emits even if all its packages are unknown.

- **D-05:** **`Domain.uri`** shape: `domain:<repo_org>/<repo_name>/<domain_name>` (consistent with Phase 28/29 URI helpers — add `domain_uri(ctx, domain_name)` to `uri.py`).

### YAML parsing & dependencies

- **D-06:** Use **`PyYAML`** (`yaml.safe_load`). Already commonly in Python projects; check `packages/graph-io/pyproject.toml` — add as a dep if not present. `safe_load` only — never `yaml.load` (security). Catch `yaml.YAMLError` and exit 4 (consistent with Phase 28 D-X schema-mismatch exit code) on parse failure, message: `"domains.yaml: YAML parse error: <details>"`.

### `references` edge semantics (DERIVED-01)

- **D-07:** `references` (Domain D → Package P) emitted when EVERY of: (a) at least one package directly in D imports P, (b) P is NOT directly in D. Transitive subdomain memberships do NOT participate at compute time (DERIVED-04). `usage_count` attr = number of distinct packages directly in D that import P. Domain.uri is the source; Package.uri is the target.

- **D-08:** **No edge if P is in D**. Cross-domain only — that's the whole point of `references`. If a package is in both D and some other domain D', emit references edges from D' → P (treat P as not in D' if it's a same-domain reference; but here D' contains P so no edge from D' → P; only edges from OTHER domains that import P).

### `depends_on` edge semantics (DERIVED-02)

- **D-09:** `depends_on` (Domain A → Domain B) emitted when at least one package in A directly imports at least one package in B (A ≠ B). One edge per (A, B) pair (no per-importing-package fan-out). `usage_count` attr = number of distinct (importing_pkg_in_A, imported_pkg_in_B) pairs. Same direction as `references` (caller → callee). Self-loops (A → A) are NEVER emitted.

### Import scanning — shared module

- **D-10:** **Shared scanner module**: refactor Phase 30's test-suite import scanner into `packages/graph-io/src/graph_io/import_scan.py`:
  ```python
  def scan_package_imports(conn, pkg: PackageNode, include_test_files: bool = False) -> set[PackageId]:
      """Return distinct first-party Package ids imported by files in pkg."""
  ```
  Phase 30's `test_suites.emit` is refactored to call this helper with `include_test_files=True` (scoped to TestSuite member files). Phase 31's `derived_edges.compute` calls with `include_test_files=False` (production code only).
  **Risk note:** Phase 30 is currently planning in a background agent (this session). The planner for Phase 31 should:
  1. Check Phase 30's plan files for whether `import_scan.py` is already factored out.
  2. If yes, build on it.
  3. If no, fold the refactor into Phase 31's Wave 1, plus a back-port edit to Phase 30's `test_suites.emit` to use the shared helper. Avoid two parallel scanners.

- **D-11:** **Test files excluded from derived edges**: `derived_edges.compute` queries `File` nodes WHERE `is_test=false` only. Test imports are reflected by Phase 30's `TestSuite → Package` edges and (per D-13 below) the new `TestSuite → Domain` edges; they do NOT count toward `references` or `depends_on`. Keeps domain coupling semantics about production code.

### `TestSuite → Domain` edge derivation (Phase 30 D-13 deferred)

- **D-12:** **Trigger**: emit `tests` edge `TestSuite → Domain(D)` when ALL of these hold:
  - The TestSuite has ≥2 distinct `TestSuite → Package` edges (single-package suites get no Domain edge — they're unit suites).
  - Every Package that TestSuite touches (via `TestSuite → Package`) has a `belongs_to_domain → D` edge.
  - No Package the TestSuite touches has a `belongs_to_domain` edge to ANY domain other than D.

- **D-13:** **Multi-domain suites**: if a TestSuite's packages span multiple domains, emit NO `TestSuite → Domain` edge. The multi-Package edges from Phase 30 already capture the cross-cutting nature. The Repository edge (Phase 30 D-12, K=5 threshold) captures whole-system suites. Avoids ambiguous "which domain does this suite test?" semantics.

- **D-14:** **Derivation home**: lives in `derived_edges.compute(conn, ctx)` alongside `references` and `depends_on`. Single transaction. Delete-all-then-recompute applies uniformly: `DELETE FROM edges WHERE kind='tests' AND child_id IN (SELECT id FROM nodes WHERE kind='Domain')` clears the prior pass's Domain-targeted tests edges without touching `TestSuite → Package` / `TestSuite → Repository` edges (those are Phase 30's responsibility; idempotency for those lives in `test_suites.emit`).

### Cycle detection (DOMAIN-03)

- **D-15:** **Surgical cycle recovery, not literal "skip ALL"**:
  - SC#2's literal wording ("skip all domain_contains_domain edges") needs an amendment. The planner MUST edit `ROADMAP.md` SC#2 as a Wave 0 task. New wording: *"A `domains.yaml` with a cycle (`payments → billing → payments`) causes `domains.emit` to print a warning identifying the cycle and skip ONLY the cycle-participating containment edges (keeping the acyclic remainder) without crashing — `cg update` exits 0."*
  - **Algorithm**: build the directed graph of (child → parent) from each domain's `parent` field. Run Tarjan's SCC. For every SCC of size > 1, identify the set of edges where both endpoints are in the SCC; do NOT emit those edges. Emit the rest.
  - **Warning format**: `"domains.yaml: cycle detected involving domains: <comma-separated SCC members>. Skipping <N> domain_contains_domain edge(s); the acyclic remainder is preserved."`. List each SCC if multiple.
  - Domain nodes still emit (DOMAIN-01: nodes are independent of containment edges). Belongs_to_domain edges still emit.

### Update.run() orchestration (continues Phase 30 D-21)

- **D-16:** **Call order** after Phase 31 lands:
  ```python
  packages.refresh(...)
  structural_nodes.emit(...)       # Phase 29
  entry_points.emit(...)           # Phase 30
  test_suites.emit(...)            # Phase 30 (uses import_scan)
  domains.emit(...)                # Phase 31 — NEW
  resolve.sweep(conn)
  _enforce_strict_tree_invariant(conn)  # Phase 30
  derived_edges.compute(...)       # Phase 31 — NEW (references, depends_on, TestSuite→Domain)
  ```
  Rationale: `domains.emit` writes Domain + belongs_to_domain + domain_contains_domain edges; these participate in `resolve.sweep` (URI-guarded by Phase 29 D-16) but are NOT part of the `physically_contains` tree so the invariant check is a no-op for them. `derived_edges.compute` runs LAST per DERIVED-03 ("after resolve.sweep completes"), reading the post-sweep stable graph.

### Derived-edge re-computation (DERIVED-03)

- **D-17:** **Delete-all-then-recompute** in a single transaction:
  ```python
  def compute(conn, ctx):
      with conn:  # single tx
          conn.execute("DELETE FROM edges WHERE kind IN ('references', 'depends_on')")
          conn.execute(
              "DELETE FROM edges WHERE kind='tests' AND child_id IN "
              "(SELECT id FROM nodes WHERE kind='Domain')"
          )
          _compute_references(conn, ctx)
          _compute_depends_on(conn, ctx)
          _compute_testsuite_domain(conn, ctx)
  ```
  - Trivially idempotent on re-run (SC#3: "running `cg update` a second time does not duplicate the derived edges").
  - One pass per edge class — easier to test in isolation.
  - `references` and `depends_on` are computed from a shared traversal of `(domain → packages → imports)` to avoid re-scanning the import graph twice. Internal implementation detail — exposed as two helpers but underpinned by one scan.

### Edge attrs (DERIVED-01, DERIVED-02)

- **D-18:** Both `references` and `depends_on` carry `usage_count: int` as an attr stored in `attrs_json` (consistent with Phase 28 D-10 pattern — only `uri` lives in column form). `TestSuite → Domain` `tests` edges carry NO additional attrs (mirrors Phase 30's `TestSuite → Package` edge shape).

### Claude's Discretion

- Domain.uri exact format (`domain:<repo_org>/<repo_name>/<domain_name>` is the proposed shape; planner can tweak to align with existing URI conventions in `uri.py`).
- Whether to add `cg list-domains` thin shim in Phase 31 (for SC#1's CLI verification) or rely on SQL-level verification only and defer the shim to Phase 33. Planner's call after reading Phase 33's plan scope.
- SCC algorithm specifics (Tarjan vs Kosaraju vs DFS-based; all O(V+E) and stdlib-implementable in ~30 LOC).
- Whether `import_scan.scan_package_imports` lives in `graph-io` or in a separate shared package — `graph-io` is fine (the test_suites.emit consumer is already in `graph-io`).
- `Domain.attrs_json` shape (e.g. should `parent` be denormalised on Domain.attrs_json as well as via the edge? Recommendation: edge-only; attrs_json carries description/owner/unknown-keys-residue only).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source-of-truth ontology spec
- `.planning/research/ONTOLOGY-SPEC.md` §3 (Domain node definition), §4.4 (Domain edges — belongs_to_domain, domain_contains_domain), §4.5 (Derived edges — references, depends_on; "Annotated with usage count"), §5 (Why DAG for domain membership; "No 'Shared' or 'Common' domain"), §6 (Nested domain semantics — tree, no transitive storage), §9 stage 7 (Domain assignment overlay), §9 stage 8 (Derived edge computation), §11 (Sample queries — "What does the Billing domain depend on")

### v1.6 research (mandatory)
- `.planning/research/ARCHITECTURE.md` — Domain emitter additive integration; derived_edges.compute pass placement
- `.planning/research/PITFALLS.md` — Pitfall list re cycle detection and idempotent derived edges
- `.planning/research/STACK.md` — confirms YAML parsing needs (PyYAML) and SCC algorithm requirements (stdlib)
- `.planning/research/FEATURES.md` — Phase 31 ships NO new CLI surface; SC#1's `cg list-domains` may need a Phase-31-internal thin shim OR be deferred to Phase 33 (see D-Claude's Discretion)

### Phase 30 prior context (just landed)
- `.planning/phases/30-entry-points-test-suites/30-CONTEXT.md` — D-09 (TestSuite→Package edges, basis for D-12 TestSuite→Domain derivation); D-10/D-11 (import scanner — D-10 here factors it out into a shared helper); D-13 (TestSuite→Domain explicitly deferred to Phase 31, this CONTEXT closes the loop); D-19/D-20 (strict-tree invariant check; D-16 here places domains.emit relative to it); D-21 (update.run call order — D-16 here extends it)

### Phase 29 prior context
- `.planning/phases/29-structural-nodes-containment-tree/29-CONTEXT.md` — D-16 (resolve.sweep URI-guard protects Domain nodes); D-18 (Package.language; not directly read by Phase 31 but useful context for import scanner cross-language behavior)

### Phase 28 prior context
- `.planning/phases/28-schema-v2-uri-foundation/28-CONTEXT.md` — D-10 (URI in column; Domain.uri lives in `uri` column, description/owner in attrs_json); D-04/D-05/D-07/D-11 (RepoContext threading, used by domains.emit and derived_edges.compute)

### Requirements + roadmap
- `.planning/REQUIREMENTS.md` — DOMAIN-01..05 (lines 54–58), DERIVED-01..04 (lines 62–65), pending-phase mapping lines 210–218
- `.planning/ROADMAP.md` — Phase 31 block + SC#1–5. **SC#2 NEEDS AMENDMENT** (D-15) — Wave 0 task for the planner

### Existing graph-io code (read before editing)
- `packages/graph-io/src/graph_io/update.py` — `run()` orchestration; D-16 inserts `domains.emit` between `test_suites.emit` and `resolve.sweep`, and inserts `derived_edges.compute(...)` after `_enforce_strict_tree_invariant(...)`
- `packages/graph-io/src/graph_io/test_suites.py` (Phase 30 deliverable) — `import_scan` extraction lands here; D-10 covers this
- `packages/graph-io/src/graph_io/upsert.py` — `_upsert_node` for Domain writes (Phase 28 D-10 path); `_upsert_edge` for belongs_to_domain / domain_contains_domain / references / depends_on / TestSuite→Domain edges
- `packages/graph-io/src/graph_io/resolve.py` — `sweep()` URI-guard (Phase 29 D-16) — verify Domain nodes survive; they carry uri so they should
- `packages/graph-io/src/graph_io/uri.py` — add `domain_uri(ctx, domain_name)` helper following Phase 28 conventions
- `packages/graph-io/src/graph_io/packages.py` — `Package.name` is the join key for D-04's validation warning

### YAML lib
- `PyYAML` >=6.0 — add to `packages/graph-io/pyproject.toml` deps if not already present. `yaml.safe_load` only.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 30 import scanner** (lives in `test_suites.py` after Phase 30 ships) — D-10 factors it into `import_scan.py` as a shared helper. The refactor is small.
- **`_upsert_node` / `_upsert_edge`** for Domain nodes and all four new edge classes (Phase 28 D-10 pattern; URI in column, attrs_json for description/owner/usage_count).
- **`uri.py` helper pattern** — add `domain_uri(ctx, domain_name)` consistent with `pkg_uri` / `subpkg_uri` / `file_uri` / `entry_point_uri` / `testsuite_uri` shape from Phases 28/29/30.
- **Phase 30 D-14 transaction-per-pass pattern** — `derived_edges.compute` wraps the whole delete-then-recompute in one `with conn:` block.
- **`Package.name` from `packages.py`** — D-04 reads this to validate `domains.yaml` package references and to format the warning's known-package list.
- **Phase 29 D-16 URI-guard in `resolve.sweep`** — Domain nodes carry `uri` so they survive the sweep without further changes to `resolve.py`.

### Established Patterns
- **Additive emitter slot pattern** — `domains.emit(conn, repo_root=..., ctx=..., skip_dirs=...)` follows Phase 29 D-23 / Phase 30 D-21.
- **Single-transaction emit/compute** — Phase 30 D-14 (re-parent) + D-19(b) (invariant check) establish the pattern. Phase 31's `domains.emit` and `derived_edges.compute` both follow.
- **Idempotency via delete-then-insert** — Phase 30 D-14 pattern reused at finer granularity: derived edges are completely rebuilt every pass (D-17).
- **`with conn:` wraps full module emit** — already standard in Phase 29 `structural_nodes.emit`. Same pattern here.
- **Warning emission via existing logger** — `graph-io` already has a logger (used by Phase 29 D-11 generated-file content scan). Reuse.

### Integration Points
- **Phase 30 → Phase 31**: `import_scan` extraction is the key seam. D-10 covers the back-port if Phase 30 lands its scanner inline.
- **Phase 31 → Phase 32**: `queries.py` helpers (`describe_domain`, `domain_refs`, `domain_deps`, `cross_cutting_packages`) consume the edges Phase 31 emits. Phase 32's planner reads Phase 31's edge shape decisions (D-08, D-09, D-18).
- **Phase 31 → Phase 33**: CLI surface (`cg list-domains`, `cg describe-domain`, `cg domain-refs`, `cg domain-deps`) — Phase 31 emits the data; Phase 33 surfaces it. Phase 31 may land a thin `cg list-domains` shim if SC#1 verification requires it (Claude's Discretion).
- **Update.run call order is locked by D-16** — any future emitter that depends on derived edges runs AFTER `derived_edges.compute`. Phase 32/33 should respect this.

</code_context>

<specifics>
## Specific Ideas

- D-15 SCC implementation: Python stdlib doesn't have a one-liner; ~30 LOC iterative Tarjan or Kosaraju. Recommend Tarjan (single DFS pass, no graph reversal). Put it in `domains.py` as a module-private helper `_detect_cycles(parent_map: dict[str, str]) -> list[list[str]]` returning a list of SCCs with len > 1.

- D-17 single-traversal compute (pseudocode):
  ```python
  def _compute_references_and_depends_on(conn, ctx):
      # Walk each Domain D, find packages directly in D, scan their imports
      domain_pkgs = {d_id: set(_packages_in_domain(conn, d_id)) for d_id in all_domains}
      pkg_imports = {p_id: scan_package_imports(conn, p_id) for p_id in all_packages}
      pkg_domains = {p_id: set(_domains_of_package(conn, p_id)) for p_id in all_packages}
      ref_buckets = defaultdict(set)   # (D, P) -> {importing_pkgs_in_D}
      dep_buckets = defaultdict(set)   # (A, B) -> {(importing_pkg, imported_pkg)}
      for d, pkgs_in_d in domain_pkgs.items():
          for src in pkgs_in_d:
              for tgt in pkg_imports[src]:
                  tgt_domains = pkg_domains.get(tgt, set())
                  if d not in tgt_domains:   # references criterion (D-08)
                      ref_buckets[(d, tgt)].add(src)
                  for b in tgt_domains:
                      if b != d:             # depends_on criterion (D-09; A != B)
                          dep_buckets[(d, b)].add((src, tgt))
      # Bulk INSERT
      for (d, p), srcs in ref_buckets.items():
          _upsert_edge(conn, kind='references', parent=d, child=p, usage_count=len(srcs))
      for (a, b), pairs in dep_buckets.items():
          _upsert_edge(conn, kind='depends_on', parent=a, child=b, usage_count=len(pairs))
  ```

- D-12 TestSuite→Domain compute (pseudocode):
  ```python
  def _compute_testsuite_domain(conn, ctx):
      for suite_id in all_test_suites:
          pkg_targets = _suite_to_package_targets(conn, suite_id)
          if len(pkg_targets) < 2:
              continue
          domain_sets = [_domains_of_package(conn, p) for p in pkg_targets]
          if not all(domain_sets):           # any package with zero domains → skip
              continue
          intersection = set.intersection(*domain_sets)
          if len(intersection) == 1 and all(ds == intersection for ds in domain_sets):
              [d] = intersection
              _upsert_edge(conn, kind='tests', parent=suite_id, child=d)
  ```

- D-04 unknown-package warning prototype (50+ packages):
  ```
  WARNING: domains.yaml: package 'billng-service' (in domain 'billing') is not a known package.
  Known packages: agent-research-eval-harness, billing-models, billing-service, core-bedrock, deepagents-cli, graph-io, graph-wiki-agent, ... (full sorted list)
  ```

- D-15 cycle warning prototype:
  ```
  WARNING: domains.yaml: cycle detected involving domains: payments, billing.
  Skipping 2 domain_contains_domain edge(s); the acyclic remainder is preserved.
  ```

- Fixture extension for tests/fixtures/sample_monorepo/: add `domains.yaml` (one cycle-free case + a separate fixture with a cycle for SC#2 testing).

- Schema validation tests should cover: missing `packages:` field; non-list `packages:` value (e.g. string); unknown top-level key; unknown package name; cycle of length 2 and length 3; orphan parent reference (parent points to non-existent domain — treat as warning, skip the containment edge).

</specifics>

<deferred>
## Deferred Ideas

- **Convention-based domain inference** — folder-name or import-graph clustering; LLM-proposed groupings. v1.7+. DOMAIN-05 explicitly defers.
- **Transitive subdomain edge bubbling at compute time** — ontology spec §6 says edges "bubble up at read time"; Phase 31 stores only direct edges (DERIVED-04). Phase 32's `queries.py` helpers will implement bubble-up at query time.
- **`tagged_with` mechanism for utility-package categorization** — ontology spec §5 mentions; not a Phase 31 deliverable.
- **Cross-repo Domain support** — ontology spec §11.3 (open question 3). Phase 31 assumes single-repo `domains.yaml`. Multi-repo domain composition is a v2.0 concern.
- **`Domain.owner` as a structured ref** (e.g. Team node) — Phase 31 stores it as a plain string. Future ontology extension could promote to a Team / Person node.
- **Per-package import-graph caching** — D-10's `scan_package_imports` runs every `cg update`. If a real repo is slow, add a caching layer keyed on File mtime. Defer until measured.
- **Wildcard package matching in `domains.yaml`** — e.g. `packages: ['billing-*']` glob expansion. Defer; explicit names only in v1.6.
- **Reverse-direction domains: list on packages** — was considered (allow each Package to declare its domains via attrs). Rejected — single source of truth (`domains.yaml`) is cleaner.
- **Edge attrs `usage_count_transitive`** — DERIVED-04 forbids transitive storage; if a query needs this it can compute on read.

</deferred>

---

*Phase: 31-domain-layer-derived-edges*
*Context gathered: 2026-05-25*
