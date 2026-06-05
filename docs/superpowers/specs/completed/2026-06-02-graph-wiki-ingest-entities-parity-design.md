# Design: graph-wiki ingest → `entities/` parity (Slice 4)

**Date:** 2026-06-02
**Status:** Approved — ready for implementation planning
**Parent:** `2026-06-02-graph-wiki-plugin-entities-parity-design.md` (Slice 4 of that roadmap)
**Topic:** Bring `ingest` to the single-`entities/`-folder wiki model on **both** the `gw` core (`graph_wiki_core.run_ingest_source`) and the `graph-wiki` Claude Code plugin. Define how ingest interacts with scanner-owned entity pages, fix the plugin's currently-broken ingest shim, and make entity pages show their inbound references via a scanner-regenerated section.

## Goal

Ingest is the last command still on the legacy `apps/`+`packages/`+`domains/` layout — and unlike scan (Slice 1), there is **no conformant `gw` behavior to port from**: `gw`'s own `run_ingest_source` also writes legacy paths. So Slice 4 must *define* the correct `entities/` ingest behavior and apply it to both sides at once.

Two concrete defects motivate the slice:

1. **The plugin's Claude-branch ingest is broken.** `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py` does `from wiki_io.ingest_source import main as _core_main`, but `wiki_io.ingest_source` is library-only and exports no `main()` — the shim raises `ImportError` on load. (Confirmed by running it.)
2. **`gw`'s `run_ingest_source` writes the legacy layout.** `_PAGE_TYPE_DIRS` routes `page_type=package → packages/<slug>.md` (`graph_wiki_core/commands/ingest.py:123`), a folder that does not exist in the `entities/` vault — producing orphan pages.

## Background (current state)

**Scan and ingest are architecturally different**, which is why ingest is "a feature, not a port":

- **Scan** (Slice 1) is mechanical. The plugin's Claude branch calls `run_scan(narrate=False)` in-process; the harness does nothing creative.
- **Ingest** is LLM-creative, and the two branches do it differently:
  - **Plugin / Claude branch:** a *prep script* (`scripts/ingest_source.py`) emits a JSON brief; the **harness agent** (`agents/ingestor.md`) then reads/discusses/writes pages by hand with Read/Write/Edit. **No Bedrock.**
  - **`gw` / Bedrock branch:** `run_ingest_source` makes a single Bedrock ingestor call that returns one page, then routes + writes it (`graph_wiki_core/commands/ingest.py:525`).

  They share only the *prep* (text extraction, source-type guess, entity lookup) and the *target-layout rules*.

**Entity pages are scanner-owned and regenerable.** Per `entity_writer.py`, the scanner fully replaces `SCANNER_OWNED_KEYS` frontmatter on every scan and rewrites exactly one H2 body region — `## Narrative` — via `inject_narrative` (`entity_writer.py:935`, `_NARRATIVE_HEADING_RE` at :943); all other sections are preserved verbatim. The project's backward-compat rule states `entity` content "can be deleted and regenerated at will," while `sources/`, `concepts/`, `adrs/`, `architecture/`, `work/` are **preserved**.

**Existing ingest→entity wiring (keep, retarget).** `run_ingest_source` already resolves the entity a source belongs to via `_lookup_entity_by_path` (`ingest.py:135`) / `_lookup_entity_by_name` (`ingest.py:166`) and writes `entity_uri:` frontmatter on the page (`_set_entity_uri_in_body`, `ingest.py:261`). Today that match also forces the *route* (to `packages/`) and slug (`slug_from_uri`). Slice 4 keeps the match but decouples it from routing.

## Decisions

These were settled during brainstorming:

- **Entity interaction:** ingest **augments a preserved section** on entity pages — but indirectly. Ingest never writes into `entities/` pages. Instead it writes durable **forward-links** (an `entity_uri:` anchor + `[[entities/...]]` body wikilinks) into preserved pages, and the **scanner derives the backlinks**.
- **Backlink upkeep:** **scanner-derived.** A new mechanical scan step regenerates a backlink section on each entity page. Robust across full entity rebuilds, zero clobber risk, no merge/dedupe logic in ingest. The section becomes scanner-owned (like `## Narrative`).
- **Backlink key:** the scanner keys backlinks off **`[[entities/<file>]]` wikilinks in page bodies**, not off the singular `entity_uri:` field — so a source touching several packages backlinks from all of them. `entity_uri:` remains the singular "primary/canonical entity" anchor used for slug alignment.
- **Section scope:** **all 7 admitted entity kinds** carry the section (uniform template + scanner logic; some kinds will often show it empty).
- **Backlink breadth:** the section lists **all preserved pages** that link the entity (sources, concepts, ADRs, architecture, work) — so it is named **`## Referenced in wiki`**, not the legacy `## Appears in sources`.
- **Scope:** **both core + plugin** — fix `run_ingest_source` *and* the plugin shim/agent/docs, keeping `gw` and the plugin convergent (as Slices 1–3 did).
- **No Bedrock lazy-imports for ingest.** Unlike scan, there is no "structural-only" ingest — ingest is inherently an LLM task. `run_ingest_source` stays Bedrock-coupled; the plugin's Claude branch never imports it (it uses the Bedrock-free prep script + harness agent), so no lazy-import work is required.
- **Migration:** none (backward-compat rule). Legacy `packages/`/`domains/` ingest output becomes orphaned; the user rebuilds. Slice-3 lint may flag orphans.

