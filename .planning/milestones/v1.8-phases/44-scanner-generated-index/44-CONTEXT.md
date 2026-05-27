# Phase 44: Scanner-Generated Index - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement `wiki_io/index_generator.py::generate_index(conn, wiki_root)` — a single new module that produces the entire `wiki/index.md` file deterministically from a combination of graph queries (for entity sections) and curated-lane frontmatter scans (ported from the legacy `update_index.py`). The index is the canonical navigation file for the vault.

**Scope expansion from ROADMAP wording.** ROADMAP Phase 44 says "driven directly from graph queries." User clarification during discussion: consolidate the *entire* index into one file — entity sections (graph-driven) plus curated lanes (concepts, ADRs, architecture, sources, work — currently scanned by `update_index.py`). Per-folder `concepts/index.md`, `adrs/index.md`, `sources/index.md`, `architecture/index.md`, `dependencies/index.md` are no longer maintained after this phase and become dead files (removed in Phase 46 cutover commit alongside the old layout).

INDEX-05 ("curated lane sections preserved") is reinterpreted accordingly: curated-lane content lives as sections *within* `wiki/index.md`, not as separate per-folder index files. The correctness test in INDEX-05 verifies the consolidated index contains a `## Concepts`, `## ADRs`, etc. section listing every curated page.

**What ships in Phase 44:**
- `packages/wiki-io/src/wiki_io/index_generator.py` — single new module.
- `generate_index(conn: sqlite3.Connection, wiki_root: Path) -> IndexWriteResult`.
- Deterministic sort + write-if-changed guard (Pitfall 5 mitigation).
- Hypothesis or fixture-based determinism test (two runs from same graph, different node-insertion order → byte-identical output).
- Curated-lane frontmatter-scan helpers ported into the same module from `update_index.py`'s `scan_vault`.

**What is NOT in scope:**
- Wiring `generate_index` into `run_scan` — Phase 45 (SCANINT-04 / Step 12).
- Removing the old layout (`wiki/packages/`, `wiki/domains/`, etc.) — Phase 46 cutover.
- Deleting `update_index.py` and obsolete per-folder `*/index.md` files — Phase 46 cutover.
- Ingesting curated lanes as graph `doc` nodes — deferred to v1.9.
- LLM narrative on entity pages — Phase 45.

**Phase 46 ripple (must record in Phase 46 CONTEXT.md when discussed):**
- Cutover commit removes `packages/wiki-io/src/wiki_io/update_index.py`.
- Cutover commit removes `wiki/concepts/index.md`, `wiki/adrs/index.md`, `wiki/sources/index.md`, `wiki/architecture/index.md`, `wiki/dependencies/index.md` from the vault.
- Any external caller of `update_index.update_index(wiki)` (plugin, CLI, scripts) is rewired to `index_generator.generate_index(conn, wiki_root)` in Phase 45/46.

</domain>

<decisions>
## Implementation Decisions

### Module strategy

- **D-01:** **New module `packages/wiki-io/src/wiki_io/index_generator.py` is created in Phase 44.** `update_index.py` is NOT modified in this phase; it continues to function until the Phase 46 cutover commit deletes it. Both modules coexist in the codebase during Phases 44–45, but only `update_index.py` is wired into any caller until Phase 45 swaps the call site. Phase 44 ships `index_generator.py` as a standalone, testable module with no caller integration.

### Output file + section structure

