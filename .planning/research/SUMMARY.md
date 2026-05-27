# Research Summary

**Project:** agent-research — v1.8 Wiki Entity Restructure
**Domain:** Graph-driven wiki schema overhaul + LLM domain inference
**Researched:** 2026-05-26
**Confidence:** HIGH

## Executive Summary

The v1.8 Wiki Entity Restructure collapses the current page-type-per-directory wiki model into a unified `/entities/` lane where each file corresponds to one graph-io node, keyed by its stable URI. With v1.6's graph ontology and v1.7's scanner integration already shipped, the graph is the authoritative structural model; the wiki currently duplicates that structure in a parallel directory hierarchy. The restructure makes the wiki the curated human-readable projection of the graph rather than a parallel model — the graph's edges become structured frontmatter on entity pages, regenerated deterministically on each scan, while prose narrative is reserved for human authorship and LLM generation.

The recommended approach is a hard switchover, not a gradual migration. The existing exploratory vault is disposable; wipe-and-rebuild is acceptable. All seven v1.8 features (F1-F8) build on the existing dependency closure with zero new Python libraries required: `python-frontmatter`, `graph_io.queries`, stdlib string ops, and `pathlib` cover the full entity-page and index machinery. The LLM domain proposal (F9-F10) similarly requires no new libraries — import-graph clustering is ~50 LOC of BFS over the adjacency dict `derived_edges.py` already builds. The primary implementation work is new modules in `wiki-io` and `graph-io`, plus targeted modifications to `scan.py`.

The key risk is the load-bearing design contract that must be locked before any code is written: the URI-to-filename slug encoding scheme (D1) and the scanner-owned frontmatter key whitelist (D2). Both decisions cascade across every entity-writing module. A second significant risk is slug collision — naive separator replacement (`:` to `-`, `/` to `-`) is non-injective and silently overwrites pages. The recommended encoding (`:` to `__`, `/` to `__`) is collision-free and must be property-tested against all admitted URI kinds before the entity writer is wired into any scan path. A third risk specific to the LLM clustering path is degenerate output on small sparse graphs: `agent-research`'s 7-8 packages with high-degree hub nodes (e.g. `model-adapter`) can collapse into one cluster or N singletons; hub-exclusion preprocessing must be part of the initial `cg domain-clusters` implementation, not a later improvement.

## Key Findings

### Recommended Stack

All v1.8 features are implementable on the existing dependency closure. No new packages are added to any workspace member. The implementation work is new modules in existing packages: `wiki_io/entity_writer.py` (~150 LOC), `wiki_io/index_generator.py` (~120 LOC), `wiki_io/link_rewriter.py` (~60 LOC), `graph_io/cluster.py` (~50 LOC BFS), `graph_io/cli/q_domain_clusters.py` (~60 LOC), and a new `propose_domains.py` command (~100 LOC) in `graph-wiki-agent`.

**Core technologies used (existing):**
- `python-frontmatter >=1.1.0`: relation frontmatter merge on entity pages — round-trip YAML with per-key merge logic
- `graph_io.queries` (workspace): all graph edge queries for entity page population and index generation — `describe_package`, `describe_domain`, `list_domains`, etc. already exist
- `graph_io.uri` (workspace): `pkg_uri()`, `domain_uri()` etc. are the URI source; slug derivation is stdlib string ops on those URIs
- `pyyaml >=6.0` (already in graph-io deps): `domains.proposed.yaml` output from the propose-domains command
- `pathlib.Path` (stdlib): hard-delete reconciliation via `Path.unlink()`
- `re` (stdlib): inbound-link migration regex with Markdown-aware tokenization

**What is explicitly not added:** `networkx`, `igraph`, `scipy`, `jinja2`, `ruamel.yaml`. All would be overkill for the scale (200 nodes max, static templates, no complex topology algorithms needed).

### Expected Features

