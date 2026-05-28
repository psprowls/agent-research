# agent-research

## What This Is

A Python monorepo (managed with `uv`) of LangChain/deepagents-based AI tooling. The first package, **`graph-wiki-agent`**, is a reimplementation of the upstream `lattice-wiki` Claude Code plugin (being ported in this repo as `graph-wiki`) — packaged as both an MCP server (consumed by the DeepAgents CLI) and a headless CLI that runs the full agent loop. It exists primarily so Pat can run the same wiki workflows on AWS Bedrock with within-command subagent fan-out for cost and context savings.

## Core Value

**Faithfully reproduce the upstream lattice-wiki plugin's wiki-maintenance workflows (now ported as `graph-wiki`) while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.**

If everything else fails, a Bedrock-driven `graph-wiki-agent query "..."` (or the equivalent MCP tool call) must return answers as good as today's upstream lattice-wiki librarian, on cheaper models, faster.

## Current Milestone: v1.10 Wiki Index & Entity Page Enrichment

**Goal:** Make the generated wiki a genuinely readable, complete projection of the graph — a human-readable index with per-entity summaries, entity pages fleshed out with real content, and the dependency / test-suite / app classification gaps closed — plus two debt fixes.

**Target features:**

1. **Index generation polish** (`wiki-io/index_generator.py`):
   - Add an `app` section to the By-Kind ordering.
   - Human-readable entity links (`[[wiki/entities/pkg_source-parser|source-parser]]`) plus a 1-line summary per entity, matching the concepts/adrs/architecture style.
   - Test-suites rendered nested under the package(s) they test (duplicated across multiple); flat By-Kind Test Suites section dropped.
   - Dependencies rendered nested under the package(s) that use them (duplicated); flat By-Kind Dependencies section dropped.
2. **Dependency-vs-package classification fix** (`graph-io/packages.py`): a workspace package no longer emits a `dependency` node (`dep_graph-io` gone); the internal usage becomes a package→package `depends_on` edge.
3. **Entity page content + template cleanup** (`wiki-io` assets + scanner): migrate the content sections from the old `overview.md`/subpages into the `entity-<type>.md` templates (except `package/testing.md`, now covered by `entity-test-suite`); flesh out each entity type with ontology-relevant sections using `TODO: <instructions>` placeholders; fix dead links; then remove the dead `domain/` / `package/` / `plugin/` / `app/` template dirs.
4. **Scan-time template-variable population**: substitute entity-page placeholders (e.g. `# <Package Name>` → `# wiki-io`) when the scan runs, including a per-entity `summary:` frontmatter field (from the graph node description) that feeds feature 1's index summaries.
5. **Debt**: fix the `test_integration_gate.py` failure (7 integration files onto the canonical `GRAPH_WIKI_RUN_INTEGRATION` skipif or allowlist); fix PROJECT.md drift ("What This Is"/Constraints still reference `deepagents` + `lattice-wiki`).

**Key context:**

- **Bug-fix / enhancement milestone.** Phase numbering continues from Phase 53 → v1.10 starts at Phase 54.
- **All work is internal** — `wiki-io` (index_generator, entity_writer, page templates), `graph-io` (packages.py dependency filtering + `depends_on` edge), and the agent scanner. No new external dependencies expected.
- **Decisions locked at scoping:** per-entity summaries come from a scanner-written `summary:` frontmatter field (index reads it uniformly, like curated lanes); deps/test-suites nest under packages only (flat By-Kind lists for those two kinds dropped); internal package-as-dependency becomes a `depends_on` package→package edge.
- **Deferred (not in v1.10):** per-phase security reviews (v1.8/v1.9), formal milestone audits (v1.6/v1.8/v1.9), Nyquist retro-validation, Phase 50 verification backfill, dependency-family clustering, scanner 9-stage restructure.

## Previous Milestone: v1.9 Graph Refinements & Wiki Filename Slimdown (SHIPPED 2026-05-28)

**Goal (achieved):** Tighten the graph-build pipeline (built-in handling, app classification) and slim the wiki projection (shorter human-readable filenames, drop dormant `package-family`) — so the graph admits noisy stdlib calls cleanly without leaking them into the wiki, packages that are really apps get classified as such, and entity pages get human-readable filenames instead of fully-qualified URI slugs. Shipped as 5 phases (49–53), 15 plans, 24/24 requirements; merged to `main` via PR #1.

**Target features:**

1. **Built-in / stdlib `builtin` kind** — new graph node kind admitted for Python stdlib (`builtins`, `pathlib`, etc.) and JS/TS/Node stdlib (`fs`, `path`, `crypto`, etc.); npm packages stay `dependency`; excluded from wiki rendering.
2. **`package` → `app` reclassification** — best-effort inference from manifest signals (Python `pyproject.toml [project.scripts]`, JS `package.json bin`, `next` / `expo` deps, vite+`index.html`); fallback to `package` when ambiguous.
3. **Shorter, human-readable entity filenames** — `pkg__org__repo__name.md` → `pkg_<name>.md`; short repo/org hash suffix on collision; test-suite special case `unit_tests_<pkg>.md` / `int_tests_<pkg>.md`.
4. **Drop `package-family` entirely** — remove kind, URI builder, template, the v1.8 `ADMITTED_KINDS` narrow, and `wiki/package-family/`. Keep `domain_contains_domain` (unrelated).
5. **Delete LIB-003 divergence rule** — `_SLUG_ONLY_RE` and `_check_no_slug_only_wikilinks` obsolete now that `pkg_<name>.md` makes slug-only wikilinks canonical.

**Key context:**

- **Phase numbering continues from 48 → v1.9 starts at Phase 49.**
- **Format compatibility still relaxed** — exploratory `~/Personal/graph-wiki/agent-research` vault is disposable; wipe-and-rebuild via scanner + inbound-link migration.
- **Lattice-wiki is dead** — no upstream parity constraint; divergence rules prunable as scaffolding outlives its purpose.

## Current State: v1.9 Shipped — 2026-05-28

**Shipped:** v1.0 (graph-wiki-agent parity, 2026-05-15) + v1.1 (Quality Improvements, 2026-05-17) + v1.2 (Graph-Wiki Port & Debt Cleanup, 2026-05-19) + v1.3 (Tooling Cleanup, 2026-05-20) + v1.4 (Workspace Path Resolution Cleanup, 2026-05-25) + v1.5 (Repo Rename & Foundational Package Additions, 2026-05-25 retroactive) + v1.6 (Code Graph Ontology Expansion, 2026-05-26) + v1.7 (graph-io Integration & Wiki Hygiene, 2026-05-26) + v1.8 (Wiki Entity Restructure, 2026-05-27) + v1.9 (Graph Refinements & Wiki Filename Slimdown, 2026-05-28). **53 phases, 185 plans** across ten milestones.

**New in v1.9 — graph refinements + short wiki filenames:**
- **`builtin` graph kind** — Python/Node stdlib imports classified as first-class `Builtin` nodes (`builtin:<lang>/<module>`), kept out of the dependency/symbol pool and excluded from wiki rendering; `cg list-builtins` / `cg describe-builtin` surfaces.
- **`package` → `app` reclassification** — manifest signals (`[project.scripts]`, `package.json bin`, `next`/`expo` deps, vite+`index.html`) reclassify packages to a distinct `App` kind with `app_kind`; URI form preserved so inbound references survive; `cg list-apps` / `cg describe-app`.
- **Short entity filenames** — `pkg__org__repo__name.md` → `<kind>_<name>.md` via the pure `short_filename(uri, collision_set, ...)` helper, with deterministic hash suffix only on collision and `unit_tests_<pkg>.md` / `int_tests_<pkg>.md` for suites. Dead `encode_slug` / `decode_slug` / `_ADMITTED_URI_PREFIXES` removed; all consumers read `frontmatter.uri` or call `short_filename`.
- **`package-family` ripped out** — kind, URI builder, template, the v1.8 `ADMITTED_KINDS` narrow, and the LIB-003 `_SLUG_ONLY_RE` divergence rule all deleted.

