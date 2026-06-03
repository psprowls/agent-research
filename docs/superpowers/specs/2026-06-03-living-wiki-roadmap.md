# Living Wiki — Roadmap & North Star

**Date:** 2026-06-03
**Status:** Planning document (north star + decomposed roadmap). Milestone 1 is specced tightly enough to hand to `writing-plans`; M2–M5 are directional with recommendations.
**Author:** Pat (enriched with code-verified findings)
**Supersedes/extends:** the author's original "Where we are / Where we want to be" brief.
**Prerequisite status:** the **de-containerize** effort has **landed** (merge `34dab312`, 2026-06-03) — this roadmap builds on the resulting graph-only scan path; M1 is the immediate next work.

> **Goal of this document:** turn the graph-wiki from a *snapshot regenerated from scratch on every scan* into a **living knowledge base** that accrues durable human/LLM knowledge, updates incrementally as code changes, and actively assists coding agents — while staying a human-browsable Obsidian markdown vault.

---

## 0. The one-paragraph thesis

The graph layer is already incremental and commit-aware; the **entity-page layer throws that signal away** and re-renders every page from a template on every scan, wiping any human/LLM-authored prose (with the sole exception of File-map row descriptions and human frontmatter keys). The path to a "living wiki" is therefore **not** new infrastructure for change detection — that largely exists — but (1) a **preservation model** so durable knowledge survives re-scan, and (2) **plumbing the commit signal the graph already computes up into the page layer** so updates are diff-gated instead of wholesale. Everything else (source re-ingestion, drift propagation, context curation) builds on those two foundations.

---

## 1. Where we are (code-verified)

### 1.1 What works

- **Bootstrap.** Creates the workspace vault at `<workspace>/wiki/` — folder tree, schema files, config, starter templates. (`/graph-wiki:bootstrap`.)
- **Scan → graph → entity pages.** `graph_io` builds a SQLite code graph with structural node-kinds (repository, app, package, dependency, test_suite, domain) and file-level kinds (classes, functions, types), plus structural edges (`contains`, `imports`) and code edges (`calls`, exports). `write_entities` then renders one mostly-stub page per admitted entity from a per-kind template: frontmatter, a `## Narrative` H2, and a `## File map` H2 listing contained files with short descriptions.
- **`gw graph *` CLI** (`packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/main.py:59-340`). Rich read surface: `find`, `describe-{package,domain,app,agent-plugin,dependency,suite,path,repo}`, `list-*`, edge traversals (`callers`, `callees`, `imports`, `imported-by`, `exports`, `exported-by`), aggregations (`domain-clusters`, `domain-deps`, `cross-cutting`), plus `update`/`sync-wiki`/`status`/`dump`. JSON output via `--fmt json`. This is the substrate for graph-assisted agent lookups.
- **`gw wiki *` CLI** (`packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py:30-234`). `query` runs a hybrid pipeline: BM25 (`bm25s`) + Bedrock Titan embeddings with RRF fusion → librarian subagent fan-out (`SubagentPool`) → synthesizer → vault-thin code-fallback (`commands/query.py`). Plus `lint`, `log`, `ingest`.
- **Ingest.** `gw wiki ingest source` (`commands/ingest.py:491-697`) creates a `Source` page, classifies it (source/concept/adr), links the matched code entity by URI, and strips hallucinated wikilinks.

### 1.2 The core problem: re-scan is destructive

On **every** re-scan, `write_entities` re-renders each entity page's **entire body from the template** (`entity_writer.py:861-870`; the body comes purely from `_render_entity_page` → `template.content`, `:519-522` — the existing body is discarded). Consequences:

- **Frontmatter is merged** — scanner-owned keys replaced, human keys (`status`, `last_reviewed`, `owner`, `notes`, non-empty `summary`) preserved (`merge_frontmatter`, `:358-402`; `SCANNER_OWNED_KEYS`, `:104-137`).
- **`## File map` row descriptions are preserved** via an explicit snapshot→restore: `_snapshot_file_map_descriptions` (`scan.py:108`) captures filled cells *before* the reset, `inject_file_map(preserved=…)` / `_merge_preserved_descriptions` (`entity_writer.py:1127`, `:1088`) graft them back for paths that still exist.
- **Everything else in the body is wiped back to template placeholders.** `## Purpose` and `## Public API` — the natural home for human/LLM prose — are reset to `> TODO:` on every scan. **There is no `inject_purpose` / `inject_public_api`; no snapshot step.** This is the central blocker to a living wiki.

### 1.3 The forward-link sections are duplicative dead weight

