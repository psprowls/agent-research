# Roadmap: agent-research / graph-wiki-agent

**Project:** agent-research (v1 = graph-wiki-agent)
**Created:** 2026-05-13
**Current milestone:** v1.10 — Wiki Index & Entity Page Enrichment (in progress, Phase 54+)

---

## Milestones

- ✅ **v1.0 — graph-wiki-agent parity** — Phases 1-5 (shipped 2026-05-15) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 — Quality Improvements** — Phases 6-10 (shipped 2026-05-17) — [archive](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 — Graph-Wiki Port & Debt Cleanup** — Phases 11-16 (shipped 2026-05-19) — [archive](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 — Tooling Cleanup** — Phases 17-21 (shipped 2026-05-20) — [archive](milestones/v1.3-ROADMAP.md) · [audit](milestones/v1.3-MILESTONE-AUDIT.md)
- ✅ **v1.4 — Workspace Path Resolution Cleanup** — Phases 22-26 (shipped 2026-05-25) — [archive](milestones/v1.4-ROADMAP.md) · [audit](milestones/v1.4-MILESTONE-AUDIT.md)
- ✅ **v1.5 — Repo Rename & Foundational Package Additions** — Phase 27 (shipped 2026-05-25, retroactive) — [archive](milestones/v1.5-ROADMAP.md)
- ✅ **v1.6 — Code Graph Ontology Expansion** — Phases 28-34 (shipped 2026-05-26) — [archive](milestones/v1.6-ROADMAP.md)
- ✅ **v1.7 — graph-io Integration & Wiki Hygiene** — Phases 35-41 (shipped 2026-05-26) — [archive](milestones/v1.7-ROADMAP.md) · [audit](milestones/v1.7-MILESTONE-AUDIT.md)
- ✅ **v1.8 — Wiki Entity Restructure** — Phases 42-48 (shipped 2026-05-27) — [archive](milestones/v1.8-ROADMAP.md)
- ✅ **v1.9 — Graph Refinements & Wiki Filename Slimdown** — Phases 49-53 (shipped 2026-05-28) — [archive](milestones/v1.9-ROADMAP.md)
- 🔄 **v1.10 — Wiki Index & Entity Page Enrichment** — Phases 54-57 (in progress)

---

## Phases

<details>
<summary>✅ v1.0 graph-wiki-agent parity (Phases 1-5) — SHIPPED 2026-05-15</summary>

- [x] Phase 1: Infrastructure, Vault IO, and MCP Skeleton (5/5 plans) — completed 2026-05-13
- [x] Phase 2: Subagent Fan-Out Runtime (4/4 plans) — completed 2026-05-13
- [x] Phase 3: Query Vertical Slice + Hybrid Search (6/6 plans) — completed 2026-05-14
- [x] Phase 4: Eval Harness (4/4 plans) — completed 2026-05-14
- [x] Phase 5: Remaining Commands (6/6 plans) — completed 2026-05-14

Full detail: [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Quality Improvements (Phases 6-10) — SHIPPED 2026-05-17</summary>

- [x] Phase 6: Prompt Content Port + Divergence Eval (16/16 plans) — completed 2026-05-17
- [x] Phase 7: Cost-Frontier Sweep (7/7 plans) — completed 2026-05-17
- [x] Phase 8: Host Reliability (3/3 plans) — completed 2026-05-17
- [x] Phase 9: Trace/Observability Polish (6/6 plans) — completed 2026-05-17
- [x] Phase 10: Subagent Context Completion (7/7 plans) — completed 2026-05-17

Full detail: [`milestones/v1.1-ROADMAP.md`](milestones/v1.1-ROADMAP.md)
Audit: [`milestones/v1.1-MILESTONE-AUDIT.md`](milestones/v1.1-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.2 Graph-Wiki Port & Debt Cleanup (Phases 11-16) — SHIPPED 2026-05-19</summary>

- [x] Phase 11: workspace-io Port (M1) (6/6 plans) — completed 2026-05-18
- [x] Phase 12: Drift Backport + Ecosystem Rebrand (M2) (4/4 plans) — completed 2026-05-18
- [x] Phase 13: Plugin Spec (M3a) (5/5 plans) — completed 2026-05-18
- [x] Phase 14: Plugin Port (M3b) (3/3 plans) — completed 2026-05-19
- [x] Phase 15: Wiki Self-Update (1/1 plan) — completed 2026-05-19
- [x] Phase 16: Carry-Forward Debt Cleanup (2/2 plans) — completed 2026-05-19

Full detail: [`milestones/v1.2-ROADMAP.md`](milestones/v1.2-ROADMAP.md)

</details>

<details>
<summary>✅ v1.3 Tooling Cleanup (Phases 17-21) — SHIPPED 2026-05-20</summary>

- [x] Phase 17: wiki-io Bug Fixes (5/5 plans) — completed 2026-05-20
- [x] Phase 18: Plugin Command Rename (6/6 plans) — completed 2026-05-20
- [x] Phase 20: Workspace Manifest Model Config (4/4 plans) — completed 2026-05-20
- [x] Phase 21: Rename graph-wiki-agent → graph-wiki-agent (5/5 plans) — completed 2026-05-20
- [x] Phase 19: Phase 16 Code Review Burndown (5/5 plans) — completed 2026-05-20

Full detail: [`milestones/v1.3-ROADMAP.md`](milestones/v1.3-ROADMAP.md)
Audit: [`milestones/v1.3-MILESTONE-AUDIT.md`](milestones/v1.3-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.4 Workspace Path Resolution Cleanup (Phases 22-26) — SHIPPED 2026-05-25</summary>

- [x] Phase 22: workspace-api-internal-rename (1/1 plan) — completed 2026-05-20
- [x] Phase 23: workspace-api-external-rename (1/1 plan) — completed 2026-05-20
- [x] Phase 24: eval-harness-workspace-rename (1/1 plan) — completed 2026-05-21
- [x] Phase 25: packages-dir-misclassification-fix (1/1 plan) — completed 2026-05-21
- [x] Phase 26: plugin-prompt-source-mirror-sync (4/4 plans) — completed 2026-05-23

Full detail: [`milestones/v1.4-ROADMAP.md`](milestones/v1.4-ROADMAP.md)
Audit: [`milestones/v1.4-MILESTONE-AUDIT.md`](milestones/v1.4-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.5 Repo Rename & Foundational Package Additions (Phase 27) — SHIPPED 2026-05-25 (retroactive)</summary>

- [x] Phase 27: post-v1.4-foundation-changes (0 plans — retroactive; SUMMARY.md is the canonical artifact) — completed 2026-05-25

Full detail: [`milestones/v1.5-ROADMAP.md`](milestones/v1.5-ROADMAP.md)

</details>

<details>
<summary>✅ v1.6 Code Graph Ontology Expansion (Phases 28-34) — SHIPPED 2026-05-26</summary>

- [x] Phase 28: Schema v2 + URI Foundation (5/5 plans) — completed 2026-05-26
- [x] Phase 29: Structural Nodes + Containment Tree (4/4 plans) — completed 2026-05-26
- [x] Phase 30: Entry Points + Test Suites (4/4 plans) — completed 2026-05-26
- [x] Phase 31: Domain Layer + Derived Edges (4/4 plans) — completed 2026-05-26
- [x] Phase 32: Query Layer Extensions (3/3 plans) — completed 2026-05-26
- [x] Phase 33: CLI Surface (5/5 plans) — completed 2026-05-26
- [x] Phase 34: Brand Sweep (5/5 plans) — completed 2026-05-26

Full detail: [`milestones/v1.6-ROADMAP.md`](milestones/v1.6-ROADMAP.md)

</details>

<details>
<summary>✅ v1.7 graph-io Integration & Wiki Hygiene (Phases 35-41) — SHIPPED 2026-05-26</summary>

- [x] Phase 35: Wiki & Bootstrap Hygiene Burn-Down (2/2 plans) — completed 2026-05-26
- [x] Phase 36: `cg find` Parser Ergonomics (1/1 plan) — completed 2026-05-26
- [x] Phase 37: Librarian Grounding Tools (2/2 plans) — completed 2026-05-26
- [x] Phase 38: `graph-wiki-agent graph` Subcommand (2/2 plans) — completed 2026-05-26
- [x] Phase 39: Scanner Consumes graph-io (1/1 plan) — completed 2026-05-26
- [x] Phase 40: Ingestor Consumes graph-io (1/1 plan) — completed 2026-05-26
- [x] Phase 41: Address v1.7 tech debt — integration_gate + traceability (1/1 plan) — completed 2026-05-26

Full detail: [`milestones/v1.7-ROADMAP.md`](milestones/v1.7-ROADMAP.md)
Audit: [`milestones/v1.7-MILESTONE-AUDIT.md`](milestones/v1.7-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.8 Wiki Entity Restructure (Phases 42-48) — SHIPPED 2026-05-27</summary>

- [x] Phase 42: URI Slug Scheme + Per-Kind Templates (3/3 plans) — completed 2026-05-27
- [x] Phase 43: Entity Writer (3/3 plans) — completed 2026-05-27
- [x] Phase 44: Scanner-Generated Index (2/2 plans) — completed 2026-05-27
- [x] Phase 45: Scanner Integration (3/3 plans) — completed 2026-05-27
- [x] Phase 46: Inbound-Link Migration + Cutover (3/3 plans) — completed 2026-05-27 · UAT 8/8 passed
- [x] Phase 47: `cg domain-clusters` (3/3 plans) — completed 2026-05-27
- [x] Phase 48: `graph propose-domains` (3/3 plans) — completed 2026-05-27

Full detail: [`milestones/v1.8-ROADMAP.md`](milestones/v1.8-ROADMAP.md)

</details>

<details>
<summary>✅ v1.9 Graph Refinements & Wiki Filename Slimdown (Phases 49-53) — SHIPPED 2026-05-28</summary>

- [x] Phase 49: Builtin Kind (graph-io) (3/3 plans) — completed 2026-05-28
- [x] Phase 50: App Reclassification (graph-io) (3/3 plans) — completed 2026-05-28
- [x] Phase 51: package-family Removal + Divergence Rule Cleanup (4/4 plans) — completed 2026-05-28
- [x] Phase 52: Wiki Filename Slimdown — Core (3/3 plans) — completed 2026-05-28
- [x] Phase 53: Wiki Filename Cutover (2/2 plans) — completed 2026-05-28

Full detail: [`milestones/v1.9-ROADMAP.md`](milestones/v1.9-ROADMAP.md)

</details>

### v1.10 Wiki Index & Entity Page Enrichment (Phases 54-57) — IN PROGRESS

- [x] **Phase 54: Debt Clearance** — Fix the integration-gate test failure and correct PROJECT.md stack references (completed 2026-05-28)
- [x] **Phase 55: Dependency Classification Fix** — Stop emitting `dependency` nodes for workspace packages; add package→package `depends_on` edges (completed 2026-05-28)
- [ ] **Phase 56: Entity Templates & Scan-Time Population** — Migrate legacy template content into `entity-<type>.md` templates; add scan-time variable substitution and `summary:` frontmatter field
- [ ] **Phase 57: Index Generation Polish** — Add `app` section, human-readable links with summaries, and nested test-suite/dependency rendering to `index.md`

---

## Phase Details

### Phase 54: Debt Clearance
**Goal**: The test suite is clean and the project documentation accurately describes the current stack
**Depends on**: Nothing (independent cleanup)
**Requirements**: DEBT-01, DEBT-02
**Success Criteria** (what must be TRUE):
  1. `pytest tests/test_integration_gate.py` passes with no failures — every integration test file uses the canonical `GRAPH_WIKI_RUN_INTEGRATION` skipif guard
  2. PROJECT.md "What This Is" and Constraints sections reference `subagent-runtime`, `langchain-aws`, `langchain-core`, and `graph-wiki` naming — no `deepagents` or `lattice-wiki` references remain in those sections
**Plans**: TBD

### Phase 55: Dependency Classification Fix
**Goal**: Workspace packages are never double-classified as both a `package`/`app` node and a `dependency` node in the same repo
**Depends on**: Phase 54
**Requirements**: CLASS-01, CLASS-02
**Success Criteria** (what must be TRUE):
  1. After a full `cg update`, no `dep_graph-io.md` (or equivalent) entity page exists for any name that is also a workspace package — the dependency node is suppressed entirely
  2. An internal package→package import relationship appears as a `depends_on` edge between the two package/app nodes in the graph database
  3. The `depends_on` edge between internal packages surfaces correctly in graph queries (e.g. `cg describe-package <name>` shows internal dependents)
**Plans**: TBD

### Phase 56: Entity Templates & Scan-Time Population
**Goal**: Generated entity pages contain real content from migrated templates with all placeholder variables substituted, each page carries a `summary:` field, and legacy template directories are gone
**Depends on**: Phase 55
**Requirements**: ENTITY-01, ENTITY-02, ENTITY-03, SCAN-01, SCAN-02
**Success Criteria** (what must be TRUE):
  1. Running `graph-wiki-agent scan` produces entity pages where heading placeholders like `# <Package Name>` are replaced with real values (e.g. `# wiki-io`) — no literal `<...>` text survives in any generated page
  2. Every generated entity page has a populated `summary:` frontmatter field derived from the graph node's description
  3. Each `entity-<type>.md` template contains ontology-relevant sections for its kind; sections requiring human or LLM authorship show `TODO: <instructions>` rather than empty headings or dead links
  4. The legacy `package/`, `domain/`, `plugin/`, and `app/` template directories no longer exist in the repository; no dead links remain in any generated entity pages
**Plans**: 56-01 (SCAN-01 substitution + SCAN-02 summary, wiki-io), 56-02 (ENTITY-01/02 template migration, wiki-io assets), 56-03 (ENTITY-03 legacy deletion), 56-04 (SCAN-02 D-06 description population, graph-io)
**UI hint**: yes

### Phase 57: Index Generation Polish
**Goal**: The generated `wiki/index.md` is a genuinely readable projection of the graph — apps listed separately, entity links are human-readable with inline summaries, and test-suites and dependencies nest under their packages
**Depends on**: Phase 55 (for correct dependency/`depends_on` data), Phase 56 (for `summary:` frontmatter field)
**Requirements**: IDX-01, IDX-02, IDX-03, IDX-04, IDX-05
**Success Criteria** (what must be TRUE):
  1. The generated index contains a distinct `app` section in the By-Kind ordering, separate from the `packages` section
  2. Entity links in the By-Kind and Domain sections render as `[[wiki/entities/<stem>|<name>]]` — the display text is the human-readable entity name, not the raw file stem
  3. Each entity entry in the index shows a one-line summary inline, sourced from the entity page's `summary:` frontmatter field
  4. Test-suite entries appear nested under the package(s) they test (duplicated across multiple packages where appropriate); no standalone flat By-Kind "Test Suites" section exists
  5. Dependency entries appear nested under the package(s) that use them (duplicated across packages where appropriate); no standalone flat By-Kind "Dependencies" section exists
**Plans**: TBD
**UI hint**: yes

---

## Progress

| Phase             | Milestone | Plans Complete | Status   | Completed  |
| ----------------- | --------- | -------------- | -------- | ---------- |
| 1. Infrastructure, Vault IO, MCP Skeleton | v1.0 | 5/5 | Complete | 2026-05-13 |
| 2. Subagent Fan-Out Runtime | v1.0 | 4/4 | Complete | 2026-05-13 |
| 3. Query Vertical Slice + Hybrid Search | v1.0 | 6/6 | Complete | 2026-05-14 |
| 4. Eval Harness | v1.0 | 4/4 | Complete | 2026-05-14 |
| 5. Remaining Commands | v1.0 | 6/6 | Complete | 2026-05-14 |
| 6. Prompt Content Port + Divergence Eval | v1.1 | 16/16 | Complete | 2026-05-17 |
| 7. Cost-Frontier Sweep | v1.1 | 7/7 | Complete | 2026-05-17 |
| 8. Host Reliability | v1.1 | 3/3 | Complete | 2026-05-17 |
| 9. Trace/Observability Polish | v1.1 | 6/6 | Complete | 2026-05-17 |
| 10. Subagent Context Completion | v1.1 | 7/7 | Complete | 2026-05-17 |
| 11. workspace-io Port (M1) | v1.2 | 6/6 | Complete | 2026-05-18 |
| 12. Drift Backport + Ecosystem Rebrand (M2) | v1.2 | 4/4 | Complete | 2026-05-18 |
| 13. Plugin Spec (M3a) | v1.2 | 5/5 | Complete | 2026-05-18 |
| 14. Plugin Port (M3b) | v1.2 | 3/3 | Complete | 2026-05-19 |
| 15. Wiki Self-Update | v1.2 | 1/1 | Complete | 2026-05-19 |
| 16. Carry-Forward Debt Cleanup | v1.2 | 2/2 | Complete | 2026-05-19 |
| 17. wiki-io Bug Fixes | v1.3 | 5/5 | Complete | 2026-05-20 |
| 18. Plugin Command Rename | v1.3 | 6/6 | Complete | 2026-05-20 |
| 19. Phase 16 Code Review Burndown | v1.3 | 5/5 | Complete | 2026-05-20 |
| 20. Workspace Manifest Model Config | v1.3 | 4/4 | Complete | 2026-05-20 |
| 21. Rename graph-wiki-agent | v1.3 | 5/5 | Complete | 2026-05-20 |
| 22. workspace-api-internal-rename | v1.4 | 1/1 | Complete | 2026-05-20 |
| 23. workspace-api-external-rename | v1.4 | 1/1 | Complete | 2026-05-20 |
| 24. eval-harness-workspace-rename | v1.4 | 1/1 | Complete | 2026-05-21 |
| 25. packages-dir-misclassification-fix | v1.4 | 1/1 | Complete | 2026-05-21 |
| 26. plugin-prompt-source-mirror-sync | v1.4 | 4/4 | Complete | 2026-05-23 |
| 27. post-v1.4-foundation-changes | v1.5 | 0/0 | Complete | 2026-05-25 |
| 28. Schema v2 + URI Foundation | v1.6 | 5/5 | Complete | 2026-05-26 |
| 29. Structural Nodes + Containment Tree | v1.6 | 4/4 | Complete | 2026-05-26 |
| 30. Entry Points + Test Suites | v1.6 | 4/4 | Complete | 2026-05-26 |
| 31. Domain Layer + Derived Edges | v1.6 | 4/4 | Complete | 2026-05-26 |
| 32. Query Layer Extensions | v1.6 | 3/3 | Complete | 2026-05-26 |
| 33. CLI Surface | v1.6 | 5/5 | Complete | 2026-05-26 |
| 34. Brand Sweep | v1.6 | 5/5 | Complete | 2026-05-26 |
| 35. Wiki & Bootstrap Hygiene Burn-Down | v1.7 | 2/2 | Complete | 2026-05-26 |
| 36. `cg find` Parser Ergonomics | v1.7 | 1/1 | Complete | 2026-05-26 |
| 37. Librarian Grounding Tools | v1.7 | 2/2 | Complete | 2026-05-26 |
| 38. `graph-wiki-agent graph` Subcommand | v1.7 | 2/2 | Complete | 2026-05-26 |
| 39. Scanner Consumes graph-io | v1.7 | 1/1 | Complete | 2026-05-26 |
| 40. Ingestor Consumes graph-io | v1.7 | 1/1 | Complete | 2026-05-26 |
| 41. Address v1.7 tech debt — integration_gate + traceability | v1.7 | 1/1 | Complete | 2026-05-26 |
| 42. URI Slug Scheme + Per-Kind Templates | v1.8 | 3/3 | Complete | 2026-05-27 |
| 43. Entity Writer | v1.8 | 3/3 | Complete | 2026-05-27 |
| 44. Scanner-Generated Index | v1.8 | 2/2 | Complete | 2026-05-27 |
| 45. Scanner Integration | v1.8 | 3/3 | Complete | 2026-05-27 |
| 46. Inbound-Link Migration + Cutover | v1.8 | 3/3 | Complete | 2026-05-27 |
| 47. `cg domain-clusters` | v1.8 | 3/3 | Complete | 2026-05-27 |
| 48. `graph propose-domains` | v1.8 | 3/3 | Complete | 2026-05-27 |
| 49. Builtin Kind (graph-io) | v1.9 | 3/3 | Complete   | 2026-05-28 |
| 50. App Reclassification (graph-io) | v1.9 | 3/3 | Complete   | 2026-05-28 |
| 51. package-family Removal + Divergence Rule Cleanup | v1.9 | 4/4 | Complete    | 2026-05-28 |
| 52. Wiki Filename Slimdown — Core | v1.9 | 3/3 | Complete    | 2026-05-28 |
| 53. Wiki Filename Cutover | v1.9 | 2/2 | Complete   | 2026-05-28 |
| 54. Debt Clearance | v1.10 | 1/1 | Complete   | 2026-05-28 |
| 55. Dependency Classification Fix | v1.10 | 2/2 | Complete    | 2026-05-28 |
| 56. Entity Templates & Scan-Time Population | v1.10 | 0/TBD | Not started | - |
| 57. Index Generation Polish | v1.10 | 0/TBD | Not started | - |

---

*Last updated: 2026-05-28 — v1.10 (Wiki Index & Entity Page Enrichment) roadmap created. Phases 54-57, 14 requirements.*