- **D-02:** **`generate_index` writes a full rewrite of `wiki/index.md`.** Single output file. No per-folder `*/index.md` sub-indexes are written by this module. No HTML comment markers / partial-rewrite — the file is fully owned by the generator.
- **D-03:** **Section order (top to bottom):**
  1. H1: `# Index — <wiki_name>`
  2. Auto-generated banner line: `_Auto-generated <ISO date> • <N> entities • <M> curated pages_`
  3. `## Domains` (graph-driven, nested tree per D-07)
  4. `## By Kind` (graph-driven, holds entities that don't fit cleanly under a single domain — per D-04)
  5. `## Architecture` (frontmatter-scan of `wiki/architecture/`)
  6. `## ADRs` (frontmatter-scan of `wiki/adrs/`)
  7. `## Concepts` (frontmatter-scan of `wiki/concepts/`)
  8. `## Sources` (frontmatter-scan of `wiki/sources/`)
  9. `## Work` (frontmatter-scan of `<workspace>/work/` — workspace-rooted per existing `update_index.py` convention)

  Curated-lane sections appear in the order Architecture → ADRs → Concepts → Sources → Work. Section is omitted entirely if it has zero pages (D-08).

### Domain section composition

- **D-04:** **Single-placement rule — each entity appears in exactly one section.**
  - Compute "qualifying domains" for each entity:
    - `package`: domains reached via direct `belongs_to_domain` edges (cardinality 0..N).
    - `test_suite`: domains reached via `tests -> package -> belongs_to_domain` (one-hop transitive); cardinality is the deduplicated set across all tested packages.
    - `dependency`: domains reached via `used_by -> package -> belongs_to_domain` (one-hop transitive); cardinality is the deduplicated set across all consumer packages.
    - `plugin`: always cardinality 0 (plugins have no inbound edges in v1.8 per Phase 43 D-03); always in `## By Kind`.
    - `repository`, `domain`: not enumerated under `## By Kind`; repositories appear once at the top of `## Domains` as a parent header; domains ARE the sections (see D-07).
  - **Placement:**
    - Qualifying-domain count == 1 → entity is nested under that domain's section.
    - Qualifying-domain count == 0 (cross-cutting per INDEX-03) → entity goes to `## By Kind`.
    - Qualifying-domain count >= 2 (multi-domain) → entity goes to `## By Kind`. **Departure from INDEX-02's "entities appear twice."** User decision: clean single-placement is preferred over duplication; the by-kind section is the canonical home for anything that doesn't fit cleanly under exactly one domain.

- **D-05:** **Nested-tree structure under each domain.** Each `## Domain: <name>` section renders as:
  ```
  ## Domain: <name>
  
  - [[wiki/entities/pkg__<repo>__<pkg-a>]] — <pkg-a summary if available>
    - Test Suites
      - [[wiki/entities/test_suite__<repo>__<pkg-a>__<suite>]]
    - Dependencies
      - [[wiki/entities/dependency__pypi__<dep>]]
  - [[wiki/entities/pkg__<repo>__<pkg-b>]] — <pkg-b summary>
    - ...
  ```
  Packages are top-level bullets inside the domain section. Each package's test_suites and dependencies are listed under indented `Test Suites` / `Dependencies` sub-bullets. Sub-headings (`### Packages` etc.) are NOT used inside domain sections — bullets only, to keep the tree readable.

- **D-06:** **Entities appear under the package they belong to within a domain.** For a single-qualifying-domain dependency `dependency:pypi/boto3` used_by `pkg:agent-research/graph-io`, the dependency renders under the `pkg:agent-research/graph-io` bullet inside that domain. If a dependency is used_by multiple packages in the same single qualifying domain, it appears under each consumer package (this is intra-domain duplication and is acceptable — it's not the "single placement" rule, which is at the section level). The "appears once" rule applies to section-level placement, not intra-domain consumer nesting.

- **D-07:** **Sub-domain handling = nested under parent domain.** When `domain:X` has a `parent_domain` edge to `domain:Y`, the section for X does NOT appear at the top of `## Domains`. Instead, Y's section contains a `### Sub-Domain: X` sub-heading after Y's own packages, with X's full tree inlined underneath. Sub-domains of sub-domains nest further. No cross-references. Determinism: parent-domain sort order is alphabetical by domain name; sub-domains sort alphabetically within their parent.

- **D-08:** **Empty sections are omitted entirely.**
  - A domain section with zero placed entities is not rendered.
  - A `Test Suites` sub-bullet under a package is omitted if the package has no test_suites.
  - A `Dependencies` sub-bullet under a package is omitted if the package has no dependencies.
  - A `## By Kind` sub-heading (e.g., `### Plugins`) is omitted if no entities of that kind landed in by-kind.
  - The `## By Kind` section itself is omitted if no entities at all landed in by-kind.
  - Any curated lane section (`## Architecture`, `## ADRs`, etc.) is omitted if its folder has zero non-`index.md` pages.
  - **No `(0)` or `—` placeholders anywhere.** Empty == absent.

### By-Kind section composition

- **D-09:** **By-Kind sub-heading order = hierarchy of importance.** Hard-coded ordering in `index_generator.py`:
  1. `### Packages`
  2. `### Test Suites`
  3. `### Dependencies`
  4. `### Plugins`
  
  Within each sub-heading, entities sort alphabetically by URI. **Do NOT iterate `ADMITTED_KINDS` directly** — Python frozenset iteration is implementation-defined and breaks Pitfall-5 determinism. The ordering is a tuple constant in the module.

- **D-10:** **`repository` and `domain` kinds are never in `## By Kind`.** The repository appears once at the top of `## Domains` as a parent header (e.g., `## Domains — agent-research`). Domains ARE the sections, not list items.

### Curated-lane scan (ported from update_index.py)

- **D-11:** **Curated-lane scan logic ported into `index_generator.py` as private helpers.** Source: `update_index.py::scan_vault` (filesystem walk + `parse_frontmatter`) and `update_index.py::scan_work` (workspace-rooted work walk). Adapted shape: returns one dict per lane keyed by alphabetical title, with the same `{path, title, summary}` schema. Helpers are private (`_scan_curated_lane(wiki_root, lane: str)`, `_scan_work(workspace_root)`). The original `update_index.py` is left untouched in this phase.

- **D-12:** **Curated lane folder map** (mirror of existing `update_index.py` `CATEGORY_INDEX_FILES`, minus the per-folder index target):
  ```python
  CURATED_LANES = (
      ("architecture", "wiki/architecture", "Architecture"),
      ("adrs",         "wiki/adrs",         "ADRs"),
      ("concepts",     "wiki/concepts",     "Concepts"),
      ("sources",      "wiki/sources",      "Sources"),
      # "work" handled separately — workspace-rooted, not wiki-rooted
  )
  ```
  Ordering is locked by tuple order; section render order in the index follows this tuple.

- **D-13:** **Curated-page row format inside each curated lane section** — flat link list, one entry per page, with summary from frontmatter if present:
  ```
  ## Concepts
  
  - [[wiki/concepts/per-repo-layout]] — <summary if present in frontmatter>
  - [[wiki/concepts/<another>]] — <summary>
  ```
  Sort: alphabetical by title. Title is extracted from frontmatter (preferred) or filename stem fallback. No nesting under domains for curated pages in v1.8 — that's the v1.9 graph-ingestion idea.

- **D-14:** **`generate_index` does NOT write any per-folder `*/index.md` file.** Even though `update_index.py` still writes `concepts/index.md` etc. when called, `index_generator.py` only writes `wiki/index.md`. Phase 46 cutover removes the per-folder files from the vault and deletes `update_index.py`.

### Determinism + write-if-changed (Pitfall 5)

- **D-15:** **Deterministic sort rules** (encoded as helpers in `index_generator.py`):
  - Domains: alphabetical by domain name (case-insensitive); ties broken by URI alphabetical.
  - Packages within a domain section: alphabetical by URI.
  - Test suites under a package: alphabetical by URI.
  - Dependencies under a package: alphabetical by URI (`dependency:pypi/<name>` sorts naturally).
  - `## By Kind` sub-headings: hard-coded order per D-09.
  - Entities within a by-kind sub-heading: alphabetical by URI.
  - Sub-domains nest after parent's packages, sorted alphabetically by sub-domain name.
  - Curated-lane sections: hard-coded order per D-12.
  - Curated pages within a lane: alphabetical by title (frontmatter `title` or filename stem fallback).

- **D-16:** **Write-if-changed guard implementation.** Render the full index to a string in memory. If `wiki/index.md` exists and `existing_bytes == new_bytes` (after UTF-8 encoding with `\n` line endings), skip the write and report `unchanged` in the return value. Otherwise atomic write (write to temp file in same directory + `os.replace`). Pre-req: rendering MUST be deterministic per D-15 for this guard to actually prevent churn.

- **D-17:** **Determinism test** (acceptance for INDEX-04): build a fixture sqlite graph; render via `generate_index` to memory once; shuffle node insertion order by re-creating the graph from a permuted node list; render again; assert byte-identical output. Use a known-deterministic shuffle (seeded) for reproducibility.

### Return shape + error handling

- **D-18:** **`IndexWriteResult` dataclass:**
  ```python
  @dataclass(frozen=True)
  class IndexWriteResult:
      path: Path                          # wiki/index.md absolute path
      bytes_written: int                  # 0 if unchanged
      changed: bool                       # True if write occurred
      entity_count: int                   # entities placed (sum across domains + by-kind)
      curated_count: int                  # curated pages enumerated
      domain_count: int                   # number of domain sections rendered
      by_kind_count: int                  # entities in ## By Kind
  ```
  Mirrors the spirit of Phase 43's `EntityWriteResult` (per-state counts, no exceptions in the happy path). Callers can log diagnostics from this.

- **D-19:** **No partial-success error model.** Index generation is all-or-nothing: if a graph query fails, the function raises and the caller decides. Index is a single artifact — partial results would mean a half-rendered file, which is worse than a clean failure. (Contrast with Phase 43's `write_entities`, which has per-page failure isolation because each entity is independent.)

- **D-20:** **No scan.lock acquired by `generate_index`.** The lock is acquired by `run_scan` in Phase 45 before calling `write_entities`; `generate_index` is called inside that lock (Step 12, after writes). Locking inside `generate_index` would be redundant. Tests for `generate_index` instantiate without a lock context — the function is lock-agnostic.

### Module structure (`index_generator.py` contents)

- **D-21:** **All Phase 44 code lives in `packages/wiki-io/src/wiki_io/index_generator.py`.** Module-level constants:
  - `BY_KIND_ORDER: tuple[str, ...] = ("package", "test_suite", "dependency", "plugin")`
  - `CURATED_LANES: tuple[tuple[str, str, str], ...]` (per D-12)
  - `KIND_LABELS: dict[str, str]` — display labels (e.g., `"package" → "Packages"`)
  
  Public functions/classes:
  - `class IndexWriteResult`
  - `def generate_index(conn, wiki_root) -> IndexWriteResult`
  
  Private helpers (named with leading underscore):
  - `_compute_qualifying_domains(conn, uri, kind) -> set[str]`
  - `_place_entities(conn) -> tuple[dict[str, DomainPlacement], list[NodeRecord]]` — returns (per-domain placements, by-kind fallback list)
  - `_render_domain_tree(placements) -> list[str]`
  - `_render_by_kind(fallback_entities) -> list[str]`
  - `_scan_curated_lane(wiki_root, lane_dir) -> list[dict]`
  - `_scan_work(workspace_root) -> list[dict]`
  - `_render_curated_section(label, entries) -> list[str]`
  - `_render(conn, wiki_root) -> str` — orchestrates everything, returns the full rendered index string

- **D-22:** **No new wiki-io dependencies.** `python-frontmatter` (already used by entity_writer / update_index), `pathlib`, `dataclasses`, `sqlite3` (via conn passed in). No new third-party packages.

### Claude's discretion

- Exact dataclass field types (frozenset vs list vs tuple inside `IndexWriteResult` — implementer's call within Python conventions).
- Exact internal helper signatures (the names in D-21 are a sketch; planner may consolidate).
- Whether `_scan_curated_lane` returns a list of `dict` or a small `CuratedEntry` dataclass.
- Whether the determinism test uses Hypothesis or a fixed seeded permutation — fixed seed is probably cheaper and adequate.
- Trailing newline convention in the rendered file (POSIX: file ends with `\n`).
- Whether `bytes_written` field returns the actual byte length or `0` when unchanged (lean toward actual length when changed, `0` when unchanged — easy to log).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Direct predecessors
- `.planning/phases/42-uri-slug-scheme-per-kind-templates/42-CONTEXT.md` — Slug encoding (D-01..D-05), ADMITTED_KINDS, SCANNER_OWNED_KEYS, URI builders. `entity_writer.encode_slug` is used to build wikilinks inside the index.
- `.planning/phases/43-entity-writer/43-CONTEXT.md` — Wave 1 graph-io extension (dependency, plugin kinds added to `_VALID_KINDS`); `write_entities` semantics; `STRUCTURAL_KEYS` constant. Phase 44 reads the graph for the same kinds Phase 43 ingests.

### Milestone-level
- `.planning/REQUIREMENTS.md` §INDEX — INDEX-01 through INDEX-05 (five requirements). Note that INDEX-02's "entities appear twice in the index" is reinterpreted by D-04 to "each entity appears exactly once at the section level"; downstream agents should treat D-04 as authoritative.
- `.planning/ROADMAP.md` Phase 44 — Goal + 5 success criteria.
- `.planning/STATE.md` — Pitfall 5 (index churn) — mitigated by D-15 (deterministic sort) + D-16 (write-if-changed) + D-17 (determinism test).

### Existing code (must be read by planner/researcher)
- `packages/wiki-io/src/wiki_io/update_index.py` — Legacy frontmatter-scan-based index writer. Source of `scan_vault`, `scan_work`, `parse_frontmatter`, `render_index`, `render_category_index` patterns. Curated-lane helpers in `index_generator.py` (D-11, D-12) are ports of `scan_vault`'s subset for `architecture/adrs/concepts/sources` plus `scan_work`. To be deleted in Phase 46 cutover.
- `packages/graph-io/src/graph_io/queries.py` — `list_packages`, `list_test_suites`, `list_domains`, `cross_cutting_packages`; will be extended in Phase 43 with `list_dependencies`, `list_plugins`. Phase 44 calls these for entity enumeration.
- `packages/graph-io/src/graph_io/queries.py` §`belongs_to_domain` edge handling (around `cross_cutting_packages` and `describe_package`) — pattern for the "qualifying domains" computation in D-04.
- `packages/wiki-io/src/wiki_io/entity_writer.py` (post-Phase 42) — `encode_slug` is used to build wikilink targets (`[[wiki/entities/<slug>]]`).
- `packages/wiki-io/src/wiki_io/_workspace.py` — `resolve_wiki_and_repo` pattern (the workspace-rooted work-lane path — needed for `_scan_work`).

### Research baseline (Phase 43 reuses much of this)
- `.planning/research/ARCHITECTURE.md` — Curated lane definitions, vault layout (the `wiki/` directory structure that the scan helpers walk).
- `.planning/research/PITFALLS.md` Pitfall 5 (index churn) — addressed by D-15, D-16, D-17.
- `.planning/research/FEATURES.md` §index regeneration — original requirement source for "domain-first + by-kind."

### Tests (where new Phase 44 tests land)
- `packages/wiki-io/tests/test_index_generator.py` (new) — unit + determinism + write-if-changed tests.
- `packages/wiki-io/tests/fixtures/` — small fixture graphs (sqlite or builder helpers) for index rendering tests.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`update_index.py::scan_vault`** — Filesystem walker + frontmatter parser. Curated-lane helpers in `index_generator.py` reuse this shape (D-11). Port, don't import — the new module owns its scan logic so `update_index.py` can be deleted in Phase 46.
- **`update_index.py::scan_work`** — Workspace-rooted walk for the work lane. Same port treatment.
- **`update_index.py::parse_frontmatter`** — Simple regex-based YAML extractor. Can be reused via copy-port or replaced with `python-frontmatter.loads()` (already a wiki-io dependency).
- **`update_index.py::_entry_link`** — Builds a wikilink from a path. Pattern is fine for curated entries; entity entries use `encode_slug` directly for `[[wiki/entities/<slug>]]`.
- **`graph_io.queries.list_packages` / `list_domains` / `list_test_suites`** — Existing list helpers; Phase 43 adds `list_dependencies` and `list_plugins`. Phase 44 calls all five to enumerate placeable entities.
- **`graph_io.queries.cross_cutting_packages`** — Direct precedent for the zero-qualifying-domain query pattern (D-04).

### Established Patterns
- **CLAUDE.md §8 — pytest + Hypothesis + syrupy.** Determinism test (D-17) uses a fixed seeded permutation (cheaper than Hypothesis for this case). Hypothesis is the right tool if the planner prefers generating arbitrary node sets.
- **Atomic write pattern**: write to `wiki/index.md.tmp` in the same directory + `os.replace` → durable + atomic on POSIX. `update_index.py` uses `path.write_text()` directly today — Phase 44's write-if-changed guard upgrades to atomic write.
- **JSON-flavored docstring + dataclass return type** (per Phase 43 D-08 / D-09 precedent): `IndexWriteResult` follows the same shape philosophy.
- **`v1.7 trace JSONL convention`** is not relevant here — the index is markdown, not JSONL.

### Integration Points
- **`generate_index` is callable standalone.** Phase 44 does NOT wire it into `run_scan`. That's Phase 45's Step 12. In Phase 44 the only callers are tests.
- **No filesystem dependencies beyond `wiki_root`.** All curated-lane discovery uses paths derived from `wiki_root`; work-lane uses the workspace-rooted path (computed inside the helper).
- **No graph mutations.** `generate_index` is read-only on the graph; it accepts a `sqlite3.Connection` and queries it.
- **No scanner lock needed inside this function** (D-20); the caller (Phase 45) holds the lock for the full scan pass.

</code_context>

<specifics>
## Specific Ideas

- **Determinism test fixture**: build the same logical graph two ways — once via insertion order `[domain_a, pkg_x, pkg_y, test_suite_1]`, once via `[test_suite_1, pkg_y, domain_a, pkg_x]`. Both must produce byte-identical output. Use a seeded `random.Random` for the permutation so the test is reproducible.
- **Write-if-changed integration test**: run `generate_index` twice in a row against the same graph. Second call must return `changed=False, bytes_written=0` and the file's mtime must be unchanged. Assertion: `os.path.getmtime(index_path)` is identical before and after the second call.
- **Multi-domain placement test (D-04)**: fixture has `test_suite:X` testing `pkg:A` (domain α) and `pkg:B` (domain β). Assert `X` appears in `## By Kind > Test Suites` and NOT inside the α or β domain sections.
- **Empty-section omission test (D-08)**: fixture with one domain containing one package with no test_suites and no dependencies. Assert the domain section contains only the package bullet — no `Test Suites` or `Dependencies` sub-bullets.
- **Sub-domain nesting test (D-07)**: fixture with `domain:billing` having `parent_domain` edge to `domain:core`. Assert `## Domain: core` section contains `### Sub-Domain: billing` sub-heading, and there is no top-level `## Domain: billing` section.
- **Curated-lane scan parity test (D-11)**: vault has 3 ADR pages and 2 concept pages. Assert `## ADRs` section has 3 entries (sorted alphabetically by title) and `## Concepts` has 2 entries.
- **Plugins always in by-kind test (D-04)**: fixture has one `plugin` node. Assert it appears in `## By Kind > Plugins` and nowhere else.
- **Render `agent-research` itself**: integration test runs `generate_index` against the live graph for the `agent-research` workspace. Snapshot the rendered output via syrupy. This is the "does it produce something sensible" sanity check.

</specifics>

<deferred>
## Deferred Ideas

- **Ingest curated lanes as `doc` (or `wiki_page`) graph nodes** — v1.9. Would let `generate_index` be purely graph-driven and unify the placement rule for curated pages alongside entities (e.g., an ADR could `belongs_to_domain` like a package). Requires graph-io schema extension + ingestion in `scan.py`. Not load-bearing in v1.8.
- **Per-domain page in addition to a domain section in the index** — a domain entity page (`wiki/entities/domain__<repo>__<name>.md`) already exists per Phase 42. Out-of-scope for Phase 44 to write per-domain navigation pages distinct from the index domain section.
- **Cross-references for multi-domain entities** — D-04 routes multi-domain entities to `## By Kind`. An alternative was "primary domain + cross-ref note in other domains" — rejected as adding markdown noise without commensurate value. Revisit if users say "I went to domain X looking for test_suite Y and didn't find it."
- **Dedicated `## Repository` section** — D-10 places the repository as a `## Domains — <repo>` header. An alternative was a separate `## Repository` section with repo-level metadata. Not done because v1.8 has exactly one repository per workspace; the header is sufficient.
- **`status: deprecated` curated pages hidden from the index** — curated-lane scan in D-11 lists all pages regardless of frontmatter status. If users start marking ADRs `deprecated`, hiding them in the index would be a small enhancement. Not in v1.8.
- **Index page size budgeting** — large vaults could produce a huge `wiki/index.md`. v1.8 vault is <200 entities + ~30 curated pages; no budgeting needed. Revisit if size becomes a problem.
- **Markdown anchor links / table-of-contents at the top** — could add a `## Contents` ToC block at the top of `wiki/index.md` after the banner. Skipped in v1.8 — section headings are navigable from a markdown viewer's outline pane.
- **Per-folder index files via a fallback `update_index.py` invocation in Phase 44/45** — explicitly rejected. Phase 46 cutover deletes them.

</deferred>

---

*Phase: 44-Scanner-Generated Index*
*Context gathered: 2026-05-26*
