# Feature Research

**Domain:** Graph-driven wiki entity restructure — collapsing a page-type-per-directory wiki into a unified `/entities/` lane keyed by graph-io URIs, with scanner-populated relation frontmatter and LLM-assisted domain proposal.
**Researched:** 2026-05-26
**Confidence:** HIGH (all findings from direct codebase inspection; no external sources needed for this internal feature milestone)

---

## Feature Landscape

### Table Stakes (Must Land for v1.8 Goal)

These features are the core restructure. Without them the milestone goal — "wiki becomes the curated human-readable projection of graph-io" — is not achieved.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **F3: URI-keyed entity pages** | Stable identity across renames is the foundational promise of the graph-io ontology (§8 of ONTOLOGY-SPEC). Without URI keying, `/entities/` is just a renamed `/packages/` with the same drift problem. | MEDIUM | URI → filename mapping decision: strip scheme + replace `/` with `--` (e.g. `pkg:agent-research/graph-io` → `pkg--agent-research--graph-io.md`). Must land before F1/F2 can be generated correctly. Single biggest design-lock in v1.8. |
| **F1: `/entities/` lane** | The flat folder with `kind` discriminator in frontmatter is the output container for the entire restructure. Without it, F2/F3/F4 have nowhere to write. | MEDIUM | `wiki_io/init_vault.py` `FIXED_VAULT_DIRS` must add `entities`. Scanner writes here; existing `packages/`, `dependencies/`, `domain/`, `plugin/` directories retire. Kind whitelist: `repository`, `domain`, `package`, `package-family`, `plugin`, `dependency`, `test-suite`. |
| **F2: Per-kind templates** | The existing `package/overview.md`, `package/api.md` etc. are directory-scoped. Collapsing package-as-folder into a single `entity-package.md` page requires new template machinery. | MEDIUM | New templates: `entity-package.md`, `entity-domain.md`, `entity-dependency.md`, `entity-test-suite.md`, `entity-repository.md`, `entity-plugin.md`, `entity-package-family.md`. `layout_io.ensure_subpage()` and `ensure_domain_page()` are replaced by a new `ensure_entity_page(kind, uri, ...)` helper. Directory templates (`package/`, `domain/`) go away for graph-derived entities. |
| **F4: Scanner-populated relation frontmatter** | Without this, entity pages are static stubs. The value of the graph-io integration is that graph edges become queryable, human-readable frontmatter on every page. | HIGH | Scanner must: (1) open read-only conn, (2) for each entity, query edges from `graph_io.queries`, (3) write whitelisted keys into frontmatter. Whitelist must be explicit (e.g. `covered_by`, `belongs_to_domain`, `depends_on`, `declared_entry_points`). Human-authored keys (e.g. `status`, `notes`) are never overwritten. The whitelist contract is the critical design decision for this feature. |
| **F5: Domain-first + by-kind scanner-generated index** | The index is the primary navigation surface. If it's not domain-first, the wiki's claim of being "domain-driven" is only in entity pages, not the entry point. Q5 answer: fully scanner-generated (regenerated each run, not a human-authored shell). | HIGH | `update_index.py` currently infers categories from directory structure (`CATEGORY_DIRS`). Needs a full rewrite: read all `entities/*.md` frontmatter, group by `belongs_to_domain` (domain section), then flatten by `kind` (by-kind section). Both views in the same file. Entities appear twice (once under domain, once in kind section). `update_index.py` must also preserve curated lane sections (concepts, adrs, etc.). |
| **F6: Hard-delete reconciliation** | Without this, deleted packages accumulate ghost pages forever. The v1.7 pattern (`_add_stale_tag`) was a workaround; v1.8 replaces it with hard delete for `/entities/`. Q2 answer: hard delete accepted; vault is disposable, dangling-link risk accepted. | LOW | Extension of existing `compute_diff` + scan loop: when a graph node is absent from the graph on next scan, delete the entity page instead of marking stale. `stale: true` tagging is retained only for curated lanes (not `/entities/`). The `diff["deleted"]` branch in `run_scan()` currently calls `_add_stale_tag()`; this branches on entity vs. curated page. |
| **F7: One-shot inbound-link migration** | Without this, existing `/concepts/`, `/adrs/`, `/architecture/` pages have broken wikilinks after the restructure. Q3 answer: one-shot migration pass at cutover. | MEDIUM | New standalone script (not a scanner stage): walks `/concepts/`, `/adrs/`, `/architecture/`; for each wikilink matching old paths (`packages/X/X`, `dependencies/X`, `domain/X/overview`), replaces with new URI-based path (`entities/<uri-slug>`). Requires the URI slug mapping table from the first `/entities/` scan output. One-shot: run once at vault cutover; not idempotent by design. |