**Must have — v1.8 core (F1-F8):**
- **F3: URI-keyed entity pages** — URI-to-filename mapping is the identity contract; must land first because everything else keys off it. Recommended slug: `pkg:agent-research/graph-io` to `pkg--agent-research--graph-io.md` (replace `:` with `__`, `/` with `__`). Design lock D1.
- **F1: `/entities/` lane** — flat folder, `kind` in frontmatter, `init_vault.py` updated. Admitted kinds: `repository`, `domain`, `package`, `package-family`, `plugin`, `dependency`, `test-suite`. Old directories (`packages/`, `dependencies/`, `domain/`, `plugin/`) retire at cutover.
- **F2: Per-kind templates** — 7 new `entity-*.md` templates alongside existing directory templates. `layout_io.ensure_subpage()` replaced by `ensure_entity_page(kind, uri, ...)` for entity lane.
- **F4: Scanner-populated relation frontmatter** — scanner queries graph edges and writes whitelisted keys to frontmatter. Design lock D2: whitelist must be defined in code as a `frozenset` constant before any page is written. Human-authored keys (`status`, `notes`, `last_reviewed`) are never touched.
- **F5: Domain-first + by-kind scanner-generated index** — fully regenerated each scan (not a human-authored shell). Entities appear twice: once under their domain section, once in the global by-kind section. Write-if-changed guard prevents git churn when nothing changed.
- **F6: Hard-delete reconciliation** — entity pages for disappeared graph nodes are deleted on next scan. Stale-tagging retained only for curated lanes. Log every deletion.
- **F7: One-shot inbound-link migration** — single rewrite pass of `/concepts/`, `/adrs/`, `/architecture/` wikilinks at cutover. Markdown-aware (skips code fences and inline code spans). Idempotent: running twice is a no-op.
- **F8: Curated lanes preserved** — zero new code; correctness gate only. Index rewrite must preserve concepts/adrs/architecture/work/sources sections.

**Should have — stretch (F9-F10), v1.9 candidates if scope too large:**
- **F9: `cg domain-clusters`** — deterministic import-graph clustering; new `graph_io/cli/q_domain_clusters.py`. No LLM. Hub-node exclusion preprocessing required from day one to avoid degenerate output on small sparse graphs.
- **F10: `graph-wiki-agent graph propose-domains`** — LLM proposes `domains.proposed.yaml` from cluster data + graph context. Grounding check (every package name validated against live graph) and cycle detection required before the file is written. Never auto-applied.

**Explicitly deferred or anti-featured:**
- Scanner pipeline restructure to 9 stages — remains deferred per PROJECT.md
- Auto-apply for `domains.proposed.yaml` — hard no; destroys the human-review checkpoint
- Sub-package entity pages — implementation detail; referenced from parent package page as frontmatter counts
- Compatibility shim redirect pages at old paths — vault is disposable; one-shot migration covers it

### Architecture Approach

The key architectural resolution (Q4) is that relation-frontmatter generation **replaces** the existing scanner Steps 9+10 for graph-derived entities rather than augmenting them. The new pipeline splits Step 9 into two sub-steps: 9a (deterministic entity page write from graph — no LLM) and 9b (LLM prose narrative — fan-out only for new or structurally-changed pages). The LLM no longer generates frontmatter; it writes prose sections only into pre-populated pages. Steps 1-8 and Step 13 are untouched. The cutover is a single commit: `entity_writer.write_entities` to `link_rewriter.rewrite_links` to remove old directories to regenerate index.

**Major new components:**

