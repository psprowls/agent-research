---
phase: 57-index-generation-polish
plan: 01
type: execute
status: complete
requirements: [IDX-01, IDX-02, IDX-03, IDX-04, IDX-05]
---

# 57-01 Summary — Index Generation Polish

## What landed

All five IDX changes plus the cross-cutting structural fix (D-01), across one
new graph-io query and the wiki-io index renderer.

### graph-io: `internal_dependencies_of` (D-11 reuse, not parallel SQL)

`packages/graph-io/src/graph_io/queries.py` gained a module-level
`internal_dependencies_of(conn, *, name) -> list[str]` returning the outgoing
`depends_on_package` dst-names for a node of kind **package OR app**, sorted,
`[]` when none. It runs the exact query shape extracted from
`describe_package`'s internal-dependencies block (`src.kind IN ('package','app')`,
`?` placeholder only). It exists because `describe_package` gates on
`kind='package'` and returns `None` for apps — so the index renderer needs a
standalone function to surface internal deps for apps too. This is the single
source of internal-dependency truth reused by wiki-io (D-11); wiki-io writes no
`depends_on_package` SQL of its own (`grep -c depends_on_package
index_generator.py` == 0).

### The D-01 crux: `_PLACEABLE_KINDS` vs `BY_KIND_ORDER`

`_PLACEABLE_KINDS = ("app","package","test_suite","dependency","plugin")` drives
`_place_entities` iteration AND the by-kind sort key. `BY_KIND_ORDER =
("app","package","plugin")` drives ONLY the flat `## By Kind` render groups.
Decoupling them means test_suites/dependencies are still discovered and placed
(so they can nest under their packages), while the flat By-Kind section no
longer renders them as standalone groups. Removing the flat `### Test Suites` /
`### Dependencies` groups is safe precisely because every package/app now nests
its own Test Suites / Dependencies / Internal dependencies wherever it renders.

### The five IDX changes (wiki-io `index_generator.py`)

- **IDX-01 / D-03/D-04**: `### Apps` flat group, rendered before `### Packages`;
  `KIND_LABELS["app"]="Apps"`. Apps are placed via `list_apps` and routed by the
  same single-vs-multi-domain rule as packages — `_compute_qualifying_domains`
  now handles `kind="app"` identically to `package` (direct `belongs_to_domain`).
  A single-domain app renders under its `## Domain: X`; zero/multi → `### Apps`.
- **IDX-02 / D-05**: `_entity_wikilink` returns piped
  `[[wiki/entities/<stem>|<entity.name>]]` everywhere. Stem derivation
  (kind-aware, collision-aware) is unchanged.
- **IDX-03 / D-06/D-07**: `PlacedEntity` gained `summary: str = ""`, populated in
  `_place_entities` by reading the entity page file
  `wiki_root/entities/<stem>.md` frontmatter `summary:` (NOT the graph attr —
  Phase 56 makes `summary:` fill-when-empty/human-editable). The stem uses the
  same `_short_filename` call `_entity_wikilink` makes, so file lookup agrees
  with the link. Missing dir/file/frontmatter → empty summary (tolerant read
  like `_scan_curated_lane`). Every entity bullet renders `- {link} — {summary}`,
  suffix omitted when empty (shared `_entity_bullet` helper).
- **IDX-04 / D-01/D-10**: test_suites nest under the package(s) they test in BOTH
  domain and By-Kind contexts; no flat `### Test Suites`. Duplication across
  packages is expected (a suite testing N packages appears under each).
- **IDX-05 / D-08/D-09/D-11**: dependencies nest under the package(s) that use
  them as TWO separate sub-lists — `Dependencies` (external `used_by` →
  dependency entity links) and `Internal dependencies` (workspace package→package
  via `internal_dependencies_of` → links to the internal package/app entity
  page). The two sub-lists are never merged; the internal sub-list is never
  dropped. Internal-dep names are resolved to links via a `name→PlacedEntity`
  index built for package+app kinds during placement; unmatched names are
  skipped defensively.

