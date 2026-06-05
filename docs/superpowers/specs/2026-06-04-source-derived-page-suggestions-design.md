# Source-Derived Page Suggestions — Inline Extraction Phase

**Date:** 2026-06-04
**Status:** Design — ready for `writing-plans`.
**Author:** Pat (brainstormed + code-verified)
**Milestone:** Living Wiki **M3** — the *extraction step* deferred by M3 Part A. This spec covers **suggestion only** (propose derived pages; write nothing under `concepts/`/`adrs/`/`architecture/`). The **creation** step (act on approved suggestions) and **code-as-arbiter** Source shape are explicitly **out of scope** and get the next spec.
**Depends on:** `docs/superpowers/specs/2026-06-04-ingest-hardening-always-source-design.md` (M3 Part A). This spec assumes Part A's always-land-a-Source-page guarantee and its hardened `run_ingest_source` shape.
**Roadmap:** `docs/superpowers/specs/2026-06-03-living-wiki-roadmap.md` §M3, open-question #3.

> **Goal:** after a source doc lands as a `Source` page, run an inline LLM pass that proposes which `concept` / `adr` / `architecture` pages the doc justifies — distinguishing *create-new* from *update-existing* — and records those proposals durably on the Source page for later human approval. Propose only; create nothing.

---

## 1. Background (code-verified 2026-06-04)

- `run_ingest_source` (`packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py:491-696`) is the source-ingest path. Post-Part-A it always writes the page to `sources/` and returns an `IngestResult`.
- **`IngestResult`** (`:90-119`) today carries `status, page_path, slug, title, page_type, source_path, cross_refs_updated, entity_uri`. Part A adds `source_kind`, `stripped_wikilinks`, `frontmatter_parsed`. This spec adds two more (§5).
- **Curated-page directories** already exist as a named tuple: `_PRESERVED_WIKI_DIRS = ("sources", "concepts", "adrs", "architecture")` (`packages/wiki-io/src/wiki_io/backlink_index.py:35`). These are the dirs the dedup pass lists.
- **Page templates** for the proposable kinds exist under `packages/wiki-io/src/wiki_io/assets/page-templates/`: `concept.md`, `concept-pattern.md`, `adr.md`, `architecture.md`. Their frontmatter carries a `title` and a `summary` — enough for a cheap "what already exists" listing without parsing bodies.
- **Frontmatter mutation precedent.** Part A's `_set_entity_uri_in_body` / `_rewrite_target_slug_in_body` operate on the **raw** page text, preserving comments/order, and no-op without a `---` block. `wiki_io.entity_writer` also exposes `set_frontmatter_value` (`:708`), `update_frontmatter` (`:729`), and `merge_frontmatter` (`:359`) as structured read-merge-write helpers. The suggested-pages merge (§3.4) follows this precedent — it does **not** invent a new parser.
- **Models are role-based.** `model_adapter/models.toml` defines `[roles.*]` (ingestor, narrator, librarian, synthesizer, …) each with a default tier + `sweep_candidates`; models are obtained only via `make_llm(role)` (never `ChatBedrockConverse` directly). Adding a role is the standard extension point.

**Not touched:** `run_ingest_work_item`; the `sources/` Source page body produced by Part A (this phase *appends* a section, see §3.5); any `concepts/`/`adrs/`/`architecture/` page contents (this spec never writes them).

---

## 2. The model — ingest proposes, a human disposes, a later step creates

Part A made ingest a **landing zone**: every doc becomes a `Source` page. This spec adds the next link: a `Source` page can *justify* curated knowledge pages (a cross-cutting `concept`, a dated `adr`, an `architecture` synthesis), but **deriving** them is a distinct, reviewed act.

The flow has three owners across two specs:

1. **Suggest (this spec, inline in ingest):** the LLM proposes candidate pages and records them as `suggested_pages` on the Source page with `status: proposed`. Nothing under the curated dirs is written.
2. **Dispose (human, by editing frontmatter):** you flip each entry to `approved` or `rejected`.
3. **Create (next spec):** a later run reads `approved` entries, scaffolds the pages from templates, wires cross-refs, and flips them to `created`.

This honors roadmap open-question #3's lean — *"keep scan structural-only; let ingestion + human authoring create curated pages, to avoid low-quality auto-generated concepts"* — by making **ingestion the proposal mechanism** and keeping a human approval gate in front of any curated-page write.

---

## 3. Design

### 3.1 Inline suggest phase in `run_ingest_source` (D1)

After the Source page is written, `run_ingest_source` runs a **suggest phase**:

1. **Build a cheap vault index** — walk `concepts/`, `adrs/`, `architecture/` (the curated subset of `_PRESERVED_WIKI_DIRS`); for each page collect `slug`, `title`, `summary` from frontmatter only. Directory + frontmatter read; **no graph, no BM25/embedding retrieval** in the ingest path.
2. **One LLM call** (§3.2) takes the just-written Source page content + the vault index and returns a structured proposal list.
3. **Parse** the proposals (§3.3), **merge** them into the Source page's `suggested_pages` frontmatter (§3.4), **regenerate** the `## Suggested pages` body mirror (§3.5), and **surface** them in `IngestResult` (§5).

**Non-catastrophic, mirroring Part A.** The Source page has already landed. If the suggest call errors or its output won't parse, write **zero** suggestions, set `suggestions_parsed=False`, print a loud warning, and return `status="ok"`. The suggest phase **never fails an ingest**.

### 3.2 New `extractor` role, separate call (D2)

- Add `[roles.extractor]` to `model_adapter/models.toml` (default tier + `sweep_candidates`), reached via `make_llm("extractor")`. A dedicated role keeps the tier independently tunable (the §5 cost-offloading lever) and leaves Part A's single ingestor-call parsing untouched.
- *Name:* `extractor` (matches the roadmap's "extraction step"). The role *suggests*; the next spec's creation step performs the actual extraction.
- The prompt is **conservative by default** (roadmap open-q #3): propose only well-supported pages; **returning zero proposals is correct and expected**; prefer `update_existing` when the vault index shows a near-match; `adr` only for a genuine decision, `architecture` only for a cross-cutting synthesis, `concept` for a reusable technical idea; soft cap of ~5 proposals.

### 3.3 Proposal output + robust parse (D3)

The extractor emits a single YAML block: a list of proposals, each with `kind`, `title`, `slug`, `mode`, `existing_slug` (when `update_existing`), `rationale`. Parsing reuses Part A's D3 discipline:

1. `yaml.safe_load(block)`; if it yields a `list` of dicts, use it.
2. Tolerate a leading code fence (same pre-pass as Part A).
3. On any miss (`YAMLError`, non-list, malformed entries) → **zero proposals** + `suggestions_parsed=False`. No new hand-rolled parser; no crash.

`slug` is normalized to a URL-safe slug command-side; `kind` is validated against `{concept, adr, architecture}` and an out-of-set `kind` drops that one entry (logged) rather than failing the batch.

### 3.4 `suggested_pages` frontmatter — the machine contract (D4)

Structured list on the **Source page** frontmatter:

```yaml
suggested_pages:
  - kind: concept              # concept | adr | architecture
    title: "Section-ownership model"
    slug: section-ownership-model
    mode: create_new           # create_new | update_existing
    existing_slug:             # set only when mode: update_existing
    rationale: "Source defines a reusable scanner/human ownership split not yet captured."
    status: proposed           # proposed | approved | rejected | created
```

- **Identity key = `(kind, slug)`.**
- **Status lifecycle.** The suggest phase only ever writes `proposed`. The human sets `approved`/`rejected`. The next spec's creation step sets `created`. Status is the one signal that cannot be re-derived — it is a human decision — so it lives here, machine-readable, not in prose.
- **Merge on re-ingest (idempotent).** Because the phase re-runs on every ingest:
  - An entry whose key matches an existing entry with a **human status** (`approved`/`rejected`/`created`) is **left untouched** — decisions are never stomped. A `rejected` key is preserved so it is not re-proposed.
  - A matching-key entry still at `proposed` is **refreshed** (title/mode/existing_slug/rationale may update).
  - An unmatched proposal is **appended** as `proposed`.
  - A no-op re-ingest (same source, same vault) is **byte-stable**.
- **Known limitation (documented, not fixed):** if the extractor proposes a *different* slug for an idea you rejected under another slug, the key won't match and it may reappear. Acceptable for this milestone.
- **This key is ingest-written but human-edited** — the merge preserves your status edits the way the entity-page model preserves human sections. Implemented with the structured read-merge-write helpers (`entity_writer.update_frontmatter` / `merge_frontmatter` precedent), preserving the rest of the frontmatter and the body.

### 3.5 `## Suggested pages` body section — regenerated readable mirror (D5)

Append a `## Suggested pages` H2 to the Source page body, **regenerated from `suggested_pages` frontmatter every run** (template-authoritative — a render, not a second source of truth):

```markdown
## Suggested pages

- **concept · create new** — [Section-ownership model] (`section-ownership-model`) · _proposed_
  Source defines a reusable scanner/human ownership split not yet captured.
- **adr · update** — existing `adrs/0007-markdown-canonical` · _approved_
  Source revisits the markdown-vs-DB decision; update the consequences.
```

- **Approve in the frontmatter, not the body.** The body is a read-only mirror; edits to it are overwritten on the next ingest. The section header states this. This is the same "scanner-data section is template-authoritative" exception already in the ownership model (`.claude/rules/backward-compatibility.md`), applied to a Source-page section.
- Rendered from frontmatter, so it always agrees with the contract; nothing in the body is parsed back.

### 3.6 Dedup is vault-listing, not frontmatter (D6)

Distinguishing `create_new` from `update_existing` compares each proposal against the **existing curated pages** (the §3.1 vault index), **not** against `suggested_pages`. Frontmatter shape therefore never affects dedup. The vault index is title/slug/summary only — deliberately cheap; semantic near-dup via the retrieval stack is **out of scope** (a future enhancement if title/slug matching proves too coarse).

---

## 4. Components & boundaries

| Unit | Responsibility | Depends on |
|---|---|---|
| vault-index reader | list `concepts/`/`adrs/`/`architecture/` → `[{slug,title,summary}]` | `wiki_io` paths + frontmatter parse |
| `extractor` prompt | Source content + vault index → YAML proposals | prompt fragments |
| proposal parser | YAML block → validated `[Proposal]`; loud zero-fallback | Part A D3 helpers |
| suggested-pages merge | merge proposals into FM by `(kind,slug)`, preserve decisions | `entity_writer` FM helpers |
| body mirror renderer | FM `suggested_pages` → `## Suggested pages` markdown | — |
| `run_ingest_source` wiring | sequence the phase; populate `IngestResult`; best-effort guard | all above |

Each unit is independently testable: the merge and the renderer are pure functions of (existing FM, proposals); the parser is a pure function of LLM text; the vault-index reader is a pure function of the vault dir.

---

## 5. `IngestResult` — additions (on top of Part A)

```
... (Part A fields: source_kind, stripped_wikilinks, frontmatter_parsed) ...
suggested_pages      list[dict]   NEW — proposals present after this run's merge (the full
                                  current list, each with kind/slug/mode/status/…)
suggestions_parsed   bool         NEW — False when the extractor call errored or its output
                                  did not parse (zero suggestions written); drives a loud CLI warning
```

- **CLI** (`wiki_cli/main.py`) prints a human summary, e.g. `→ 2 suggestion(s): concept "Section-ownership model" (new, proposed); adr → update adrs/0007 (approved)`, and a `⚠ suggestion pass degraded — wrote 0 suggestions` line when `suggestions_parsed is False`. `--json`/MCP serialize the new fields via `asdict`.

---

## 6. Testing

- **Propose new vs update:** a novel cross-cutting idea → an entry with `mode: create_new`; an idea overlapping an existing curated page (present in the vault index) → `mode: update_existing` + `existing_slug` set.
- **Conservatism:** a thin/low-signal source → **zero** proposals, `suggestions_parsed=True`, ingest `ok`.
- **Merge preserves decisions:** seed a Source page with an `approved`, a `rejected`, and a `created` entry; re-ingest → those three are byte-identical; a matching `proposed` entry is refreshed; a brand-new proposal is appended as `proposed`.
- **Idempotence:** no-op re-ingest (same source + vault) leaves `suggested_pages` and the `## Suggested pages` body byte-stable.
- **Body mirror:** `## Suggested pages` renders exactly the frontmatter entries; a hand-edit to the body is overwritten on re-ingest (frontmatter is authoritative).
- **Degraded path:** extractor returns unparseable output → zero suggestions, `suggestions_parsed=False`, CLI warning fires, ingest still `status="ok"`, the Source page itself is intact.
- **Dedup independence:** dedup labeling is driven by the vault index, verified independent of pre-existing `suggested_pages` content.
- **Role wiring:** `make_llm("extractor")` resolves; the call goes through the guarded adapter.

**Success criteria:** (1) ingesting a substantive doc records honest `create_new`/`update_existing` proposals on the Source page, defaulting to `proposed`; (2) re-ingest never overwrites a human `approved`/`rejected`/`created` decision and is byte-stable on a no-op; (3) the `## Suggested pages` body always mirrors the frontmatter; (4) a degraded extractor pass writes zero suggestions loudly and never fails the ingest; (5) **nothing** is written under `concepts/`/`adrs/`/`architecture/` by this phase.

---

## 7. Out of scope

- **Creation** of pages from `approved` suggestions (template scaffold, cross-ref wiring, `status: created`) — the next spec.
- **Code-as-arbiter** Source shape — distilled-claims section + append-only change log + re-ingest-appends — the next spec (overlaps creation).
- **Semantic near-dup** via BM25/embeddings in the suggest path (title/slug/summary matching only for now).
- **Approval UX** beyond editing frontmatter (no interactive prompt, no queue page).
- **Drift propagation** to existing backlinked pages (M4).
- `run_ingest_work_item`; any LLM tier/model changes beyond adding the `extractor` role.