### Differentiators (v1.8 Competitive Advantage)

Features that make the restructured wiki meaningfully better than the prior model.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **F8: Curated lanes preserved** | Mixed graph-derived + human-curated wiki is the design. Preserving `/concepts/`, `/adrs/`, `/architecture/` means the wiki is useful for things the graph can't express. | LOW | Zero new code — existing curated lanes are untouched. The `update_index.py` rewrite must preserve their sections. The only risk is accidentally sweeping them in a batch-delete. Mitigation: lane discrimination logic in scanner: "is this path under `/entities/`?" gates hard-delete vs. stale-tag. |
| **F9: `cg domain-clusters`** | Import-graph clustering gives the LLM proposal (F10) a grounded, deterministic starting point. Without it, F10 is purely hallucinated. The cluster command is also independently useful as a diagnostic (`cg domain-clusters --show-unclustered` surfaces cross-cutting packages). | HIGH | New `graph_io.cli.ops_domain_clusters` module. Algorithm: connected-component or community-detection over the `imports`/`imported_by` edges between package nodes, weighted by edge count. Output: `domains.proposed.yaml`-compatible YAML (or JSON for F10 to consume). Independently testable: input is the SQLite graph, output is a deterministic text artifact. No LLM involved. |
| **F10: `graph-wiki-agent graph propose-domains`** | LLM-proposed domain groupings make the domain authoring workflow dramatically faster: instead of reading the import graph yourself, you start from a draft. The human is still in the loop (proposals never auto-apply). | HIGH | New Typer subcommand under `graph_app`. Consumes `cg domain-clusters` output + `graph describe domain` for existing domains + package names/paths. Emits `domains.proposed.yaml` alongside `domains.yaml`. Prompt must include the cluster data, existing domain names (as hard constraints), and a clear instruction that cross-cutting packages (zero domain membership) are intentional. Result is a YAML file — not a graph mutation. |

### Anti-Features (Scope Traps for v1.8)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Scanner pipeline restructure (9-stage)** | ONTOLOGY-SPEC §9 describes the clean 9-stage pipeline; the current scanner is a monolithic `run_scan()`. Tempting to restructure as part of F4. | Turns a feature milestone into an architectural refactor. `run_scan()` is ~650 LOC and already production-wired with graph-io in v1.7. Restructuring it is a different milestone (deferred per PROJECT.md). F4 relation frontmatter can be implemented as a new post-scan pass in the existing `run_scan()` without restructuring. | Add relation frontmatter generation as a new block in `run_scan()` after Step 10 (page write), using the already-open `conn`. Document it as a "stage 9 precursor" for the eventual pipeline refactor. |
| **Auto-apply LLM domain proposals** | `propose-domains` produces `domains.proposed.yaml`; it's tempting to add `--apply` to merge it into `domains.yaml` automatically. | Destroys the human-review checkpoint. The entire value of `domains.proposed.yaml` is that it is separate from `domains.yaml` until a human inspects and curates it. Auto-apply silently corrupts curated domain config. | The workflow is: `propose-domains` → inspect `domains.proposed.yaml` → manually merge into `domains.yaml` → `cg build`. This is the correct design. No `--apply` flag. |
| **Sub-package entity pages** | Sub-packages are modeled as first-class nodes in graph-io. Tempting to expose them as wiki entities since the data is there. | Explodes page count with low-signal entities. Sub-packages are implementation details, not architectural units. The wiki stops at the package boundary by explicit policy (design doc §Entity boundary). | Sub-package information appears as structured data on the parent `package` entity page (via F4 relation frontmatter), not as separate pages. |
| **In-file node entity pages (class/function/method)** | Same as sub-packages — the data exists in the graph. | Same problem at larger scale. A medium monorepo might have thousands of classes. The wiki is for navigating architecture, not AST browsers. | Included in parent package entity page's relation frontmatter as counts/summaries, not as individual pages. |
| **Compatibility shim redirect pages at old paths** | Q3 reconciliation option: leave stub redirect pages at old paths like `packages/graph-io/overview.md` so old wikilinks don't break. | Creates a parallel shadow directory structure. Obsidian doesn't support HTTP-style redirects; shim pages are dead weight. The vault is declared disposable (PROJECT.md: "wipe-and-rebuild is acceptable"). | One-shot migration pass (F7) updates all inbound links at cutover. No shims needed. |
| **`status: removed` tombstone pattern for entities** | Q2 reconciliation option: keep deleted entity pages with `status: removed` frontmatter instead of deleting. | Dangling-link risk from curated lanes is accepted per PROJECT.md. Tombstones add cognitive overhead with no benefit in a disposable vault. | Hard delete (F6). Dangling wikilinks in `/concepts/` and `/adrs/` are acceptable and surfaced by linter. |
| **`domains.proposed.yaml` → auto-push to `domains.yaml`** | (variant of auto-apply anti-feature above) | Same reasons. | Same alternative. |

