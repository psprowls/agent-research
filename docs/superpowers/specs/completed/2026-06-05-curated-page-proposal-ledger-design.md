# Curated-Page Proposal Ledger — Shared Foundation (+ M3 Retrofit)

**Date:** 2026-06-05
**Status:** Design — ready for `writing-plans`.
**Author:** Pat (brainstormed + code-verified against `main` @ `ea66c314`)
**Milestone:** Living Wiki — the **shared proposal foundation** that sits between **M3** (source-derived page suggestions, landed) and **M4** (drift propagation to backlinks, next). This spec covers the **ledger + the M3 retrofit only**. M4's scan-time drift producer is the next spec and becomes a thin producer on top of this foundation.
**Depends on:** M3 suggestion step (`merge ea66c314`, landed on `main`) — `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py` and its ingest wiring.
**Roadmap:** `docs/superpowers/specs/2026-06-03-living-wiki-roadmap.md` §M3/§M4, open-question #3 and #6.

> **Goal:** replace M3's per-Source-page `suggested_pages` storage with a single, vault-native **proposal ledger** — one markdown note per proposed curated-page change, in a `proposals/` directory — so that *both* producers (M3's ingest-time suggestions and M4's scan-time drift detection) write into one machine-readable, human-reviewable queue instead of two parallel surfaces. Propose only; create nothing under `concepts/`/`adrs/`/`architecture/`.

---

## 0. One-paragraph thesis

M3 records page proposals as a `suggested_pages` frontmatter list (plus a `## Suggested pages` body mirror) **on the originating Source page** (`suggest_pages.py`). M4 will need to record a *different* kind of proposal — "this existing curated page has gone stale because a backlinked entity changed" — and the natural M2e instinct is to flag it on yet another page (the changed entity). Left alone, that yields **two parallel proposal ledgers** with different shapes, no single review surface, and duplicated lifecycle logic. This spec defines a **shared, central ledger first**: a `proposals/` directory of per-proposal notes with a single lifecycle (`proposed → approved/rejected/created`), one merge/upsert API, and one CLI surface. M3 is retrofitted to write into it; M4 later becomes a second producer that calls the same `upsert_proposal` with `source: drift` origins. The architecture, the per-note lifecycle, and the dedup-by-target collapse are the durable parts; the M3 retrofit proves them end-to-end with zero new LLM work.

---

## 1. Where we are (code-verified 2026-06-05, `main` @ `ea66c314`)

- **M3 is merged.** `run_ingest_source` runs an inline suggest phase (`commands/ingest.py:780-788`) that calls `run_suggest_phase(wiki, page_path, prior_entries=…)` (`commands/suggest_pages.py:366-423`). Proposals are stored as a `suggested_pages` frontmatter list on the **Source page** and mirrored into a `## Suggested pages` body section.
- **Reusable M3 internals** (decision logic — kept by the retrofit): `parse_extractor_response` (`:84`), `_validate_proposal` (`:49`), `build_curated_vault_index` (`:131`), `build_extract_suggestions_prompt` (`:339`), and the `extractor` role + `EXTRACTOR_SYSTEM` prompt (`prompts/extractor.py`).
- **Source-page-storage M3 internals** (to be removed): `merge_suggested_pages` (`:158`), `read_suggested_pages` (`:217`), `set_suggested_pages_in_frontmatter` (`:232`), `render_suggested_pages_section` (`:277`), `set_suggested_pages_section_in_body` (`:299`), and the `prior_suggested` capture block in `ingest.py:751-758`.
- **`IngestResult`** (`ingest.py:140`) carries `suggested_pages: list[dict]` + `suggestions_parsed: bool`; the CLI prints them (`wiki_cli/main.py:230-239`) and the MCP surface serializes them (`db42f943`).
- **Vault tree** is created from `init_vault.py:43 FIXED_VAULT_DIRS = ["concepts","architecture","adrs","entities","sources",".templates"]`. The queue-like `work/` dir lives at the **workspace root** (sibling of `wiki/`), created at `init_vault.py:131`.
- **Curated dirs** for dedup/backlinks: `build_curated_vault_index` walks `concepts/`/`adrs/`/`architecture/`; `backlink_index.py:35 _PRESERVED_WIKI_DIRS = ("sources","concepts","adrs","architecture")` drives `## Referenced in wiki` regeneration.
- **Index lanes:** `index_generator.py:97 CURATED_LANES` = architecture/adrs/concepts/sources; `work/` is **not** a lane.
- **`wiki-io` helpers** the ledger will reuse: `slugify` (`wiki_io.ingest_source`), `parse_frontmatter` (`wiki_io.update_index`).

