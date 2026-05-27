# Phase 44: Scanner-Generated Index - Research

**Researched:** 2026-05-26
**Domain:** Python module design + SQLite graph queries + deterministic markdown rendering + filesystem-scan helpers + write-if-changed semantics
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (22 total — verbatim from `44-CONTEXT.md`)

**Module strategy:**
- **D-01** — New module `packages/wiki-io/src/wiki_io/index_generator.py`. `update_index.py` untouched in Phase 44; both modules coexist until Phase 46 cutover deletes the old one. Phase 44 ships `index_generator` as a standalone, testable module with no caller integration.

**Output file + section structure:**
- **D-02** — `generate_index` writes a full rewrite of `wiki/index.md`. Single output file. No per-folder `*/index.md` sub-indexes. No HTML-comment markers or partial-rewrite — generator owns the file end-to-end.
- **D-03** — Section order (top to bottom):
  1. `# Index — <wiki_name>`
  2. Auto-generated banner: `_Auto-generated <ISO date> • <N> entities • <M> curated pages_`
  3. `## Domains` (graph-driven, nested tree per D-07)
  4. `## By Kind` (graph-driven, fallback per D-04)
  5. `## Architecture` (frontmatter-scan)
  6. `## ADRs` (frontmatter-scan)
  7. `## Concepts` (frontmatter-scan)
  8. `## Sources` (frontmatter-scan)
  9. `## Work` (workspace-rooted frontmatter-scan)

**Domain section composition:**
- **D-04** — **Single-placement rule.** Compute qualifying domains per entity (direct `belongs_to_domain` for `package`; one-hop transitive via `tests->package` / `used_by->package` for `test_suite` / `dependency`; always 0 for `plugin`). Place under that domain if exactly 1 qualifying; otherwise `## By Kind`. **Departs from REQUIREMENTS.md INDEX-02's "entities appear twice"** — user opted for clean single-placement.
- **D-05** — Nested-tree under each domain (bullets only, no sub-headings inside a domain section). Each package is a top-level bullet; its test_suites and dependencies indent as `Test Suites` / `Dependencies` sub-bullets.
- **D-06** — Within a single-qualifying-domain section, a dependency that's `used_by` multiple consumer packages appears under each consumer (intra-domain duplication is fine; "single placement" is the section-level rule).
- **D-07** — Sub-domain handling: `domain:X` with `parent_domain:Y` is rendered as a `### Sub-Domain: X` block inside Y's section, with X's full tree inlined. No top-level `## Domain: X` for sub-domains. Sub-domains nest recursively. Parent order alphabetical; sub-domains alphabetical within parent.
- **D-08** — Empty sections are omitted entirely (no `(0)` placeholders, no `—` filler).

**By-Kind section composition:**
- **D-09** — Hard-coded by-kind sub-heading order (NOT frozenset iteration — Pitfall 5 risk):
  1. `### Packages`
  2. `### Test Suites`
  3. `### Dependencies`
  4. `### Plugins`
  Within each, entities sort alphabetical by URI.
- **D-10** — `repository` and `domain` are never in `## By Kind`. Repository is the `## Domains — <repo>` parent header; domains ARE the sections.

**Curated-lane scan (ported from update_index.py):**
- **D-11** — Curated-lane scan logic ported into `index_generator.py` as private helpers (`_scan_curated_lane`, `_scan_work`). Source: `update_index.py::scan_vault` and `scan_work`. `update_index.py` itself is untouched in Phase 44.
- **D-12** — Curated lane folder map (mirror of `CATEGORY_INDEX_FILES` minus the per-folder target):
  ```python
  CURATED_LANES = (
      ("architecture", "wiki/architecture", "Architecture"),
      ("adrs",         "wiki/adrs",         "ADRs"),
      ("concepts",     "wiki/concepts",     "Concepts"),
      ("sources",      "wiki/sources",      "Sources"),
      # work handled separately — workspace-rooted
  )
  ```
- **D-13** — Curated-page row format: flat link list, alphabetical by title (frontmatter `title` or filename stem fallback). No nesting under domains (deferred to v1.9 doc-node ingest).
- **D-14** — `generate_index` writes ONLY `wiki/index.md`. No per-folder `*/index.md` writes (Phase 46 cutover removes them).

