# Phase 57 — Index Generation Polish — Research

**Researched:** 2026-05-28
**Question answered:** "What do I need to know to PLAN Phase 57 well?"

> All five changes live in **one file**: `packages/wiki-io/src/wiki_io/index_generator.py`,
> with test updates in `packages/wiki-io/tests/test_index_generator.py`. This research
> grounds the locked decisions D-01..D-11 against the *current* code (line numbers in
> 57-CONTEXT.md drifted; this doc supersedes them) and resolves the one non-obvious
> structural problem the decisions imply.

---

## 1. Current code reality (verified)

### `index_generator.py`
- `BY_KIND_ORDER = ("package", "test_suite", "dependency", "plugin")` (**L67**).
- `KIND_LABELS = {package, test_suite, dependency, plugin}` (**L69-74**).
- `PlacedEntity` frozen dataclass (**L114-133**): fields `kind, name, uri, parent_pkg_names, suite_kind, pkg_for_suite`. No `summary` field.
- `_compute_qualifying_domains(conn, *, kind, name)` (**L140-195**): handles `package` (direct `belongs_to_domain`), `test_suite` (via `tests→package→belongs_to_domain`), `dependency` (via `used_by→package→belongs_to_domain`), `plugin` (empty). **Raises `ValueError` for any other kind, including `app`.**
- `_consumer_pkgs_in_domain(conn, *, kind, entity_name, domain_name)` (**L198-231**): for a dependency/test_suite scoped to one domain, returns the package names in that domain that consume/are-tested-by it. Returns `()` for other kinds. **Domain-scoped only** — there is no by-kind analog today.
- `_place_entities(conn)` (**L234-290**): iterates `for kind in BY_KIND_ORDER`, maps each to a `list_*` fn via `kind_to_list_fn` (**L246-251**, keys: package/test_suite/dependency/plugin — *no app*). Single-qualifying-domain → `domain_buckets`; else → `by_kind`. Populates `parent_pkg_names` only when `len(qualifying)==1 and kind in (dependency,test_suite)` (**L258-262**). Final sort of `by_kind` uses `BY_KIND_ORDER.index(e.kind)` (**L289**).
- `_entity_wikilink(entity, collision_set)` (**L419-432**): returns `f"[[wiki/entities/{stem}]]"` where `stem = _short_filename(entity.uri, collision_set, suite_kind=..., pkg_for_suite=...)`. **Bare-stem, no display text, no summary.**
- `_render_domain_section(...)` (**L435-500**): the existing nesting pattern (D-01 mirror target). Per package bullet (**L464-479**) it emits `- {pkg_link}`, then a `  - Test Suites` sub-heading + `    - {ts_link}` lines, then a `  - Dependencies` sub-heading + `    - {d_link}` lines. Grouping is via `sub_for_pkg[parent][kind]` built from each dep/suite's `parent_pkg_names` (**L456-461**).
- `_render_by_kind(by_kind_entities, collision_set)` (**L534-559**): renders **flat** `### {label}` per kind in `BY_KIND_ORDER`, each entity a bare `- {link}` (**L552-555**). No nesting.
- `_render_curated_section(label, entries)` (**L562-572**): renders `- {link}{summary}` where `summary = f" — {e['summary']}" if e.get("summary") else ""` (**L569-570**). **This is the exact inline-summary shape IDX-03 must match.**
- `_scan_curated_lane(...)` (**L329-354**): reads each page's frontmatter via `_parse_frontmatter` and stores `summary = fm.get("summary", "")` (**L351**). **This is the frontmatter-read pattern IDX-03 must mirror for entity pages.**
- `_render(conn, wiki_root)` (**L580-630**): computes `collision_set` once (**L589**), calls `_place_entities`, `_render_domains`, `_render_by_kind`, curated sections. `entity_count = sum(domain buckets) + len(by_kind)` (**L592**).
- `__all__` (**L678-700**) re-exports the public + underscore helpers; tests import several. **Any new public helper should be added here.**

