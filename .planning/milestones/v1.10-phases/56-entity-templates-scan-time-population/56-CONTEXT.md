# Phase 56: Entity Templates & Scan-Time Population - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Make generated entity pages contain real, substituted content instead of raw template scaffolding:

1. **ENTITY-01/02** — Migrate the legacy per-kind `overview.md` prose into the `entity-<type>.md` templates (curated per kind), with `TODO` placeholders for human/LLM-authored sections.
2. **ENTITY-03** — Delete the legacy `package/`, `domain/`, `plugin/`, `app/` template directories; no dead links remain.
3. **SCAN-01** — At scan time, substitute template data placeholders with real values so no unsubstituted placeholder token survives.
4. **SCAN-02** — The scanner writes a `summary:` frontmatter field per entity page, derived from the graph node's description, consumed by IDX-03 (Phase 57).

**Cross-package note:** this phase is NOT wiki-io-only. The `summary:` decision (D-05/D-06) requires a small **graph-io** change to populate `attrs["description"]` from pyproject for packages/apps. Plan accordingly.
</domain>

<decisions>
## Implementation Decisions

### Placeholder syntax & substitution (SCAN-01)
- **D-01:** **Two distinct token syntaxes.** Scan-substituted *data* placeholders use **`{{var}}`** (double-brace). Human-authoring *instructions* use **`<...>`** and are NEVER substituted by the scanner. This resolves the literal SCAN-01 ↔ ENTITY-02 contradiction (SCAN-01 said "no `<...>` survives"; ENTITY-02 wants `TODO: <instructions>` to survive). **Reinterpret SCAN-01's verify as: "no unsubstituted `{{...}}` token survives in a generated entity page."** The `# <Package Name>` example in SCAN-01 becomes `# {{package_name}}` in the entity templates.
- **D-02:** **Reuse the existing mechanism.** `wiki_io.init_vault.render_template()` already does `text.replace("{{"+key+"}}", value)` (init_vault.py:~78-94). Invoke the same `{{...}}` substitution from `entity_writer._render_entity_page()` (entity_writer.py:482-500), which currently does NO body substitution. Don't introduce Jinja or a new templating dep.
- **D-03:** **Unfilled placeholder → TODO.** When a `{{var}}` has no value available from the node (e.g. missing version/description), substitute a `TODO: <add ...>` marker (see D-12 format) rather than leaving the raw `{{var}}` or an empty string. Keeps SCAN-01 satisfied (no surviving `{{...}}`) and surfaces the gap.
- **D-04:** Exact variable set is **Claude's discretion**, grounded in the node's available data (name, slug, kind, path, language, version, domains, description, etc.). Must cover every `{{var}}` the migrated templates introduce.

### summary: field (SCAN-02) — cross-package
- **D-05:** **Source = `node.attrs["description"]`, read uniformly** across all kinds. Today this is only reliably populated for domains.
- **D-06:** **Populate it (small in-scope graph-io change).** Extend the graph-io package/app scan to store `[project].description` (pyproject) into the package/app node's `attrs["description"]`, so packages/apps get a real summary. Domains already carry a description. This is a deliberate cross-package touch — graph-io is where the description originates; SCAN-02's "derived from the node's description" is only meaningful if the description exists on the node. Empty/absent → `TODO:` fallback (D-03 style).
- **D-07:** **`summary:` ownership = fill-when-empty (NOT plain scanner-owned).** The scanner writes `summary:` only if the page has none; a human-edited summary survives re-scans. This is a **third category** — neither in the overwrite-every-scan `SCANNER_OWNED_KEYS` set nor purely human-owned. **Special-case it in `merge_frontmatter`** (entity_writer.py); do NOT just add `summary` to `SCANNER_OWNED_KEYS` (that would clobber human edits). Verify: re-scan preserves a human-set summary; re-scan fills an empty/absent one from the description.

