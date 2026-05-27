# Requirements: agent-research — Milestone v1.8 (Wiki Entity Restructure)

**Status:** 🚧 ACTIVE — defined 2026-05-26
**Core Value:** Faithfully reproduce the graph-wiki plugin's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Milestone Goal:** Collapse the wiki's parallel page-type-per-directory layout into a unified entity model driven by the graph (`/entities/` lane, URI-keyed pages, scanner-populated relation frontmatter, domain-first scanner-generated index), with hard-delete reconciliation and a one-shot inbound-link migration at cutover. Add the LLM/import-graph domain inference layer (`cg domain-clusters` + `graph-wiki-agent graph propose-domains` emitting `domains.proposed.yaml`) needed to make the new domain-first index work — so v1.8 closes with the wiki as the curated, human-readable projection of `graph-io` rather than a parallel structural model.

**Research:** `.planning/research/SUMMARY.md` (consolidates STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md)

---

## v1.8 Requirements

### URI — URI Slug Scheme & Per-Kind Templates (design lock)

- [x] **URI-01** — Slug encoder function in `wiki_io/entity_writer.py` derives entity filename from graph URI deterministically; `:` and `/` both encoded as `__`; property test over ≥1,000 synthetic URIs from all 7 admitted kinds asserts injective mapping (zero collisions)
- [x] **URI-02** — Slug encoder round-trip stable: `decode_slug(encode_slug(uri)) == uri` for every URI in property test corpus
- [x] **URI-03** — Per-kind templates added under `packages/wiki-io/src/wiki_io/assets/page-templates/`: `entity-repository.md`, `entity-domain.md`, `entity-package.md`, `entity-package-family.md`, `entity-plugin.md`, `entity-dependency.md`, `entity-test-suite.md` (7 files); each template declares `kind:` frontmatter and reserves prose region with a `## Narrative` H2 section for LLM narrative
- [x] **URI-04** — `init_vault.py` adds `entities` to `FIXED_VAULT_DIRS`; freshly-bootstrapped vault contains `wiki/entities/` directory with a `_index.md` placeholder
- [x] **URI-05** — Admitted-kinds taxonomy (`repository`, `domain`, `package`, `package-family`, `plugin`, `dependency`, `test-suite`) declared as a single `frozenset` constant in `entity_writer.py`; sub-packages and in-file nodes (`class`, `function`, `method`) explicitly excluded; new graph kinds require code change to admit
- [x] **URI-06** — Scanner-owned frontmatter key whitelist declared as a single canonical `frozenset` constant in `entity_writer.py`, reconciled from ARCHITECTURE.md per-kind breakdown + FEATURES.md initial list; human-authored keys (`status`, `last_reviewed`, `owner`, `notes`) explicitly excluded from whitelist

### ENTITY — Entity Writer (create / merge / delete)

- [ ] **ENTITY-01** — `wiki_io/entity_writer.py::write_entities(conn, wiki_root, admitted_kinds)` queries graph for all admitted nodes; creates new entity pages from per-kind templates with URI-derived slug; populates whitelisted relation frontmatter from graph edges
- [ ] **ENTITY-02** — Merge semantics preserve human-authored frontmatter keys verbatim; scanner only writes whitelisted keys; merge test: write a page with `status: deprecated`, run `write_entities`, assert `status: deprecated` is preserved
- [ ] **ENTITY-03** — Hard-delete reconciliation: when graph node no longer present but entity page exists, delete the page; append-log every deletion to `.graph-wiki/deletions.log` (path, URI, timestamp) for forensic recovery
- [ ] **ENTITY-04** — `write_entities` returns `EntityWriteResult(created, updated, deleted, needs_narrative)` where `needs_narrative` is the set of URIs requiring LLM prose generation (new pages + structurally-changed pages)
- [ ] **ENTITY-05** — Workspace-scoped lock file (`.graph-wiki/scan.lock`) prevents concurrent `write_entities` calls; acquires on entry, releases on exit (including exception paths)

### INDEX — Domain-First + By-Kind Scanner-Generated Index

- [ ] **INDEX-01** — `wiki_io/index_generator.py::generate_index(conn, wiki_root)` produces the wiki index page from graph queries directly (not by parsing entity page frontmatter); domain-first hierarchy at top, global by-kind sections below
- [ ] **INDEX-02** — Each domain section lists its contained packages, test-suites, and dependencies nested under it; entities appear twice in the index (once under domain, once in global by-kind list)
- [ ] **INDEX-03** — Cross-cutting packages (zero `belongs_to_domain` edges) appear in the global by-kind sections only; deterministic sort order: domain name alphabetical, then URI alphabetical within section
- [ ] **INDEX-04** — Write-if-changed guard: `generate_index` does not write the file if generated content is byte-identical to existing content; determinism test asserts byte-identical output across two runs from the same graph with different node-insertion orders
- [ ] **INDEX-05** — Curated lane sections (`/concepts/`, `/adrs/`, `/architecture/`, `/work/`, `/sources/`) preserved by index regeneration; correctness test: existing curated index sections present and unchanged after `generate_index` runs

