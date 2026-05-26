# Phase 32: Query Layer Extensions - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

After Phase 32, `packages/graph-io/src/graph_io/queries.py` exposes a complete read-only API over the v1.6 graph:

1. **Extended `find`** (QUERY-01) — accepts new `kind` filters: `repository`, `subpackage`, `entry_point`, `test_suite`, `domain`. Existing kinds continue to work unchanged.

2. **Extended `describe_package`** (QUERY-02) — PackageDescription gains three new fields: `domains: list[str]`, `entry_points: list[EntryPointDescription]`, `test_suites: list[SuiteDescription]`. Existing fields unchanged. Backwards-compatible (new fields default to empty list when no data exists).

3. **Extended `describe_path`** (QUERY-03) — PathDescription gains `role_flags: dict[str, bool] | None`. Populated only when the resolved node has `kind='File'`; `None` for Repository / Package / SubPackage / Domain / etc. paths. Exactly 7 keys when populated: `is_importable`, `has_main`, `is_test`, `is_config`, `is_generated`, `is_type_only`, `is_executable`.

4. **16 new read-only helpers** (QUERY-04) — `describe_repository`, `describe_domain`, `describe_entry_point`, `describe_test_suite`, `domain_references`, `domain_depends_on`, `cross_cutting_packages`, `tests_for_package`, `tests_for_domain`, `entry_points_for_package`, `list_repositories`, `list_packages`, `list_entry_points`, `list_test_suites`, `list_domains`, `list_scripts`. Three of them (`tests_for_domain`, `domain_references`, `domain_depends_on`) bubble through `domain_contains_domain` via SQLite recursive CTE at query time per ontology spec §6.

