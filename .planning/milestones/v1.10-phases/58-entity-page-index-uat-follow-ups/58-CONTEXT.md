# Phase 58: Entity Page & Index UAT Follow-Ups - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Three wiki-io defects/enhancements surfaced during v1.10 UAT (Phases 56–57):

1. **Related section** — entity pages ship a static `## Related` block of `<...>` placeholder links.
2. **Summary placeholder** — the empty-description `summary:` marker breaks Obsidian rendering inline.
3. **Test-suite fan-out** — every package nests the same nine `tests`-named suites in the generated index.

Bug-fix / polish phase confined to `wiki-io` and `graph-io`. No new product capabilities.

> **Roadmap criterion #1 is reinterpreted by this discussion** — see D-01. Criterion #1 as written ("populate `## Related` from the node's graph edges") is **superseded**: Related becomes a clean empty marker now; dynamic population is deferred (see Deferred Ideas). The ROADMAP success criterion should be updated to match before verification.

</domain>

<decisions>
## Implementation Decisions

### Item #1 — `## Related` section
- **D-01: Clean empty marker now; defer real population.** Related is conceptually about inbound references from *curated* wiki pages (`concepts/`, `adrs/`, `architecture/`) that reference the entity — **not** graph edges. Those curated pages are not in the graph today (confirmed: `describe_*` exposes no concept/ADR/architecture relation). So Phase 58 does NOT derive Related from graph edges and does NOT build a backlink scanner. Instead, replace the static `<...>` placeholder bullet list in the entity templates with a single clean fill-me-in message, e.g. `No related concept, ADR, or architecture pages yet.`
- **D-02: Marker must be Obsidian-safe** — no leading `>` (blockquote), no angle brackets (`<...>`), and avoid `:` per Item #2's rendering concern. Same constraint family as D-05.
- **D-03: Scope = entity templates.** Edit the `## Related` blocks in the `entity-*.md` page templates (`entity-package.md:36`, `entity-app.md:42`, `entity-plugin.md:24`, and any other `entity-*` template carrying a `## Related`). The block is `<...>` instruction text left untouched by the renderer (two-token rule), so editing the template files is sufficient — no `entity_writer` logic change needed for this item. Leave `## Related patterns` in `concept*.md` alone (different section).

### Item #2 — `summary:` placeholder format
- **D-04: Plain-text, Obsidian-safe marker.** Replace `> TODO: <add a one-line summary for {name}>` at `entity_writer.py:587` with a plain-text form carrying **no leading `>`, no angle brackets, and no `:`** (Pat flagged that a colon may also break inline rendering). Recommended form: `TODO add a one-line summary for {name}`. Final exact string is planner's discretion within those constraints.
- **D-05: Scope strictly to the entity `summary:` placeholder** (the one rendered inline in the index, `index_generator.py` `_read_entity_summary`). Do NOT sweep sibling templates (`source.md`, `AGENTS.md.template`, `CLAUDE.md.template` `<one-line summary>`) — they are body authoring instructions, not index-rendered.
- **D-06: Update test expectations** that assert on the exact placeholder string (tolerant-read / empty-summary tests).