1. `wiki_io/entity_writer.py` — deterministic entity-page writer. Accepts a graph conn + admitted node list; queries edges; derives slug from URI; creates or merges pages; hard-deletes disappeared nodes. Returns `(created, updated, deleted, needs_narrative_set)` for the LLM fan-out gate.
2. `wiki_io/index_generator.py` — graph-driven index. Queries `list_domains`, `list_packages`, etc. directly (not by parsing entity page frontmatter — that would create a second source of truth). Sorted deterministically; write-if-changed guard.
3. `wiki_io/link_rewriter.py` — one-shot inbound-link migration. Markdown-aware tokenizer + idempotency marker in wiki manifest.
4. `graph_io/cluster.py` — ~50 LOC stdlib BFS connected-components on the import adjacency dict. Hub-node exclusion preprocessing. Degenerate-cluster warning output.
5. `graph_io/cli/q_domain_clusters.py` — `cg domain-clusters` command. Independently testable with no LLM dependency.
6. `graph_wiki_agent/commands/propose_domains.py` — `graph propose-domains` Typer subcommand. Consumes clusters via `_capture_run`, writes `domains.proposed.yaml` with grounding validation and cycle detection applied before write.

**Recommended build order:** Phase A (URI slug scheme + templates) to Phase B (`entity_writer.py`) to Phase C (`index_generator.py`) to Phase D (scanner integration in `scan.py`) to Phase E (`link_rewriter.py` + cutover commit). Phases F (`cg domain-clusters`) and G (`propose-domains`) are independent of A-E and can overlap or slip to v1.9.

### Critical Pitfalls

1. **URI-to-filename slug collision** — naive separator replacement is non-injective; `pkg:org/foo-bar` and `pkg:org/foo/bar` can produce the same filename. Use `__` as the separator (not `-`). Build the slug encoder as a standalone function with a property test over 1,000 synthetic URIs from all admitted kinds before writing any entity pages. This test must pass before the entity writer is wired into any scan path.

2. **Frontmatter key collision — scanner overwrites human-authored keys** — the easy implementation (discard frontmatter, write from scratch) silently deletes `status`, `last_reviewed`, `owner` etc. The whitelist merge function (`merge_frontmatter(existing, scanner_update, owned_keys)`) must be in place before any entity page is touched. Test: write a page with human `status: deprecated`, run entity updater, assert `status: deprecated` is preserved.

3. **Degenerate import clusters on small sparse graphs** — `agent-research`'s 7-8 packages with high-degree hub nodes will produce one giant blob or N singletons under standard connected-components. Hub-node exclusion (exclude packages imported by >50% of others) and degenerate-cluster detection must be in the initial `cg domain-clusters` implementation. Test against the `agent-research` monorepo itself.

4. **Index regeneration churning git history** — fully regenerated index without a write-if-changed guard produces a new diff on every scan even when nothing changed. Deterministic sort order (domain name, then URI within section) + `if existing_content == new_content: return` guard prevents this. Add a determinism test: generate the index twice from the same graph with different insertion orders, assert byte-identical output.

5. **Migration regex over-matching** — a simple `re.sub` rewrites wikilinks inside fenced code blocks and inline code spans, breaking documentation examples. The migration script must tokenize the Markdown document into code regions (skip) and prose regions (rewrite). Test: a concepts page with a wikilink inside a fenced code block is untouched after migration.

## Implications for Roadmap

F3 must be decided before any code touches entity pages. The URI-to-filename mapping and the scanner-owned frontmatter whitelist are the two design locks that cascade across all downstream phases.

### Phase A: URI Scheme + Per-Kind Templates (design lock)

**Rationale:** The slug derivation scheme (D1) and scanner-owned key whitelist (D2) are foundational contracts. Settling them first prevents renaming entity pages partway through the milestone. No entities can be written until D1 is locked.

**Delivers:** `wiki_io/entity_writer.py` slug encoder with property test; 7 `entity-*.md` template files; `frozenset` whitelist constant in `entity_writer.py`; `init_vault.py` updated with `entities` in `FIXED_VAULT_DIRS`.

**Addresses:** F3 (URI keying), F1 (lane initialization), F2 (templates)

**Avoids:** Pitfall 1 (slug collision), Pitfall 2 (frontmatter key collision) — both must be resolved at design time, tested here, before any downstream phase builds on them.

**Research flag:** None — URI scheme is an internal design decision; no external API research needed.