### `graph_io.queries` (read-only, already landed)
- `list_apps(conn)` **exists** (queries.py L866) — returns `app` NodeRecords alphabetically. `list_packages/list_test_suites/list_dependencies/list_plugins/list_domains` all exist and are already imported.
- `describe_package(conn, *, name)` (queries.py L367) returns `PackageDescription` with **`internal_dependencies: list[str]`** (outgoing `depends_on_package`, sorted) and `internal_dependents: list[str]` (incoming), populated by the Phase 55 Plan 02 queries at L437-460. **`describe_package` only matches `kind='package'` nodes (L369) — it returns `None` for an `app` node.** There is **no `describe_app`** with internal-dep surfacing.
- The raw `depends_on_package` query (queries.py L437-447) selects `dst.name` WHERE `src.name = ? AND src.kind IN ('package','app') AND dst.kind IN ('package','app')` — i.e. it already works for apps as the *source* if invoked directly, but is wrapped inside `describe_package` which gates on `kind='package'`.
- Schema (`schema.py`) has **no CHECK constraint** on node/edge kinds — the test fixture can build `app` nodes and `depends_on_package` edges freely.
- `entity_writer.ADMITTED_KINDS` already includes `app` (L60-69); `_URI_PREFIX_BY_KIND["app"]="app"`, `_FILENAME_PREFIX_BY_URI_PREFIX["app"]="app"`, and `_kind_list_fns()["app"]=list_apps` (L514). So **the collision pre-pass already covers apps and `short_filename` already derives `app_<name>` stems** — `_entity_wikilink` works for an `app` PlacedEntity with no change.

---

## 2. The one structural problem the decisions imply (and its resolution)

**Problem:** `_place_entities` iterates `for kind in BY_KIND_ORDER`. D-08 removes `test_suite` and `dependency` from `BY_KIND_ORDER`. If placement keeps iterating `BY_KIND_ORDER`, **test_suites and dependencies will never be discovered or placed**, so they cannot nest anywhere — breaking IDX-04/05 entirely.

**Resolution (drives the plan):** Decouple *placement kinds* from *render order*.
- Introduce a module constant `_PLACEABLE_KINDS = ("app", "package", "test_suite", "dependency", "plugin")` used **only** by `_place_entities`' iteration loop and the `by_kind` sort key.
- `BY_KIND_ORDER = ("app", "package", "plugin")` is used **only** for *rendering* the flat top-level By-Kind groups (D-03/D-08).
- The `by_kind.sort` key (L289) must use `_PLACEABLE_KINDS.index(e.kind)` — using `BY_KIND_ORDER.index` would `ValueError` on a by-kind-placed test_suite/dependency (which still land in `by_kind` for multi/zero-domain cases).
- `_render_by_kind` iterates `BY_KIND_ORDER` (app/package/plugin) for flat groups; it must **separately** nest test_suites/deps under each package/app it renders, and never emit a flat `### Test Suites` / `### Dependencies` group.

This is exactly D-01's "key fix that makes flat-section removal safe."

---

## 3. By-Kind nesting (D-01/D-02) — what data is needed

`_render_domain_section` nests via `parent_pkg_names`, but that field is **only populated for single-domain placements** today (L258). A cross-cutting (by-kind) package's test_suites/deps land in `by_kind` (or under a domain if single-domain) and currently carry no link to the by-kind package.

**Needed:** populate `parent_pkg_names` for **by-kind-placed** dependencies/test_suites too — the consuming/tested package names, *unscoped by domain*. The existing `_consumer_pkgs_in_domain` is domain-scoped; planning adds a domain-agnostic helper (or generalizes it) returning all consumer/tested package names. Then `_render_by_kind` groups by-kind deps/suites under their parent package/app bullets exactly like `_render_domain_section`.

**Edge case — a by-kind package whose test_suite/dep was placed under a domain (single-domain) won't appear in by_kind.** Per D-04 routing this is correct: if the suite/dep qualifies for a single domain it renders there; only multi/zero-domain suites/deps are in by_kind. A by-kind *package* (zero/multi-domain) nests only the suites/deps that are themselves in by_kind under it. Duplication across contexts is expected (D-10).