The template ships `## Concepts`, `## Dependencies`, `## Decisions`, `## Contrasts / alternatives` as forward-link stubs (`entity-package.md:40-50`). **Nothing populates them**, and they're wiped each scan. Meanwhile `## Referenced in wiki` is the real, working cross-reference: `regenerate_referenced_in_wiki` (`backlink_index.py:100-142`) walks the *preserved* dirs for `[[entities/…]]` links pointing **at** the entity and lists them. Two caveats:

- It's a **backlink** (page→entity), the inverse of the forward stubs.
- `_PRESERVED_WIKI_DIRS = ("sources", "concepts", "adrs", "architecture")` + `work/` (`backlink_index.py:35`, `:79-81`). Post-decontainerize, **dependency pages are themselves entities** (`entities/dep_*.md`) — there is no curated `dependencies/` dir. So the `## Dependencies` stub is redundant with the dependency entity's own page plus the scanner-owned `depends_on` frontmatter key, which is where the relationship data actually lives.

**Decision:** remove the four forward stubs; `## Referenced in wiki` supersedes them.

### 1.4 The big enabler you already have: an incremental, commit-aware graph

`graph_io/update.py` stores `last_indexed_commit`, `last_indexed_at`, `deriver_version` in a graph-level `metadata` table (`:329-331`) and rebuilds by diffing `git diff --name-status <prev>..HEAD` (`_changed_files`, `:74`, `:277`; reads `last_indexed_commit` at `:268`). **The hard part of "maintain a `last_updated_commit` and review diffs since last scan" already exists — at the graph level.** The gap: this signal is *not* propagated to the page layer. `write_entities` re-renders all pages regardless, and the only re-narration gate is a frontmatter structural-key delta (`_detect_structural_change` / `STRUCTURAL_KEYS`, `entity_writer.py:477`, `:287-299`; `needs_narrative` fan-out gated at `scan.py:703-707`) — **git-agnostic**.

Reusable precedent for file-level "changed drastically": the embedding index already does **SHA256 content-hash incremental updates** (`commands/query.py:768-806`) — only re-embeds changed pages. The same pattern can gate file re-description.

### 1.5 Ingest fragility — root cause (not a model problem)

The "fails through the Bedrock flow, works in the plugin" symptom traces to robustness, not model capability:

- A **single** ingestor LLM call (`make_llm("ingestor")`) returns frontmatter + body, parsed by a **hand-rolled YAML parser** (`ingest.py:358-449`) that **silently falls back to a "concept" page** when the model wraps frontmatter in a ` ```yaml ` fence or emits slightly-malformed YAML (`:628-630`).
- Post-write **wikilink stripping** (`:283-350`) silently drops hallucinated `[[…]]` links — content the model believed it added.
- **Hard-fail** (exit 3) if the graph isn't initialized (`:59-79`, `:526-534`).

The Claude-plugin path "works better" only because the host LLM happens to format frontmatter more reliably. Fix = harden parsing + make fallbacks loud, not swap models.

### 1.6 Two execution paths (relevant to cost-offloading)

Each command runs either **headless on Bedrock** (`make_llm` + `SubagentPool` fan-out, JSONL traces) or **inside the Claude Code plugin** (host LLM, interactive, user-in-the-loop). The plugin shim selects the backend (`plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py:13-29`). `gw scan --no-narrate` already skips the LLM fan-outs entirely (structural-only pages). "Offloading harness work to Bedrock to save cost" = deciding **which roles** (narrator, code_reader, ingestor, librarian, synthesizer) run on cheap Bedrock tiers vs. the host.

### 1.7 Alignment with in-flight work

The **de-containerize** effort (`docs/superpowers/specs/2026-06-03-graph-wiki-decontainerize-design.md`, plan, and staleness audit) **landed 2026-06-03** (merge `34dab312`). What that establishes, now in `main`: **the graph is the sole source of truth; entity pages are disposable/regenerable; file maps are re-sourced from graph node paths** (`scan.py:820-823`, `build_file_map(repo / node_path)`); `detect_containers.py`, `layout_io.py`, the container/layout-block concept, and the source-sync/container lint checks are **deleted**; dependency pages are now entities (`entities/dep_*.md`). This roadmap builds directly on that simplified, graph-only scan path — it is the immediate next work, not a future dependency.

---

## 2. Where we want to be

A wiki that is a **living snapshot of the current state of the project** and an **active assistant to coding agents**:

- Re-scanning an updated repo **reconciles** each entity page against its template (adds/removes H2 sections), **preserves** human/LLM knowledge, and **refreshes only what changed**, gated on the commit diff.
- `Source` documents are ingested reliably, with **code as the final arbiter** when a doc drifts from reality.
- The graph + wiki + skills feed a **context-curation** layer that assembles task-relevant knowledge packages for agents.

### 2.1 The central tension — and its resolution

The de-containerize work declares entity pages **disposable** (`.claude/rules/backward-compatibility.md`: *"entity content can be deleted and regenerated at will"*). The living-wiki vision wants them to hold **durable** human knowledge. These reconcile via a **section-ownership model**:

> An entity page is partitioned into **scanner-owned** sections (regenerated from the graph every scan — disposable) and **human-owned** sections (preserved across scans — durable). The same split already exists implicitly for frontmatter (scanner keys vs. human keys) and for the File map (regenerated structure + preserved descriptions). We make it **explicit and general** for the whole page.

This refines — does not break — the backward-compat rule: *scanner-owned* content remains regenerable; *human-owned* content is preserved. **This document recommends updating that rule's wording accordingly.**

---

## 3. Architecture decisions

### D1 — Markdown stays the canonical, browsable format (persistence-DB fork left OPEN)

Milestone 1 keeps **markdown files as the source of truth** and the wiki as a human-browsable Obsidian vault (honoring the CLAUDE.md format-compat constraint). The SQLite graph and embedding index remain **derived caches**.

The **MongoDB / document-DB-as-source-of-truth** idea from the original brief is recorded as the **key open architectural decision** (§6), not adopted now. **Decision criteria for revisiting:** (a) section-level preservation via markdown parsing proves too fragile in practice; (b) cross-page querying/assembly needs outgrow BM25+embeddings; (c) concurrent multi-writer scenarios appear. Until then, a DB would break Obsidian browsing/editing and is a large rearchitecture for unproven benefit. The hybrid "DB-as-preservation-ledger" option (a SQLite append-only store keyed by entity+heading) is the most likely first step **if** markdown preservation proves fragile — noted as the fallback, not the plan.

### D2 — Section-ownership preservation via heading-aware merge (chosen: Approach A)

On re-scan, instead of re-rendering the whole body from the template, **read the existing page and keep every H2 except the scanner-owned set** (`## Narrative`, `## File map`, `## Referenced in wiki`), regenerating only those. Human sections (`## Purpose`, `## Public API`, and anything a user adds) survive **by default** — preservation becomes the rule, clobbering the exception.

- No new in-file syntax (keeps the Obsidian vault clean) — unlike managed-block markers (Approach B) or frontmatter-declared ownership (Approach C), both considered and rejected for M1.
- Generalizes to M2's template reconciliation: adding/removing an H2 = adjusting the owned/unowned partition.
- **Risk + mitigation:** a renamed scanner-owned heading orphans its region. Mitigated by the existing "humans must not rename this heading" convention (`entity_writer.py:938-942`) plus a lint rule that flags missing/renamed scanner headings.

### D3 — Reuse existing change-detection infra; don't rebuild

M2 plumbs the graph's existing `last_indexed_commit` into a per-entity `last_updated_commit` frontmatter key and gates refresh on `git diff` of the entity's files. File-level "changed drastically" reuses the **content-hash** pattern from the embedding index (`query.py:768-806`). No net-new diffing engine.

---

## 4. Roadmap

| Milestone | Goal | Size | Depends on |
|---|---|---|---|
| **M1 — Preservation** | Stop wiping human/LLM sections; remove duplicative stubs | Small (~1 plan) | De-containerize ✓ (landed) |
| **M2 — Commit-gated incremental updates** | Living snapshot: refresh only what changed | Medium–Large | M1 |
| **M3 — Source re-ingestion + code-as-arbiter** | Reliable, self-correcting knowledge intake | Medium | M1 (ingest hardening can parallelize) |
| **M4 — Drift propagation to backlinks** | Flag/propose updates to stale concept/ADR pages | Large, expensive | M2, M3 |
| **M5 — Context curation & new categories** | Assemble task-relevant context packages for agents; Ideas/Knowledge | Large | M2–M4 |

### M1 — Preservation (specced for `writing-plans`)

**Goal:** durable human/LLM knowledge on entity pages survives re-scan; the page is honest about what's scanner-owned vs. human-owned.