### SCANINT — Scanner Integration (wire into `run_scan`)

- [ ] **SCANINT-01** — `commands/scan.py::run_scan` Step 9a calls `entity_writer.write_entities`; Step 9b fans out the LLM scanner ONLY for URIs in `needs_narrative_set` (not for every entity page on every scan)
- [ ] **SCANINT-02** — LLM scanner role narrowed to prose-only on entity pages; the LLM does not generate frontmatter for entity pages (frontmatter is scanner-owned via `entity_writer`)
- [ ] **SCANINT-03** — Step 11 deletion branch updated: entity pages are hard-deleted; curated-lane pages retain stale-tag behavior unchanged
- [ ] **SCANINT-04** — Step 12 calls `index_generator.generate_index` for the entity portion of the index; curated-lane index sections continue to flow through existing `update_index.py` path
- [ ] **SCANINT-05** — `scan_monorepo.py::_load_existing_pages` and `compute_diff` extended to handle `wiki/entities/` by URI rather than by directory walk; entity pages key off URI slug, not filesystem path
- [ ] **SCANINT-06** — Existing plugin (`plugins/graph-wiki/`) smoke test still passes against the modified scanner; regression guard included as success criterion of the scanner-integration phase

### MIGRATION — One-Shot Inbound-Link Migration + Cutover

- [ ] **MIGRATION-01** — `wiki_io/link_rewriter.py` provides a Markdown-aware wikilink rewriter; tokenizes documents into prose regions and code regions (fenced code blocks + inline code spans + indented code blocks); rewrites occur ONLY in prose regions
- [ ] **MIGRATION-02** — Rewriter maps old layout wikilinks (e.g. `[[packages/graph-io/index]]`, `[[dependencies/click/overview]]`) to new entity slugs (e.g. `[[entities/pkg__agent-research__graph-io]]`); rewrite table derived from graph queries, not hardcoded
- [ ] **MIGRATION-03** — Idempotency: running the migration twice on the same vault is a no-op; idempotency marker written to wiki manifest (`migrated_to: v1.8-entity-restructure` flag); test asserts second invocation makes zero file changes
- [ ] **MIGRATION-04** — Code-block exclusion test: a curated page containing a wikilink inside a fenced code block remains byte-identical after migration
- [ ] **MIGRATION-05** — Cutover commit consolidates: `write_entities` populates `wiki/entities/`, `rewrite_links` rewrites `/concepts/`, `/adrs/`, `/architecture/` wikilinks, old directories (`wiki/packages/`, `wiki/dependencies/`, `wiki/domain/`, `wiki/plugin/`, `wiki/package-family/`) are removed via `git rm -r`, and `generate_index` produces the new index — all in a single atomic commit

### CLUSTER — `cg domain-clusters` (Import-Graph Clustering)

- [ ] **CLUSTER-01** — `graph_io/cluster.py::compute_clusters(conn, hub_threshold=0.5)` produces deterministic connected-component clusters from the import adjacency dict in `derived_edges.py`; hub-node exclusion preprocessing removes packages imported by more than `hub_threshold` proportion of others before clustering
- [ ] **CLUSTER-02** — Degenerate-cluster warning: when output is a single cluster containing >80% of packages, or N singletons with N == package count, emit a warning to stderr explaining the likely cause (too few packages, sparse imports, or aggressive hub exclusion) and suggesting threshold adjustment
- [ ] **CLUSTER-03** — `graph_io/cli/q_domain_clusters.py` registers a new `cg domain-clusters` subcommand with `--fmt human|json` and `--hub-threshold FLOAT` flags; runs without an LLM dependency; renders via `_format.render(records, fmt="human")`
- [ ] **CLUSTER-04** — `cg --help` and `cg domain-clusters --help` exit 0; new command appears in the global help listing; integration test exercises the command against the `agent-research` graph itself
- [ ] **CLUSTER-05** — Algorithm is stable: running `cg domain-clusters` twice against the same graph snapshot produces byte-identical JSON output (no nondeterministic dict ordering or set iteration)

### PROPOSE — `graph-wiki-agent graph propose-domains` (LLM Domain Inference)