### Phase B: Entity Writer — Deterministic Page Create/Merge/Delete

**Rationale:** `entity_writer.py` is the core of the restructure. All downstream phases (index generator, scanner integration) depend on it being correct and tested in isolation.

**Delivers:** `wiki_io/entity_writer.py` — `write_entities(conn, wiki, admitted_kinds)` with create/merge/hard-delete. Returns `needs_narrative_set` for LLM gate. Merge preserves all human-authored keys. Workspace-scoped lock file (`scan.lock`) added.

**Addresses:** F4 (relation frontmatter), F6 (hard-delete reconciliation)

**Avoids:** Pitfall 2 (frontmatter key collision — merge test required as acceptance criterion), Pitfall 3 (hard-delete losing human edits — deletion policy must be explicit; log every deletion), Pitfall 9 (concurrent scan race — lock file added here).

**Research flag:** None — all graph queries exist in `graph_io.queries`; patterns established in v1.7.

### Phase C: Scanner-Generated Index

**Rationale:** `index_generator.py` depends on entity pages existing (from Phase B) to generate correct wikilink targets. It can be built and tested against a fixture graph once Phase B's API is settled.

**Delivers:** `wiki_io/index_generator.py` — domain-first + by-kind index. Queries graph directly (not entity page frontmatter). Deterministic sort. Write-if-changed guard. Curated lane sections preserved.

**Addresses:** F5 (domain-first index), F8 (curated lanes preserved — correctness gate threaded through index generation)

**Avoids:** Pitfall 5 (index churn — determinism test + write-if-changed guard required as acceptance criteria).

**Research flag:** None — `list_domains`, `list_packages`, `describe_domain` all exist in `graph_io.queries`.

### Phase D: Scanner Integration — Wire Entity Writer into `run_scan`

**Rationale:** `scan.py` integration is the riskiest change because it modifies production code with existing tests. Phase D comes after B and C are independently tested so the integration surface is narrow.

**Delivers:** Modified `scan.py` Steps 9a/9b/11/12. Step 9a calls `entity_writer.write_entities`; Step 9b fans out LLM only for `needs_narrative_set` pages; Step 11 branches on entity vs. curated page for delete vs. stale-tag; Step 12 calls `index_generator.generate_index` for entity content. `scan_monorepo.py` `_load_existing_pages` and `compute_diff` extended to handle `wiki/entities/` by URI.

**Addresses:** F1 (`/entities/` lane fully wired into scan pipeline), F6 (hard-delete integrated into scan flow)

**Avoids:** Pitfall 2 (whitelist enforced by entity_writer, already tested).

**Research flag:** None — existing scanner stage map is fully documented in ARCHITECTURE.md.

### Phase E: Inbound-Link Migration + Cutover Commit

**Rationale:** The migration script runs once at vault cutover. It must be built and tested before the cutover commit is made. The cutover itself (remove old directories, regenerate index) is the final deliverable of the core restructure.

**Delivers:** `wiki_io/link_rewriter.py` — Markdown-aware wikilink rewriter with idempotency guard and migration manifest marker. Cutover commit: `write_entities` to `rewrite_links` to remove `wiki/packages/`, `wiki/apps/`, `wiki/domains/`, `wiki/dependencies/` to regenerate index.

**Addresses:** F7 (one-shot inbound-link migration), F8 (curated lanes preserved — migration must not touch curated page content)

**Avoids:** Pitfall 4 (migration regex over-matching — Markdown-aware tokenizer required; code-block exclusion test in acceptance criteria), Pitfall 10 (re-run artifacts — idempotency test required).

**Research flag:** None — stdlib `re` + `python-frontmatter` patterns are established.

### Phase F: `cg domain-clusters` (independent — can overlap with B-E or slip to v1.9)

**Rationale:** Fully independent of the wiki restructure. Lives entirely in `graph_io/`. Can proceed in parallel with Phases B-E or slip to v1.9 with zero rework cost. The split is clean: F9/F10 touch only `packages/graph-io/` and `commands/graph.py`.

