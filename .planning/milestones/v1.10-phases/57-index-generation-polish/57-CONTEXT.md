# Phase 57: Index Generation Polish - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Make `wiki/index.md` a genuinely readable projection of the graph. Five concrete changes to `packages/wiki-io/src/wiki_io/index_generator.py`:

1. **IDX-01** — Distinct `app` By-Kind section, separate from packages.
2. **IDX-02** — Human-readable piped entity links `[[wiki/entities/<stem>|<name>]]` (not bare stem).
3. **IDX-03** — Inline one-line summary per entity entry, sourced from the entity page's `summary:` frontmatter.
4. **IDX-04** — Test-suites nested under the package(s) they test (duplicated across packages); flat By-Kind "Test Suites" section removed.
5. **IDX-05** — Dependencies nested under the package(s) that use them (duplicated across packages); flat By-Kind "Dependencies" section removed.

**Hard dependency on Phases 55 + 56:** Phase 55's `depends_on_package` edge (internal deps) and Phase 56's `summary:` frontmatter must be landed before this phase's output is correct.
</domain>

<decisions>
## Implementation Decisions

### Nesting placement — universal (IDX-04/05)
- **D-01:** **Nest test-suites/deps under package AND app entries in the By-Kind section too**, not just under domain sections. Today `_render_domain_section()` nests them but `_render_by_kind()` renders flat. After this change every package/app shows its nested items regardless of placement — so a **cross-cutting (multi-domain, By-Kind-only) package** never loses its test-suites/deps when the flat sections are removed. This is the key fix that makes flat-section removal safe.
- **D-02:** Apps nest their test-suites/deps **identically to packages** (D-06 app section).

### App section (IDX-01)
- **D-03:** **By-Kind order = `app, package, plugin`** — apps listed first as the top-level deliverables. (`test_suite` and `dependency` are removed from `BY_KIND_ORDER` entirely per D-08.) Add the `app` entry to `KIND_LABELS`. Requires `_place_entities()` to list apps (via graph-io `list_apps()` — confirm it exists; app classification landed in v1.9).
- **D-04:** **Apps follow the same placement rule as packages** — a single-domain app renders under its domain section; a multi-domain app renders in the By-Kind app section. Do NOT force apps to always live only in By-Kind. Consistent with `_place_entities()` single-vs-multi-domain routing.

### Entity links (IDX-02)
- **D-05:** `_entity_wikilink()` (index_generator.py:419-432) renders `[[wiki/entities/{stem}|{name}]]` — display text = `entity.name` (the `PlacedEntity.name` field, always available). Stem derivation via `_short_filename()` is unchanged. **This forces test updates:** existing assertions expecting the bare-stem form (e.g. `test_cross_cutting_in_by_kind_only` asserting `[[wiki/entities/pkg_pkg-cross]]`, ~L773) and any syrupy snapshot must be updated to the piped form.

### Inline summaries (IDX-03)
- **D-06:** **Source = the entity page's own `.md` frontmatter `summary:` field** — NOT the graph node `attrs["description"]`. Rationale: Phase 56 (D-07) makes `summary:` fill-when-empty, so a human can edit a page's summary; reading the graph attr would show a stale/different value. Reading the entity file mirrors the existing `_scan_curated_lane()` pattern (the index already reads curated-page frontmatter), so it's not a new I/O smell.
- **D-07:** Add a `summary` field to `PlacedEntity` (dataclass ~L114-133); populate it when placing entities by reading the entity `.md` frontmatter. Render inline as `- {link} — {summary}` exactly matching `_render_curated_section()` (~L569-570). Empty summary → render the link with no ` — …` suffix (same as curated lanes today).

### Nested dependency composition (IDX-05)
- **D-08:** **Remove `test_suite` and `dependency` from `BY_KIND_ORDER`** (and from `_render_by_kind()` flat subsections). After this phase By-Kind has only `app`, `package`, `plugin`. Test-suites/deps appear ONLY nested under their package/app (in both domain and By-Kind contexts per D-01).
- **D-09:** **Under each package/app, render TWO separate nested sub-lists:**
  - **"Dependencies"** — external deps via `used_by` edges → link to dependency entities.
  - **"Internal dependencies"** — internal package deps via the Phase 55 `depends_on_package` edge → link to the internal package/app entities.
  The distinct heading reflects that internal deps link to real package pages (not dependency pages) and surfaces the Phase 55 data the roadmap says IDX-05 relies on. Do NOT merge them into one list and do NOT drop the internal sub-list.
- **D-10:** **Duplication is expected** — a test-suite testing 2 packages appears under both; a dependency used by N packages appears under each (per IDX-04/05 wording "duplicated across packages where appropriate").
- **D-11:** **New graph-io queries needed** for the `depends_on_package` edge: given a package, list outgoing `depends_on_package` (its internal dependencies). Phase 55 Plan 02 already adds `describe_package` both-direction surfacing — reuse/extend those queries rather than writing parallel SQL in wiki-io.