### Item #3 — test-suite fan-out
- **D-07: Confirmed root cause.** `_consumer_pkgs` (`index_generator.py:282`) and `_consumer_pkgs_in_domain` (`index_generator.py:251`) both resolve target packages with `ts.name = ?`. All 9 `test_suite` nodes share `name='tests'`, so each suite matches every other suite's `tests` edges and nests under every consumer package. The underlying per-suite `tests` edges are correct.
- **D-08: Fix BOTH sides (Pat's explicit choice).**
  - **Scan-side (graph-io):** give `test_suite` nodes unique, human-meaningful names at scan time — package-qualified, e.g. `wiki-io-unit-tests`, `graph-wiki-agent-int-tests`. Rename point is `test_suites.py:336-338` where package-owned suites currently take `Path(r.rel_path).name`. New shape: `<owner_name>-<suite_kind>-tests`. (Abbreviation of `integration`→`int` per Pat's example is a minor open detail — see Discretion.)
  - **Renderer-side (wiki-io):** resolve consumer packages by `test_suite` node **uri/id** rather than `name`. `PlacedEntity` already carries `.uri`; thread it into `_consumer_pkgs` and fix the same name-keyed flaw in `_consumer_pkgs_in_domain`.
- **D-09: Cascade awareness.** Renaming suite nodes changes the `physically_contains` edge `dst=("test_suite", suite_name, rel_path)` tuple (`test_suites.py:371`), the `tests` derived edges (`derived_edges.py`), `describe_test_suite(suite_name=...)`, and many name-keyed queries in `graph_io/queries.py`. Researcher must map every name-based suite lookup. Repository-owned suites (which use full `rel_path` as name) are already unique — confirm they don't need the rename.

### Item #4 — golden / fixture rebaseline
- **D-10: Regenerate affected goldens in-phase.** All three changes alter generated output. Rebaseline entity-page + index golden/integration fixtures by **regenerating from the fixed generator** (the source of truth), as part of this phase's plans. Consistent with `.claude/rules/backward-compatibility.md` ("entity content can be deleted and regenerated at will"). The suite-rename (D-08) will also move `graph-io` fixtures.

### Claude's Discretion
- Exact final string of the summary marker (D-04) and the Related marker (D-01), within the no-`>`/no-`<>`/no-`:` constraint.
- Whether suite-kind appears as `integration` or abbreviated `int` in the node name (Pat's example used `int`; default to the literal `suite_kind` value unless an abbreviation map is cheap).
- Regenerate-vs-edit decision *per individual fixture* where blast radius makes wholesale regeneration awkward (D-10 sets the default to regenerate).

### Folded Todos
All three pending todos map 1:1 to the success criteria and are folded into scope:
- **`2026-05-28-populate-entity-related-section-from-graph-edges`** → Item #1. NOTE: resolution diverges from the todo's "derive from graph edges" framing — see D-01 (clean marker now, defer population).
- **`2026-05-29-fix-entity-summary-placeholder-breaks-obsidian-rendering`** → Item #2 (D-04/D-05/D-06).
- **`2026-05-29-test-suites-fan-out-under-every-package-in-index`** → Item #3 (D-07/D-08/D-09).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition & todos
- `.planning/ROADMAP.md` — Phase 58 goal + success criteria (criterion #1 reinterpreted by D-01).
- `.planning/todos/pending/2026-05-28-populate-entity-related-section-from-graph-edges.md` — Item #1 background.
- `.planning/todos/pending/2026-05-29-fix-entity-summary-placeholder-breaks-obsidian-rendering.md` — Item #2 background.
- `.planning/todos/pending/2026-05-29-test-suites-fan-out-under-every-package-in-index.md` — Item #3 background + live-graph evidence.

### Item #1 — Related
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md` §`## Related` (line 36) — static placeholder block to replace.
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md` §`## Related` (line 42).
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md` §`## Related` (line 24).

### Item #2 — Summary placeholder
- `packages/wiki-io/src/wiki_io/entity_writer.py:587` — `summary:` placeholder origin (`scanner_frontmatter_for_node`).
- `packages/wiki-io/src/wiki_io/index_generator.py` — `_read_entity_summary` / inline-summary render (the breakage site).

### Item #3 — Test-suite fan-out
- `packages/wiki-io/src/wiki_io/index_generator.py:260` — `_consumer_pkgs` (name-keyed; fix to uri/id).
- `packages/wiki-io/src/wiki_io/index_generator.py:224` — `_consumer_pkgs_in_domain` (same flaw).
- `packages/wiki-io/src/wiki_io/index_generator.py:131` — `PlacedEntity` (already carries `.uri`).
- `packages/graph-io/src/graph_io/test_suites.py:331-375` — test_suite node naming + `physically_contains` edges (rename point).
- `packages/graph-io/src/graph_io/derived_edges.py` — `tests` edge recomputation (name-referenced).
- `packages/graph-io/src/graph_io/queries.py` — name-keyed suite queries (e.g. `describe_test_suite`, lines ~427/574/1089/1140).

### Project rule
- `.claude/rules/backward-compatibility.md` — entity content regenerated at will (basis for D-10).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PlacedEntity.uri` (`index_generator.py:131`) — already populated; the uri/id needed for the renderer-side Item #3 fix is in hand, no new plumbing to fetch it.
- `_classify_suite_kind` (`test_suites.py:112`) → `suite_kind` ∈ {`unit`, `integration`} — the kind component for the new package-qualified suite names.
- Two-token rule (`entity_writer._render_entity_page`) — `<...>` template text is left untouched by the renderer, so Item #1 is a template-content edit, not a code-path change.

### Established Patterns
- **Two-token convention** (Phase 56 D-01): `{{var}}` = scanner-substituted; `<...>` = authoring instruction. Item #1's marker must not reintroduce `<...>` or `{{...}}`.
- **`summary:` is fill-when-empty** (Phase 56 D-07), not scanner-owned — Item #2 only changes the *empty* placeholder, not the merge semantics.
- **Suite filename scheme is already kind-aware** (`short_filename` with `suite_kind`/`pkg_for_suite` → `unit_tests_<pkg>`). The D-08 node rename makes the node *name* meaningful too; confirm interaction so filenames and names stay consistent (and the rename doesn't make the filename disambiguator redundant in a confusing way).

### Integration Points
- Item #3 spans **two packages**: `graph-io` (node naming, scan-time) and `wiki-io` (index renderer). Plan ordering should land the graph-io rename + its fixture rebaseline before/with the wiki-io renderer fix.

</code_context>

<specifics>
## Specific Ideas

- Suite naming examples Pat gave: `wiki-io-unit-tests`, `graph-wiki-agent-int-tests` → pattern `<package>-<suite_kind>-tests`.
- Related empty message should name the curated page types it will eventually link: concepts, ADRs, architecture.

</specifics>

<deferred>
## Deferred Ideas

- **Dynamic `## Related` population** — populate Related with the curated `concepts/`/`adrs/`/`architecture/` pages that reference an entity. Pat's stated future direction: this becomes possible "if we decide to add the non-entity wiki pages to the graph." A future phase either (a) adds those pages as graph nodes and derives Related via edges, or (b) builds a filesystem wikilink-backlink index. Out of scope for Phase 58.
- **Graph-edge relations in Related** (the literal roadmap-criterion-#1 reading: `depends_on`/domains/dependencies) — judged redundant with frontmatter + index nesting and not what Pat wants in Related; not pursued.

### Reviewed Todos (not folded)
None — all three matched todos were folded.

</deferred>

---

*Phase: 58-entity-page-index-uat-follow-ups*
*Context gathered: 2026-05-28*