### Core principle

> **Ingest writes durable forward-links into preserved categories; the scanner derives backlinks onto entity pages.** Ingest never edits `entities/` pages.

## Slice 4 — components

### A. Shared routing rules — `graph_wiki_core.run_ingest_source`

1. **Drop `package` from `_PAGE_TYPE_DIRS`** (`ingest.py:123`). Valid ingest page_types collapse to `source | concept | adr` — all ingest-owned, preserved dirs. The default-fallback (`page_type not in _PAGE_TYPE_DIRS → concept`) is unchanged.
2. **Decouple entity match from routing.** Keep `_lookup_entity_by_path` / `_lookup_entity_by_name` and `entity_uri:` writing. A matched entity no longer changes the route or forces `slug_from_uri` for the *filename*; instead the matched entity drives:
   - the `entity_uri:` frontmatter anchor (unchanged mechanism, `_set_entity_uri_in_body`), and
   - a `[[entities/<prefix>_<name>]]` body wikilink whose target equals the scanner's on-disk filename.
   The wikilink target must be computed with the **same** filename rule the scanner uses (`wiki_io.entity_writer.short_filename`, `entity_writer.py:159`) — not the legacy `slug_from_uri`. Factor a shared `entity_filename_for_uri(...)` (Bedrock-free) usable by both `run_ingest_source` and the plugin prep.
3. **Ingestor prompt** (`graph_wiki_core/prompts/ingestor.py`): remove `package` from the page_type menu; instruct the model to *reference* entities via `[[entities/...]]` rather than author a package page; describe the `source | concept | adr` choices in entities/ terms.

### B. Scanner backlink regeneration — `run_scan` + `wiki_io` + templates

4. **Add a scanner-owned `## Referenced in wiki` section** to all 7 entity templates (`packages/wiki-io/src/wiki_io/assets/page-templates/entity-*.md`), with a placeholder mirroring `## Narrative` (e.g. `_(scanner will populate on next scan)_`).
5. **New mechanical regen step** — a `wiki_io` helper (sibling to `inject_narrative`, e.g. `wiki_io.backlink_index.inject_referenced_in_wiki`) plus an orchestrating pass that:
   - walks every preserved page (`sources/`, `concepts/`, `adrs/`, `architecture/`, `work/`),
   - collects each `[[entities/<file>]]` wikilink (resolving the link target to an entity filename / URI),
   - for each entity, rewrites its `## Referenced in wiki` body region with a deterministic, sorted list of referencing pages (bullet → `[[<category>/<slug>]]` + title + `source_type`/date when available).
   It uses the same single-H2-region rewrite technique as `inject_narrative` (anchored heading regex; replace body up to the next H2). It is **pure Python, no Bedrock**, and runs in **both** narrated and `narrate=False` scans. Wire it into `run_scan` after `write_entities` / index regeneration, alongside `regenerate_dependencies_index` / `generate_index` (`scan.py:47–64`).
6. **Register `## Referenced in wiki` as scanner-owned** so lint/drift and re-scan treat it like `## Narrative` (idempotent rewrite; not flagged as human content).

### C. Plugin Claude-branch fix — prep + agent + docs (no Bedrock)

7. **Restore the prep `main()`** the shim calls (`_core_main`), Bedrock-free, built on `wiki_io.ingest_source` library functions. It emits the JSON brief consumed by `agents/ingestor.md` step 1:
   - preview / title / `source_type` (`extract`, `guess_source_type`, `slugify`),
   - `folder_brief` for folder ingests,
   - **entity-match hint**: matched URI + entity filename, via the entity lookup moved to a Bedrock-free home (`wiki_io` or `graph_io`) shared with `run_ingest_source`,
   - suggested summary path `sources/<YYYY-MM>-<slug>.md`,
   - `state_gate` (in-repo-doc sync gating) via the existing `compute_state_gate` helper.
   This both fixes the `ImportError` and gives the harness agent the entity URI + filename it needs to write `entity_uri:` and the correct `[[entities/...]]` wikilink. Decide the prep entrypoint's home (plugin script vs. a thin `wiki_io` `main`) during planning; it must import without `model_adapter` / `subagent_runtime`.
