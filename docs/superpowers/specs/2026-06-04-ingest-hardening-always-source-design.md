# Ingest Hardening — Always-Source + Loud Fallbacks

**Date:** 2026-06-04
**Status:** Design — ready for `writing-plans`.
**Author:** Pat (brainstormed + code-verified)
**Milestone:** Living Wiki **M3 Part A** (ingest robustness). Part B (code-as-arbiter Source shape) and the Source→concept/ADR/architecture **extraction step** are explicitly **out of scope** and get their own specs.
**Roadmap:** `docs/superpowers/specs/2026-06-03-living-wiki-roadmap.md` §1.5, §M3.

> **Goal:** make `run_ingest_source` robust and honest. Every ingested doc becomes a `Source` page; the ingestor stops silently demoting unparseable output to a `concept` page; parse failures, stripped wikilinks, and degraded results are **surfaced loudly** instead of buried. This is robustness hardening, not a model swap.

---

## 1. Background (code-verified 2026-06-04)

`run_ingest_source` (`packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py:491-696`) is the source-ingest path. Current shape:

- **Step 5** — single `make_llm("ingestor")` call returns frontmatter + body (`:589-624`).
- **Step 6** — `_parse_ingestor_response` (`:358-449`) splits the response. It already strips a leading ```` ```yaml ```` fence (defense-in-depth, `:379-403`), then parses the YAML block with a **hand-rolled scalar/list parser** (`:419-447`) — *not* `yaml.safe_load`. On any miss it returns `({}, body)`.
- **The silent-demotion bug (`:628-630`):** `page_type = str(fm.get("page_type", "concept")).lower()`; if not in `_PAGE_TYPE_DIRS` → `"concept"`. So an empty `fm` (parse miss) **silently becomes a concept page** with zero signal that frontmatter never parsed.
- **Step 7 routing** — `_route_target_path(wiki, page_type, slug)` (`:137-152`) maps `page_type` → dir via `_PAGE_TYPE_DIRS = {"concept": "concepts", "adr": "adrs", "source": "sources"}` (`:130-134`), defaulting to `concepts`.
- **Body mutation helpers** — `_rewrite_target_slug_in_body` (`:160-194`) and `_set_entity_uri_in_body` (`:202-247`) operate on the **raw** `llm_output` text (preserving comments/order) and **silently no-op when there is no `---` block** (`:171-173`, `:218-220`). This matters: if the LLM emits no frontmatter, these write nothing.
- **Stripped wikilinks** — `_resolve_wikilinks` (`:283-350`) returns `(text, stripped_list)`. The list is **logged** (`:671-678`, `silent=True`) but **not surfaced** in `IngestResult`.
- **Graph-not-init** — opening the read-only graph raises `IngestorGraphNotInitializedError` (`:531-534`); the CLI maps it to exit code `NOT_INITIALIZED` (3) (`wiki_cli/main.py:204-208`). The graph is used only for **entity linking** (`lookup_entity_by_path` / `lookup_entity_by_name`, `:565-576`).
- **`IngestResult`** (`:90-119`) fields: `status, page_path, slug, title, page_type, source_path, cross_refs_updated, entity_uri`.
- **Ingestor prompt** (`packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py:36-47`) instructs the model to "choose exactly one `page_type`" among `source`/`concept`/`adr`, each routing to a different dir, and that `category` should agree with `page_type`.

**Not in this path / not touched:** `run_ingest_work_item` (`:704-766`) — work items always file under `work/` via `file_work_item`, use `_parse_frontmatter`/`_validate` from `wiki_io.ingest_work_item`, and carry `page_type="work"`. It is **out of scope**.

---

## 2. The reframe — every ingested doc is a Source

The old design made the ingestor a classifier: pick `source`/`concept`/`adr`, route to a dir. That coupling is the root of the silent-demotion bug — a parse failure becomes a *wrong classification*, not an honest "couldn't tell."

**New model:** ingest is a **landing zone**. Every ingested doc becomes a `Source` page, full stop. The work of deriving `concept` / `adr` / `architecture` pages **from** Source docs is a separate **extraction step** (deferred; overlaps Part B). Decoupling classification from routing dissolves the bug: there is nothing to demote.

This makes parse failure non-catastrophic — an unparseable doc still lands as a valid Source page marked `source_kind: unknown`, which is honest rather than wrong.

---

## 3. Design

### 3.1 Always route to `sources/` (D1)

`run_ingest_source` writes every page to `sources/`. The `concept`/`adr` routing branches are not exercised by this path.

- Replace the `_route_target_path(wiki, page_type, slug)` call (`:637`) with a fixed `sources/` target. `_PAGE_TYPE_DIRS` and `_route_target_path` **remain in the module** (the deferred extraction step and the untouched work-item adjacency may still want them) but the source-ingest path no longer depends on `page_type` for routing.
- **Ingestor prompt** (`prompts/ingestor.py:36-47`): drop the "choose `page_type` → different dir" instruction and the `category`-agrees-with-`page_type` rule. The model's job is "distill this doc into a Source page." It may still emit a descriptive `source_kind` (see 3.2) but must not be told it controls the destination.

### 3.2 `source_kind` frontmatter, default `unknown` (D2)

Rename the descriptive `page_type` frontmatter key on Source pages to **`source_kind`** — signaling it is *descriptive*, not a router.

- `source_kind` holds the LLM's classification when parseable; **`unknown`** on any parse miss (replacing today's `"concept"` default at `:628-630`).
- **No new vocabulary is invented now.** Practical values are `source` (clean ingest) and `unknown` (couldn't classify); a richer vocabulary is the deferred extraction step's concern. The point of this milestone is the honest `unknown` marker, not a taxonomy.
- Routing **never** depends on `source_kind`.

### 3.3 `yaml.safe_load` with graceful fallback (D3)

In `_parse_ingestor_response`, after isolating the frontmatter block:

1. Try `yaml.safe_load(block)`. If it returns a `dict`, use it.
2. If it raises `yaml.YAMLError` **or** returns a non-dict, fall back to the existing hand-rolled scalar/list parser (kept verbatim — it tolerates LLM quirks `safe_load` rejects).
3. If both miss, return `({}, body)` as today.

The existing fence-strip pre-pass (`:379-403`) stays ahead of this.

**Synthesize-frontmatter rule (critical):** the body-mutation helpers no-op without a `---` block, so when the LLM emits **no** frontmatter at all (`fm == {}` *and* the raw output has no leading `---`), `run_ingest_source` must **synthesize a minimal frontmatter block** — `source_kind: unknown`, `target_slug: <fallback slug>`, `entity_uri: <uri|null>` — and prepend it to the body **before** calling `_rewrite_target_slug_in_body` / `_set_entity_uri_in_body`. Otherwise the unknown-type Source page lands without its metadata. (When the LLM *did* emit a `---` block but it parsed empty, the helpers already function — no synthesis needed; just ensure `source_kind` is written/defaulted.)

### 3.4 Surface stripped wikilinks (D4)

`stripped_wikilinks` is already computed (`:656`). Thread it out:

- Add `stripped_wikilinks: list[str] = field(default_factory=list)` to `IngestResult`.
- CLI (`wiki_cli/main.py`, after `:216`) prints a visible `⚠ stripped N unresolved wikilink(s): …` line when non-empty (both text and `--json` already serialize it; `--json` via `dataclasses.asdict`).
- MCP (`server.py:339`) surfaces it for free through `asdict`.
- The existing log line (`:671-678`) stays as the durable audit trail.

### 3.5 Loud "degraded" signal (D5)

So an unparsed frontmatter is **loud**:

- Add `frontmatter_parsed: bool = True` to `IngestResult`; set `False` whenever the path fell through to `source_kind: unknown` via a parse miss (empty `fm`).
- CLI prints a clear warning (e.g. `⚠ frontmatter did not parse — wrote Source page with source_kind: unknown`) when `frontmatter_parsed is False`.
- The page still lands (honoring always-write-Source); nobody is misled into thinking it was cleanly classified.

### 3.6 Graph-not-init — unchanged (D6)

Keep the current typed hard-fail: `IngestorGraphNotInitializedError` → CLI exit `NOT_INITIALIZED` (3). Ingest requires an initialized graph. *(Considered: proceed-without-graph writing `entity_uri: null` + a warning. Rejected for this milestone to keep the change surgical and the entity-linking contract intact; revisit if capturing docs before the graph exists becomes a real need.)*

---

## 4. `IngestResult` — before / after

```
status              str            (unchanged)
page_path           str            (unchanged)
slug                str            (unchanged)
title               str            (unchanged)
page_type           str            (unchanged field; source-ingest now always "source", work-item "work")
source_kind         str | None     NEW — descriptive kind on Source pages; "unknown" on parse miss; None for work items
source_path         str            (unchanged)
cross_refs_updated  int            (unchanged)
entity_uri          str | None     (unchanged)
stripped_wikilinks  list[str]      NEW — unresolved [[links]] stripped from the body
frontmatter_parsed  bool           NEW — False when we fell through to source_kind: unknown
```

`page_type` is retained on the result object (it is the routing *category*: always `"source"` here, `"work"` for work items) to avoid churning the work-item path; `source_kind` is the new *descriptive* field. The two are deliberately distinct.

---

## 5. Testing

- **Parse robustness:** valid YAML frontmatter → `source_kind` from the model, `frontmatter_parsed=True`. Malformed YAML that `safe_load` rejects but the hand-rolled parser recovers → parsed values, `frontmatter_parsed=True`. No-frontmatter output → synthesized block, `source_kind="unknown"`, `frontmatter_parsed=False`, and `target_slug`/`entity_uri` **present** in the written file (proves synthesis ran before the body helpers).
- **Always-Source routing:** an LLM response that *claims* `page_type: adr` (or `concept`) still writes to `sources/`, never `adrs/`/`concepts/`.
- **Loud surfacing:** a body with fabricated `[[links]]` → `IngestResult.stripped_wikilinks` non-empty and the CLI prints the `⚠` line; `--json` includes the field.
- **Degraded signal:** parse-miss ingest → `frontmatter_parsed=False` and the CLI warning fires; the page still lands.
- **Graph-not-init:** unchanged — `IngestorGraphNotInitializedError` → exit 3 (existing test stays green).
- **Idempotence/format:** `_set_entity_uri_in_body` / `_rewrite_target_slug_in_body` remain idempotent on the synthesized block.

**Known migration (call out, don't fix silently):** existing tests asserting concept/adr routing or a `page_type` *frontmatter* key on ingested pages must move to the always-Source + `source_kind` model. Expected under the single-dev no-migrations rule (`.claude/rules/backward-compatibility.md`); the plan enumerates the affected test files.

**Success criteria:** (1) no ingested doc is ever silently demoted to a concept page; (2) an unparseable doc lands as a valid `sources/*.md` with `source_kind: unknown` and a loud warning; (3) stripped wikilinks are visible in `IngestResult` and CLI output; (4) all routing for `run_ingest_source` targets `sources/`.

---

## 6. Out of scope

- The **extraction step** that derives `concept`/`adr`/`architecture` pages from Source docs (its own spec; overlaps Part B).
- **Code-as-arbiter** Source shape — distilled-claims section + append-only change log + re-ingest-appends (Part B).
- `run_ingest_work_item` and the work-item filing path.
- Proceed-without-graph ingest (deliberately deferred — see D6).
- Any LLM model/tier changes (this is a robustness fix, not a model swap).