---

## Feature Dependencies

```
F3: URI-keyed entity pages
    └──enables──> F1: /entities/ lane (filenames are URI-slugged)
                      └──enables──> F2: Per-kind templates (need a page to write to)
                      └──enables──> F4: Scanner relation frontmatter (need entity pages to decorate)
                      └──enables──> F5: Domain-first index (needs entity frontmatter to aggregate)
                      └──enables──> F6: Hard-delete reconciliation (needs entity vs. curated discrimination)

F1: /entities/ lane
    └──enables──> F7: One-shot inbound-link migration (needs entity URI slugs to be settled)

F9: cg domain-clusters
    └──enables──> F10: propose-domains (clusters are the structured input to the LLM prompt)

F4: Scanner relation frontmatter
    └──enhances──> F5: Domain-first index (richer frontmatter → richer index views)

F8: Curated lanes preserved
    └──conflicts with nothing (zero-touch; risk only from F5/F6 scope creep)
```

### Dependency Notes

- **F3 must land before F1/F2**: The URI-to-filename mapping is the contract that all entity page writers depend on. Settling it first avoids renaming pages partway through the milestone.
- **F1 must land before F7**: The migration script needs to know the destination paths (`entities/<uri-slug>.md`) before it can rewrite inbound links. Running F7 before F1 is settled produces dead links.
- **F9 feeds F10**: `propose-domains` without cluster data is pure hallucination. The cluster output gives the LLM structured, deterministic groupings to annotate and refine rather than invent.
- **F4 and F5 can proceed in parallel** once F1/F3 are settled, because F4 writes to entity pages and F5 reads from entity pages — they share the frontmatter contract but don't conflict.
- **F6 depends on F1** only for the discrimination logic (entity vs. curated page); the `compute_diff` mechanics already exist in v1.7.

---

## MVP Definition

### Foundation (must land together — v1.8 core)

These four features form the minimum viable foundation. Without all four, the wiki is not actually restructured — it's just partial.

- [ ] **F3: URI-keyed entity pages** — URI-to-filename mapping is the identity contract. Everything else keys off it.
- [ ] **F1: `/entities/` lane** — flat folder is the output container; `init_vault.py` updated; scanner writes here.
- [ ] **F2: Per-kind templates** — scanner needs templates to generate entity pages; old directory templates replaced.
- [ ] **F5: Domain-first + by-kind index** — index is the primary navigation surface; if it still shows `packages/` and `dependencies/` sections the restructure isn't visible to the user.

### Core Restructure (add in same milestone wave)

These are required for the restructure to be production-usable, but can follow the foundation by a phase or two.