5. **Test coverage** (SC#4) — each new helper has ≥1 unit test against a session-scoped seeded in-memory DB built by running `cg update --full` on `tests/fixtures/sample_monorepo/` (the canonical fixture from Phase 29 D-22 / Phase 30 D-19a, extended with `domains.yaml` by Phase 31 D-03). Edge-case tests (empty DB, cycle-fixture from Phase 31, single-domain repo) use targeted seeds. All tests open read-only connections.

**Strictly NOT in this phase:**
- CLI surface adds (`cg list-domains`, `cg describe-repo`, `cg what-tests`, `cg list-scripts`, etc.) → Phase 33 (Phase 32 ships the underlying helpers; Phase 33 wires them to subcommands)
- Brand sweep → Phase 34
- New emitters or edge types — Phase 32 is read-only over Phases 28-31's output
- Performance optimization (materialised closure tables, query caching, pagination) — Phase 32 ships correctness; perf is deferred to v1.7 if measured
- Multi-language import resolution beyond what Phase 30/31 already produce
- Write-path testing — every Phase 32 helper opens a `mode=ro` connection

Requirements addressed: QUERY-01, QUERY-02, QUERY-03, QUERY-04.

</domain>

<decisions>
## Implementation Decisions

### Dataclass design

- **D-01:** **Extend `PackageDescription` in place** with three new fields:
  ```python
  @dataclass(frozen=True)
  class PackageDescription:
      name: str
      language: str
      version: str
      files: list[str]
      counts: dict[str, int]
      # NEW (default to empty list — backwards-compatible)
      domains: list[str] = field(default_factory=list)
      entry_points: list[EntryPointDescription] = field(default_factory=list)
      test_suites: list[SuiteDescription] = field(default_factory=list)
  ```
  Phase 27 callers see empty lists for new fields. No subclass split, no shadow API. New attrs MUST have `default_factory=list` so the dataclass stays compatible with positional construction.

- **D-02:** **New minimal dataclasses** in queries.py, all `@dataclass(frozen=True)`:
  - `RepoDescription(name, uri, owner, url, default_branch, package_count)`
  - `DomainDescription(name, uri, parent: str | None, description: str | None)`
  - `EntryPointDescription(name, uri, kind: str, callable: str | None, implemented_by_path: str | None, source: str)`
  - `SuiteDescription(name, uri, kind: str, file_count: int)`

  Keep nested types lightweight. Callers needing more detail call the dedicated `describe_<thing>` helper. EntryPointDescription's `kind` is `"executable" | "library"` per Phase 30 D-08; `source` is `"pyproject.scripts" | "pyproject.entry-points" | "package.json.bin" | "package.json.main" | "package.json.module" | "package.json.exports"` etc. (Phase 30 D-08 / D-07).

- **D-03:** **`describe_<thing>` helpers** return the corresponding Description dataclass:
  - `describe_repository(conn) -> RepoDescription` (always exactly one Repository per DB per Phase 29 D-01; no arg needed)
  - `describe_domain(conn, name) -> DomainDescription | None`
  - `describe_entry_point(conn, package_name, entry_name) -> EntryPointDescription | None`
  - `describe_test_suite(conn, suite_name) -> SuiteDescription | None`
  All return `None` on missing lookup (consistent with existing queries.py pattern; no exceptions for graceful CLI degradation in Phase 33).

- **D-04:** **`list_<thing>` helpers** return `list[NodeRecord]` (the existing dataclass from queries.py). Sorted alphabetically by `name`. No pagination in v1.6 — repos are bounded; if a real repo hits 10k+ nodes we revisit.

- **D-05:** **`describe_path`** extension adds `role_flags: dict[str, bool] | None`. dict keys are the 7 role-flag names exactly as stored in File node attrs. None when resolved node is not a File. Don't introduce a `RoleFlags` dataclass — the dict is enough and survives Phase 29's role-flag set being extended in v1.7.

### Bubble-up at query time

- **D-06:** **Three helpers walk `domain_contains_domain`** via SQLite recursive CTE:
  - `tests_for_domain(conn, domain_name)` — returns TestSuites covering the domain or any descendant
  - `domain_references(conn, domain_name)` — returns Packages referenced from the domain or any descendant (with aggregated usage_count)
  - `domain_depends_on(conn, domain_name)` — returns Domains depended on by the domain or any descendant

  All others (`describe_domain`, `list_domains`, etc.) return direct data only. Ontology spec §6 calls out bubble-up at READ time; these three are the natural surface for it.

- **D-07:** **Recursive CTE pattern**:
  ```sql
  WITH RECURSIVE descendants(id) AS (
    SELECT id FROM nodes WHERE name = :domain_name AND kind = 'Domain'
    UNION ALL
    SELECT e.child_id FROM edges e
    JOIN descendants d ON e.parent_id = d.id
    WHERE e.kind = 'domain_contains_domain'
  )
  SELECT ... FROM edges WHERE parent_id IN descendants AND kind = '<target_kind>'
  ```
  Cycle protection: Phase 31 D-15 guarantees no cycles in `domain_contains_domain`, so the CTE terminates. Single DB round-trip. Idiomatic SQLite.

- **D-08:** **usage_count aggregation when bubbling**:
  - `domain_references(D)` returns rows `(Package, total_usage_count, distinct_domain_count)` where `total_usage_count = SUM(usage_count)` across the references edges from D and its descendants pointing at the same package; `distinct_domain_count = COUNT(DISTINCT domain)` of those source domains. Both metrics exposed; CLI can pick.
  - `domain_depends_on(D)` returns rows `(Domain, total_usage_count)` where `total_usage_count = SUM(usage_count)` across depends_on edges from D and its descendants pointing at the same target domain. Self-dependencies (D's descendant depends on D itself) are still excluded.

- **D-09:** **`tests_for_domain` query-time inference** — return a UNION of:
  (a) TestSuites with a direct `TestSuite → Domain(D-or-descendant)` edge (from Phase 31 D-12 — single-domain suites), AND
  (b) TestSuites whose `TestSuite → Package` edges include any package with a `belongs_to_domain → D-or-descendant` edge (catches Phase 31 D-13 multi-domain suites which have NO Domain edge).

  Captures cross-cutting suites without breaking Phase 31's emit-side cleanliness. SQL is a UNION DISTINCT of two SELECTs.

### cross_cutting_packages

- **D-10:** **Strict definition**: packages with `COUNT(belongs_to_domain edges) = 0`. Exactly matches ontology spec §11.4 ("zero `belongs_to_domain` edges"). The "No Shared/Common domain" principle (spec §5) is the architectural anchor — zero is the signal.

- **D-11:** **Ranking metric** = **sum of usage_count across incoming references edges** (NOT distinct-domain count). This is a deliberate divergence from the ontology spec's "ranked by incoming references count from distinct domains" wording — user chose "how heavily depended on" over "how broadly depended on". Note for downstream: this is a query-layer choice, not a spec amendment; ontology spec stays as written.

- **D-12:** **Output shape**: `cross_cutting_packages(conn) -> list[tuple[PackageDescription, int]]` sorted by score descending (score = total usage_count). Caller gets full Package detail in one call; no second describe_package roundtrip needed. Ties broken alphabetically by name (stable, predictable).

  ```python
  def cross_cutting_packages(conn) -> list[tuple[PackageDescription, int]]:
      # ... join nodes (kind=Package) LEFT JOIN edges (belongs_to_domain)
      # WHERE belongs_to_domain edge is NULL (zero-domain)
      # JOIN edges (references where child = this package), SUM(usage_count) AS score
      # ORDER BY score DESC, name ASC
  ```

### Test fixture strategy

- **D-13:** **Hybrid fixture strategy**:
  - **Happy-path fixture**: `tests/fixtures/sample_monorepo/` (Phase 29 D-22 / Phase 30 D-19a / Phase 31 D-03's domains.yaml extension). Session-scoped pytest fixture `seeded_db` runs `cg update --full` against a tmp_path-copy of this fixture once per test session, then yields a read-only connection (`mode=ro`).
  - **Targeted edge-case fixtures**: dedicated per-test seeds for empty-DB queries, the Phase 31 cycle fixture (if it exists separately), single-domain repo, single-package-no-domain repo, large-domain-tree-fixture. Use raw SQL inserts via `_upsert_node` / `_upsert_edge` for these — no need to run emitters.

- **D-14:** **Session scope, read-only access**:
  ```python
  @pytest.fixture(scope="session")
  def seeded_db(tmp_path_factory):
      repo_dir = tmp_path_factory.mktemp("queries_seed") / "repo"
      shutil.copytree("tests/fixtures/sample_monorepo", repo_dir)
      db_path = repo_dir / ".graph-wiki" / "graph" / "code.db"
      _run_cli(["cg", "update", "--full"], cwd=repo_dir)
      yield sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
  ```
  Safe because the fixture is read-only by design. Fast: one `cg update --full` per CI run vs N runs for function scope.

- **D-15:** **Sample_monorepo fixture extensions needed in Phase 32** — if Phase 31 didn't ship them all:
  - At least 2 Domains with one parent-child relationship (`financial → billing`) to exercise the CTE
  - At least 1 cross-cutting package (zero domains, referenced from multiple domains' packages) for `cross_cutting_packages` test
  - At least 1 EntryPoint with a `callable` (e.g. `pkg.cli:main`) and at least 1 wildcard `exports` EntryPoint for `describe_entry_point` test
  - At least 2 TestSuites, one single-domain (D-12 direct edge) and one multi-domain (D-13 inferred edge), for `tests_for_domain` UNION query
  The Phase 32 planner inspects what Phase 31's `domains.yaml` already provides; back-port additions as a Wave 0 task if needed.

### Reused queries.py conventions

- **D-16:** **Read-only connections**: every helper signature is `helper(conn, ...) -> ...` and assumes `conn` was opened with `mode=ro`. Document this in the module-level docstring (the existing one already says "All callers open a read-only conn" — extend if needed). No INSERT/UPDATE/DELETE SQL in queries.py — enforce via code review, not runtime check.

- **D-17:** **`_RESOLVED_FILTER` reuse**: the existing queries.py constant `_RESOLVED_FILTER` for excluding unresolved edges (`(e.attrs_json IS NULL OR json_extract(e.attrs_json, '$.resolution') != 'unresolved')`) is reused for the new helpers where applicable (e.g. `tests_for_package` should not return suites where the tests edge resolution is unresolved).

- **D-18:** **JSON attrs extraction**: helpers that read attrs (e.g. `usage_count` from references edges, `kind` from EntryPoint) use `json_extract(attrs_json, '$.key')` — consistent with the existing `_RESOLVED_FILTER` style.

### `find` extension (QUERY-01)

- **D-19:** **`find(conn, kind=None, ...)`** existing signature is extended — `kind` parameter now accepts the new node kinds. Use `kind in ('Function', 'Class', 'Method', 'File', 'Package', 'Repository', 'SubPackage', 'EntryPoint', 'TestSuite', 'Domain')` as the allow-list (case-sensitive, matches the strings emitters write). Unknown kinds raise `ValueError` with the allow-list in the message (existing behavior — extend, don't change).

### Claude's Discretion

- Exact SQL strings (single-statement vs multi-statement, JOIN order, sub-select strategy) — planner picks idiomatic SQLite, can prefer CTE chaining over deeply nested sub-queries for readability.
- list_* sort order beyond alphabetical (e.g. `list_test_suites` could sort by file_count desc; alphabetical is fine for v1.6).
- Whether to inline the recursive-descendants CTE in each of the three bubble-up helpers or extract a helper function that returns the descendant id set (Python list → IN clause). Recommend inline CTE for ≤3 helpers; extract if it grows.
- Internal helper functions vs module-private constants for shared SQL fragments. queries.py already uses one constant (`_RESOLVED_FILTER`); add more as needed.
- `entry_points_for_package` ordering: by `kind` (executable first) then alphabetical, or pure alphabetical — planner picks.
- `list_scripts` deduplication: a File node that's the target of an EntryPoint AND has `is_executable=true` could appear in both branches. Planner decides: union all (with dedup by node id) OR explicit annotation `(kind: declared | conventional)`. SC#4 in Phase 33 ("union of EntryPoint kind:executable and File is_executable:true") suggests UNION with implicit dedup; verify with the Phase 33 planner.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source-of-truth ontology spec
- `.planning/research/ONTOLOGY-SPEC.md` §3 (Node kinds, including v1.6 additions), §4 (Edge kinds, including derived `references`, `depends_on`, `tests`), §6 (Nested domain semantics — explicit bubble-up at READ time), §11 (Sample queries — "What does the Billing domain depend on", "Which utility packages are most widely used")

### Phase 31 prior context (decisions Phase 32 reads at query time)
- `.planning/phases/31-domain-layer-derived-edges/31-CONTEXT.md` — D-07 (direct-only usage_count; Phase 32 bubbles), D-12/D-13 (TestSuite→Domain trigger; Phase 32 query-time infers cross-cutting suites in D-09), D-15 (no cycles in domain_contains_domain — CTE termination guarantee), D-17 (delete-then-recompute means edges always reflect latest), D-18 (usage_count in attrs_json — D-08 here reads it)

### Phase 30 prior context
- `.planning/phases/30-entry-points-test-suites/30-CONTEXT.md` — D-03/D-04 (EntryPoint.callable attr; D-02 here exposes it via EntryPointDescription), D-07/D-08 (EntryPoint source values; D-02 here lists them), D-12 (K=5 Repository edge threshold; not bubbled by Phase 32), D-13 (TestSuite→Domain deferred to Phase 31; D-09 here infers at query time)

### Phase 29 prior context
- `.planning/phases/29-structural-nodes-containment-tree/29-CONTEXT.md` — D-09 amended by Phase 30 D-01 (role flags on File nodes; D-05 here exposes them as role_flags dict in PathDescription)

### Phase 28 prior context
- `.planning/phases/28-schema-v2-uri-foundation/28-CONTEXT.md` — D-10 (URI in column form, attrs in attrs_json; D-02 here reads both shapes)

### Requirements + roadmap
- `.planning/REQUIREMENTS.md` — QUERY-01..04 (lines 74–77); QUERY-04 enumerates the 16 helpers; pending-phase mapping lines 219–222
- `.planning/ROADMAP.md` — Phase 32 block + SC#1–4. SC#4 ("each new query helper has at least one unit test passing against a seeded in-memory DB BEFORE Phase 33 begins") is the test-fixture decision driver (D-13/D-14)

### Existing graph-io code (read before editing)
- `packages/graph-io/src/graph_io/queries.py` — current state: PackageDescription, PathDescription, NodeRecord, CallRecord, ImportRecord dataclasses; `_RESOLVED_FILTER` constant; existing helpers (find, describe_package, describe_path, callers, callees). Phase 32 extends in place.
- `packages/graph-io/src/graph_io/upsert.py` — `_upsert_node` / `_upsert_edge` used by D-13's targeted-edge-case fixtures (raw inserts for cycle / empty / etc. cases).
- `packages/graph-io/tests/test_queries.py` (if it exists; else create) — new test module home.
- `packages/graph-io/tests/fixtures/sample_monorepo/` — canonical happy-path fixture; D-13 reuses it.

### Test helper landmarks
- Phase 29 D-22 / Phase 30 D-19a established the `_run_cli` helper + tmp_path-copied-fixture pattern. D-14 reuses it for the session-scoped seeded_db fixture.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **PackageDescription / PathDescription / NodeRecord** — extend in place per D-01 / D-05. Don't fork.
- **`_RESOLVED_FILTER` constant** — Phase 32 SQL JOINs reuse it (D-17).
- **`_run_cli` + tmp_path fixture pattern** (Phase 29 D-22 / Phase 30 D-19a) — D-14 builds on it.
- **`sample_monorepo` fixture** — Phase 31 should land `domains.yaml`; Phase 32 may need to add a multi-domain TestSuite plus a cross-cutting package per D-15.
- **`_upsert_node` / `_upsert_edge`** for raw-SQL targeted seeds (D-13 edge-case fixtures).

### Established Patterns
- **Read-only connections** in queries.py (`sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`) — D-16 enforces continuity.
- **Frozen dataclasses** for return types (`@dataclass(frozen=True)`) — every new Description type follows this.
- **`None` on missing lookup** (existing `describe_package(name)` returns None if name doesn't match) — D-03 keeps this convention.
- **JSON extraction via `json_extract`** — Phase 32 SQL reads `attrs_json` for usage_count, kind, etc.
- **Module-private SQL constants** at the top of queries.py — Phase 32 may add `_DOMAIN_DESCENDANTS_CTE` if shared by multiple helpers.

### Integration Points
- **Phase 31 emit-side output is the input** — every Phase 32 helper queries the post-Phase-31 graph. If Phase 31 doesn't emit something, Phase 32 returns empty / None gracefully (no crashes on partial graphs).
- **Phase 33 CLI is the primary downstream consumer** — every Phase 32 helper has a Phase 33 subcommand. Output shapes are designed for "format as text" not "format as JSON" — frozen dataclasses with `__repr__` are fine; if Phase 33 needs JSON, asdict() works.
- **Phase 30 entry_points.callable + path resolution** — `EntryPointDescription.implemented_by_path` is the relative path of the File node `implemented_by` points to; `None` when the edge is NULL (Phase 30 D-06 broken-declaration case).
- **Pre-existing helpers continue working** — find, describe_package, describe_path, callers, callees keep their existing signatures (signature *extensions* are additive — new optional params if needed, never removing).

</code_context>

<specifics>
## Specific Ideas

- D-07 CTE prototype for `domain_references`:
  ```sql
  WITH RECURSIVE descendants(id) AS (
    SELECT id FROM nodes WHERE name = :domain AND kind = 'Domain'
    UNION ALL
    SELECT e.child_id FROM edges e
    JOIN descendants d ON e.parent_id = d.id
    WHERE e.kind = 'domain_contains_domain'
  )
  SELECT
    n.name AS package_name,
    SUM(json_extract(e.attrs_json, '$.usage_count')) AS total_usage_count,
    COUNT(DISTINCT e.parent_id) AS distinct_domain_count
  FROM edges e
  JOIN descendants d ON e.parent_id = d.id
  JOIN nodes n ON e.child_id = n.id
  WHERE e.kind = 'references'
  GROUP BY n.name
  ORDER BY total_usage_count DESC, package_name ASC
  ```

- D-09 UNION for `tests_for_domain`:
  ```sql
  WITH RECURSIVE descendants(id) AS ( ... )
  SELECT DISTINCT s.name, s.uri, ...  -- TestSuite rows
  FROM nodes s
  WHERE s.kind = 'TestSuite' AND s.id IN (
    -- Branch 1: direct TestSuite → Domain edge to a descendant
    SELECT e.parent_id FROM edges e
    JOIN descendants d ON e.child_id = d.id
    WHERE e.kind = 'tests'
    UNION
    -- Branch 2: indirect via TestSuite → Package → belongs_to_domain → descendant
    SELECT pkg_tests.parent_id FROM edges pkg_tests
    JOIN edges bt ON pkg_tests.child_id = bt.parent_id AND bt.kind = 'belongs_to_domain'
    JOIN descendants d ON bt.child_id = d.id
    WHERE pkg_tests.kind = 'tests'
  )
  ORDER BY s.name
  ```

- D-12 cross_cutting_packages:
  ```sql
  WITH ref_scores AS (
    SELECT e.child_id AS pkg_id, SUM(json_extract(e.attrs_json, '$.usage_count')) AS score
    FROM edges e
    WHERE e.kind = 'references'
    GROUP BY e.child_id
  )
  SELECT n.name, COALESCE(rs.score, 0) AS score
  FROM nodes n
  LEFT JOIN ref_scores rs ON rs.pkg_id = n.id
  WHERE n.kind = 'Package'
    AND NOT EXISTS (
      SELECT 1 FROM edges bt
      WHERE bt.kind = 'belongs_to_domain' AND bt.parent_id = n.id
    )
  ORDER BY score DESC, n.name ASC
  ```

- D-14 session-scoped fixture in conftest.py — pytest-asyncio compatible if needed (graph-io tests are sync; no special handling).

- D-15 fixture audit checklist (Phase 32 planner runs this against `tests/fixtures/sample_monorepo/`):
  - [ ] ≥2 Domains with parent-child (financial → billing minimum)
  - [ ] ≥1 cross-cutting Package
  - [ ] ≥1 EntryPoint with non-NULL `callable`
  - [ ] ≥1 wildcard `exports` EntryPoint (is_wildcard=true)
  - [ ] ≥1 TestSuite covering a single Domain (gets direct edge per Phase 31 D-12)
  - [ ] ≥1 TestSuite covering packages across multiple Domains (gets NO Domain edge per D-13; D-09 here infers)
  - Add what's missing via fixture edits + a corresponding `_run_cli ['cg', 'update', '--full']` re-build of the fixture DB in the test session.

- `find` allow-list expansion test: parameterised test asserting `find(conn, kind=k)` returns the right type for k in each of the 10 kinds; rejects unknown kinds with ValueError.

</specifics>

<deferred>
## Deferred Ideas

- **CLI subcommands** — Phase 33 wires Phase 32 helpers to `cg` subcommands. Phase 32 ships zero new CLI surface.
- **Pagination** for list_* and bubble-up queries — v1.6 assumes bounded sizes. Revisit when a real repo hits the limit.
- **Query result caching** — every helper hits SQLite fresh. Cheap because SQLite + in-process; revisit if measured.
- **Materialised closure tables for domain hierarchy** — query-time CTE is fine for v1.6; if domain trees grow deep, consider caching at update time (would violate DERIVED-04 only if applied to edges, not hierarchy).
- **JSON output mode** — Phase 33 CLI might format as text by default + `--json` flag using `dataclasses.asdict()`. Phase 32 helpers return dataclasses, so JSON serialisation is free.
- **`tests_for_domain` inferred-mode toggle** — D-09 always does UNION. A future flag `infer=False` could return direct-edge-only results for debugging. Defer until needed.
- **Streaming results** for very-large queries — generators instead of lists. Defer.
- **Cross-language symbol resolution in describe_path** — current PathDescription handles per-file; multi-file describe across language boundaries is a v1.7 concern.

</deferred>

---

*Phase: 32-query-layer-extensions*
*Context gathered: 2026-05-25*