**Delivers:** `graph_io/cluster.py` (~50 LOC BFS with hub-exclusion preprocessing); `graph_io/cli/q_domain_clusters.py` (`cg domain-clusters` command, `--fmt human|json`). Independently testable with no LLM.

**Addresses:** F9 (`cg domain-clusters`)

**Avoids:** Pitfall 6 (degenerate clusters — hub-node exclusion and degenerate-cluster warning output must be in initial implementation, not v1.9).

**Research flag:** None — algorithm (connected-components on adjacency dict) is deterministic and well-understood; hub-exclusion threshold is a tunable parameter (recommended default: packages imported by >50% of others).

### Phase G: `graph propose-domains` (depends on Phase F)

**Rationale:** Depends on Phase F (`cg domain-clusters`). Does not depend on wiki restructure phases A-E. Can slot in any time after Phase F.

**Delivers:** `graph_wiki_agent/commands/propose_domains.py` — `graph propose-domains` Typer subcommand. Validates every proposed package name against `graph_io.queries.list_packages`. Detects and strips cycle edges. Writes `domains.proposed.yaml` with `proposed_domains:` top-level key (not `domains:` — schema-level differentiation prevents accidental parsing as authoritative). `graph_io.packages.refresh` allowlist hardened to exclude `domains.proposed.yaml`.

**Addresses:** F10 (LLM-proposed domain groupings)

**Avoids:** Pitfall 7 (LLM hallucinating package names — grounding check before write), Pitfall 8 (`domains.proposed.yaml` auto-applied — allowlist in `graph_io.packages.refresh` added in same commit as the propose-domains command; isolation test required).

**Research flag:** None — prompt pattern and `_capture_run` integration point are established from v1.7 graph commands.

### Phase Ordering Rationale

- **F3 (URI scheme) before everything else** — it is the load-bearing contract. Settling it first prevents mid-milestone renaming cascades.
- **F1+F2 proceed with Phase A** — vault initialization and template files don't depend on the slug scheme being finalized beyond the kind taxonomy, but practically they're designed together.
- **F4 (entity writer) after F3 and F2** — the writer needs the slug function and the templates to be settled.
- **F5 (index) after F4** — index generator queries the graph directly but uses entity page slugs for wikilink targets; those slugs must be settled.
- **F6 (hard delete) is part of Phase B** — it's ~5 lines inside `entity_writer.write_entities`, not a separate phase.
- **F7 (migration) after F1** — the migration script rewrites links to `entities/<slug>.md`; the slug format must be settled before the rewriter is written.
- **F9+F10 are fully independent of F1-F8** — if F4 or F5 prove larger than estimated, F9+F10 slide to v1.9 with zero rework cost.

### Research Flags

All phases have standard patterns derived from direct codebase inspection; no external API research is needed. The "research flag" for v1.8 is not about unknown technologies — it is about two design decisions that must be locked before Phase A implementation begins:

- **D1 lock (Phase A):** The URI-to-filename slug encoding scheme. Recommended value is in FEATURES.md D1 (`__` separator). Must be recorded as an explicit decision in the phase plan, not discovered during implementation.
- **D2 lock (Phase A):** The scanner-owned frontmatter whitelist. ARCHITECTURE.md provides a per-kind breakdown; FEATURES.md provides an initial flat list. Phase A must reconcile these two and produce a single canonical frozenset. Must be recorded before any entity page is written.
- **Deletion policy lock (Phase B):** Hard-delete with append-log record vs. warn-and-stale for pages with human-edited bodies. The vault-is-disposable policy from PROJECT.md favors hard-delete-with-log; this must be stated explicitly in Phase B's plan.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All findings from direct codebase inspection of `pyproject.toml` files and existing modules. Zero new dependencies confirmed by examining all 7 feature areas against actual source. |
| Features | HIGH | Feature set derived from inspection of `scan_monorepo.py`, `update_index.py`, `layout_io.py`, `init_vault.py`, `queries.py`, and PROJECT.md. All 10 target features have identified implementation paths. |
| Architecture | HIGH | Q4 (scanner pipeline integration point) is fully resolved by reading the actual 14-step `run_scan()` source. The "replace Steps 9+10" conclusion is grounded in code, not inference. All integration interfaces confirmed to exist. |
| Pitfalls | HIGH | Pitfalls are grounded in: (a) specific existing code patterns that would fail, (b) prior-milestone retrospective lessons, (c) mathematical properties of the slug encoding. No pitfalls are speculative. |