---

## 4. Internal-dependencies sub-list (D-09/D-11)

Under each package/app render two **separate** nested sub-lists:
1. **"Dependencies"** — external deps via `used_by` (existing `parent_pkg_names` grouping → dependency entity links).
2. **"Internal dependencies"** — workspace package→package deps via `depends_on_package`, linking to the **package/app** entity page (not a dependency page).

**Source (D-11):** reuse Phase 55's `describe_package(conn, name=<pkg>).internal_dependencies` (outgoing). For an **app** node, `describe_package` returns `None`, so the plan must obtain outgoing `depends_on_package` for apps too. Cheapest faithful approach: add a tiny graph-io read that returns outgoing `depends_on_package` dst-names for a node of kind package **or** app (or call the existing parameterized query shape). Since wiki-io must not write parallel SQL (D-11) and `describe_package` is package-only, **the plan adds one small query function to `graph_io.queries` — `internal_dependencies_of(conn, *, name)` — that runs the L437-447 query for `src.kind IN ('package','app')`** and is reused by wiki-io for both packages and apps. This keeps the SQL in graph-io (honoring D-11's intent) and covers apps that `describe_package` cannot.

To render an internal-dep as a wikilink we need the **target package/app's URI** (for `short_filename`). `internal_dependencies_of` returns names; map each name → its `PlacedEntity`/URI. Build a `name→PlacedEntity` index for package+app kinds during placement so `_render_by_kind`/`_render_domain_section` can resolve internal-dep names to links. Internal deps whose target isn't a known package/app entity are skipped (defensive).

---

## 5. Inline summaries (D-06/D-07)

- Add `summary: str = ""` to `PlacedEntity`.
- Populate during `_place_entities` by reading the entity page file `wiki_root/entities/<stem>.md` frontmatter `summary:` (NOT the graph attr — Phase 56 makes `summary:` human-editable / fill-when-empty). The stem is `_short_filename(uri, collision_set, suite_kind=, pkg_for_suite=)` — the **same** derivation `_entity_wikilink` uses, so they agree.
- **`_place_entities` does not currently receive `wiki_root` or `collision_set`.** It is called from `_render` (which has both). Planning threads `wiki_root` + `collision_set` into `_place_entities` (signature change; `_render` already computes both at L589/L594). The collision_set is needed so the stem matches the written entity filename including `__<6hex>` disambiguators.
- Render inline as `- {link} — {summary}` (empty summary → no suffix), matching `_render_curated_section` L569-570. Applies to **every** entity entry (packages, apps, plugins, nested suites/deps, internal deps) per SC#3 ("each entity entry").
- Reading a missing entities dir / missing file / no-frontmatter must degrade to empty summary (no crash) — mirror `_scan_curated_lane`'s tolerant reads.

---

## 6. Tests that MUST change (IDX-02 fallout + new coverage)