- [ ] **PROPOSE-01** — `graph_wiki_agent/commands/propose_domains.py` registers `graph propose-domains` Typer subcommand under existing `graph` subcommand group; runs `cg domain-clusters` internally and supplies clusters + per-package describe context as LLM input
- [ ] **PROPOSE-02** — Grounding check: every package name in the LLM-proposed `belongs_to_domain` edges validated against `graph_io.queries.list_packages` before write; unknown packages stripped with a logged warning, never silently included
- [ ] **PROPOSE-03** — Cycle detection: proposed `domain_contains_domain` edges checked for cycles; any cycle-introducing edge stripped with a logged warning before write
- [ ] **PROPOSE-04** — Output schema: file is `domains.proposed.yaml` (NOT `domains.yaml`); top-level key is `proposed_domains:` (NOT `domains:`) — schema-level differentiation prevents accidental parsing by `graph_io.packages.refresh` as authoritative
- [ ] **PROPOSE-05** — Isolation guard: `graph_io.packages.refresh` allowlist explicitly excludes `domains.proposed.yaml`; isolation test runs `graph propose-domains`, then `cg update`, asserts proposed-domain edges did NOT enter the graph
- [ ] **PROPOSE-06** — Cost-tracked trace: per-LLM-call cost record written to `.graph-wiki/traces/` matching the v1.7 trace schema; `--model` flag supported via the `model-adapter` role-tier mechanism

---

## Future Requirements (Deferred to v1.9+)

- Sub-package entity pages (deliberately excluded in v1.8 boundary; revisit if a query need emerges)
- Scanner 9-stage pipeline restructure (ONTOLOGY-SPEC §9) — still deferred; this milestone only narrows the LLM scanner role at one integration point
- Tagging mechanism (ONTOLOGY-SPEC §11 Q2) — orthogonal to the entity restructure
- Cross-repo `Domain` aggregation (ONTOLOGY-SPEC §11 Q3) — out of v1.8 scope
- Role-flag confidence metadata (ONTOLOGY-SPEC §11 Q7)
- Plugin (`plugins/graph-wiki/`) wiring to graph-io — plugin remains on Claude Code inference; touch-zero in v1.8

## Out of Scope (Explicit Exclusions)

- **Compatibility-shim redirect pages at old paths** — vault is disposable per user direction; one-shot migration covers it (Q3 = one-shot pass)
- **Tombstone or archive-folder reconciliation** — Q2 = hard-delete; deletion is logged for forensic recovery but pages do not survive
- **Human-authored index shell with scanner-injection blocks** — Q5 = fully scanner-generated; index is a regenerable artifact, no prose preservation
- **Auto-applying `domains.proposed.yaml`** — explicit anti-feature; destroys the human-review checkpoint
- **Per-package directories surviving the cutover** — the old `wiki/packages/<name>/{index,context,...}.md` layout retires at cutover commit; entity model is the only graph-derived layout
- **Format-compatibility with the upstream `lattice-wiki` vault format** — relaxed for this milestone; existing exploratory vaults are disposable
- **`networkx` / `igraph` / `scipy`** — overkill for the scale (≤200 nodes); in-house BFS connected-components is the chosen approach

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| URI-01 | Phase 42 | Complete |
| URI-02 | Phase 42 | Complete |
| URI-03 | Phase 42 | Complete |
| URI-04 | Phase 42 | Complete |
| URI-05 | Phase 42 | Complete |
| URI-06 | Phase 42 | Complete |
| ENTITY-01 | Phase 43 | Pending |
| ENTITY-02 | Phase 43 | Pending |
| ENTITY-03 | Phase 43 | Pending |
| ENTITY-04 | Phase 43 | Pending |
| ENTITY-05 | Phase 43 | Pending |
| INDEX-01 | Phase 44 | Pending |
| INDEX-02 | Phase 44 | Pending |
| INDEX-03 | Phase 44 | Pending |
| INDEX-04 | Phase 44 | Pending |
| INDEX-05 | Phase 44 | Pending |
| SCANINT-01 | Phase 45 | Pending |
| SCANINT-02 | Phase 45 | Pending |
| SCANINT-03 | Phase 45 | Pending |
| SCANINT-04 | Phase 45 | Pending |
| SCANINT-05 | Phase 45 | Pending |
| SCANINT-06 | Phase 45 | Pending |
| MIGRATION-01 | Phase 46 | Pending |
| MIGRATION-02 | Phase 46 | Pending |
| MIGRATION-03 | Phase 46 | Pending |
| MIGRATION-04 | Phase 46 | Pending |
| MIGRATION-05 | Phase 46 | Pending |
| CLUSTER-01 | Phase 47 | Pending |
| CLUSTER-02 | Phase 47 | Pending |
| CLUSTER-03 | Phase 47 | Pending |
| CLUSTER-04 | Phase 47 | Pending |
| CLUSTER-05 | Phase 47 | Pending |
| PROPOSE-01 | Phase 48 | Pending |
| PROPOSE-02 | Phase 48 | Pending |
| PROPOSE-03 | Phase 48 | Pending |
| PROPOSE-04 | Phase 48 | Pending |
| PROPOSE-05 | Phase 48 | Pending |
| PROPOSE-06 | Phase 48 | Pending |