**Determinism + write-if-changed (Pitfall 5):**
- **D-15** — Deterministic sort rules (alphabetical-by-name for domains; alphabetical-by-URI within sections; hard-coded by-kind sub-heading order; hard-coded curated-lane order; alphabetical-by-title within a curated lane).
- **D-16** — Write-if-changed guard: render to string; if `existing_bytes == new_bytes` (UTF-8 + `\n` line endings), skip write and report `unchanged`. Otherwise atomic write via temp-file-and-`os.replace`.
- **D-17** — Determinism test: build fixture graph twice with permuted node insertion order; assert byte-identical output. Seeded random permutation (reproducible).

**Return shape + error handling:**
- **D-18** — `IndexWriteResult` dataclass: `path`, `bytes_written`, `changed`, `entity_count`, `curated_count`, `domain_count`, `by_kind_count`. Mirrors Phase 43's `EntityWriteResult` spirit.
- **D-19** — No partial-success error model. Graph-query failure raises; caller decides. Index is all-or-nothing.
- **D-20** — `generate_index` does NOT acquire `scan.lock`. Caller (Phase 45 `run_scan`) holds the lock for the full scan pass. Tests instantiate without a lock context.

**Module structure (`index_generator.py` contents):**
- **D-21** — Module-level constants (`BY_KIND_ORDER`, `CURATED_LANES`, `KIND_LABELS`); public `IndexWriteResult` + `generate_index`; private helpers (`_compute_qualifying_domains`, `_place_entities`, `_render_domain_tree`, `_render_by_kind`, `_scan_curated_lane`, `_scan_work`, `_render_curated_section`, `_render`).
- **D-22** — No new wiki-io dependencies. Uses `python-frontmatter`, `pathlib`, `dataclasses`, `sqlite3` (already in wiki-io / stdlib).

### Folded Todos
None. Phase 44 is a clean single-module addition.

### Claude's Discretion
- Dataclass field types (frozenset vs list vs tuple inside `IndexWriteResult`).
- Exact internal helper signatures (D-21 names are a sketch; planner may consolidate).
- Whether `_scan_curated_lane` returns `list[dict]` or a small `CuratedEntry` dataclass.
- Determinism test: Hypothesis vs fixed-seed permutation (lean fixed-seed — cheaper).
- Trailing newline (POSIX `\n` at EOF).
- `bytes_written` semantics when unchanged: actual length when changed, `0` when unchanged.

### Deferred Ideas (OUT OF SCOPE — Phase 44)
- Wiring `generate_index` into `run_scan` (Phase 45 / SCANINT-04).
- Removing old layout `wiki/packages/`, `wiki/domains/`, etc. (Phase 46 cutover).
- Deleting `update_index.py` and per-folder `*/index.md` files (Phase 46 cutover).
- Ingesting curated lanes as graph `doc` nodes (v1.9).
- LLM narrative on entity pages (Phase 45).
- Per-domain navigation pages distinct from index domain sections (v1.9).
- Cross-references for multi-domain entities (rejected — adds noise).
- Dedicated `## Repository` section beyond the parent header (v1.8 has 1 repo).
- `status: deprecated` curated pages hidden from index (v1.9 enhancement).
- ToC anchor block at top of index (v1.8 deferred).
- Per-folder index files via fallback `update_index.py` invocation (rejected; Phase 46 deletes them).

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description (REQUIREMENTS.md) | Research Support |
|----|------------------------------|------------------|
| INDEX-01 | `wiki_io/index_generator.py::generate_index(conn, wiki_root)` produces the wiki index page from graph queries directly (not by parsing entity page frontmatter); domain-first hierarchy at top, global by-kind sections below | D-01, D-02, D-03, D-21; entities sourced via `graph_io.queries.list_*` + `belongs_to_domain` traversal; markdown rendering deterministic per D-15. |
| INDEX-02 | Each domain section lists its contained packages, test-suites, and dependencies nested under it; entities appear twice (once under domain, once in global by-kind) | **D-04 reinterprets this requirement** — clean single-placement is the canonical reading. Each entity appears in exactly one section (domain OR by-kind, not both). Acceptance test asserts single-placement. Update REQUIREMENTS.md note (NOT in this phase — informational for the auditor). |
| INDEX-03 | Cross-cutting packages (zero `belongs_to_domain` edges) appear in by-kind only; deterministic sort | D-04 (qualifying-domains == 0 → by-kind); D-15 (alphabetical sort). Existing `graph_io.queries.cross_cutting_packages` is the direct precedent. |
| INDEX-04 | Write-if-changed guard; determinism test asserts byte-identical output across runs with permuted insertion order | D-15, D-16, D-17; render-to-string + byte-compare + atomic write. Determinism is upstream — fixed-seed permutation suffices (Hypothesis optional). |
| INDEX-05 | Curated lane sections (`/concepts/`, `/adrs/`, `/architecture/`, `/work/`, `/sources/`) preserved by index regeneration | **D-11..D-14 reinterpret this requirement** — curated sections are CONSOLIDATED into `wiki/index.md`, not preserved as separate per-folder index files. Acceptance test asserts the consolidated index contains `## Concepts`, `## ADRs`, `## Architecture`, `## Sources`, `## Work` sections each listing every page in the corresponding folder. The old per-folder files are unaffected by this phase (Phase 46 cutover deletes them). |