| Test (current line) | Change |
|---|---|
| `test_module_constants` (L76-86) | `BY_KIND_ORDER == ("app","package","plugin")`; `KIND_LABELS` adds `app→"Apps"`, drops `test_suite`/`dependency` labels (or keeps them harmlessly — but assertions on removed keys must go). |
| `test_by_kind_section_order` (L510-527) | No more `### Dependencies` flat group. Rewrite to assert app/package/plugin order and that deps nest under their package, not a flat `### Dependencies`. |
| `test_test_suites_subheading` (L545-565) | `### Test Suites` flat heading no longer exists at top level; nested `  - Test Suites` under a package does (only for by-kind/domain-nested placement). Update to assert the nested form. |
| `test_generate_index_against_fixture_graph` (L568-633) | `### Dependencies` flat assertion (L621) removed; `by_kind_count` semantics change (boto3 is multi-consumer → now nests under pkg-a & pkg-b rather than a flat group). Recount. Add piped-link + summary assertions. |
| `test_multi_domain_entity_in_by_kind` (L785-802) | Asserts `### Test Suites` flat heading (L799) — update to nested form. |
| `test_cross_cutting_in_by_kind_only` (L764-783) | Bare-stem `[[wiki/entities/pkg_pkg-cross]]` (L772-775) → piped `[[wiki/entities/pkg_pkg-cross|pkg-cross]]`. |
| `test_empty_sections_omitted` (L834-859) | Asserts bare `[[wiki/entities/pkg_pkg-solo]]` (L853) → piped form. |
| `test_single_domain_with_one_package` (~L470) | Bare-stem assertion → piped form. |
| `test_sub_domain_nesting`, `test_plugin_always_by_kind`, etc. | Any bare-stem `[[wiki/entities/...]]` substring assertions → piped form (grep for `[[wiki/entities/` in the test file). |
| `test_snapshot_against_agent_research` (L968-974) | syrupy snapshot — **regenerate** with `--snapshot-update` after the render changes (skipped if no live graph, but regenerate when a live `.graph-wiki/graph.db` exists). |
| **NEW** | App By-Kind section (IDX-01): seed an `app` node multi/zero-domain → `### Apps` appears before `### Packages`; single-domain app → renders under its domain. |
| **NEW** | Internal-deps sub-list (IDX-05/D-09): seed `depends_on_package` edge → `  - Internal dependencies` nested sub-list with a link to the internal package's entity page, distinct from `  - Dependencies`. |
| **NEW** | Inline summary (IDX-03): write an entity page with `summary:` frontmatter → index entry renders `- {link} — {summary}`; empty summary → no suffix. |

**Piped-link assertion shape:** display text = `entity.name`. For `pkg-cross` → `[[wiki/entities/pkg_pkg-cross|pkg-cross]]`. For a test_suite the *target stem* is kind-aware (`tests_cross`, `unit_tests_<pkg>`) but the *display name* is `entity.name` (the suite's node name) per D-05.

---

## 7. Determinism / write-if-changed invariants (must not regress)
- `test_determinism_across_permutations` (L679) and `test_write_if_changed` (L701) must stay green. New reads (entity-page frontmatter) and new sub-lists must be **sorted deterministically** (alphabetical by name/uri — Claude's discretion per CONTEXT, alpha is the safe default) so permuted insertion order still yields byte-identical output.
- The summary read introduces **filesystem dependence**: the same graph with different entity-page files produces different output. That's intended (IDX-03). Determinism tests build a fresh `tmp_path` wiki with no entity pages → all summaries empty → still deterministic. Confirmed safe.

---

## 8. Hard execution-ordering dependency (NOT a planning blocker)
- Phase 55 (`depends_on_package` edge + `describe_package` internal-deps) is **landed** (Complete, 2/2 + VERIFICATION passed).
- Phase 56 (`summary:` frontmatter on entity pages) is **planned but NOT executed** (4 plans, 0 summaries as of 2026-05-28). IDX-03's output is only *correct* once Phase 56 populates `summary:` on entity pages — but the code reads frontmatter tolerantly (empty when absent), so Phase 57 *code* is correct regardless; only the *rendered content* depends on 56.
- **Therefore: planning Phase 57 now is safe. EXECUTION of Phase 57 must occur after Phase 56 lands** (otherwise the snapshot regenerates against summary-less pages and IDX-03 shows no inline summaries). The plan records this as an execution-gate note.

---

## 9. Validation Architecture
- **Framework:** pytest (wiki-io package), existing `test_index_generator.py` + `make_index_fixture_graph` conftest fixture (builds in-memory graph from a declarative node/edge spec; supports `app` nodes + `depends_on_package` edges with no schema change).
- **Quick command:** `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py -q`
- **Snapshot:** `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py -q --snapshot-update` (syrupy) — run once after render changes, then commit the updated `.ambr`.
- All five IDX requirements have unit-test coverage in this one file. No manual-only verifications.