- [ ] **F4: Scanner relation frontmatter** — the killer feature that makes entity pages richer than the old stubs. Without it, entity pages are just stubs with a different path.
- [ ] **F6: Hard-delete reconciliation** — prevents ghost page accumulation on every subsequent scan.
- [ ] **F7: One-shot inbound-link migration** — vault is currently broken (old wikilinks point at retired paths) until this runs.
- [ ] **F8: Curated lanes preserved** — zero-touch, but must be verified as a success criterion for F5/F6 (index still shows concepts/adrs/architecture sections; scanner doesn't delete curated pages).

### Stretch (can slip to v1.9 if scope too large)

These are differentiators but the core restructure is complete without them.

- [ ] **F9: `cg domain-clusters`** — independently testable; no scanner changes needed. Can ship in a separate phase even after wiki restructure is done.
- [ ] **F10: `graph-wiki-agent graph propose-domains`** — depends on F9. High-value for domain authoring workflow but not required for the wiki layout change.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| F3: URI-keyed entity pages | HIGH | MEDIUM | P1 — blocking everything |
| F1: `/entities/` lane | HIGH | MEDIUM | P1 — foundation container |
| F2: Per-kind templates | HIGH | MEDIUM | P1 — scanner output format |
| F5: Domain-first index | HIGH | HIGH | P1 — primary navigation |
| F4: Scanner relation frontmatter | HIGH | HIGH | P1 — core differentiation |
| F6: Hard-delete reconciliation | MEDIUM | LOW | P1 — hygiene, blocks accumulation |
| F7: One-shot migration | HIGH | MEDIUM | P1 — vault broken without it |
| F8: Curated lanes preserved | MEDIUM | LOW | P1 — correctness gate, not new work |
| F9: `cg domain-clusters` | MEDIUM | HIGH | P2 — stretch, v1.9 candidate |
| F10: `propose-domains` | MEDIUM | HIGH | P2 — stretch, depends on F9 |

**Priority key:**
- P1: Must have for v1.8 milestone close
- P2: Should have; split to v1.9 if scope too large
- P3: Nice to have (nothing here for v1.8)

---

## Key Design Decisions Surfaced

### D1: URI-to-filename mapping scheme

The URI-keyed identity (F3) requires a deterministic URI → filename transformation. The scheme `pkg:agent-research/graph-io` must become a valid, readable filename.

**Recommended:** strip scheme prefix, replace `:` with `--`, replace `/` with `--`.
- `pkg:agent-research/graph-io` → `pkg--agent-research--graph-io.md`
- `domain:billing` → `domain--billing.md`
- `repo:agent-research` → `repo--agent-research.md`
- `test-suite:agent-research/eval-harness/unit` → `test-suite--agent-research--eval-harness--unit.md`

This is readable, Obsidian-compatible (no special chars), and reversible. The scheme prefix preserves kind information in the filename, making kind visible without opening the file.

**Must decide at scoping for Phase 42** — this is the load-bearing contract.

### D2: Scanner-owned frontmatter whitelist

F4 requires a whitelist of keys the scanner may overwrite. Human-authored keys must never be clobbered.

**Recommended whitelist (scanner-owned):**
```yaml
# Written by scanner; do not edit manually
uri: pkg:agent-research/graph-io
kind: package
title: graph-io
belongs_to_domain: [graph]
covered_by: [test-suite--agent-research--eval-harness--unit]
depends_on: [langchain-core, boto3]
declared_entry_points: [cg]
```

**Human-owned (never touched by scanner):** `status`, `notes`, `last_reviewed`, `summary`, `tags`, any key not in the whitelist.

**Implementation:** scanner reads existing frontmatter, merges whitelisted keys (overwrite), preserves all others, writes back. Order convention: scanner keys first, human keys below a comment marker.

**Must decide at scoping** which specific edge types map to which frontmatter keys — the ONTOLOGY-SPEC §4 edge table is the input.

### D3: `update_index.py` rewrite scope

F5 requires `update_index.py` to change from directory-walk-based category inference to frontmatter-based graph projection.

**Recommended approach:** keep `update_index.py` as the module but replace `scan_vault()` with a new `scan_entities()` that reads from `/entities/` specifically, groups by `belongs_to_domain` frontmatter, then by `kind`. The curated lanes scan (`concepts`, `sources`, `adrs`, `architecture`) stays as-is. The index structure changes from flat-by-category to:
1. Domain sections (inline expanded, entities listed under their domain)
2. By-kind sections (flat lists for navigation by kind regardless of domain)
3. Curated sections (concepts, sources, adrs, architecture — unchanged)

**`MAIN_INDEX_CATEGORIES` and `CATEGORY_DIRS` in `update_index.py` become obsolete** for the entities section; retain them only for curated lane rendering.

### D4: Migration ordering — which features form the unblockable sequence

The dependency graph forces this ordering:
1. **F3 (URI mapping scheme)** — design decision only; no code until locked.
2. **F1 + F2** — `init_vault.py` + new templates; scanner can now write to `/entities/`.
3. **F4 (relation frontmatter whitelist)** — scanner writes enriched entity pages.
4. **F5 (index rewrite)** — reads from settled entity frontmatter.
5. **F6 (hard delete)** — one-line branch change in `run_scan()`.
6. **F7 (migration script)** — runs once against a vault that already has `/entities/` settled.

F8 (curated lanes) is a correctness gate threaded through F5 and F6, not a sequential step.
F9 and F10 are fully independent of F1-F8 and can proceed in a parallel phase track or slip to v1.9.

### D5: Q4 scanner pipeline integration point

The existing `run_scan()` in `commands/scan.py` already opens a read-only `conn` at Step 1.6 (v1.7, Phase 39). The relation frontmatter pass (F4) slots in as a new block after Step 10 (page write), using the same `conn`:

```
Step 10b (new): for each written entity page, query edges from conn,
                merge whitelisted frontmatter keys, write back.
```

This is **not** a stage-9-pipeline restructure — it's an extension of the existing pattern. The pipeline restructure remains deferred per PROJECT.md.

---

## Complexity Estimates by Feature

| Feature | Size | Primary Module(s) Touched | New Modules |
|---------|------|---------------------------|-------------|
| F3: URI mapping scheme | S | None (design decision) | `wiki_io/entity_pages.py` (new helper) |
| F1: `/entities/` lane | S | `wiki_io/init_vault.py`, `wiki_io/scan_monorepo.py` | None |
| F2: Per-kind templates | M | `wiki_io/layout_io.py`, `wiki_io/assets/page-templates/` | 7 new template files |
| F4: Scanner relation frontmatter | L | `commands/scan.py` (Step 10b), `wiki_io/entity_pages.py` | `wiki_io/entity_pages.py` |
| F5: Domain-first index | L | `wiki_io/update_index.py` | None (rewrite, not new module) |
| F6: Hard-delete reconciliation | S | `commands/scan.py` (Step 11 branch) | None |
| F7: One-shot migration | M | None (existing files) | `scripts/migrate_entity_links.py` (new, one-shot) |
| F8: Curated lanes preserved | S | `wiki_io/update_index.py` (correctness gate only) | None |
| F9: `cg domain-clusters` | L | `packages/graph-io/` | `graph_io/cli/ops_domain_clusters.py` |
| F10: `propose-domains` | L | `commands/graph.py` | New Typer subcommand |

**Size key:** S = <50 LOC, M = 50-150 LOC, L = 150+ LOC or significant design complexity

---

## Splitability: v1.8 Core vs. v1.9 Candidates

### v1.8 core (non-negotiable for milestone goal)
F3 + F1 + F2 + F4 + F5 + F6 + F7 + F8

### v1.9 candidates (split here if scope proves too large)
- **F9** (`cg domain-clusters`) — self-contained, no scanner changes; graph-io-only work.
- **F10** (`propose-domains`) — depends on F9; high-value but non-blocking for wiki layout.

The split is clean: F9/F10 touch `packages/graph-io/` and `commands/graph.py` only. They don't touch `wiki_io/`, `commands/scan.py`, or any of the entity page machinery. If F4 or F5 prove larger than estimated, F9+F10 slide to v1.9 with zero rework cost.

---

## Sources

- Direct codebase inspection: `packages/wiki-io/src/wiki_io/update_index.py` — current category model, `CATEGORY_DIRS`, `MAIN_INDEX_CATEGORIES`
- Direct codebase inspection: `packages/wiki-io/src/wiki_io/init_vault.py` — `FIXED_VAULT_DIRS`, current vault initialization structure
- Direct codebase inspection: `packages/wiki-io/src/wiki_io/layout_io.py` — `ensure_subpage()`, `ensure_domain_page()` — the directory-template helpers being replaced
- Direct codebase inspection: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — `run_scan()` existing step structure, Steps 10-11, existing conn lifetime (Phase 39)
- Direct codebase inspection: `packages/graph-io/src/graph_io/queries.py` — `_VALID_KINDS`, `NodeRecord`, query API surface available for F4 relation frontmatter population
- `.planning/notes/wiki-entity-restructure-design.md` — authoritative design direction, entity boundary policy, two-lane layout, edges-as-frontmatter contract
- `.planning/PROJECT.md` v1.8 section — 10 target features, Q1-Q5 answers, wipe-and-rebuild acceptability, F9/F10 scope
- `.planning/research/questions.md` — Q1-Q5 and their resolved answers
- `.planning/research/ONTOLOGY-SPEC.md` §8 (identity/URI), §9 (scanner pipeline + domain inference strategies 3 & 4), §4 (edge types for F4 whitelist input)
- `.planning/milestones/v1.7-research/SUMMARY.md` — existing scanner integration patterns (conn lifetime, `build_graph_tools` precedent), anti-patterns to avoid

---
*Feature research for: v1.8 Wiki Entity Restructure*
*Researched: 2026-05-26*