</phase_requirements>

## Summary

Phase 44 is a **single-module addition** that consolidates two existing concerns (graph entity enumeration + curated-lane frontmatter scan) into one deterministic, testable, write-if-changed `generate_index` function.

**Three architectural moves:**
1. **Graph-read pipeline (D-04, D-05, D-07, D-09, D-10).** Use existing `graph_io.queries.list_packages` / `list_test_suites` / `list_domains` / `list_dependencies` / `list_plugins` to enumerate entities. Compute "qualifying domains" per entity via a single helper that branches on kind (direct edge for `package`, one-hop transitive for `test_suite` / `dependency`). Single-placement rule routes entities to exactly one section. The by-kind sub-heading order is a hard-coded tuple constant — frozenset iteration is forbidden (Pitfall 5).
2. **Curated-lane scan (D-11..D-14).** Port `update_index.py::scan_vault` + `scan_work` into private helpers. Same shape: `{path, title, summary}` per entry; sorted alphabetical by title. The original `update_index.py` is untouched in Phase 44.
3. **Determinism + write-if-changed (D-15, D-16, D-17).** Render full index to an in-memory string; UTF-8-encode with `\n` line endings; compare to existing file bytes; skip write if identical; atomic `os.replace` otherwise. Determinism is verified by a fixture test that re-creates the same logical graph from two different insertion orders and asserts byte-identical output.

**Primary recommendation:** Two plans:
- **44-01 (Wave 1):** Core module skeleton — `index_generator.py` with `IndexWriteResult`, `generate_index`, all private helpers (graph + curated-lane scan + render); unit tests for each helper + happy-path integration.
- **44-02 (Wave 1):** Determinism + write-if-changed + edge-case tests (INDEX-04 acceptance, INDEX-03 cross-cutting, INDEX-02 single-placement audit, INDEX-05 curated-lane consolidation, sub-domain nesting, empty-section omission, syrupy snapshot of `agent-research` itself).

