# Requirements: Milestone v1.10 — Wiki Index & Entity Page Enrichment

**Created:** 2026-05-28
**Milestone goal:** Make the generated wiki a genuinely readable, complete projection of the graph — a human-readable index with per-entity summaries and an app section, dependencies/test-suites nested under their packages, entity pages fleshed out from migrated template content, and the internal-package-as-dependency classification bug fixed — plus two debt fixes.

---

## v1.10 Requirements

### Index generation (`wiki-io/index_generator.py`)

- [ ] **IDX-01**: The generated `wiki/index.md` includes a distinct `app` section in the By-Kind ordering, so reclassified apps are listed separately from packages.
- [ ] **IDX-02**: Entity links in the By-Kind and Domain sections render human-readable as `[[wiki/entities/<stem>|<name>]]` — link text is the entity's name (e.g. `source-parser`), target is the entity file (`wiki/entities/pkg_source-parser.md`) — not the bare file stem.
- [ ] **IDX-03**: Each entity entry in the index shows a one-line summary inline (sourced from the entity page's `summary:` frontmatter), matching how `concepts` / `adrs` / `architecture` entries render today.
- [ ] **IDX-04**: Test-suites render nested under the package(s) they test, duplicated when a suite tests multiple packages; the standalone By-Kind "Test Suites" section is removed.
- [ ] **IDX-05**: Dependencies render nested under the package(s) that use them, duplicated across packages; the standalone By-Kind "Dependencies" section is removed.

### Dependency-vs-package classification (`graph-io`)

- [x] **CLASS-01**: The scanner no longer emits a `dependency` node for a name that is also a workspace `package`/`app` in the repo — e.g. no `dep_graph-io.md` is generated when `graph-io` is a workspace package.
- [x] **CLASS-02**: An internal package→package usage (one workspace package depending on another) is represented as a dedicated `depends_on_package` edge (src=consumer, dst=internal package) between the two package/app nodes, so the relationship still surfaces in the wiki and under IDX-05 nesting. *(Amended during Phase 55 discussion: a new distinct edge kind `depends_on_package` is used rather than reusing the Domain→Domain `depends_on` kind — chosen for query ergonomics; see `phases/55-dependency-classification-fix/55-CONTEXT.md` D-04/D-05.)*

### Entity pages & templates (`wiki-io` assets)

- [ ] **ENTITY-01**: Content sections from the legacy per-kind `overview.md` pages (under the old `package/`, `domain/`, `plugin/`, `app/` template directories — the subpages have already been consolidated into each `overview.md`) are migrated into the corresponding `entity-<type>.md` templates — except the package `testing.md`-derived content, which moves to the `entity-test-suite.md` template (not `entity-package`).
- [ ] **ENTITY-02**: Each `entity-<type>.md` template carries ontology-relevant sections for its kind; sections that need human/LLM content show a `TODO: <instructions>` placeholder rather than dead links or empty headings.
- [ ] **ENTITY-03**: The legacy directory-style template assets (`package/`, `domain/`, `plugin/`, `app/`) are removed once their content is migrated, and no dead links remain in generated entity pages.

### Scan-time population (scanner + `entity_writer`)

- [ ] **SCAN-01**: When the scan runs, entity-page template variables are substituted with real values (e.g. `# <Package Name>` → `# wiki-io`); no literal `<...>` placeholder text survives in generated entity pages.
- [ ] **SCAN-02**: The scanner writes a `summary:` frontmatter field on each entity page, derived from the graph node's description, consumed by IDX-03.

### Debt

- [x] **DEBT-01**: `tests/test_integration_gate.py::test_integration_test_files_use_canonical_gate` passes — the 7 flagged integration test files adopt the canonical `GRAPH_WIKI_RUN_INTEGRATION` skipif (or the `# integration-gate-allow` marker where genuinely appropriate).
- [x] **DEBT-02**: PROJECT.md "What This Is" and Constraints are corrected to reflect the actual stack — in-house `subagent-runtime` + `langchain-aws` + `langchain-core` and the `graph-wiki` naming — rather than the stale `deepagents` / `lattice-wiki` wording.

---

## Future Requirements (Deferred)

- **Dependency-family / dependency clustering** — group related external dependencies (e.g. the `langchain-*` family) modeled on domain clustering. Defer until a concrete render need surfaces (now that internal packages are deduped from deps, external-dep grouping is the next natural step).
- **Scanner pipeline 9-stage restructure** (ONTOLOGY-SPEC §9) — for cheap domain-overlay re-runs.
- **Open questions §11 of ONTOLOGY-SPEC** — tagging mechanism, cross-repo domain scope, role-flag confidence metadata.
- **Novel-pattern inference for app classification** — LLM step if manifest-signal rules under-classify in practice.

## Out of Scope (this milestone)

- **Per-phase security reviews + formal milestone audits (v1.6/v1.8/v1.9 backfill)** — process debt; separate decision, not v1.10 feature work.
- **Phase 50 verification backfill** — acknowledged debt from v1.9 close; not blocking v1.10.
- **Nyquist retro-validation** — long-standing process decision, orthogonal to this milestone.
- **SUMMARY.md `one_liner:` write-time enforcement** — GSD-tool debt, not graph-wiki-agent code; filed against the GSD SDK separately.
- **New entity kinds or graph-schema expansion** — v1.10 enriches the projection of existing kinds; the only new edge kind is `depends_on_package` (CLASS-02), and no new *node* kinds are added. (Edge kinds are free-text in the `edges.kind` column, so this needs no schema migration.)

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| IDX-01 | 57 | Pending |
| IDX-02 | 57 | Pending |
| IDX-03 | 57 | Pending |
| IDX-04 | 57 | Pending |
| IDX-05 | 57 | Pending |
| CLASS-01 | 55 | Complete |
| CLASS-02 | 55 | Complete |
| ENTITY-01 | 56 | Pending |
| ENTITY-02 | 56 | Pending |
| ENTITY-03 | 56 | Pending |
| SCAN-01 | 56 | Pending |
| SCAN-02 | 56 | Pending |
| DEBT-01 | 54 | Complete |
| DEBT-02 | 54 | Complete |