8. **Rewrite the docs/agents** to the entities/ link model:
   - `agents/ingestor.md` — replace "update 5–15 package/domain/concept pages" with: write the source summary (+ optional concept/ADR pages), set `entity_uri:` + `[[entities/...]]` wikilinks, **never edit entity pages**, and note that the scanner backfills `## Referenced in wiki`.
   - `commands/ingest.md` — update the "Source types → typical touches" table and the step list (the "Update package pages / domain / concept pages" steps become "link the relevant entities; do not edit entity pages").
   - `references/ingest-workflow.md` — same rewrite at reference depth.
   - `source.md` template (`page-templates/source.md`) — change `## Touches` bullets from `[[packages/<pkg>]]`/`[[domains/<domain>]]` to `[[entities/...]]`; add an `entity_uri:` frontmatter field (so the harness agent and `run_ingest_source` write the same shape).

### D. Migration

9. No migration. Existing legacy `packages/`/`domains/` ingest pages become orphans under the entities/ layout; the user rebuilds per the backward-compat rule. Mention in the plan that Slice-3 lint surfaces such orphans.

## Verification / success criteria

- **Core routing test** (`graph-wiki-core`): `run_ingest_source` against a fixture source that matches a package entity produces a page under `sources/` (or `concepts/`/`adrs/`) — **never** `packages/` — with `entity_uri:` set and a body `[[entities/pkg_<name>]]` wikilink whose target matches `short_filename` for that URI. Assert `packages/` is never created.
- **Backlink regen test** (`wiki-io` and/or `graph-wiki-core`): given a fixture vault with sources/concepts/adrs that wikilink known entities, a scan regenerates each entity's `## Referenced in wiki` to the expected sorted list. Multi-entity source backlinks from every linked entity. Re-running the scan is **idempotent**. Regen runs and produces identical output under `narrate=False` (no Bedrock import).
- **Scanner-owned-section test:** human edits to other entity-page H2s survive a scan; only `## Narrative` and `## Referenced in wiki` are rewritten.
- **Plugin prep test** (`graph-wiki-cli` / plugin): the restored prep `main()` is importable with `model_adapter` / `subagent_runtime` un-importable (monkeypatched to raise), and emits a valid JSON brief including the entity-match hint and suggested `sources/` path. The current `ImportError` is gone.
- **Existing Bedrock-shim argv contract test** (`packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`) still passes; the `backend_for("ingest") == "bedrock"` branch still shells `gw wiki ingest source`.

## Out of scope (Slice 4)

- Any change to the `entities/` schema, `short_filename`, `ADMITTED_KINDS`, `SCANNER_OWNED_KEYS`, or the narrator/file-describer Bedrock steps.
- Deep cross-ref link-rewriting beyond the `## Referenced in wiki` regen and the existing index-only update (`update_index`) — the CONTEXT.md "ingest cross-ref deep linking" deferral stands.
- URI-drift reconciliation of orphaned `entity_uri:` values on rename (still the v1.8 item noted at `ingest.py:589`).
- Migrating or deleting pre-existing legacy `packages/`/`domains/` ingest pages.
- `run_ingest_work_item` routing (work items already file under `work/` via `file_work_item`, bypassing `_route_target_path`) — unaffected.

## Sources

- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` — `_PAGE_TYPE_DIRS` (L123), `_route_target_path` (L196), entity lookups (L135/L166), `_set_entity_uri_in_body` (L261), `run_ingest_source` (L525).
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py` — ingestor system/user prompt (page_type menu).
- `packages/graph-wiki-core/src/graph_wiki_core/uri_slug.py` — `slug_from_uri` (L16) — to be supplemented by an entity-filename mapping.
- `packages/wiki-io/src/wiki_io/ingest_source.py` — library-only; no `main()` (root cause of the broken shim).
- `packages/wiki-io/src/wiki_io/entity_writer.py` — `SCANNER_OWNED_KEYS` (L104), `short_filename` (L159), `inject_narrative` (L935), `_NARRATIVE_HEADING_RE` (L943) — pattern for the new `## Referenced in wiki` regen.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` — `run_scan` pipeline + index-regen wiring (L47–64) — insertion point for the backlink pass.
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-*.md` — 7 entity templates (add `## Referenced in wiki`).
- `packages/wiki-io/src/wiki_io/assets/page-templates/source.md` — `## Touches` + add `entity_uri:`.
- `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py` — broken shim (`from wiki_io.ingest_source import main`).
- `plugins/graph-wiki/agents/ingestor.md`, `plugins/graph-wiki/commands/ingest.md`, `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md` — docs to rewrite.
- `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py` — argv contract test that must keep passing.