### Migration mapping & TODO convention (ENTITY-01/02)
- **D-08:** **Curated per-kind migration.** Migrate the meaningful sections into each `entity-<type>.md` (e.g. Purpose / Key patterns / Conventions → entity-package; Scope → entity-domain; Purpose / Platform & runtime → entity-app), exercising editorial judgment. Drop redundant/obsolete sections — do NOT carry over the `plugin/overview.md` Purpose+testing **duplication** the scout found.
- **D-09:** **All testing-derived content → `entity-test-suite.md`** (per ENTITY-01's explicit rule), including the package testing sections and `app/testing.md`. `entity-test-suite.md` already exists (2026-05-28).
- **D-10:** The 7 `entity-<type>.md` templates **already exist** — this phase fills them with migrated content, it does not create them from scratch.
- **D-11:** Sections needing human/LLM authorship get a `TODO` placeholder, not an empty heading or dead link (ENTITY-02).
- **D-12:** **TODO format = visible blockquote: `> TODO: <instructions>`.** Renders visibly in the wiki (so a reader sees the gap), stands out from real content, and the `<...>` inside is authoring-instruction text (never scanner-substituted per D-01).

### Legacy deletion (ENTITY-03)
- **D-13:** **Delete** the legacy `package/`, `domain/`, `plugin/`, `app/` template directories (incl. their `overview.md` / `testing.md`) once content is migrated.
- **D-14:** **No init_vault code change expected.** `init_vault.py:~251-263` copies `page-templates/` recursively via rglob; deleting the source subdirs means they simply stop being seeded. Confirm during execution that no *other* code references those dirs by path.
- **D-15:** **Delete the 4 obsolete tests** in `packages/wiki-io/tests/test_overview_template_wikilinks.py` — they assert wikilinks in the now-deleted overview/context templates (these are the 4 pre-existing failures the Phase 54 executor flagged, FileNotFoundError, explicitly "slated for removal in Phase 56"). New entity-template coverage lives in `test_entity_templates.py` + the SCAN-01 substitution tests.
- **D-16:** **Dead-link verification = repo grep only, NO new permanent test.** During execution, grep for references to the legacy dirs and confirm generated pages have no dead links. Don't add a standing dead-link regression test.

### Claude's Discretion
- The exact `{{var}}` variable set and per-kind section lists (D-04, D-08), grounded in node data and the scout's section analysis.
- How the graph-io description-population (D-06) is wired in `packages.refresh()` — coordinate with the Phase 55 changes already planned for the same function (55-01-PLAN.md touches `refresh()`); avoid stepping on that work.
- Whether to add a focused SCAN-01 test (assert no `{{...}}` in generated pages) and a SCAN-02 test (summary fill-when-empty) — encouraged but shape is open.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope
- `.planning/REQUIREMENTS.md` §ENTITY-01/02/03, §SCAN-01/02 (lines ~25-32) — the five requirements this phase satisfies.
- `.planning/ROADMAP.md` §"Phase 56" — goal + 4 success criteria (note SC#1 substitution, SC#2 summary, SC#3 TODO sections, SC#4 legacy dirs gone / no dead links).
- `.claude/rules/backward-compatibility.md` — entity content is regenerable; user rebuilds the wiki on migration; **existing-vault `.templates/` cleanup needs no migration shim** (relevant to D-13/D-14).

### Templates (the assets being migrated/deleted)
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md`, `entity-domain.md`, `entity-plugin.md`, `entity-app.md`, `entity-dependency.md`, `entity-repository.md`, `entity-test-suite.md` — the 7 targets to fill (D-10).
- `packages/wiki-io/src/wiki_io/assets/page-templates/package/overview.md`, `domain/overview.md`, `plugin/overview.md`, `app/overview.md`, `app/testing.md` — LEGACY sources to migrate-then-delete (D-08/D-09/D-13). Note plugin/app duplication.

### Entity writer & substitution (wiki-io)
- `packages/wiki-io/src/wiki_io/entity_writer.py:482-500` — `_render_entity_page()`: where `{{...}}` substitution must be added (D-02); currently uses template body verbatim.
- `packages/wiki-io/src/wiki_io/entity_writer.py:522-525` — `_template_path_for_kind()`: kind → `entity-<kind>.md` mapping.
- `packages/wiki-io/src/wiki_io/entity_writer.py:658-799` — `write_entities()` orchestrator; `scanner_frontmatter_for_node()` (~731) builds the scanner frontmatter dict (where `summary:` derivation hooks in, D-05/D-07); `merge_frontmatter()` (~737) — where the fill-when-empty special-case for `summary` goes (D-07).
- `packages/wiki-io/src/wiki_io/entity_writer.py:104-137` — `SCANNER_OWNED_KEYS` (note: `summary` deliberately NOT added here per D-07).
- `packages/wiki-io/src/wiki_io/init_vault.py:~78-94` — `render_template()` `{{...}}` `.replace()` mechanism to reuse (D-02); `~251-263` — recursive template copy (D-14).

### Graph-io (cross-package — description population)
- `packages/graph-io/src/graph_io/packages.py::refresh()` — where package/app node attrs are built; add `attrs["description"]` ← pyproject `[project].description` (D-06). **Coordinate with `55-01-PLAN.md`, which also edits `refresh()`** (Phase 55 suppression/edge work) — both phases touch the same function; sequence to avoid conflict.
- `packages/graph-io/src/graph_io/queries.py` — `DomainDescription.description` (the existing typed description, ~L90-95); confirm how entity_writer reads node attrs/description.

### Index generator (downstream consumer — Phase 57)
- `packages/wiki-io/src/wiki_io/index_generator.py:~351,380,569` — already reads `summary` from entity pages; SCAN-02's field feeds IDX-03 inline summaries (Phase 57). `summary:` must land in this phase first.

### Tests
- `packages/wiki-io/tests/test_overview_template_wikilinks.py` — the 4 obsolete tests to DELETE (D-15).
- `packages/wiki-io/tests/test_entity_writer.py` — merge/render/lock tests; the merge tests (~L117-247) will need a case for the `summary` fill-when-empty behavior (D-07).
- `packages/wiki-io/tests/test_entity_templates.py` — entity template existence/frontmatter validation; extend for migrated content + SCAN-01 (D-04 discretion).
- `packages/wiki-io/tests/integration/test_entity_writer_integration.py` — real-workspace roundtrip (`# integration-gate-allow`); good home for an end-to-end "no `{{...}}` survives + summary populated" assertion.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `init_vault.render_template()` `{{...}}` `.replace()` (init_vault.py:~88) — directly reusable for SCAN-01 substitution in `_render_entity_page()` (D-02); no new templating dependency.
- All 7 `entity-<type>.md` templates already exist (D-10) — phase fills, not creates.
- `entity-test-suite.md` already exists (2026-05-28) as the migration target for all testing-derived content (D-09).
- `merge_frontmatter()` already distinguishes scanner-owned vs human keys — extend it with the fill-when-empty case for `summary` (D-07).

### Established Patterns
- python-frontmatter for read/write; `SCANNER_OWNED_KEYS` (entity_writer.py:104-137) enumerates overwrite-every-scan keys — `summary` intentionally stays out of it (D-07).
- Scanner-owned vs human-owned merge model — `summary` introduces a NEW third "fill-when-empty" category; implement carefully so it doesn't clobber human edits.

### Integration Points
- `entity_writer.write_entities()` runs during scan, reading graph-io node data — the join point for both `{{...}}` substitution (D-02) and `summary:` derivation (D-05).
- **graph-io `packages.refresh()` is touched by BOTH Phase 55 (already planned: 55-01-PLAN.md) and Phase 56 (D-06 description population).** Execution must sequence Phase 55 before/around this to avoid stepping on the same function.
- Index generator (Phase 57) consumes `summary:` — downstream dependency, not modified here.

</code_context>

<specifics>
## Specific Ideas

- The SCAN-01/ENTITY-02 contradiction (no `<...>` vs keep `TODO: <instructions>`) is real and was resolved by the two-syntax rule (D-01) — downstream agents must honor it: `{{...}}` = data (substituted), `<...>` = instruction (retained). Don't "fix" surviving `<...>` inside TODO blockquotes.
- The 4 failing `test_overview_template_wikilinks.py` tests are NOT a regression — they're pre-existing (fail against pre-Phase-54 commit too) and this phase deletes them (D-15).
- Pat values self-documenting code (carried from Phases 54/55) — comment the `summary` fill-when-empty special-case and the `{{...}}`-vs-`<...>` distinction so a future reader doesn't collapse them.

</specifics>

<deferred>
## Deferred Ideas

- **Richer per-kind summary sources** (deps ← ecosystem/version blurb, test-suites ← derived from tested packages) — rejected in favor of the uniform `attrs["description"]` source (D-05). Revisit only if TODO-fallback summaries prove too sparse in practice.
- **Permanent dead-link regression test** — explicitly deferred per D-16 (repo grep only this phase). Could be added later if legacy-path references keep creeping back.
- **Dependency-family clustering** — already in REQUIREMENTS.md "Future Requirements"; out of scope here.

None of these expand Phase 56 scope.

</deferred>

---

*Phase: 56-entity-templates-scan-time-population*
*Context gathered: 2026-05-28*