**Overall confidence:** HIGH

### Gaps to Address

- **D1 (URI-to-filename mapping) — value confirmed, decision not yet recorded as a phase-plan spec:** FEATURES.md recommends `__` as the separator. This must be written into Phase A's plan as an explicit decision record before implementation, not discovered mid-phase.

- **D2 (Scanner-owned frontmatter whitelist) — two slightly different lists in FEATURES.md vs. ARCHITECTURE.md:** Phase A must reconcile them and produce a single canonical `frozenset` constant. ARCHITECTURE.md's per-kind breakdown is more complete and should be the base.

- **Deletion policy for pages with human-edited bodies (Pitfall 3):** Research identifies two acceptable policies; the decision is deferred to Phase B's plan. PROJECT.md's vault-is-disposable policy favors hard-delete-with-log but this must be confirmed explicitly.

- **Hub-exclusion threshold for `cg domain-clusters` (Pitfall 6):** Recommended default is packages-imported-by->50%-of-others, but the right value for `agent-research`'s specific graph is unknown until Phase F tests against the actual graph. Treat as a tunable parameter.

## Sources

### Primary (HIGH confidence — direct source inspection)

- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — 14-step `run_scan()` pipeline; Steps 9+10 as the replacement target; stale-tag behavior; graph conn lifetime
- `packages/wiki-io/src/wiki_io/scan_monorepo.py` — `_load_existing_pages`, `compute_diff`, `_wiki_relative_path_for`, `regenerate_dependencies_index`
- `packages/wiki-io/src/wiki_io/update_index.py` — `CATEGORY_DIRS`, `MAIN_INDEX_CATEGORIES`, `render_index`
- `packages/wiki-io/src/wiki_io/layout_io.py` — `ensure_subpage`, `ensure_domain_page`
- `packages/wiki-io/src/wiki_io/init_vault.py` — `FIXED_VAULT_DIRS`
- `packages/graph-io/src/graph_io/queries.py` — confirmed all query functions needed for F4 exist
- `packages/graph-io/src/graph_io/derived_edges.py` — confirmed `pkg_imports` adjacency dict already built
- `packages/graph-io/src/graph_io/uri.py` — confirmed `pkg_uri()`, `domain_uri()`, `repo_uri()` etc. exist
- `packages/graph-io/pyproject.toml` — confirmed `pyyaml>=6.0` already a dep
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` — confirmed `_capture_run` pattern
- `.planning/notes/wiki-entity-restructure-design.md` — entity boundary policy, two-lane layout, edges-as-frontmatter contract
- `.planning/PROJECT.md` v1.8 section — 10 target features, Q1-Q5 resolutions, disposable vault policy
- `.planning/research/ONTOLOGY-SPEC.md` — §8 URI identity, §9 scanner pipeline + domain inference strategies 3 & 4, §4 edge types for whitelist

### Secondary (context and lessons)

- `.planning/milestones/v1.7-research/SUMMARY.md` — established scanner integration patterns, conn lifetime, `build_graph_tools` precedent
- `.planning/RETROSPECTIVE.md` — v1.0-v1.7 lessons on port discipline, spec-first phases, architectural restraint

---
*Research completed: 2026-05-26*
*Ready for roadmap: yes*