### Claude's Discretion
- Ordering within each nested sub-list (alphabetical by name is the safe default).
- Exact sub-list heading text/indentation, matching the existing `_render_domain_section()` nesting style (~L471-479).
- Whether to thread `summary` via a small file-read pass or fold it into the existing entity placement read.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope
- `.planning/REQUIREMENTS.md` §IDX-01..IDX-05 (lines ~12-16) — the five requirements.
- `.planning/ROADMAP.md` §"Phase 57" — goal + 5 success criteria; **UI hint: yes** (index.md layout is the user-facing surface).

### Upstream phase contracts (hard dependencies)
- `.planning/phases/55-dependency-classification-fix/55-CONTEXT.md` — `depends_on_package` edge (D-04: src=consumer, dst=internal package); used for IDX-05 internal-deps sub-list. Phase 55 Plan 02 adds the `describe_package` queries to reuse (D-11).
- `.planning/phases/56-entity-templates-scan-time-population/56-CONTEXT.md` — `summary:` frontmatter is **fill-when-empty** (D-07); this is WHY IDX-03 reads the page file not the graph attr (this phase's D-06).

### The code being changed (wiki-io)
- `packages/wiki-io/src/wiki_io/index_generator.py`:
  - `BY_KIND_ORDER` (L67), `KIND_LABELS` (L69-74) — add `app`, remove `test_suite`/`dependency` (D-03/D-08).
  - `_render_by_kind()` (L534-559) — add nesting (D-01), drop flat test_suite/dependency subsections (D-08).
  - `_render_domain_section()` (L435-500, nesting at L454-479) — existing nesting pattern to mirror in By-Kind.
  - `_entity_wikilink()` (L419-432) — piped link (D-05).
  - `PlacedEntity` dataclass (L114-133) — add `summary` field (D-07).
  - `_place_entities()` (L234-290) — list apps (D-03), populate `summary` (D-07), `parent_pkg_names` (L257-262).
  - `_scan_curated_lane()` (L329-354, `summary` at L351) + `_render_curated_section()` (L562-572, render at L569-570) — the summary-read + inline-render pattern to match for entities (D-06/D-07).
  - `_render()` (L580-630), `generate_index()` (L633-674) — top-level orchestration / write-if-changed.

### Graph-io queries
- `packages/graph-io/src/graph_io/queries.py` — `list_packages`/`list_test_suites`/`list_dependencies`/`list_plugins`; confirm `list_apps()`; `describe_package()` (Phase 55 Plan 02 adds `depends_on_package` both-direction — reuse for D-11). Edges: `tests` (test_suite→package), `used_by` (package→dependency), `depends_on_package` (consumer→internal package).

### Tests
- `packages/wiki-io/tests/test_index_generator.py` — `BY_KIND_ORDER` assertion (L77, update for app/removed kinds), By-Kind order test (L510-527), `test_cross_cutting_in_by_kind_only` bare-stem assertion (~L773, update to piped per D-05), curated summary render test (L895-931, model for IDX-03), syrupy snapshot `test_snapshot_against_agent_research` (L967-976, regenerate after changes).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_render_domain_section()` already nests test-suites/deps under packages (L454-479) — the exact pattern to apply in `_render_by_kind()` for D-01.
- `_scan_curated_lane()` + `_render_curated_section()` already read frontmatter `summary` and render `- {link} — {summary}` (L351, L569-570) — directly reusable shape for IDX-03 (D-06/D-07).
- Phase 55 Plan 02's `describe_package` queries surface `depends_on_package` both directions — reuse for the internal-deps sub-list (D-11), avoid parallel SQL.

### Established Patterns
- `_place_entities()` routes single-domain entities under domains, multi-domain into By-Kind — apps must follow the same routing (D-04).
- Write-if-changed byte comparison + atomic replace (L648-665) — no change needed.
- Syrupy snapshot test asserts byte-for-byte index output — must be regenerated after every render change.

### Integration Points
- Reads graph via graph-io queries; reads entity `.md` frontmatter from the vault (new for entities — D-06).
- Hard upstream: `depends_on_package` (Phase 55) and `summary:` (Phase 56) must be present in the graph/pages for correct output.

</code_context>

<specifics>
## Specific Ideas

- IDX-02's piped-link change WILL break bare-stem test assertions and the snapshot — that's expected, not a regression; update them (D-05).
- Two distinct sub-lists ("Dependencies" vs "Internal dependencies", D-09) is a deliberate readability choice — don't let a reviewer merge them.
- Pat values self-documenting code (carried from 54/55/56) — comment why By-Kind packages now nest (D-01 cross-cutting rationale) and why summary is read from the page not the graph (D-06 / Phase 56 fill-when-empty).

</specifics>

<deferred>
## Deferred Ideas

- **Dependency-family clustering** (grouping `langchain-*` etc.) — already in REQUIREMENTS.md "Future Requirements"; out of scope.
- **Usage counts / weights on nested entries** — not required by any IDX SC; skip unless trivially free.

None of these expand Phase 57 scope.

</deferred>

---

*Phase: 57-index-generation-polish*
*Context gathered: 2026-05-28*