Both plans touch the same file (`index_generator.py`) and the same test file (`tests/test_index_generator.py`). Wave-2 isolation would require a different artifact split; instead we keep them in Wave 1 with `44-02` depending on `44-01` (sequential within Wave 1's plan order, NOT a different graph wave). **However**, if the planner judges the two plans can run as a single combined plan ~50% context, that's also valid. Default: split for cleaner per-plan acceptance criteria.

**Architectural risks (all addressed):**
1. *Index churn from non-deterministic ordering* (Pitfall 5) — mitigated by D-15 (every sort key locked) + D-09 (hard-coded by-kind tuple, NOT `ADMITTED_KINDS` iteration) + D-17 (determinism test).
2. *Single-placement vs duplication interpretation drift* — locked by D-04 with explicit "departure from INDEX-02" note. Plans must implement single-placement; acceptance tests assert it.
3. *Curated-lane scan parity with update_index.py* — mitigated by D-11 (port, don't import) + D-13 (same `{path, title, summary}` schema). Phase 46 cutover deletes the old module; both must produce semantically equivalent enumerations in Phase 44 (verified by a parity test against a fixture vault).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|-----------|---|---|---|
| Graph enumeration of admitted kinds (package, test_suite, dependency, plugin, domain) | `graph_io.queries.list_*` (existing) | — | Pre-existing tier; Phase 44 is a pure consumer. |
| Qualifying-domain computation per entity | `index_generator._compute_qualifying_domains` (new helper, this phase) | `graph_io.queries.find` + raw SQL for the one-hop transitive query | Local to `index_generator` — not generally useful elsewhere; lives close to the placement logic. |
| Entity placement (domain section vs by-kind) | `index_generator._place_entities` (new helper) | — | Pure function over a (kind → entities) input + qualifying-domain map. |
| Domain-tree rendering | `index_generator._render_domain_tree` | — | Pure markdown string generation; tested via syrupy snapshot. |
| By-kind rendering | `index_generator._render_by_kind` | — | Same. |
| Curated-lane scan | `index_generator._scan_curated_lane` (port from `update_index.py::scan_vault`) | `python-frontmatter` library | Single-file-walker + frontmatter parser. |
| Work-lane scan | `index_generator._scan_work` (port from `update_index.py::scan_work`) | `python-frontmatter` library | Workspace-rooted walk; same shape as curated. |
| Write-if-changed guard | `index_generator._render` + `generate_index` | `os.replace` for atomicity | Pure render then byte-compare then optionally atomic write. |
| Lock acquisition | NOT in `index_generator` (D-20) | `run_scan` (Phase 45) | Locking is a caller concern; `generate_index` is lock-agnostic. |
| Test fixtures (in-memory sqlite graph) | `tests/conftest.py` (existing) | — | Reuse Phase 43's connection fixture; extend with `make_index_fixture_graph()` if needed. |

## Standard Stack (recap from project CLAUDE.md)

- **Language:** Python 3.11+ (typing features required).
- **Workspace:** `uv` workspaces; `index_generator.py` lives in `packages/wiki-io/src/wiki_io/`.
- **Graph reads:** `graph_io.queries` (12 admitted kinds after Phase 43, no new graph schema in Phase 44).
- **Frontmatter parsing:** `python-frontmatter` (already a wiki-io dependency; the helper in `update_index.py::parse_frontmatter` is a regex-based subset — port can either reuse the regex or upgrade to `frontmatter.loads()` — planner's call per D-22 "no new deps").
- **Testing:** `pytest >= 8.3` + `syrupy` (for snapshot of rendered index against `agent-research`'s real graph) + optional `hypothesis` (already a dependency from Phase 42; not required for D-17 since fixed-seed permutation is adequate).
- **No new deps** (D-22).

## Architecture Patterns (reusable from prior phases)

| Pattern | Source | Application in Phase 44 |
|---------|--------|------------------------|
| Frozen `@dataclass` return type for I/O operations | Phase 43 `EntityWriteResult` | `IndexWriteResult` (D-18). |
| Atomic write via `temp + os.replace` | Standard POSIX pattern; Phase 43 uses for `deletions.log` | `_atomic_write_if_changed` helper. |
| Render-to-string then byte-compare for write-if-changed | Phase 43 D-15 + D-16 | D-16 here mirrors verbatim. |
| Hard-coded ordering tuple (not frozenset iteration) | Phase 42 URI builders + Phase 43 `STRUCTURAL_KEYS` list | `BY_KIND_ORDER` + `CURATED_LANES` here (D-09, D-12). |
| Helper-named-with-leading-underscore for module-private functions | Pervasive convention in `graph_io` and `wiki_io` | All `_*` helpers in D-21. |
| Test fixture builders for in-memory graphs | `packages/graph-io/tests/conftest.py` | Reuse + extend for `test_index_generator.py`. |
| Syrupy snapshot of generated artifact against real workspace | New for v1.8 (Phase 43 introduces) | Snapshot the rendered `wiki/index.md` for `agent-research` itself. |

## Don't Hand-Roll

| Concern | Use This | NOT This |
|---------|----------|----------|
| Frontmatter parsing | `python-frontmatter.loads(...)` OR copy `update_index.py::parse_frontmatter` verbatim | Re-write a regex from scratch. |
| Atomic write | `tempfile.NamedTemporaryFile(dir=parent, delete=False)` + `os.replace` | `open(path, "w").write(...)` (not crash-safe). |
| Wikilink building for entity targets | `entity_writer.encode_slug(uri)` from Phase 42 | Manual slug munging. |
| Graph queries | `graph_io.queries.list_*` / `describe_*` | Direct SQL in `index_generator.py`. |
| Workspace-root resolution for work-lane scan | `wiki_io._workspace.resolve_wiki_and_repo` (existing) | Hand-roll workspace discovery. |
| ISO date for banner | `datetime.date.today().isoformat()` | Hand-format. |

## Common Pitfalls (project Pitfall log)

1. **Pitfall 5 — Index churn.** Two scans of the same graph that produce semantically-equivalent but byte-different output cause spurious git diffs.
   - **Mitigation:** D-15 (every sort key locked) + D-16 (write-if-changed byte-compare) + D-17 (determinism test as Wave-0 acceptance).
   - **Anti-trap:** Iterating `ADMITTED_KINDS` (frozenset) for the by-kind section order would re-introduce the bug. D-09 mandates a hard-coded tuple constant. Tests must assert the section order.

2. **Frontmatter scan ignores generated files.** `update_index.py` excludes `GENERATED_FILES = {"index.md", "log.md"} | set(CATEGORY_INDEX_FILES.values())` from `scan_vault`. **Phase 44 must preserve this exclusion in the port** — otherwise the generated `wiki/index.md` could try to include itself.

3. **Workspace-rooted vs wiki-rooted paths.** Work entries are scanned from `<workspace>/work/` (sibling of the wiki), not from `<wiki>/work/`. The link format differs (`[[work/<stem>]]` vs `[[wiki/<lane>/<stem>]]`). The port must preserve this distinction.

4. **Sub-domain edge naming — `domain_contains_domain`, NOT `parent_domain`.** CONTEXT.md D-07 refers to "`parent_domain` edge", but the v1.8 graph schema uses `domain_contains_domain` (verified: `packages/graph-io/src/graph_io/domains.py:29` defines `_DOMAIN_CONTAINS_DOMAIN_KIND = "domain_contains_domain"`; `queries.py:463` queries it). The edge direction is parent → child: `domain:core -[domain_contains_domain]-> domain:billing` means billing is a sub-domain of core. The query for "sub-domains of X" is `SELECT child.name FROM edges e JOIN nodes parent ON e.src=parent.id JOIN nodes child ON e.dst=child.id WHERE e.kind='domain_contains_domain' AND parent.name = ?`. Treat CONTEXT.md D-07's "parent_domain" as a synonym — the actual edge kind is `domain_contains_domain`.

5. **Multi-domain placement is "0 OR ≥2" not "≥2".** D-04 routes both zero-qualifying-domain AND multi-qualifying-domain entities to `## By Kind`. Don't accidentally hardcode `placement_domain_count != 1` as `placement_domain_count >= 2`.

6. **Empty-section omission is recursive.** D-08 omits empty Test Suites / Dependencies sub-bullets under a package AND empty domain sections AND empty by-kind sub-headings AND empty `## By Kind` itself AND empty curated lanes. The renderer must check at every level, not just at the section-header level.

7. **Atomic write must replace, not append.** `os.replace(tmp_path, real_path)` is the right primitive. Don't use `pathlib.Path.write_text(...)` directly — that's not crash-safe.

8. **Workspace_root for `_scan_work` is not `wiki_root`.** `wiki_root` is the vault directory; `workspace_root` is its parent. The function signature accepts `wiki_root`; `_scan_work` derives `wiki_root.parent` (matching `update_index.py::scan_work(wiki.parent)`).

## Validation Architecture

Tests organize into four categories. Each maps to a determinism property + an acceptance criterion in the PLAN.

| Test Category | Acceptance | Test Files |
|---------------|------------|------------|
| Unit — `_compute_qualifying_domains` | Returns correct set for each kind (D-04 placement contract) | `tests/test_index_generator.py::TestQualifyingDomains` |
| Unit — `_place_entities` | Single-placement contract: every entity in exactly one section | `tests/test_index_generator.py::TestPlacement` |
| Unit — render helpers (`_render_domain_tree`, `_render_by_kind`, `_render_curated_section`) | Pure functions over canned inputs; output is exact-string-equal to expected | `tests/test_index_generator.py::TestRender` |
| Unit — `_scan_curated_lane` / `_scan_work` | Discovers all `.md` files; respects `GENERATED_FILES` exclusion; honors frontmatter title/summary | `tests/test_index_generator.py::TestCuratedScan` |
| Integration — `generate_index` happy path | Renders against a fixture graph; section ordering correct; bytes-written > 0 first call | `tests/test_index_generator.py::test_generate_index_against_fixture_graph` |
| Integration — write-if-changed (INDEX-04) | Second consecutive call returns `changed=False`, `bytes_written=0`, file mtime unchanged | `tests/test_index_generator.py::test_write_if_changed` |
| Integration — determinism (INDEX-04) | Two builds from permuted insertion orders produce byte-identical output | `tests/test_index_generator.py::test_determinism_across_permutations` |
| Integration — cross-cutting (INDEX-03) | Package with zero `belongs_to_domain` edges appears in `## By Kind > Packages`, NOT in any `## Domain:` section | `tests/test_index_generator.py::test_cross_cutting_in_by_kind_only` |
| Integration — single placement (D-04 / INDEX-02) | test_suite testing two packages in different domains appears in `## By Kind > Test Suites` (NOT in either domain) | `tests/test_index_generator.py::test_multi_domain_entity_in_by_kind` |
| Integration — sub-domain nesting (D-07) | `domain:billing` with `parent_domain:core` renders as `### Sub-Domain: billing` inside `## Domain: core`; no top-level `## Domain: billing` | `tests/test_index_generator.py::test_sub_domain_nesting` |
| Integration — empty omission (D-08) | Fixture with one domain, one package, no test_suites, no deps → only package bullet appears, no sub-bullet headers | `tests/test_index_generator.py::test_empty_sections_omitted` |
| Integration — curated lanes (INDEX-05) | Fixture vault with 3 ADR pages + 2 concept pages → `## ADRs` lists 3, `## Concepts` lists 2 (alphabetical by title) | `tests/test_index_generator.py::test_curated_lanes_consolidated` |
| Integration — plugins-always-by-kind (D-04) | Fixture with one plugin node → appears in `## By Kind > Plugins` only | `tests/test_index_generator.py::test_plugin_always_by_kind` |
| Integration — generated-files exclusion | Vault has `wiki/index.md`, `wiki/concepts/index.md`, `wiki/log.md` → none of these appear in any section | `tests/test_index_generator.py::test_generated_files_excluded` |
| Snapshot — agent-research vault | Snapshot the rendered `wiki/index.md` against `agent-research`'s live graph; lock the surface in syrupy | `tests/test_index_generator.py::test_snapshot_against_agent_research` |

**Wave 0 requirements:** `tests/test_index_generator.py` does not exist yet (NEW file). Wave 0 creates the file plus a conftest fixture-builder (`make_index_fixture_graph(...)`) that takes a list of `(kind, name, ...)` tuples and returns an in-memory sqlite connection populated via `upsert.upsert_records`.

## Open Questions

Q1: **`parent_domain` vs `domain_contains_domain` edge naming.** RESOLVED. CONTEXT.md D-07 says "parent_domain"; the actual graph schema uses `domain_contains_domain` (parent → child). Plans reference the actual edge kind `domain_contains_domain` and treat D-07's "parent_domain" as a synonym. No blocker.

Q2: **Should the curated-lane scan use `python-frontmatter.loads()` (already a dep) or copy `parse_frontmatter` verbatim?** Both work. The verbatim copy is identical to `update_index.py`'s behavior (so parity tests trivially pass). The library upgrade is cleaner but introduces a subtle behavior difference (proper YAML parsing vs the regex-based subset). **Recommendation:** copy the regex verbatim for v1.8; upgrade to library in v1.9 when the per-folder index files are deleted. The port is dead code after Phase 46 anyway.

Q3: **What happens if `wiki/index.md` doesn't exist yet (first call)?** D-16's byte-compare needs `existing_bytes`. If the file doesn't exist, treat `existing_bytes = None`, always write, and report `changed=True`. **Recommendation:** explicit `if not path.exists(): existing_bytes = None`; planner must spec this in the helper.

Q4: **Snapshot test stability — does the live `agent-research` graph mutate between test runs?** If yes, the syrupy snapshot needs `--snapshot-update` rebaselining every time a new entity is added. **Recommendation:** mark the snapshot test `@pytest.mark.live_graph` and exclude from CI default; run on demand via `pytest -m live_graph`. Alternatively, snapshot a fixture-graph rather than the live one — same coverage with deterministic input. Planner's call.

Q5: **`bytes_written` semantics when unchanged.** `IndexWriteResult.bytes_written = 0` when `changed=False` makes log readers easy ("did we write anything? check `bytes_written > 0`"). But it loses the information of "the file would be this size if we wrote it." **Recommendation:** lean toward `0 when unchanged, len(new_bytes) when changed` — simpler caller logic. CONTEXT.md D-18 leaves this open; lock it in PLAN frontmatter `truths`.

## Existing-Code Reads (planner must read these BEFORE writing PLAN.md)

- `packages/wiki-io/src/wiki_io/update_index.py` — source of `scan_vault`, `scan_work`, `parse_frontmatter`, `_entry_link`, `GENERATED_FILES`, `CATEGORY_INDEX_FILES`. Port shape, not import.
- `packages/graph-io/src/graph_io/queries.py` lines 290–366 (`describe_package`), 522–556 (`list_*` helpers), 865–902 (`cross_cutting_packages` — direct precedent for the zero-qualifying-domain pattern), and grep for `parent_domain` to answer Open Question Q1.
- `packages/wiki-io/src/wiki_io/_workspace.py` — `resolve_wiki_and_repo` shape (the workspace-vs-wiki distinction is load-bearing for `_scan_work`).
- `packages/graph-io/tests/conftest.py` — in-memory sqlite fixture (re-use as the basis for `test_index_generator.py`).
- `.planning/phases/43-entity-writer/43-CONTEXT.md` — `EntityWriteResult` shape (template for `IndexWriteResult`); atomic-write pattern.
- `.planning/phases/42-uri-slug-scheme-per-kind-templates/42-CONTEXT.md` — `encode_slug(uri)` signature for building entity wikilinks.

## Confidence Sources

| Decision | Confidence | Evidence |
|----------|-----------|----------|
| Section structure (D-03) | HIGH | User-locked in CONTEXT.md; mirrors a clean information-architecture: domain → by-kind → curated. |
| Single-placement rule (D-04) | HIGH | User-locked; explicitly departs from REQUIREMENTS.md INDEX-02. Acceptance test enforces. |
| Hard-coded BY_KIND_ORDER (D-09) | HIGH | Pitfall 5 mitigation is well-understood; precedent in Phase 43's `STRUCTURAL_KEYS`. |
| Port curated-lane scan (D-11) | HIGH | `update_index.py` is 422 LOC of working code; the port surface is ~80 LOC. Phase 46 will delete the original. |
| Write-if-changed (D-16) | HIGH | Direct mirror of Phase 43 D-15/D-16 pattern. |
| Sub-domain edge kind = `domain_contains_domain` (D-07) | HIGH | Verified in `packages/graph-io/src/graph_io/domains.py:29` and `queries.py:463`. CONTEXT.md D-07's "parent_domain" is a synonym; plans use the actual schema name. |
| Fixed-seed permutation for determinism test (D-17) | HIGH | Cheaper than Hypothesis; reproducible; sufficient for the property tested. |
| No new deps (D-22) | HIGH | Inventory check: `python-frontmatter`, `pathlib`, `dataclasses`, `sqlite3` all present. |
</phase_requirements>

---

*Researched 2026-05-26 for Phase 44.*
*Sources: CONTEXT.md (22 locked decisions), REQUIREMENTS.md §INDEX (5 reqs), `update_index.py` (port surface), `graph_io.queries.py` (consumer interface), Phase 43 CONTEXT.md (pattern precedent).*