**Scope:**
1. Implement **heading-aware merge** (D2): re-scan preserves all non-scanner-owned H2 sections; regenerates only `## Narrative`, `## File map`, `## Referenced in wiki`. Define the scanner-owned heading set as a single named constant.
2. **Remove** `## Concepts`, `## Dependencies`, `## Decisions`, `## Contrasts / alternatives` from all entity templates (superseded by `## Referenced in wiki`; dependency relationships live in `depends_on` frontmatter + the dependency's own entity page).
3. **Tests:** re-scan preserves a hand-edited `## Purpose` / `## Public API` and a user-added custom H2; still regenerates Narrative/File map/Referenced-in-wiki; File-map description preservation continues to pass; byte-stability/idempotence on a no-op re-scan.
4. Update `.claude/rules/backward-compatibility.md` wording to the section-ownership model.

**Out of scope:** commit gating, template reconciliation (M2), any LLM calls.

**Success criteria:** a populated `## Purpose` survives N re-scans unchanged; the four stub sections no longer appear; no regression in the de-containerize parity snapshot.

### M2 — Commit-gated incremental updates

Per-entity `last_updated_commit` frontmatter (sourced from graph `last_indexed_commit`, D3). On re-scan: **template reconciliation** (add/remove H2s per the current template, respecting ownership); refresh `## Narrative` **only if the entity's files changed** since `last_updated_commit`; File map adds/removes rows from node paths and **re-describes a file only when its content hash changed materially**; detect when human/LLM sections may have **drifted** (entity changed underneath them) and flag for review. *Recommendation:* start with **flag-don't-auto-edit** for human sections — propose updates, don't silently overwrite.

### M3 — Source re-ingestion + code-as-arbiter

Harden the ingest path (§1.5): robust frontmatter parsing, **loud** fallbacks instead of silent "concept" demotion, surfaced wikilink-strip reports. Establish the **code-as-arbiter Source page shape**: a top "documentation" section (the ingested content's distilled claims) + a bottom **append-only change log** recording when code contradicted the doc and how it was reconciled. Re-ingesting an updated source appends to the log rather than overwriting. *Open:* exact reconciliation UX (§6).

### M4 — Drift propagation to backlinks

On re-scan, examine pages that backlink a changed entity (concepts/ADRs/architecture) and **propose** updates where their claims have gone stale. This is the **most expensive, LLM-heaviest, highest-false-positive** step — it should be opt-in, batched, and propose-only (never auto-edit curated pages). Strong candidate for cheap-Bedrock-tier offloading.

### M5 — Context curation & new categories

Specialized subagents analyze a prompt/spec/plan and assemble a **context package** from wiki + graph + skills (best practices, relevant entities, prior decisions) to prime a coding agent. This is the **payoff** milestone — it only pays off once the knowledge layer (M1–M4) is durable and current. Also: decide `Ideas` (likely a `work/`-style item, not a new top-level category) and `Knowledge` (evaluate as a category vs. a sibling collection) — *recommendation: prefer reusing existing categories over adding top-level collections unless a concrete need appears.*

---

## 5. Cross-cutting: cost-offloading to Bedrock

Independent of the milestones: tune which **roles** run on which tier (`models.toml` / `.graph-wiki.yaml`). Cheap-tier candidates: narrator, code_reader, M4 drift-proposer (high volume, low-stakes). Reserve stronger tiers for synthesizer and ingestor (correctness-sensitive). `--no-narrate` and the `--model` single-role swap already exist as levers; the eval harness (`deepeval`) can measure quality-per-dollar per role swap.

---

## 6. Open questions

1. **Persistence DB (the big one).** Markdown-only (current plan) vs. DB-as-source-of-truth vs. hybrid SQLite preservation-ledger. Revisit per D1's criteria. *Leaning: markdown + optional ledger if §D2 proves fragile.*
2. **Code-as-arbiter Source shape.** Doc-section + append-only change log — exact format, and how reconciliation is triggered/surfaced (M3).
3. **Initial source-code ingestion.** Should we seed concept/architecture pages from the code itself on first scan, or only from ingested docs? *Leaning: keep scan structural-only; let ingestion + human authoring create curated pages, to avoid low-quality auto-generated concepts.*
4. **Cost-offloading targets.** Which roles to push to cheap Bedrock tiers, validated by eval (§5).
5. **`Ideas` / `Knowledge` categories.** Work-item vs. category vs. sibling collection (M5).
6. **Drift propagation aggressiveness** (M4): propose-only vs. auto-edit; batching cadence; false-positive budget.

---

## 7. Sequencing summary

De-containerize ✓ (landed 2026-06-03) → **M1 Preservation** → **M2 Commit-gated updates** → **M3 Ingest robustness / code-as-arbiter** (parallelizable with M2) → **M4 Drift propagation** → **M5 Context curation**. M1 is the next thing to spec.