### Shared rendering + global grouping

- `_render_pkg_nested(conn, pkg, sub_for_pkg, name_to_entity, collision_set)`
  renders the three nested sub-lists and is used by BOTH `_render_domain_section`
  and `_render_by_kind`, keeping the two contexts byte-identical (DRY).
- `_build_sub_for_pkg` builds the dep/suite-under-package grouping ONCE over ALL
  placed entities (domain buckets + by_kind) in `_render`, and is shared by both
  render contexts. This was a necessary refinement beyond the plan's literal
  text: a by-kind-placed (multi/zero-domain) dependency or test_suite must nest
  under a consumer package even when that package renders in a domain section
  (and vice-versa). Building the grouping per-section would have lost those
  cross-context nestings, breaking D-10. The deviation is faithful to D-01/D-10
  intent.

### Plumbing

`_place_entities` now takes `(conn, wiki_root, collision_set)` and returns a
3-tuple `(domain_buckets, by_kind, name_to_entity)`. It iterates
`_PLACEABLE_KINDS`, populates domain-agnostic `parent_pkg_names` for every
dep/test_suite (new `_consumer_pkgs` helper), reads summaries, and sorts by_kind
via `_PLACEABLE_KINDS.index`. `_render`, `_render_domains`,
`_render_domain_section`, `_render_by_kind` thread `name_to_entity` +
`sub_for_pkg`. New public helpers added to `__all__`.

## Tests

- **Updated** for the piped-link/flat-removal fallout: `test_module_constants`
  (new BY_KIND_ORDER/KIND_LABELS), every bare-stem entity-link assertion → piped
  form, `test_by_kind_section_order` (app<package<plugin, nested deps, no flat
  group), `test_test_suites_subheading` + `test_multi_domain_entity_in_by_kind`
  (nested `  - Test Suites`, D-10 duplication count = 2),
  `test_generate_index_against_fixture_graph` (`by_kind_count == 2`, nested deps,
  piped links). Added a `_place(conn)` test helper for the new 3-tuple signature.
- **New tests**: `test_app_zero_domain_renders_in_by_kind_apps_first` +
  `test_app_single_domain_renders_under_its_domain` (IDX-01);
  `test_internal_dependencies_subsection_distinct_from_dependencies`
  (IDX-05/D-09); `test_inline_summary_from_entity_page_frontmatter` incl.
  empty-summary no-suffix case (IDX-03). graph-io:
  `test_internal_dependencies_of_package_and_app` (package + app source + empty).
- **Determinism / write-if-changed** tests stay green unchanged (fresh tmp_path
  wikis have no entity pages → all summaries empty → deterministic).

### Test results

- `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -q`
  → 88 passed, 1 skipped (pre-existing unrelated skip).
- `uv run --package wiki-io pytest` (full) → 1556 passed, 39 skipped, 2 xfailed.
- graph-io scoped to its package dir surfaces ONE pre-existing collection ERROR:
  `src/graph_io/uri.py::test_suite_uri` — a production function whose name starts
  with `test_`, mis-collected by pytest. Unrelated to this phase, not in any
  changed file; the normal `tests/` invocation doesn't hit it.

## Snapshot status

The syrupy snapshot test `test_snapshot_against_agent_research` is **skipped** —
no live `.graph-wiki/graph.db` exists in this execution environment (the resolver
walks up 8 parents and finds none). Per the plan's output note: the snapshot must
be regenerated with `--snapshot-update` against the live post-Phase-56 graph when
one is available. The renderer code is correct regardless; only the live-graph
byte-snapshot remains to be captured.

## Files changed

- `packages/graph-io/src/graph_io/queries.py`
- `packages/graph-io/tests/test_queries.py`
- `packages/wiki-io/src/wiki_io/index_generator.py`
- `packages/wiki-io/tests/test_index_generator.py`