**Process notes from v1.9 (carried as debt):**
- **Phase 50 never formally verified** — executed with 3 plan summaries and APP-01..06 marked Complete, but no `VERIFICATION.md` (the only v1.9 phase missing one). Accepted at close.
- **No formal milestone audit** — `/gsd:audit-milestone` skipped again; per-phase verification (4/5 phases) + Phase 53 UAT + Phase 53 security audit carried the close.

**Prior state — v1.8 Shipped 2026-05-27:** **48 phases, 170 plans** across nine milestones. v1.8 closed without a formal milestone audit (operator-acknowledged) — UAT 8/8 passed for the Phase 46 cutover; 38/38 requirements satisfied across URI / ENTITY / INDEX / SCANINT / MIGRATION / CLUSTER / PROPOSE lanes.

**New in v1.8 — wiki collapsed into URI-keyed entity model:**
- **URI-keyed `/entities/` lane** — flat folder, one file per admitted graph node (`repository`, `domain`, `package`, `package-family`, `plugin`, `dependency`, `test-suite`), URI-derived filename (slug uses `__` for both `:` and `/`), per-kind page templates with `## Narrative` H2 reserving the LLM prose region. `package-family` admitted in the codebase but dormant in v1.8 (deferred to v1.9). `ADMITTED_KINDS` + `SCANNER_OWNED_KEYS` frozensets; human-authored frontmatter keys explicitly excluded from whitelist and preserved on merge.
- **`write_entities()` — deterministic create / merge / hard-delete** — single public entry in `wiki_io.entity_writer`. Acquires `.graph-wiki/scan.lock` (non-blocking flock); byte-stable write-if-changed; partial-failure isolation; returns `EntityWriteResult(created, updated, deleted, needs_narrative)` where `needs_narrative` gates LLM fan-out. Hard-deletions append-logged to `.graph-wiki/deletions.log` (JSONL, 10MB two-file rotation) with `body_was_empty` flag.
- **`generate_index()` — domain-first scanner-generated index** — `wiki/index.md` produced from graph queries directly. Domain hierarchy at top with single-placement (entities appear under their qualifying domain iff exactly one, else in by-kind). Global by-kind sections + consolidated curated-lane sections (architecture, ADRs, concepts, sources, work). Deterministic sort, write-if-changed via `os.replace`. 49 tests including permuted-insertion determinism.
- **`run_scan` integration (Steps 9a/9b/10/11/12)** — entity writer called pre-LLM (Step 9a); LLM narrator fans out only over `needs_narrative` URIs (Step 9b); `inject_narrative` writes prose into the `## Narrative` region only (Step 10); hard-deletions on Step 11; index regenerated on Step 12. 8 integration tests verifying call graph, gating, and frontmatter integrity. Existing plugin smoke test unchanged.
- **One-shot inbound-link migration + atomic cutover** — `graph-wiki-agent migrate-vault` (CLI under the agent) builds a graph-derived rewrite table, walks curated lanes with a CommonMark-aware tokenizer (code-block / inline-code excluded), and produces a single git commit on the vault repo: populates `wiki/entities/` (47 pages), rewrites 122 wikilinks, removes legacy `wiki/packages/` + `wiki/dependencies/`, regenerates `wiki/index.md`, writes `.graph-wiki/manifest.json#migrated_to`. `--dry-run` previews; second run is no-op via the manifest marker.
- **Domain inference layer** — `cg domain-clusters` produces deterministic connected-component clusters from the import-graph with hub-node exclusion (>50% reverse-dep packages elided then re-attached as cross-cutting), degenerate-cluster warnings (>80% single cluster OR all singletons), `--fmt human|json`. `graph-wiki-agent graph propose-domains` consumes clusters, fans out to a Bedrock LLM via the new `domain-proposer` role, validates every proposed package name against `graph_io.queries.list_packages`, strips cycle-introducing `domain_contains_domain` edges, writes `domains.proposed.yaml` (never `domains.yaml` — proposals never auto-apply). Per-call cost records in `.graph-wiki/traces/` per v1.7 trace schema.

**Process notes from v1.8:**
- **Operator-acknowledged: no formal milestone audit** — `/gsd:audit-milestone` was skipped for v1.8 close. Per-phase verification + Phase 46 cutover UAT carried the burden. Add to deferred process candidates.
- **Operator-acknowledged: no per-phase security review** — `workflow.security_enforcement=true` but no `*-SECURITY.md` files for Phases 42-48. Mostly internal package work touching no external attack surface; flagged at close.

**Accepted into v1.9:**
- `package-family` re-admit + entity rendering (`ADMITTED_KINDS - {"package_family"}` was the v1.8 narrow); `wiki/package-family/` cutover deferred (no entity replacements exist yet).
- Carry-forward: Nyquist retro-validation decision (0/35+ phases produced VALIDATION.md); v1.6 + v1.8 missing milestone audits acknowledged.

**New in v1.7 — graph-io is now the agent's identity layer:**
- **`cg find` named-flag UX** — `--name`/`--kind`/`--in-package` replace positional; anti-regression guard prevents silent re-introduction of the old form.
- **Librarian Grounding Tools** — 5 closure-bound `@tool` callables wrap `graph_io.queries`; one read-only conn opened at command entry, shared across tools, closed in `finally`; CountTokens pre-flight budget gate; graceful vault-thin fallback when graph is missing.
- **`graph-wiki-agent graph` subcommand** — first-class `build`/`describe`/`query` in agent CLI + 3 parallel MCP tools (`graph_build`/`graph_describe`/`graph_query`).
- **Scanner ↔ graph-io** — `run_scan` dispatches `cg update` before fan-out; workspaces decorated with graph `uri` + `domain`; vault slug recomputed on domain change; strict NOT_INITIALIZED error with filesystem fallback.
- **Ingestor ↔ graph-io** — entity URIs come from graph before LLM routing; missing graph hard-fails with exit code 3 (no silent drift).
- **Wiki & Bootstrap Hygiene** — 10 deferred quick-tasks + 2 bootstrap todos closed (self-healing `uv` re-exec, `--interactive` flag, testing.md subpage scaffold, file-map table format, plugin shim docs).
- **Tech debt closeout** — canonical `INTEGRATION_GATE` restored on scan-e2e test; 20 REQUIREMENTS.md checkboxes + 20 traceability rows synced; v1.6-era `sample_monorepo` fixture allowlisted.

**Accepted into v1.8:**
- Exit-code-3 collision between LIBTOOLS-05 (BUDGET_EXCEEDED) and INGESTOR-02 (NOT_INITIALIZED) — documented intentional per Phase 37 D-04.
- URI-drift / orphaned-page reconciliation (INGESTOR-03) — already v1.8 design item.
- Formal VERIFICATION.md coverage for code-only phases — v1.8 process candidate.

**New in v1.6 — `graph-io` ontology landed:**
- **Schema v2 + URI identity** — `nodes.uri TEXT` column; `graph_io.uri` exposes `repo_uri`, `pkg_uri`, `subpkg_uri`, `file_uri`, `domain_uri`, `entry_point_uri`, `test_suite_uri`. `cg update --full` v1→v2 rebuild; `SCHEMA_MISMATCH` (exit 4) on incremental v1→v2.
- **Structural containment tree** — `Repository`, `SubPackage` (Python-only), `File` with 7 role flags (`is_importable`, `is_executable`, `has_main`, `is_test`, `is_config`, `is_generated`, `is_type_only`). `physically_contains` strict tree; `resolve.sweep` guard.
- **EntryPoints + TestSuites** — manifests (pyproject.scripts, package.json bin/main/exports) produce `EntryPoint` nodes with polymorphic `implemented_by`. `TestSuite` nodes from FS layout + framework configs (pytest/jest/vitest/mocha); test files re-parented out of Package containment.
- **Domains + derived edges** — `domains.yaml` at repo root drives `Domain` nodes; `belongs_to_domain`, `domain_contains_domain` with cycle detection; derived `references` (Domain → Package with usage count) and `depends_on` (Domain → Domain) computed post-update.
- **14 new `cg` CLI subcommands** — `describe-repo`, `list-packages`, `list-entry-points`, `list-scripts`, `list-suites`, `describe-suite`, `what-tests`, `list-domains`, `describe-domain`, `domain-refs`, `domain-deps`, `cross-cutting`, plus `cg status` extended with repository line. `cg --help` lists 25 subcommands total.
- **Brand sweep in `graph-io`** — `lattice-graph-core` → `graph-io` README, `~/.lattice/graph/code.db` → `paths.graph_dir(workspace)`, CLI description rebranded, `LATTICE_GRAPH_LOCK_TIMEOUT_MS` straight-renamed to `GRAPH_WIKI_LOCK_TIMEOUT_MS` with **no alias** (revised mid-milestone — single-user repo, no backwards compat). Dead `_SKIP_REPO_PREFIXES` deleted. Brand grep gate passes.