---

## 2. The model — central ledger, two producers, deferred consumer

A new `proposals/` directory **inside `wiki/`** holds **one markdown note per proposed curated-page change**. The note is a browsable Obsidian file; its frontmatter is the machine contract; its body is a regenerated human-readable evidence list.

The flow has three roles across multiple specs:

1. **Produce** — a producer proposes a curated-page change and calls `upsert_proposal`:
   - **Ingest producer (this spec):** M3's extractor pass, retargeted from Source-page frontmatter to `proposals/` notes. Origin = the Source page; `source: ingest`.
   - **Drift producer (M4, next spec):** scan-time, for curated pages backlinking a changed entity. Origin = the changed entity; `source: drift`. **Not built here**, but the schema accommodates it with zero foundation changes.
2. **Dispose (human)** — review and flip `status` to `approved`/`rejected` via `gw wiki proposal approve|reject` (or by editing frontmatter).
3. **Create (deferred — M3's "creation" spec)** — a later step reads `approved` notes, scaffolds/edits curated pages, wires cross-refs, and flips them to `created`. **Out of scope here.**

The ledger is **append/merge, never wholesale-regenerated**: proposals accrue from many runs and producers over time. Nothing under `concepts/`/`adrs/`/`architecture/` is written by this spec.

This honors roadmap open-q #3 (*ingestion + human authoring create curated pages; avoid low-quality auto-generated concepts*) by keeping a human approval gate in front of any curated-page write, and resolves the §0 two-ledger risk by making the gate **central**.

---

## 3. Design

### 3.1 Identity and the proposal note (D1)

**Identity = filename = `<kind>-<target_slug>.md`** under `wiki/proposals/`. All evidence for a single proposed change to one target page collapses into one reviewable note, regardless of how many sources/entities triggered it.

```markdown
# wiki/proposals/adr-0007-markdown-canonical.md
---
kind: adr                      # concept | adr | architecture
mode: update_existing          # create_new | update_existing
target_slug: 0007-markdown-canonical
title: "Markdown stays canonical"   # mainly meaningful for create_new
status: proposed               # proposed | approved | rejected | created
origins:                       # structured; accumulates across runs/producers
  - ref: sources/2026-06-03-living-wiki-roadmap
    source: ingest             # ingest | drift
    rationale: "Source revisits the markdown-vs-DB decision; the ADR's consequences should record the new criteria."
  # M4 (drift producer, next spec) will append entries shaped like:
  # - ref: entities/pkg_wiki_io
  #   source: drift
  #   detected_commit: a1b2c3d
  #   hash: 9f2c...
  #   rationale: "Narrative now describes async fan-out; the ADR assumes sync."
---
<!-- Body regenerated from origins[] while status: proposed. Do not edit here;
     approve via `gw wiki proposal approve adr-0007-markdown-canonical`. -->

**ingest · [[sources/2026-06-03-living-wiki-roadmap]]**
Source revisits the markdown-vs-DB decision; the ADR's consequences should
record the new criteria.
```

- **`kind`** ∈ `{concept, adr, architecture}` (the `SUGGESTION_KINDS` set).
- **`mode`** ∈ `{create_new, update_existing}`. For `create_new`, `target_slug` is the proposed new page slug; for `update_existing`, it is the existing curated page's slug.
- **`origins[]`** is a structured list. Each entry: `ref` (a wiki-relative page reference, e.g. `sources/<slug>` or `entities/<stem>`), `source` (`ingest`|`drift`), `rationale` (one short line), and the **M4-reserved** `detected_commit` / `hash` keys (the ingest producer never sets these — same forward-compat move M2e used by scoping `agent_plugin` early).
- **`title`** is carried mainly for `create_new` (the page does not exist yet to derive a title from).
- **`status`** is the one human-decided signal; everything else is producer-derived.

**Known limitation (documented, not fixed):** two producers proposing the *same idea* under *different* slugs produce two notes (no collapse). Acceptable — inherited verbatim from M3's documented limitation.

### 3.2 The lifecycle merge — `upsert_proposal` (D2)

Generalizes M3's `merge_suggested_pages` from "a list on one page" to "a directory of notes," keyed by filename. For a producer-supplied proposal `(kind, mode, target_slug, title, origin)`:

- **No note exists** → create it as `proposed` with `origins = [origin]`; render the body.
- **Note exists with a human status** (`approved`/`rejected`/`created`) → **left untouched**. A `rejected` note is preserved so the same key is not re-proposed.
- **Note exists at `proposed`** → **refresh**: merge `origin` into `origins[]` keyed by `ref` (append if new; update in place if the same `ref` re-fires); refresh `title`/`mode`; re-render the body. Status stays `proposed`.
- **Byte-stable on a no-op** re-run (same producer, same evidence → identical bytes).
- Notes **not** re-proposed this run are **left as-is** (the ledger is append/merge — a proposal from a different source or earlier run persists).

Deterministic serialization (fixed key order, `yaml.safe_dump(sort_keys=False)`) mirrors M3's `_ENTRY_KEY_ORDER` discipline so no-op re-runs are byte-identical. Writes are atomic (temp-file + `os.replace`, the `inject_referenced_in_wiki` precedent).

### 3.3 Dedup of `mode` stays in the producer (D3)

Distinguishing `create_new` from `update_existing` compares each proposal against the **existing curated pages** via `build_curated_vault_index` — this stays in the **producer** (M3's extractor pass), unchanged. The ledger is dumb storage + lifecycle: it stores whatever `mode` the producer decided and never re-derives it. Semantic near-dup via the retrieval stack remains out of scope (title/slug/summary matching only).

### 3.4 The ledger module (D4)

A new pure-Python module `packages/wiki-io/src/wiki_io/proposals.py` (alongside `backlink_index.py` / `ingest_source.py`) — no LLM, no graph, independently testable:

| Function | Responsibility |
|---|---|
| `proposal_path(wiki, kind, target_slug) -> Path` | identity → `proposals/<kind>-<target_slug>.md` |
| `read_proposal(path) -> dict` | parse one note → `{kind, mode, target_slug, title, status, origins[]}` |
| `list_proposals(wiki, status=None, kind=None) -> list[dict]` | glob the dir → records (CLI list + lint roll-up) |
| `upsert_proposal(wiki, proposal) -> dict` | the §3.2 lifecycle merge; writes one note atomically; returns the merged record |
| `render_proposal_body(record) -> str` | `origins[]` → evidence markdown (the body) |
| `set_proposal_status(wiki, kind, target_slug, status) -> bool` | targeted frontmatter write for approve/reject |

The merge and body renderer are pure functions of `(existing note, proposal)`; the parser is a pure function of note text; the lister is a pure function of the dir. (wiki-io convention: module docstring **first**, above `from __future__ import annotations`.)

### 3.5 The M3 retrofit (D5)

`suggest_pages.py` keeps everything about *deciding* proposals and drops everything about *Source-page storage*:

- **Reused unchanged:** `parse_extractor_response`, `_validate_proposal`, `build_curated_vault_index`, `build_extract_suggestions_prompt`, the `extractor` role/prompt.
- **Replaced — the output target.** `run_suggest_phase` stops writing the Source page's frontmatter/body and instead, for each validated proposal, calls `upsert_proposal(wiki, …)` mapping `slug → target_slug` (and `existing_slug → target_slug` when `mode: update_existing`), with `origin = {ref: "sources/<source-slug>", source: "ingest", rationale: <proposal rationale>}`. It returns the list of merged records and `parsed`.
- **Deleted:** `merge_suggested_pages`, `read_suggested_pages`, `set_suggested_pages_in_frontmatter`, `render_suggested_pages_section`, `set_suggested_pages_section_in_body`, the `## Suggested pages` constants, and the `prior_suggested` capture block in `ingest.py:751-758` (the per-note merge now lives in the ledger, keyed by filename — there is nothing to capture-before-overwrite).
- **Degraded path unchanged in spirit:** on extractor error or parse-miss, write **zero** notes, set `suggestions_parsed=False`, print a loud warning, return `status="ok"`. The suggest phase never fails an ingest.
- **The Source page no longer carries** `suggested_pages` frontmatter or a `## Suggested pages` section.

### 3.6 `IngestResult` reporting field (D6)

`IngestResult.suggested_pages: list[dict]` and `suggestions_parsed: bool` **stay** as the reporting fields, now sourced from the notes upserted this run. **The reporting dict keeps the keys the existing CLI/MCP read** — `kind`, `title`, `slug` (= `target_slug`), `mode`, `status` — so `wiki_cli/main.py:230-239` and the MCP serializer work **unchanged**. Only the *storage* moved; the *report* shape is preserved.

### 3.7 CLI surface (D7)

`gw wiki` gains:

- **`gw wiki proposals [--status proposed|approved|rejected|created] [--kind concept|adr|architecture]`** — read-only list (table: kind, mode, target, status, origin-count). Defaults to open (`proposed`).
- **`gw wiki proposal approve <kind>-<target_slug>`** / **`gw wiki proposal reject <kind>-<target_slug>`** — convenience writes over `set_proposal_status` (the M2e `ack-drift` precedent). Hand-editing the note's `status:` stays equally valid.
- `--json` serializes records via `asdict`, matching M3's ingest-field exposure.
- **`graph-wiki:lint` roll-up:** a count of open (`proposed`) notes added to the lint report (the convenience deferred from M2e §4 — natural to land here).

### 3.8 Integration touchpoints & deliberate non-changes (D8)

- **Bootstrap creates the dir.** Add `"proposals"` to `init_vault.py:43 FIXED_VAULT_DIRS` so `gw bootstrap` creates `wiki/proposals/`. (Decision: `proposals/` lives **inside** `wiki/`, browsable in Obsidian — not a workspace sibling like `work/`/`raw/`.)
- **NOT a curated index lane.** `index_generator.py:97 CURATED_LANES`, `GENERATED_FILES`, and `init_vault.py:51 SECTION_INDEX_STUBS` are **unchanged** — proposals are a transient queue, excluded from the wiki index exactly as `work/` is. (Stated so an implementer does not "helpfully" add it.)
- **NOT a backlink source.** `backlink_index.py:35 _PRESERVED_WIKI_DIRS` stays `("sources","concepts","adrs","architecture")` — `proposals/` is **not** added, so proposal notes (whose M4 `origins[]` will contain `entities/…` refs) never generate `## Referenced in wiki` backlinks on entity pages. (Explicit non-change.)
- **No migration** of already-landed Source-page `suggested_pages`. Per `.claude/rules/backward-compatibility.md` (rebuild on schema change, no migrations before v2.0), the retrofitted writer simply emits `proposals/` notes going forward; the user rebuilds the vault. No migration code.

---

## 4. Components & boundaries

| Unit | Responsibility | Depends on |
|---|---|---|
| `wiki_io.proposals` | ledger: path/read/list/upsert/render/set-status | `wiki_io` frontmatter + slug helpers |
| `suggest_pages.run_suggest_phase` (retrofit) | extractor pass → `upsert_proposal` per proposal | `wiki_io.proposals`, extractor role |
| `ingest.py` wiring | drop `prior_suggested`; populate `IngestResult` from upserted records | `suggest_pages` |
| `wiki_cli` proposals commands | list + approve/reject over the ledger | `wiki_io.proposals` |
| lint roll-up | count open proposals | `wiki_io.proposals.list_proposals` |

Each unit is independently testable: the ledger functions are pure (note text / dir in, record / bytes out); the retrofit is the extractor pass (mockable at the `make_llm("extractor")` boundary, as M3 tests already do) feeding pure ledger calls.

---

## 5. Testing (success criteria)

Pure-function unit tests dominate; the LLM is mocked at the extractor boundary (mirror M3's suggest tests).

**Ledger lifecycle**
1. **Create-new:** `upsert_proposal` on an empty dir writes `proposals/<kind>-<slug>.md` with `status: proposed` and one origin; body renders that origin.
2. **Human status untouched:** a note at `approved`/`rejected`/`created` is byte-identical after a re-`upsert` with a matching key (decisions never stomped; `rejected` not re-proposed).
3. **Refresh + origin accumulation:** a `proposed` note re-`upsert`ed with a *new* `ref` gains a second `origins[]` entry; re-`upsert` with the *same* `ref` updates it in place (no duplicate). Status stays `proposed`.
4. **Identity collapse:** two proposals for the same `(kind, target_slug)` from different origins → **one** note, two `origins[]` entries.
5. **Byte-stable no-op:** identical re-`upsert` produces identical bytes.

**M3 retrofit**
6. **Notes not Source frontmatter:** ingesting a substantive doc writes the expected `proposals/` notes; the Source page carries **no** `suggested_pages` frontmatter and **no** `## Suggested pages` section.
7. **Report shape preserved:** `IngestResult.suggested_pages` entries expose `kind/title/slug/mode/status` (slug = target_slug); the existing CLI print and MCP serializer run unchanged.
8. **Degraded:** extractor error/parse-miss → zero notes written, `suggestions_parsed=False`, loud CLI warning, ingest `status="ok"`, the Source page intact.

**CLI**
9. `gw wiki proposals --status proposed` lists open proposals; `proposal approve <id>` flips status to `approved` and the decision survives a subsequent re-ingest (test 2 at the command level).

**Lint**
10. The lint roll-up reports the count of open `proposed` notes.

**Bootstrap**
11. `gw bootstrap` creates `wiki/proposals/`; proposals are absent from the generated wiki index and from any entity page's `## Referenced in wiki` (guards D8 non-changes).

---

## 6. Scope

**In scope:** the `wiki_io.proposals` ledger module (§3.4); the per-note lifecycle/upsert (§3.2); the M3 retrofit (§3.5) and `IngestResult` report-shape preservation (§3.6); `gw wiki proposals` + `proposal approve|reject` + the lint roll-up (§3.7); the bootstrap dir + deliberate non-changes (§3.8); the M4-reserved `origins[]` keys (unused by the ingest producer).

**Out of scope:**
- **M4 drift producer** (scan-time backlink traversal, `drift_judge` cross-page extension, writing `source: drift` proposals) — the next spec; it only *calls* `upsert_proposal`.
- **Creation/update consumer** (acting on `approved` notes to scaffold/edit curated pages, flip to `created`) — M3's deferred "creation" spec.
- **Any write** under `concepts/`/`adrs/`/`architecture/`.
- **Migration** of existing Source-page `suggested_pages` (rebuild instead).
- **Semantic near-dup** via BM25/embeddings (title/slug/summary matching only, inherited from M3).
- Code-as-arbiter Source shape; `run_ingest_work_item`; model-tier changes beyond reusing the `extractor` role.

---

## 7. Sequencing & open questions

**Order:** M3 ✓ (landed) → **this foundation (+ M3 retrofit)** → **M4 drift producer** → M3 creation consumer (deferred) → M5.

**Open questions**
1. **Body authoring vs. regeneration** for a `proposed` note: this spec regenerates the body from `origins[]` every run. If, in M4, a human wants to annotate a still-`proposed` note before deciding, the regen would clobber it — revisit if it bites (the human can always set `status` to freeze it). *Leaning: regenerate-while-proposed; freeze-on-decision is sufficient.*
2. **Stale-proposal hygiene:** `proposed` notes whose triggering evidence disappeared are never auto-removed (append/merge model). A future lint convenience could flag long-stale `proposed` notes — out of scope here.
3. **Multi-origin rationale rendering** detail (one block per origin vs. a deduped summary) — settle during `writing-plans`; not architecture-affecting.