**What works today (post-v1.3):**
- `graph-wiki-agent {init|scan|ingest|query|lint|log|trace}` — full graph-wiki workflow on Bedrock with within-command subagent fan-out
- All MCP tools exposed via `graph-wiki-mcp` stdio server; verified end-to-end via DA-CLI integration test
- Agent prompts incorporate canonical SKILL.md content; divergence eval flags remaining drift
- Cost-frontier validated: per-workspace `<workspace>/.graph-wiki.yaml` `plugins[].roles[]` block carries the role-model map; packaged `models.toml` is the per-role fallback
- Trace renderer with per-(role,model) cost rollup, `usage_metadata` populated across all 4 production fan-out callsites
- Subagent context completion: `wiki/CLAUDE.md` layout + style + log format injected into scanner/linter/ingestor system prompts
- `packages/workspace-io/` owns workspace bootstrap + manifest IO + config resolution under the `graph-wiki` brand; `wiki-io._workspace` delegates to it; `.graph-wiki.yaml` is the per-workspace manifest filename; `GRAPH_WIKI_WORKSPACE` is the env override
- `plugins/graph-wiki/` is the ported Claude Code plugin (runs on Claude Code inference, NOT a wrapper around `graph-wiki-agent`); `/graph-wiki:*` namespace; `/graph-wiki:bootstrap` (renamed from `/graph-wiki:init` in v1.3 Phase 18 so Claude Code's native `/init` is reachable)
- **New in v1.3:** wiki-io scan no longer reports 28 phantom companion-page deletions; CountTokens API uses correct `input=...` boto3 shape; workspace/repo resolution works at the v2 `<workspace>/wiki/` layout
- **New in v1.3:** Agent package mechanically renamed `code-wiki-agent → graph-wiki-agent` across the full repository (Phase 21 — `git mv` preserved history; brand-gate enforces no reintroduction)
- **New in v1.3:** Phase 16 review burndown complete — 15 findings dispositioned (13 fixed + 2 no-action); `19-REVIEW-BURNDOWN.md` is the canonical record

**Workspace rename history:** `cores/` → `packages/` (commit `c5a47ba`, v1.1). Brand rename `lattice` → `graph-wiki` swept in v1.2 Phase 12. Agent package rename `code-wiki-agent` → `graph-wiki-agent` swept in v1.3 Phase 21. Repo rename `deep-agents` → `agent-research` and package rename `vault-io` → `wiki-io` swept in v1.5 Phase 27.

## Previous Milestone: v1.8 Wiki Entity Restructure (SHIPPED 2026-05-27)

**Goal (achieved):** Collapse the wiki's parallel page-type-per-directory layout into a unified entity model driven by the graph, and add the LLM/import-graph domain inference layer needed to make the new domain-first index work — so the wiki becomes the curated human-readable projection of `graph-io` rather than a separate structural model.

**Target features:**

1. **`/entities/` lane** — flat folder, one file per graph-derived entity, `kind` discriminator in frontmatter. Admitted kinds: `repository`, `domain`, `package`, `package-family`, `plugin`, `dependency`, `test-suite`. Sub-packages and in-file nodes (class/function/method) excluded by policy; new graph kinds require explicit admit/deny.
2. **Per-kind templates** — replace directory templates with per-kind page templates (e.g. `entity-package.template`). Package-as-folder collapses into a single `entity-package` page.
3. **URI-keyed entity pages** — entity identity is the `graph-io` URI (Q1 = URI-as-key). Filename derives from URI; renames don't create ghost pages.
4. **Scanner-populated relation frontmatter** — graph edges surfaced as structured frontmatter on entity pages, populated by the scanner. Prose reserved for narrative. Whitelist of scanner-owned keys coexists with human-authored frontmatter on the same page.
5. **Domain-first + by-kind index** — fully scanner-generated (Q5). Domain sections expanded inline at top, then global by-kind sections (all packages, all plugins, all dependencies, all test-suites). Entities appear in both views.
6. **Hard-delete reconciliation** (Q2) — when a graph node disappears, its entity page is deleted on next scan. Exploratory vaults are disposable so dangling-link risk is accepted.
7. **One-shot inbound-link migration** (Q3) — single rewrite pass for existing `/concepts/`, `/adrs/`, `/architecture/` wikilinks at cutover.
8. **Curated lanes preserved** — `/concepts/`, `/adrs/`, `/architecture/`, `/work/`, `/sources/` keep current homes; not direct graph projections.
9. **Import-graph clustering** — new `cg domain-clusters` command produces deterministic cluster candidates from the import graph. Standalone CLI surface, independently testable.
10. **LLM-proposed domain groupings** — new `graph-wiki-agent graph propose-domains` subcommand consumes `cg domain-clusters` + graph context and emits `domains.proposed.yaml` for human review/merge into authored `domains.yaml`. Proposals never auto-apply.

**Key context:**

- **Supersedes aborted v1.8** (URI-Keyed Wiki & Reconciliation, aborted 2026-05-26 before research synthesis). URI-keying is folded into this restructure as Q1 rather than the headline.
- **Format-compatibility constraint relaxed** for this milestone — existing exploratory `~/Personal/graph-wiki/agent-research` vault is disposable per user direction (2026-05-26). Wipe-and-rebuild is acceptable; no in-place migration script required.
- **`domains.yaml` remains the authored source of truth.** LLM proposals land in `domains.proposed.yaml` for human review/merge — never auto-applied to the graph.
- **Q4 (scanner pipeline integration point)** deferred to research/planning — depends on existing scanner stage map; expect a scoping phase to lock the design before rewrites.
- **ONTOLOGY-SPEC §9 inference strategies** — explicit config + convention shipped in v1.6; this milestone delivers import-graph clustering + LLM-proposed groupings (strategies 3 & 4). Manual overrides remain "always win" via authored `domains.yaml`.
- **Phase numbering continues from Phase 41 → v1.8 starts at Phase 42.**
- **Design notes**: `.planning/notes/wiki-entity-restructure-design.md` and `.planning/research/questions.md` Q1–Q5 are the load-bearing pre-research inputs.

## Previous Milestone: v1.7 graph-io Integration & Wiki Hygiene (SHIPPED 2026-05-26)

**Goal:** Wire `graph-io` into `graph-wiki-agent` as the source of truth for librarian/scanner/ingestor, expose graph operations through a new `graph-wiki-agent graph` subcommand, fix `cg find` parser ergonomics, and burn down accumulated wiki/bootstrap/test-infra debt — so v1.7 closes with the agent actually using the ontology v1.6 built.

**Target features:**

1. **Librarian grounding tools** — expose graph-io queries to librarian as `@tool`-decorated callables (find_symbol, list_packages, what_tests, describe_domain, etc.) so it resolves identity via graph rather than guessing.
2. **Scanner consumes graph-io** — scanner uses graph-io as source of truth for what gets scanned and where pages land (URI-keyed, not path-keyed).
3. **Ingestor consumes graph-io** — ingestor pulls existence/identity from graph-io rather than reconstructing from filesystem.
4. **New `graph-wiki-agent graph` subcommand** — surfaces `build` / `describe` / `query` operations through the agent CLI (mirroring `cg` patterns but agent-aware / cost-tracked).
5. **`cg find` parser ergonomics** — `--kind file --name foo.py` (and similar shape) parses correctly.
6. **Wiki & bootstrap hygiene burn-down** — focused hygiene phase folding in the 10 deferred quick tasks + 2 bootstrap todos: scanner wikilink prefix (`hfr`), `{{CONTAINER_DIR}}` template var (`i26`), file-map format (`he3`), testing.md subpage (`i35`), overview page renames (`iws`), plugin-docs `uv run` shim (`kxi`), Typer ANSI strip (`ans`), workspace-io repo discovery + 3 other lint fixes (`gc0`), workspace-io sparse plugins (`lj3`), bootstrap self-healing uv re-exec (`mfm`), bootstrap interactive flag, bootstrap stub category index files.

**Key context:**

- **v1.6 built the ontology explicitly to enable this milestone** — no consumers wired yet; v1.7 is where graph-io stops being a parallel artifact and becomes the agent's identity layer.
- **Schema v2 + URI identity is the integration surface** — `find_symbol` returns a URI; `scanner` keys pages by URI; `graph` subcommand mirrors `cg` semantics. No new schema work expected.
- **Hygiene folded in, not parallel** — one dedicated phase early in v1.7 so the wiki backlog clears before integration touches the same files (scanner/templates/bootstrap overlap with `hfr`/`i26`/`he3`/`i35`/`iws`/`mfm`/bootstrap todos).
- **Plugin stays untouched** (`plugins/graph-wiki/` continues to run on Claude Code inference) — except for the `kxi` docs-only fix.
- **Wiki redesign deferred to v1.8.** The full URI-keyed wiki rendering (flat-by-ID / by-domain / by-repo views) is its own milestone; v1.7 only takes the integration prerequisites.
- Phase numbering continues from Phase 34 → v1.7 starts at Phase 35.

## Previous Milestone: v1.6 Code Graph Ontology Expansion (SHIPPED 2026-05-26)

**Goal (achieved):** Land the full ontology spec (`.planning/research/ONTOLOGY-SPEC.md`) inside `graph-io` — schema v2, URI identity, all new node + edge types, additive scanner extensions, brand sweep — so v1.7 can integrate graph-io into `graph-wiki-agent` and redesign the wiki on top of it. Plugin and existing wiki scripts stay functional and untouched.

**Target features:**

1. **Schema v2 + URI identity** — bump `SCHEMA_VERSION` to 2 (full rebuild required on upgrade). Add stable URI-style IDs (`repo:org/foo`, `pkg:org/foo/auth-service`, `domain:billing`, etc.) as the new identity layer; `path` becomes an attribute, not identity. Reserved error codes (`SCHEMA_MISMATCH`, `UPDATE_IN_PROGRESS`) wired up.
2. **Structural nodes + tree** — `Repository`, `SubPackage` (Python-only), `File` with role flags (`is_importable`, `is_executable`, `has_main`, `is_test`, `is_config`, `is_generated`, `is_type_only`). `physically_contains` edges forming a strict tree. Generic containers (`packages/`, `libs/`, `tests/`) explicitly NOT modeled.
3. **Entry points** — `EntryPoint` nodes from manifest declarations (`pyproject.toml [project.scripts]`, `package.json bin`/`main`/`exports`). `declares_entry_point` + `implemented_by` edges (polymorphic over `File`/`Function`/`Class`).
4. **Test suites** — `TestSuite` nodes from FS layout + framework config (pytest.ini, jest.config.js, etc.). Re-parent test files from package containment to suites. Derived `tests` edges at suite-level (strong) and file/function-level (best-effort, advisory). Flat — no suite nesting.
5. **Domains** — `Domain` first-class nodes. Curated `belongs_to_domain` edges from explicit `domains.yaml` config + convention-based inference (top-level named folders). `domain_contains_domain` for nested domains (tree). Multi-domain membership supported; zero-domain (cross-cutting) supported.
6. **Derived edges** — `references` (Domain → Package, with usage count) and `depends_on` (Domain → Domain) computed from import graph + domain membership. Re-runnable.
7. **Scanner extensions (additive)** — extend existing scanner to emit the new node/edge kinds inline. Do NOT restructure into the 9-stage pipeline yet (deferred to v1.7 when domain-overlay re-runs become a real requirement).
8. **`cg` CLI surface for new node/edge types** — describe/query commands for `Repository`, `Domain`, `EntryPoint`, `TestSuite`; reverse-direction queries (`what tests cover X`, `what entry points does pkg Y declare`, `what does domain D reference`).
9. **Lattice → graph-wiki brand sweep in `graph-io`** — `README.md` ("lattice-graph-core" → graph-wiki phrasing), `~/.lattice/graph/code.db` paths → canonical graph-wiki path, comments, exit-code docs. Aligns graph-io with the rest of the rebranded workspace.

**Key context:**

- **graph-io-only milestone.** `graph-wiki-agent` does NOT yet consume graph-io in v1.6 — agent integration is v1.7. Justification: landing the full ontology + URI migration is already a heavy surface; a focused milestone is cleaner.
- **Plugin untouched.** `plugins/graph-wiki/` and its scripts continue to function as today — they don't touch graph-io.
- **Source-of-truth spec:** `/Users/pat/Downloads/code-graph-ontology-spec_2.md` (Pat's brainstorm — should be copied into the repo as a planning artifact at scoping time).
- **Open questions §11 of spec** (tagging, cross-repo domains, role-flag confidence, etc.) left for v1.7 — except where v1.6 must answer to ship (e.g., `EntryPoint.implemented_by` polymorphic over `File`/`Function`/`Class` — decided yes).
- **Schema v2 forces full rebuild.** Existing `code.db` files become invalid on upgrade; users run `cg update --full`. Acceptable since the only consumers today are direct `cg` invocations.
- Phase numbering continues from Phase 27 → v1.6 starts at Phase 28.

## Deferred to v1.10+

**Done in v1.9 (shipped — see Validated):**
- **`package-family` removal** — ripped out entirely in Phase 51 (kind, URI builder, template, ADMITTED_KINDS narrow). A future milestone may re-introduce dependency-family clustering on top of domain mechanics.
- **`librarian.py` `_SLUG_ONLY_RE` parity fix** — LIB-003 deleted outright in Phase 51; the `pkg_<name>.md` scheme makes slug-only wikilinks canonical.

**Still deferred (process / tooling debt):**
- **Formal milestone audit (v1.6 + v1.8 + v1.9)** — all shipped without `/gsd:audit-milestone`; backfill or accept as process-only debt.
- **Phase 50 formal verification (v1.9)** — executed + requirements marked Complete, but no `VERIFICATION.md` was produced. Backfill `/gsd:verify-work 50` (or verify-phase) or accept as debt.
- **Per-phase security review for v1.8 phases 42-48 and v1.9 phases 49-52** — `workflow.security_enforcement=true` but only Phase 53 produced a `*-SECURITY.md`; others skipped (mostly internal package work, no external attack surface).
- **Pre-existing `test_integration_gate.py` failure now on `main`** — `test_integration_test_files_use_canonical_gate` fails (7 integration test files don't match the canonical `GRAPH_WIKI_RUN_INTEGRATION` skipif). Predates v1.9; rode along the merge. Quick cleanup candidate.
- **SUMMARY.md `one_liner:` write-time enforcement** — GSD-tool debt, not graph-wiki-agent code; MILESTONES.md is currently ingesting deviation-report bold headings as one-liners. File separately against the GSD SDK / executor.
- **Nyquist compliance retroactive decision** — 0/35+ phases produced VALIDATION.md despite the toggle being enabled. Decide: retro-validate vs. disable the toggle. **Overdue** since v1.6 close.

**Still deferred (graph / wiki):**
- **Scanner pipeline restructure** — split into the 9-stage pipeline per spec §9 (FS walk → manifest parse → test detect → AST → import resolve → test target derive → domain assign → derived edges → wiki render). Becomes a real requirement when domain-overlay re-runs need to be cheap.
- **Open questions §11 of ONTOLOGY-SPEC** — tagging mechanism, cross-repo domain scope, domain config location in multi-repo, role-flag confidence metadata, test suite consolidation threshold, test-support file flag.
- **Dependency-family / dependency clustering** — re-introduce a "package-family"-like mechanism for grouping related dependencies (e.g., `langchain-*`), modeled on domain clustering rather than the original `package_family` kind. Defer until there's a concrete render need.
- **Optional novel-pattern inference for app classification** — extension to v1.9 G2 if the manifest-signal rules under-classify in practice.
- **check-brand.sh regex over-breadth** — `workspace_io|lattice_wiki_core` in the regex causes legitimate matches across the repo; minimal allowlist papered over it. A regex trim would let `.brand-grep-allow` shrink dramatically.
- **Pre-existing test failure** — `tests/test_integration_gate.py` fails on `packages/graph-io/tests/fixtures/sample_monorepo/tests/integration/test_top.py`. Confirmed pre-v1.6 via `git stash` during Phase 34.
- **Phase 14 SC#4 plugin smoke transcript** — manual `/graph-wiki:query` transcript still not captured (carried since v1.2 close).

**Now in v1.7 (formerly Deferred to v1.7+):**
- Wire `graph-io` into `graph-wiki-agent` (target features 1-4)
- `cg find` parser ergonomics (target feature 5)
- 10 deferred quick tasks + 2 bootstrap todos rolled into a hygiene phase (target feature 6)

**Explicitly out of v1.x (deferred to v2.0+):**
- Open-source release prep (README badges, contribution guide, PyPI publish dry-run) → **v2.0 GA**.
- `work/` subsystem port — GSD covers work-item lifecycle (thread decision 2026-05-17).
- Package-family monorepo support restoration — different approach planned (thread decision 2026-05-17).
- Modules where wiki-io was ahead of upstream lattice — leave as-is per spike 002 / v1.2 Phase 12 verdicts.

Full v1.3 retrospective in `.planning/RETROSPECTIVE.md`; v1.3 archive in `.planning/milestones/v1.3-ROADMAP.md`; v1.3 audit in `.planning/milestones/v1.3-MILESTONE-AUDIT.md`.

## Requirements

### Validated

#### Milestone v1.9 SHIPPED — 2026-05-28 (Graph Refinements & Wiki Filename Slimdown)

24/24 requirements satisfied across Phases 49-53. Full detail: `.planning/milestones/v1.9-ROADMAP.md` and `.planning/milestones/v1.9-REQUIREMENTS.md`.

- ✓ **`builtin` graph kind** — v1.9 (BUILTIN-01..06): Python + Node stdlib imports admitted as `Builtin` nodes (`builtin:<lang>/<module>`, `language` + `module_name` attrs, `used_by` edges only), excluded from wiki rendering; `cg list-builtins` / `cg describe-builtin`. (Phase 49)
- ✓ **`package` → `app` reclassification** — v1.9 (APP-01..06): manifest-signal classifier promotes packages to a distinct `App` kind with `app_kind` (cli/nextjs/expo/spa), documented precedence on multi-match, no false positives, URI form preserved; `cg list-apps` / `cg describe-app`. (Phase 50 — *executed but not formally verified; accepted at close*)
- ✓ **`package-family` removed** — v1.9 (PKGFAM-01..05, CLEANUP-01): kind, `package_family_uri` builder, template, `ADMITTED_KINDS` narrow, and CLI surfaces deleted from graph-io + wiki-io; LIB-003 `_SLUG_ONLY_RE` divergence rule + baseline retired. (Phase 51)
- ✓ **Short entity filenames** — v1.9 (WIKI-FN-01..04): `short_filename(uri, collision_set, ...)` pure helper produces `<kind>_<name>.md` with deterministic collision-hash suffix and framework-aware `unit_tests_/int_tests_` suite names; property-tested for idempotence + collision-resistance. (Phase 52)
- ✓ **Filename cutover** — v1.9 (WIKI-FN-05/06): dead `encode_slug`/`decode_slug`/`_ADMITTED_URI_PREFIXES` removed; every consumer derives filenames via `short_filename` and reads URIs via `frontmatter.uri`; verified by from-scratch vault regen UAT + 13/13 threat-secure audit. (Phase 53)

#### Milestone v1.2 SHIPPED — 2026-05-19 (Graph-Wiki Port & Debt Cleanup)

30/30 requirements satisfied across Phases 11-16. Full detail: `.planning/milestones/v1.2-ROADMAP.md` and `.planning/milestones/v1.2-REQUIREMENTS.md`.

- ✓ **workspace-io package shipped** — v1.2 (WS-01..10): new `packages/workspace-io/` ported from upstream `lattice-workspace` with `.graph-wiki.yaml` manifest, `GRAPH_WIKI_WORKSPACE` env var, `GraphWikiConfig` dataclass; `wiki-io._workspace.resolve_wiki_and_repo` delegates to `workspace_io.config.resolve()`; 67 ported tests green; two-phase `graph-wiki-agent init` bootstrap.
- ✓ **Selective drift backport** — v1.2 (BACKPORT-01..04): body-diff inventory of 11 overlapping modules between `wiki-io` and upstream `lattice-wiki-core` at pinned SHA; zero PORT verdicts (every drift hunk intentional or out-of-v1.2 subsystem); decisions logged in `packages/wiki-io/DRIFT-DECISIONS.md`.
- ✓ **Ecosystem rebrand complete** — v1.2 (BRAND-01/02/04): `lattice` → `graph-wiki` (kebab) / `graph_wiki` (snake) swept across `packages/`, `agents/`, `plugins/`, `.planning/`, `CLAUDE.md` in 5 atomic commits; `scripts/check-brand.sh` + `.brand-grep-allow` grep-gate enforces ongoing discipline; `.planning/spikes/CONVENTIONS.md` corrected.
- ✓ **Plugin contract locked + ported** — v1.2 (PLUGIN-01..05): Phase 13 produced CONTRACT-INDEX.md + SHELL-OUT-PATTERN.md locking that the ported `plugins/graph-wiki/` plugin runs on **Claude Code inference** (not a wrapper around `graph-wiki-agent`); Phase 14 ported the plugin with renamed `plugin.json` id, `/graph-wiki:*` namespace, agent/skill renames, and shims wired through wiki-io. Phase 14 prerequisite: `wiki_io.lint_wiki` (~509 LOC) + `wiki_io.wiki_search` (~194 LOC) verbatim-ported from upstream (VP-01).
- ✓ **Wiki self-update** — v1.2 (BRAND-03): `~/Personal/graph-wiki/agent-research` re-scanned + OTel re-ingested + librarian query run against post-rebrand codebase via Claude role-override profile (Haiku 4.5 fan-out + Sonnet 4.6 reasoning); 3 operational deviations auto-fixed inline.
- ✓ **v1.1 carry-forward debt closed** — v1.2 (TRACE-FU-01, SWEEP-FU-02/03/04, MCP-CAN-01/02, MODEL-FU-01): `TaskResult` contract on `SubagentPool` threads `response.usage_metadata` into JSONL traces; all 4 fan-out callsites emit non-None tokens/cost; DivergenceMetric wired through all 6 in-scope roles with code_reader + synthesizer rubrics; scanner re-swept against fresh-package vault; MCP wire-level cancel re-deferred behind event-driven trigger (langchain-aws#663 OR aioboto3 GA); integration-gate convention codified + grep-enforced; synthesizer model_id assertion locked to Qwen reality.

#### Milestone v1.1 SHIPPED — 2026-05-17 (Quality Improvements)

29/29 requirements satisfied across Phases 6-10. Full audit: `.planning/milestones/v1.1-MILESTONE-AUDIT.md`.

- ✓ **Lattice-wiki SKILL.md content ported** — v1.1 (PORT-01..06): librarian/ingestor/linter/scanner prompts incorporate canonical iron rules, citation rules, ingestion patterns, lint rule definitions, and scanner package-detection rules via 8 shared fragments under `prompts/_fragments/` with `# Source: / # Anchor:` provenance comments
- ✓ **Divergence detection eval shipped** — v1.1 (EVAL-11..13): 15 programmatic check rules + 4 LLM-judge rubrics + 37 unit tests + regression gate (`--accept-divergence-baseline`); flagged 0 hard-severity divergences against lattice-wiki baseline
- ✓ **Cost-frontier sweep validated the cost story** — v1.1 (SWEEP-01..05): two-gate scoring across 6 in-scope roles (corrected from "7" in original roadmap — 2 judges out of scope); BED-01 live-gate confirmed; `models.toml` defaults updated with provenance comments; full results doc under `.planning/sweep/`
- ✓ **Trace schema versioned + cost-aware renderer** — v1.1 (OBS-04..06): `schema_version: 1` stamped on every JSONL record; renderer surfaces per-(role,model) cost rollup with `(+K unknown)` accounting; collapses repeated subagent groups by default with `--expand` flag

#### Phase 10 Complete — 2026-05-17 (subagent-context-completion)
- [x] Four shared fragments shipped under `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/` — `architecture_overview.py`, `style_rules.py`, `log_format.py`, `claude_md_disambiguation.py` — each with the standard `# Source: / # Anchor: / # Source-commit:` provenance header (CTX-01, CTX-02)
- [x] `prompts/project_context.py::render_project_context(wiki_path)` reads `wiki/CLAUDE.md` (or `AGENTS.md` fallback), parses the embedded layout block via existing `wiki_io.layout_io`, returns deterministic ~30-line block or `""` on missing schema files (CTX-03)
- [x] Four prompt builders converted to `build_X_system(project_context="")` functions (scanner, linter, ingestor, librarian) with backward-compat module-level `*_SYSTEM` constant aliases preserved; three commands (scan, lint, ingest) wire `render_project_context()` at SystemMessage construction (CTX-03)
- [x] Snapshot tests in `test_prompt_snapshots.py` cover with-context, without-context, and missing-CLAUDE.md degradation paths — 14 snapshots, 26 prompt tests total pass (CTX-04)
- [x] Token-budget regression in `test_token_budget.py` enforces +1500 tokens per role ceiling; ingestor tightest at +751/1500 headroom (CTX-05)
- [x] Phase 6 divergence eval re-run live against AWS Bedrock (`GRAPH_WIKI_RUN_EVAL=1`) — librarian/ingestor/linter/scanner all PASSED, no hard-severity regression (CTX-05)

#### Phase 08 Complete — 2026-05-17 (host-reliability)
- [x] MCP cancellation wired through `SubagentPool.run_all` — per-item `status: cancelled` trace records and single `event: batch_cancelled` terminal record on cancel; `_write_trace` / `_write_batch_terminal` never raise (MCP-09, MCP-10)
- [x] Deterministic in-process asyncio cancel test with stubbed LLM — zero Bedrock cost (MCP-11)
- [x] `WikiScanInput.repo_path` field added so the E2E test can scope `wiki_scan` to a `tmp_path` vault (DACLI-01)
- [x] Single sequential E2E integration test exercises all six MCP tools as a stdio subprocess against a fresh `tmp_path` vault; gated behind `GRAPH_WIKI_RUN_INTEGRATION=1` (DACLI-02, DACLI-03)
- [x] `docs/cancellation.md` — v1.1 reference for `notifications/cancelled` protocol, internal unwinding chain, trace shapes, orphan-thread limitation, v1.2+ paths

#### Milestone v1.0 SHIPPED — 2026-05-15 (graph-wiki-agent parity)
- [x] **Phase 04 (Eval Harness)** — `cores/eval-harness` package with fixture corpus (3 repos), headless `claude -p` baseline recorder (EVAL-08 schema), `deepeval` 4.0 integration with `AmazonBedrockModel`, heterogeneous two-judge panel (claude-sonnet-4-6 + nova-pro-v1:0), cost-frontier sweep runner (`pytest-evals`), regression-check AssertionError gate, structural metrics (cites code path / wikilinks resolve / valid frontmatter) (EVAL-01..10)
- [x] **Phase 05 (Remaining Commands)** — `init`, `scan`, `ingest`, `lint`, `log` shipped on both MCP and headless CLI surfaces with a single shared command implementation; `scan` and `lint` use SubagentPool fan-out (scanner across packages; linter across 3 rule-groups); `ingest` routes to package/concept/adr pages via a single ingestor LLM call; `--config` global Typer callback + `WikiConfig` dataclass (CMD-01..08, MCP-01..08, CLI-01..07)

#### Phase 03 Complete — 2026-05-14 (query-vertical-slice-hybrid-search)
- [x] Hybrid search: BM25 via `bm25s` + Titan v2 embeddings in SQLite (WAL), sha256 incremental rebuild, RRF fusion (SEARCH-01..06)
- [x] `commands/query.py` — shared `run_query()` pipeline: hybrid search → librarian fan-out (SubagentPool) → synthesizer → QueryResult (CMD-04, CLI-03)
- [x] `graph-wiki-agent query` CLI subcommand with `--top-k`, `--vault`, `--json`, `--no-state-gate` (CLI-01..07, CMD-07, CMD-08)
- [x] `wiki_query` MCP tool with Pydantic schemas, `ctx.report_progress()` notifications (MCP-02, MCP-04, MCP-06, MCP-07)
- [x] G1 citation resolver normalises `.md`-suffixed wikilinks correctly (regression caught in UAT)
- [x] 54 unit tests; 3 integration tests gated behind `GRAPH_WIKI_RUN_INTEGRATION=1`

#### Phase 02 Complete — 2026-05-14 (subagent-fan-out-runtime)
- [x] `SubagentPool.run_all()` with partial-failure isolation, semaphore throttle, per-role concurrency (SUB-01..07)
- [x] Structured JSONL trace output to `.graph-wiki/traces/` for every fan-out call (OBS-01)
- [x] `graph-wiki-agent trace` CLI subcommand renders traces as human-readable timeline (OBS-02, OBS-03)
- [x] Real-Bedrock integration tests: 4-parallel with 1 intentional failure → 3 successes, no sibling cancellation (BED-02..05)

#### Phase 01 Complete — 2026-05-13 (infrastructure-wiki-io-and-mcp-skeleton)
- [x] `uv` workspace at repo root with tiered layout: `cores/wiki-io`, `cores/model-adapter`, `agents/graph-wiki-agent`
- [x] Project license + README seeded (MIT, open-source-ready)
- [x] Bedrock model adapter — `make_llm("haiku")` invokes real `ChatBedrockConverse`; `BedrockAccessDenied` raised with ARN on bad credentials
- [x] Vault IO round-trip — reading-then-writing every page produces byte-identical output (29 tests pass)
- [x] MCP stdio surface — FastMCP `graph-wiki-mcp` server with `_StdoutGuard`; `wiki_ping` tool; provably stdout-clean
- [x] CI pipeline (ruff + pytest); ruff clean (`ruff check .` and `ruff format --check .` both exit 0)
- [x] **Read-compatible with existing vaults** — preserve frontmatter, layout block, wikilinks, file-map format

### Active

_v1.10 (Wiki Index & Entity Page Enrichment) scoped 2026-05-28 — requirements defined in `.planning/REQUIREMENTS.md`; phase structure in `.planning/ROADMAP.md` (continues from Phase 54)._

_See "Deferred to v1.10+" below for carried-forward items (process debt + graph/wiki backlog), and "Out of Scope" for items deferred past v1.x._

### Out of Scope

- **Custom TUI in v1** — DeepAgents CLI is the host; we ship MCP + headless CLI only. (Revisit if DeepAgents CLI proves inadequate.)
- **Non-Bedrock providers in v1** — no OpenRouter, no local Ollama, no direct Anthropic API. Bedrock is the only path for cost savings on Pat's setup. (Add later if eval shows clear gaps in Bedrock's lineup.)
- **Nested subagents** — only within-command fan-out in v1, no sub-subagents. (Optimization target for later if quality demands it.)
- **Vault format migration** — read-compatible means we don't rewrite the format. (No need; existing format works for Obsidian.)
- **Writing back to old lattice-wiki vaults during transition** — read yes, write no, until the new tool is validated. (Avoids dual-writer drift.)
- **Public PyPI release on day one** — build clean enough to open-source later, but no release pipeline yet. (Personal use first; release after eval validates the cost story.)
- **Real-time file watchers / auto-sync** — commands stay manually triggered, matching lattice-wiki today. (Out of scope unless a clear pain point emerges.)

## Context

**Prior work — the thing being reimplemented:**
- `/Users/pat/Personal/lattice/plugins/lattice-wiki` — Claude Code plugin, ~400 LOC of shims + slash commands
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core` — Python core, ~4,400 LOC across 24 modules + 37 pytest files. v0.4.0, polished, stable schema
- Implements: container detection, monorepo scan, layout YAML IO, vault init, index generation, BM25 search, source ingestion, graph analysis, token counting, lint (mechanical + semantic), git state gating
- Already has a backend selector (`.lattice-wiki.json`) for Claude-Code-SDK vs Bedrock — proves Bedrock is feasible
- Today's subagents (scanner, librarian, linter, ingestor) are per-command and **sequential** — no internal fan-out; this is the big v2 lift

**Pat's experience:**
- Built lattice-wiki himself; deep familiarity with the design, iron rules, frontmatter schema, layout block convention, state-gate mechanism
- Strong opinions on what to preserve (iron rules, layout block, state gate, category-first indexing) and what could be revisited (hand-rolled YAML, bespoke argv parsing, BM25-only search)
- Wants this rewrite to pay back in two ways: lower per-run cost, and a clean eval foundation for future agent work in the monorepo

**Why Bedrock specifically:**
- Cost: a non-trivial Bedrock model lineup is cheaper than direct Anthropic for some calls; mixing in non-Claude models (Llama, Mistral, Nova) opens further savings
- Auth/infra already in place for Pat
- Concentrating on one provider in v1 lets the eval harness move fast — comparing 6 Bedrock models is simpler than comparing 6 models across 3 providers

**Why MCP server + headless CLI (not a custom TUI):**
- DeepAgents CLI already provides a competent conversation loop; rebuilding it is wasted work
- Exposing tools via MCP keeps the surface clean and makes the same core usable from other MCP hosts later (Claude Code, Cursor, etc.)
- Headless CLI is the escape hatch — when no host is running (CI, scripts), the agent loop still works

## Constraints

- **Tech stack**: Python 3.11+, `uv` workspace, `langchain` + `langchain-aws` + `deepagents` — chosen to match Pat's stack and to leverage deepagents' subagent primitives without rebuilding them
- **Model provider**: AWS Bedrock only in v1 — single-provider focus simplifies adapter layer and eval harness
- **Protocol**: MCP for the primary delivery surface — interoperates with DeepAgents CLI and other MCP hosts
- **Format compatibility**: must read existing lattice-wiki vaults without modification — preserve frontmatter schema, layout block format, wikilink/citation conventions
- **Budget**: personal project; no team; design for one-developer velocity
- **Audience**: Pat (now); open-source-ready hygiene (license, README, no secrets) for later release

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + `uv` monorepo | Pat's preferred Python tooling; `uv` workspaces fit the tiered (cores + agents) layout cleanly | Validated Phase 01 |
| LangChain + `deepagents` framework | Native subagent primitives; LangChain has mature `langchain-aws` Bedrock binding; deepagents matches the planned conversation host | Validated Phase 02 |
| AWS Bedrock only in v1 | Cost focus; Pat already has auth/setup; single-provider eval is simpler | Validated Phase 01 |
| MCP server as primary surface | DeepAgents CLI hosts the conversation; we expose tools; reusable from other MCP hosts | Validated Phase 01+03 |
| Headless CLI in addition to MCP | Same core, two surfaces; CLI runs full agent loop in-process for CI/scripts | Validated Phase 03 |
| Full parity with lattice-wiki v1 (5 commands) | Pat knows the territory; halfway parity creates a confusing transition with the existing tool | ✓ Validated Phase 05 |
| Within-command subagent fan-out (not nested) | Real parallelism wins (librarian across pages, linter rule-groups, scanner across packages) without the debugging cost of nested subagents | Validated Phase 02+03 |
| Read-compatible with existing vaults | Allows side-by-side use during transition; preserves Obsidian compatibility; no migration script needed | Validated Phase 01 |
| Eval = cost-frontier per subagent role, baselined from current tool | Direct measurement of the project's reason for existing; recorded-from-Sonnet baseline avoids hand-curation overhead | ✓ Validated Phase 04 (harness shipped; sweep run is v1.1 work) |
| Tiered monorepo (shared cores + agent packages) | Anticipates future agents reusing model adapters, subagent runtime, eval harness | Validated Phase 01 |
| Package named `graph-wiki-agent` (not `lattice-wiki`) | Clearer description of what it does; avoids confusion with the existing TS plugin during the transition period | Validated Phase 01 |
| No custom TUI in v1 | DeepAgents CLI is sufficient; building a TUI is parallel work that doesn't help the cost-savings goal | Validated Phase 01 |
| Titan Embeddings v2 (`amazon.titan-embed-text-v2:0`, 1024 dims) for embedding search | No extra IAM grants beyond Phase 1 Bedrock access; native to langchain-aws BedrockEmbeddings | Validated Phase 03 |
| CLI-05 (`--config`) deferred; `--vault` used instead in Phase 03 | ROADMAP Phase 03 success criteria do not require `--config`; tracked for Phase 05 | ✓ Closed Phase 05-01 (`--config` global Typer callback + `WikiConfig`) |
| ONE `wiki_ingest` MCP tool with `type: Literal['source','work-item']` discriminator (not two tools) | Single discoverable tool simplifies the MCP surface; type-narrowing happens server-side; matches `lattice-wiki:ingest` semantics | Validated Phase 05 |
| Inline port of `lint_wiki.py:scan()` (mechanical pass) + 3-way SubagentPool fan-out for semantic pass | Mechanical rules are deterministic — porting verbatim avoids re-implementation bugs; LLM-driven semantic checks parallelize cleanly across rule groups | Validated Phase 05 |
| Prompt content lives in `prompts/` Python module per role with provenance comments (not separate markdown files) | Drift detection: provenance comments + snapshot tests + import-based sourcing make divergence visible in code review | ✓ Validated Phase 06 |
| Two-gate qualification (Gate 1 = divergence vs. baseline, Gate 2 = LLM-judge quality) for cost-frontier sweep | Cheap models that pass divergence checks but produce subjectively worse output need to be filtered — neither gate alone is sufficient | ✓ Validated Phase 07 |
| `models.toml` updated to Qwen3-32B fan-out + Qwen3-80B synthesis as the cost-optimal default | Sweep data showed Qwen variants meet quality bar at meaningful cost reduction vs Claude defaults | ✓ Validated Phase 07 |
| Cancel test uses direct asyncio + stub LLM (deviation from "under real DA-CLI host" wording) | FastMCP SDK validates MCP protocol framing; aioboto3 not yet available for wire-level Bedrock cancel | ✓ Validated Phase 08 (scope narrowing documented in `docs/cancellation.md §4`; owner-acknowledged) |
| Single sequential E2E integration test (not 6 separate tests) exercising all MCP tools against tmp_path vault | One stdio subprocess spawn amortized across all tools; matches DA-CLI runtime shape; gated to opt-in for cost discipline | ✓ Validated Phase 08 |
| `schema_version: 1` stamped as first key on every trace JSONL record + lenient consumer that warns once per file on v0 or higher-than-known | Allows future schema evolution without breaking existing renderers; warn-but-render avoids silent skips | ✓ Validated Phase 09 |
| `render_project_context()` at command entry (not per-subagent invocation) | Render once, pass through; respects token budget (+1500 cap per role); avoids redundant `wiki/CLAUDE.md` reads on fan-out | ✓ Validated Phase 10 |
| No deepagents `SubAgentMiddleware` migration — keep existing `SubagentPool` dispatch | Architectural cost of migration outweighs the context-injection benefit; fragment curation pattern + project_context renderer achieve the same outcome | ✓ Validated Phase 10 |
| `wiki-config.toml` and `.graph-wiki.yaml` are different surfaces — no migration script (WS-10, 2026-05-18) | `wiki-config.toml` (repo root) is the runtime CLI config read by `WikiConfig` dataclass — fields `{models_path, vault_path}` — pointing the CLI at models + a default vault. `.graph-wiki.yaml` (per workspace) is the manifest read/written by `workspace_io.manifest` — fields `{version, initialized_at, plugins[{name, installed_version, applied_version}]}` — tracking which plugins initialized the workspace. The two coexist with no overlap, so no migration is needed; per D-05 the existing throwaway `~/Personal/graph-wiki/agent-research` is deleted and re-inited via `graph-wiki-agent init` rather than migrated. | ✓ Validated Phase 11 |
| **Plugin shell-out via `uv run --project "$AGENT_RESEARCH_ROOT"`** (SO-01, v1.2) | Plugin scripts at `plugins/graph-wiki/scripts/*.py` shell out to agent-research Python helpers via `uv run --project "$AGENT_RESEARCH_ROOT" python3 -m ...`; backend selection per command via `[plugin]` block in `.graph-wiki.yaml` (SO-03), defaulting to `claude` everywhere with `bedrock` as documented per-command opt-in. | ✓ Validated Phase 14 |
| **`TaskResult` contract on `SubagentPool.run_all`** (TRACE-FU-01, v1.2) | All fan-out callbacks return a `TaskResult` wrapping the LangChain `AIMessage.usage_metadata` instead of raw scalars. JSONL trace records now emit non-None `tokens_in` / `tokens_out` / `cost_usd` per item; gated regression test verifies against real Bedrock. | ✓ Validated Phase 16 |
| **MCP wire-level cancel deferral re-anchored to event trigger** (Phase 16 D-09, 2026-05-19) | Calendar re-evaluation dates generated noise without changing the gate outcome. Replaced with event-driven trigger: re-evaluate when `langchain-aws#663` merges OR aioboto3 GA/1.0 lands. Anchored signal, no scheduled toil. | ✓ Validated Phase 16 |
| **No `lattice` symbols survive in-scope** (BRAND-04, v1.2) | `scripts/check-brand.sh` runs `grep -rE` across packages/agents/plugins/.planning/CLAUDE.md and pipes through `.brand-grep-allow` (52 intentionally-preserved historical refs). Exit non-zero on unallowlisted hit. Runs as a normal pytest gate. | ✓ Validated Phase 12 |
| Phase 13 (M3a) — graph-wiki plugin contract surface locked (SP-05, 2026-05-18) | Foundational reframe: the ported graph-wiki plugin runs on **Claude Code inference** (P-01) — it is NOT a wrapper around `graph-wiki-agent`. `graph-wiki-agent` (Bedrock-backed CLI + MCP server) stays as the separate, headless, cost-frontier surface. The two coexist as parallel surfaces over the same underlying Python helpers in `wiki-io` / `workspace-io`. Verdicts: 6 upstream commands rename or reshape (`init`, `scan`, `ingest`, `lint`, `query`, `log`) + 3 dropped (`archive`, `regen-index`, `status` — work-layer out of v1.2 per C-01). Shell-out shape: `uv run --project "$AGENT_RESEARCH_ROOT" python3 ...` (SO-01) with the `[plugin]` backend-selector block in `.graph-wiki.yaml` (SO-03); backend defaults to `claude` everywhere, `bedrock` is the documented per-command opt-in (P-02). Phase 14 prerequisite: `lint_wiki.py` (~508 LOC) and `wiki_search.py` (~194 LOC) must be ported into `packages/wiki-io/` as Phase 14 Plans 1 and 2 respectively before the `/graph-wiki:lint` and `/graph-wiki:query` shims can shell out (VP-01). Source-of-truth spec: [`.planning/spec/13-plugin-contract/CONTRACT-INDEX.md`](.planning/spec/13-plugin-contract/CONTRACT-INDEX.md) (audit summary) and [`.planning/spec/13-plugin-contract/SHELL-OUT-PATTERN.md`](.planning/spec/13-plugin-contract/SHELL-OUT-PATTERN.md) (cross-cutting decisions). | ✓ Validated Phase 13 |
| **`App` is a distinct graph kind, not an attribute flag** (APP-02, v1.9) | App nodes participate in the same edges as packages but render distinctly; manifest-signal classifier with documented precedence; URI form preserved (`pkg:` → `app:`) so inbound references survive reclassification. | ✓ Validated Phase 50 (executed; formal VERIFICATION.md not produced — debt) |
| **Single source of truth for entity filenames: `short_filename(uri, collision_set, ...)`** (WIKI-FN-04, v1.9) | One pure helper for write/index/rewrite paths; reverse URI lookup via `frontmatter.uri` eliminates the bidirectional-slug round-trip surface. `_ADMITTED_URI_PREFIXES` deleted — `decode_slug` was its only consumer (Phase 53 D-06). | ✓ Validated Phase 52+53 |
| **Phase 53 scope reshape — manual single-user vault regen, no migrate-vault command** (Phase 53 D-01..D-10) | No production wikis exist; the exploratory vault is disposable. Dropped the original migration command / wikilink rewriter / atomic-cutover-commit criteria in favor of a manual delete → `cg update --full` → `scan` regen documented in `53-UAT.md`. | ✓ Validated Phase 53 (UAT pass + 13/13 threat-secure) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**Last updated:** 2026-05-28 — milestone v1.10 (Wiki Index & Entity Page Enrichment) STARTED. Scope: human-readable index with per-entity summaries + an app section; nest test-suites/dependencies under their packages; stop emitting `dependency` nodes for workspace packages (use a `depends_on` edge); migrate old overview/subpage content into `entity-<type>` templates + flesh out ontology sections with TODO placeholders + scan-time variable population; debt fixes (`test_integration_gate.py`, PROJECT.md drift). Phase numbering continues from Phase 53 → v1.10 starts at Phase 54.

**Prior update:** 2026-05-28 — milestone v1.9 (Graph Refinements & Wiki Filename Slimdown) SHIPPED. 5 phases (49-53), 15 plans, 24/24 requirements; merged to `main` via PR #1. Delivered the `builtin` graph kind, `package`→`app` reclassification, short `<kind>_<name>.md` entity filenames (dead slug machinery removed), and full `package-family` + LIB-003 removal. Known debt: Phase 50 lacks a formal VERIFICATION.md; no milestone audit run.

**Prior update:** 2026-05-27 — milestone v1.8 (Wiki Entity Restructure) SHIPPED. 7 phases (42-48), 20 plans, 38/38 requirements satisfied. UAT 8/8 passed for the Phase 46 atomic cutover (47 entities, 122 inbound-link rewrites, single commit on the external vault).

**Prior update:** 2026-05-26 — milestone v1.8 (Wiki Entity Restructure) STARTED. Scope: collapse page-type-per-directory wiki into unified `/entities/` lane driven by graph-io, URI-keyed pages, scanner-populated relation frontmatter, domain-first scanner-generated index, hard-delete reconciliation, one-shot inbound-link migration, plus LLM-proposed domain groupings + import-graph clustering (`cg domain-clusters` + `graph-wiki-agent graph propose-domains`). Supersedes aborted v1.8 URI-Keyed Wiki & Reconciliation. Phase numbering continues from Phase 41 → starts at Phase 42.

**Prior update:** 2026-05-26 — milestone v1.7 (graph-io Integration & Wiki Hygiene) STARTED. Scope: wire `graph-io` into `graph-wiki-agent` (librarian grounding tools, scanner/ingestor consume graph-io, new `graph` subcommand), fix `cg find` parser, burn down 10 deferred quick tasks + 2 bootstrap todos as a hygiene phase. Wiki redesign deferred to v1.8. Phase numbering continues from Phase 35.

**Prior update:** 2026-05-25 — milestone v1.5 (Repo Rename & Foundational Package Additions) SHIPPED retroactively. 1 phase, 0 plans (single-phase doc-only milestone). 7/7 requirements satisfied; audit skipped per operator direction.

**Earlier:** 2026-05-25 — milestone v1.4 (Workspace Path Resolution Cleanup) SHIPPED minimally. 5 phases, 8 plans. Audit skipped per operator direction; deferred items captured in STATE.md.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-28 — milestone v1.10 (Wiki Index & Entity Page Enrichment) STARTED. v1.9 SHIPPED 2026-05-28. 53 phases / 185 plans across v1.0-v1.9 (ten milestones); v1.10 starts at Phase 54.*
