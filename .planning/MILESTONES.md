# Milestones

## v1.10 Wiki Index & Entity Page Enrichment (Shipped: 2026-05-29)

**Phases completed:** 6 phases (54–59), 14 plans, 32 tasks
**Delivered:** Turned the generated wiki into a genuinely readable projection of the graph — a human-readable index with an app section, per-entity inline summaries, and dependencies/test-suites nested under their packages — backed by fleshed-out entity templates and a fixed internal-package-as-dependency classification; then decoupled the agent from `graph_io.cli` onto the typed library API.
**Git range:** `4c54c46` → `c7daeb8` · 116 commits (20 `feat`) · 135 files, +14,982 / −1,203
**Timeline:** 2026-05-28 → 2026-05-29

**Key accomplishments:**

- **Debt clearance (Phase 54):** adopted the canonical `GRAPH_WIKI_RUN_INTEGRATION` skipif across the 7 flagged integration test files (integration-gate green) and corrected PROJECT.md's "What This Is" / Constraints to the real stack — `subagent-runtime` + `langchain-aws` + `langchain-core` and `graph-wiki` naming, dropping stale `deepagents` / `lattice-wiki` wording.
- **Dependency classification fix (Phase 55):** `graph-io`'s `refresh()` no longer emits a `dependency` node for any name that is also a workspace package/app; an internal package→package usage becomes a dedicated `depends_on_package` edge (with a retargeted `used_by`), and `cg describe-package` now surfaces both directions of that edge in JSON and human output.
- **Entity templates & scan-time population (Phase 56):** migrated legacy per-kind `overview.md` content into `entity-<type>.md` templates, added scan-time `{{var}}` substitution (no literal `<...>` survives) and a `summary:` frontmatter field on every entity page; removed the legacy `package/` `domain/` `plugin/` `app/` template directories.
- **Index generation polish (Phase 57):** `wiki/index.md` gained a distinct `app` By-Kind section, human-readable `[[wiki/entities/<stem>|<name>]]` links with inline summaries, and test-suites/dependencies nested under the packages they belong to — the flat By-Kind lists for those two kinds were dropped.
- **Entity page & index UAT follow-ups (Phase 58):** replaced dead `<...>` placeholder wikilinks in entity `## Related` blocks with a clean Obsidian-safe fill-me marker, fixed the Obsidian-blockquote-breaking `summary:` placeholder in `entity_writer.py`, and fixed test-suite fan-out by keying renderer resolution on test_suite node uri rather than the shared `name`.
- **Decouple agent from `graph_io.cli` (Phase 59):** promoted the formatter to a public `graph_io.render`, rewrote `commands/graph.py` + `graph_tools.py` off the `argparse.Namespace`/stdout-capture shim onto typed `graph_io.queries`/`update`/`store`, preserving the exact exit-code contract (incl. `AMBIGUOUS(7)`) — proven byte-identical via 7 real-DB syrupy snapshots with the full suite green.

### Known Gaps (acknowledged at close)

- **No milestone audit run** — `/gsd:audit-milestone` (cross-phase integration + E2E + requirements coverage) was skipped; close proceeded on per-phase verifications alone. Consistent with the v1.6 / v1.8 / v1.9 close pattern; tracked as process debt.
- **Deferred: entity `## Related` dynamic population** — Phase 58 shipped a clean Obsidian-safe marker but deliberately deferred populating `## Related` from graph edges (CONTEXT D-01). Carried as a future-phase candidate in `.planning/todos/deferred/2026-05-28-populate-entity-related-section-from-graph-edges.md`.

---

## v1.9 Graph Refinements & Wiki Filename Slimdown (Shipped: 2026-05-28)

**Phases completed:** 5 phases (49–53), 15 plans, 25 tasks
**Delivered:** Tightened the graph-build pipeline (built-in/stdlib handling, app classification) and slimmed the wiki projection to short human-readable entity filenames, retiring the dormant `package-family` mechanism and the dead bidirectional-slug machinery.
**Git range:** `294445a` → `63a233d` · 117 commits · merged to `main` via PR #1 (`e8df39f`)
**Timeline:** 2026-05-27 → 2026-05-28

**Key accomplishments:**

- **Builtin kind (Phase 49):** stdlib/Node built-in imports classified as a first-class `Builtin` graph node (`builtin:<lang>/<module>`), with `cg list-builtins` / `cg describe-builtin` surfaces — keeps noisy stdlib calls out of the wiki.
- **App reclassification (Phase 50):** packages that are really apps (CLI / Next.js / Expo / SPA, via manifest signals) reclassified to a distinct `App` kind with `app_kind`, preserving inbound URI references.
- **package-family removal (Phase 51):** retired the dormant `package_family` kind end-to-end (graph-io schema, URI builder, wiki template, CLI surfaces) and deleted the LIB-003 slug-only divergence rule from the eval harness.
- **Wiki filename slimdown — core (Phase 52):** introduced `short_filename(uri, collision_set, ...)` — entity pages move from `pkg__org__repo__name.md` to short `<kind>_<name>.md` with deterministic hash suffixes only on collision.
- **Wiki filename cutover (Phase 53):** removed dead `encode_slug` / `decode_slug` / `_ADMITTED_URI_PREFIXES`; every consumer now derives filenames via `short_filename` and reads URIs back via `frontmatter.uri`. Verified by a from-scratch vault regen (UAT) and a 13/13 threat-secure audit.

### Known Gaps (acknowledged at close)

- **Phase 50 was never formally verified** — executed (3 plan summaries) and its APP-01..06 requirements marked Complete, but it has no `VERIFICATION.md` (the other four phases do). Accepted as tech debt at close.
- **No milestone audit run** — `/gsd:audit-milestone` (cross-phase integration + E2E + requirements coverage) was skipped; close proceeded on per-phase verifications alone.

---

## v1.8 Wiki Entity Restructure (Shipped: 2026-05-27)

**Phases completed:** 7 phases, 20 plans, 14 tasks

**Key accomplishments:**

- [Rule 1 - bug] URI prefix vs. kind name asymmetry.
- Phase 42 contracts locked; ready for Phase 43 entity-writer implementation.
- Two new graph kinds (`dependency`, `plugin`) admitted with full ingestion + read surface; folded subpackage bug fix landed in the same pass.
- Mocked-graph implementation of the write_entities pipeline with deterministic byte-stable output, scan-lock concurrency control, and partial-failure isolation — all verified against a MockGraphConn (no real sqlite needed for the inner loop).
- Choice: SHIP
- Wave 1 foundation shipped: narrator Bedrock role, idempotent `inject_narrative` helper, surgical removal of wiki/index.md from update_index, and the SCANINT-04 dual-writer rewrite — all four pieces Plan 03 depends on.
- `_load_existing_pages` now returns an ExistingPages dataclass with legacy (name-keyed, unchanged) and entities (URI-keyed, new) sub-dicts — feeds Plan 03's run_scan without re-walking the filesystem.
- run_scan now threads write_entities (Step 9a) + narrator fan-out (Step 9b) + inject_narrative (Step 10) + dual-writer index (Step 12) into the scan pipeline — v1.8 entity workflow shipped end-to-end with 8 integration tests verifying the call graph, gating, and frontmatter integrity.
- [Rule 1 - missing critical] make_llm did not accept model_override
- [Rule 2 — claude-discretion] Used 13 tests instead of exactly 10.
- [Rule 1 — missing critical] propose_domains_cmd path resolution was wrong.

---

## v1.7 graph-io Integration & Wiki Hygiene (Shipped: 2026-05-26)

**Phases completed:** 7 phases, 10 plans, 25 tasks

**Key accomplishments:**

- `cg find` migrated from positional-first to named-flag-only UX (--name / --kind / --in-package), with --in-package as a new package-scoped filter, a 50-row cap convention, and an anti-regression guard against silent re-introduction of the positional form.
- 5 closure-bound `@tool` callables wrapping `graph_io.queries` with a shared read-only conn, 50-row render cap, and never-raise error contract — ready for `commands/query.py` to bind in Plan 02.
- Librarian fan-out now opens one read-only graph conn at command entry, runs a CountTokens budget gate, binds 5 grounding tools onto the LLM (or gracefully degrades to vault-thin with a one-shot stderr signal when the graph is missing), drives an agentic tool-call loop bounded at 5 iterations per page, and closes the conn in `finally`.
- run_scan now dispatches `cg update` before fan-out, decorates every workspace dict with `pkg["uri"]` + `pkg["domain"]` from the graph (recomputing the vault slug on domain change), and enforces a strict error policy with a stderr-pattern-matched filesystem-init fallback.
- run_ingest_source now consults the workspace graph DB for canonical entity URIs before any LLM-driven routing decision — slugs and entity_uri frontmatter come from the graph when a match exists, and a missing graph hard-fails with CLI exit code 3 instead of silently producing drift.

---

## v1.5 Repo Rename & Foundational Package Additions (Shipped: 2026-05-25)

**Phases completed:** 1 phase, 0 plans (retroactive — SUMMARY.md is the canonical artifact)
**Timeline:** 2026-05-24 → 2026-05-25 (work shipped before milestone was scoped)
**Git range:** `9b8ac87` → `f896d99` (7 commits)
**Requirements:** 7/7 satisfied (REPO-01/02, PKG-01/02, RENAME-01, CLEANUP-01/02)
**Audit:** none — retroactive close, audit skipped per operator direction

**Delivered:** Retroactively captured the seven unphased commits that landed on `main` between v1.4 archive and v1.5 scoping — repo rename `deep-agents → agent-research`, env var sweep `DEEP_AGENTS_ROOT → AGENT_RESEARCH_ROOT`, two new workspace packages (`graph-io` SQLite code-graph store + `cg` CLI; `source-parser` tree-sitter SourceTree projection), the final brand rename `vault-io → wiki-io`, and a sweep of stale `lattice-wiki` doc mentions plus obsolete spike/sketch removal. Foundation milestone only — wiring the new packages into the agent loop is forward-looking work deferred to v1.6+.

### Key accomplishments

- **Repo + env rename** (REPO-01/02) — `deep-agents → agent-research` applied across README, CLAUDE.md, docs, and all internal references; `DEEP_AGENTS_ROOT → AGENT_RESEARCH_ROOT` swept across plugin shell-out templates, scripts, and tests. (commits `9b8ac87`, `39f1364`)
- **`graph-io` package added** (PKG-01) — new `packages/graph-io/` workspace member at v0.2.1: SQLite-backed code-graph store, manifest scanning, queries, and the `cg` CLI; declared workspace dependencies on `source-parser` + `workspace-io`. Not yet consumed by the agent loop. (commit `f896d99`)
- **`source-parser` package added** (PKG-02) — new `packages/source-parser/` workspace member at v0.1.0: tree-sitter-backed Python package producing span-bearing `SourceTree` with graph projection aligned to lattice-graph; declared `tree-sitter` + `tree-sitter-language-pack` deps. (commit `f896d99`)
- **`vault-io → wiki-io` rename** (RENAME-01) — final retirement of the `vault` brand at the package directory level (v1.4 had already swept `vault_path` and `vault:` from helpers and external surfaces). `git mv` preserved history; import sweep across `agents/`, `packages/`, `plugins/`, `eval-harness`, and tests; 663 files touched in the combined commit. (commit `f896d99`)
- **Doc + tree cleanup** (CLEANUP-01/02) — stale `lattice-wiki` mentions purged from README and core docs (`ff835c4`); `.planning/spikes/` and `.planning/sketches/` removed (`9ab8a58`); old docs removed (`b63bcac`); README polished (`1651d14`). Final brand and exploratory-artifact cleanup ahead of v1.6+ integration work.

### Known deferred items at close

5 items (see STATE.md `## Deferred Items`):

- 🟡 **Wire `graph-io` + `source-parser` into the agent loop** — v1.5 only added the packages; scanner/librarian do not yet consume them. Forward-looking integration deferred to v1.6+.
- 🟡 **Nyquist compliance retro-validation** — 0/21 v1.1-v1.4 phases produced VALIDATION.md. Decision (retro-validate vs. disable toggle) carried from v1.4 close.
- 🔵 **Phase 14 SC#4 plugin smoke transcript** — manual UAT, carried from v1.2.
- 🔵 **`librarian.py:21` `_SLUG_ONLY_RE` parity fix** — carried from v1.3 Phase 19.
- 🔵 **9 quick tasks + 2 todos** acknowledged-deferred at v1.4 close — still pending at v1.5 close.

---

## v1.4 Workspace Path Resolution Cleanup (Shipped: 2026-05-25)

**Phases completed:** 5 phases, 8 plans, 12 tasks

**Key accomplishments:**

- 582 passed, 33 skipped, 6 pre-existing failures
- One-liner:
- Issue:
- `_classify_dir` Rule 3 collapsed to a single permissive >=1-manifested-child branch, with honest reason strings and full plugin-reference-doc lockstep; `graph-wiki-agent bootstrap` on this repo now classifies `packages/` (5/6 manifested) as `package` instead of silently skipping it.
- 1. `_fragments/__init__.py` docstring path-prefix rebrand
- Hard-cut deletion of the 19-file upstream-snapshot tree, single-line `pyproject.toml` exclude removal, new BRAND-PROMPT-SOURCES CHECK 6 in `check-brand.sh`, and full verification (uv sync + 599-test graph-wiki-agent + 599-test eval-harness + brand-gate) green against the resulting tree.

---

## v1.3 Tooling Cleanup (Shipped: 2026-05-20)

**Phases completed:** 5 phases, 25 plans
**Timeline:** 2026-05-19 → 2026-05-20 (~2 calendar days, dense execution)
**Git range:** `04e6f8a` → `e0c2908` (65 phase commits + tracking)
**Diff:** 186 files changed, +3,396 / −1,117 lines
**Requirements:** 19/19 satisfied (13 declared at scoping + 6 WMC-* backfilled from Phase 20 at close)
**Audit:** [`milestones/v1.3-MILESTONE-AUDIT.md`](milestones/v1.3-MILESTONE-AUDIT.md) — `gaps_found` at audit time (1 brand-gate + 2 doc-refresh), all closed inline before archive.

**Delivered:** Burned down the v1.2 carry-forward bug list in `wiki-io` (scan companion-page fold, Bedrock CountTokens API shape, workspace/repo resolution), unshadowed Claude Code's native `/init` by renaming the plugin command to `/graph-wiki:bootstrap`, moved all model overrides into `<workspace>/.graph-wiki.yaml` `plugins[].roles[]` (deleting the orphan `wiki-config.toml` pathway), mechanically renamed the agent package `code-wiki-agent → graph-wiki-agent` across the full repository, and triaged all 15 Phase 16 code review findings (13 fixed + 2 no-action) with `19-REVIEW-BURNDOWN.md` as the canonical disposition table.

### Key accomplishments

- **wiki-io bug burndown** — 3 v1.2 carry-forward bugs fixed in Phase 17: companion-page diff returns 0 phantom deletions (was 28), Bedrock CountTokens uses correct `input=` param shape, `init_vault` + `detect_containers` use `resolve_wiki_and_repo()`'s repo return value at v2 workspace layout. 8 wiki pages re-stamped to non-zero tokens (TOK-03 operational closure). (SCAN-01/02, TOK-01/02/03, WSRES-01/02/03)
- **Plugin command unshadows native /init** — Phase 18 renamed `plugins/graph-wiki/commands/init.md → bootstrap.md` (git mv, history preserved). Typer CLI subcommand `init → bootstrap` + MCP tool `wiki_init → wiki_bootstrap` (with full Pydantic model rename). Brand-gate (`scripts/check-brand.sh` CHECK 2 + CHECK 3 + `.brand-grep-allow`) extended to enforce no reintroduction. SC#3 manual UAT (typing `/init` in Claude Code fires native CLAUDE.md workflow) remains user-owned. (CMD-01/02/03)
- **Workspace manifest model config** — Phase 20 moved all model overrides into `<workspace>/.graph-wiki.yaml` `plugins[].roles[]` with per-role fallback to packaged `models.toml`. Hard-cut deleted `WikiConfig.models_path`, `set_models_path()`, `--config` CLI option, and `GRAPH_WIKI_CONFIG` env var. `graph-wiki/.graph-wiki.yaml` populated with full 9-role block; live verification confirms each role resolves. (WMC-01..05b — backfilled into REQUIREMENTS.md at close per audit F3)
- **Mechanical package rename** — Phase 21 renamed `code-wiki-agent → graph-wiki-agent` across directories, Python modules (`code_wiki_agent`/`code_wiki_mcp` → `graph_wiki_agent`/`graph_wiki_mcp`), console scripts, internal symbols, user-facing strings, trace dir (`.code-wiki/ → .graph-wiki/`), plugin shell-outs, tests, and planning docs. 5 staged plans across 5 sequential waves. `scripts/check-brand.sh` extended with the new R-04 rule. (no REQ-IDs by design — rename scope captured in PLAN frontmatter `must_haves`)
- **Phase 16 code review burndown** — Phase 19 triaged all 15 Phase 16 review findings (6 warnings + 9 info, 0 critical). 13 → fixed (per-commit gate green: 395 passed / 23 skipped after every commit); 2 → no-action (IN-02 + IN-05 dispositioned as "no-action — review self-corrected on re-scan"). `19-REVIEW-BURNDOWN.md` is the canonical disposition table. Wave-based parallel execution: 4 fix plans fanned out in parallel worktrees, 5th plan consolidated the burndown table with verified commit SHAs. (REVIEW-01/02)
- **Audit-gap closures inline at close** — F1 brand-gate hit (1-line `.brand-grep-allow` for 19-02-SUMMARY.md narrative), F2 traceability checkboxes (12 of 13 flipped to Complete), F3 WMC-* backfill (6 Phase 20 requirements promoted into REQUIREMENTS.md). Brand-gate exits 0 at HEAD.

### Known deferred items at close

7 items (see STATE.md `## Deferred Items`):

- 🔴 **Phase 18 SC#3 manual UAT** — install plugin, type `/init`, confirm native CLAUDE.md workflow fires. By-design manual gate (Phase 18 D-07).
- 🟡 **2 quick-task status markers stale** — `260519-k9t-preflight-role` + `260519-lf1-bedrock-audit` shipped (PLAN + SUMMARY exist) but audit-open reports `missing`. Cosmetic.
- 🔵 **2 phases with open CONTEXT.md question lines** — Phase 18 (3) + Phase 20 (3). Answered during execution; markers not cleared from CONTEXT.md.
- 🟡 **Nyquist compliance** — 0/5 v1.3 phases produced VALIDATION.md, same pattern as v1.1 (0/5) and v1.2 (0/6). Retro decision carried to v1.4 scoping.

---

## v1.2 Graph-Wiki Port & Debt Cleanup (Shipped: 2026-05-19)

**Phases completed:** 6 phases, 21 plans
**Timeline:** 2026-05-17 → 2026-05-19 (~3 calendar days, dense execution)
**Git range:** `92e26fd` → `HEAD` (205 commits)
**Diff:** 715 files changed, +33,296 / −2,412 lines
**Requirements:** 30/30 v1.2 requirements satisfied
**Audit:** none — milestone closed without formal `/gsd:audit-milestone` run (proceeded on green Phase 11-16 VERIFICATION.md + Phase 16 UAT closure)

**Delivered:** Ported `lattice-workspace` into a new `workspace-io` package, swept the `lattice` → `graph-wiki` rebrand across the entire ecosystem, locked + ported the `graph-wiki` Claude Code plugin (`/graph-wiki:*`), re-synced the project's own wiki against the post-rebrand codebase, and closed the v1.1 carry-forward debt around trace pipeline, sweep coverage, MCP cancellation, and model config drift.

### Key accomplishments

- **workspace-io package shipped** — new `packages/workspace-io/` ported from upstream `lattice-workspace` with `.graph-wiki.yaml` manifest filename (replacing legacy `.lattice.yaml`), `GRAPH_WIKI_WORKSPACE` env var, `GraphWikiConfig` dataclass, and `workspace_io.config.resolve()` upward-walk discovery; `wiki-io._workspace.resolve_wiki_and_repo` rewritten as a 2-line delegation shim preserving the explicit-vault_path MCP boundary; 67 ported tests green under `uv run --package workspace-io pytest`; `graph-wiki-agent init` performs two-phase bootstrap (`workspace_io.init` first, then `init_wiki`); 18 `GRAPH_WIKI_REAL_VAULT_PATH` references swept to `GRAPH_WIKI_WORKSPACE` across CLI help, MCP tool descriptions, Pydantic Field descriptions, and docstrings (WS-01..10).
- **Selective drift backport** — body-diff inventory of 11 overlapping modules between `wiki-io` and upstream `lattice-wiki-core` pinned at a fixed SHA; canonical `packages/wiki-io/DRIFT-DECISIONS.md` published with verdicts. Zero PORT verdicts: every drift hunk is an intentional wiki-io divergence (lib-ification / MCP error handling / no-tiktoken) or out-of-v1.2 subsystem strip (package-family / CLI `main()`) (BACKPORT-01..04).
- **Ecosystem rebrand complete** — `lattice` / `LATTICE` / `lattice_workspace` / `lattice_wiki_core` swept to `graph-wiki` (kebab) / `graph_wiki` (snake) across `packages/`, `agents/`, `plugins/`, `.planning/`, `CLAUDE.md` in 5 atomic commits with `uv run pytest` gated green after each; `scripts/check-brand.sh` + `.brand-grep-allow` enforces ongoing brand discipline; `.planning/spikes/CONVENTIONS.md` `cores/` → `packages/` corrected (BRAND-01/02/04).
- **Plugin contract locked then ported** — Phase 13 (M3a) produced 9-row CONTRACT-INDEX.md (6 commands rename/reshape, 3 dropped per C-01 work-layer scope-out) + SHELL-OUT-PATTERN.md (SO-01..04) locking that the ported plugin runs on **Claude Code inference** (P-01) — NOT a wrapper around `graph-wiki-agent`. The Bedrock-backed `graph-wiki-agent` stays as the parallel cost-frontier surface; the two coexist over the same `wiki-io` / `workspace-io` helpers. Phase 14 (M3b) ported the plugin to `plugins/graph-wiki/` with renamed `plugin.json` id, `/graph-wiki:*` namespace, agent/skill rename, and shims wired through wiki-io; `workspace_io` manifest extended with `[plugin]` backend-selector block (PLUGIN-01..05).
- **Phase 14 prerequisite ports landed** — `wiki_io.lint_wiki` (~509 LOC) and `wiki_io.wiki_search` (~194 LOC) verbatim-ported from upstream `lattice_wiki_core` with brand rename and `_version_check` removal, unblocking the `/graph-wiki:lint` and `/graph-wiki:query` plugin shims (VP-01).
- **Project's own wiki self-updated** — `~/Personal/graph-wiki/agent-research` re-scanned + OTel re-ingested + librarian query run via `graph-wiki-agent` using a one-off Claude role-override profile (Haiku 4.5 fan-out + Sonnet 4.6 reasoning) to bring the wiki into alignment with the post-rebrand codebase; 3 operational deviations encountered and auto-fixed inline (`--config` doesn't propagate `vault_path` to subcommands; stale `cores/` container name in wiki CLAUDE.md; BM25 index requires manual rebuild after scan), documented in `15-VERIFICATION.md` (BRAND-03).
- **v1.1 carry-forward debt closed** — `TaskResult` contract on `SubagentPool.run_all` threads `response.usage_metadata` into JSONL traces; all 4 production fan-out callsites (scanner, linter, librarian, code_reader) emit non-None tokens_in/tokens_out/cost_usd on per-item trace records; gated TRACE-FU-01 regression passes against real Bedrock. DivergenceMetric wired through all 6 in-scope roles with rubrics for code_reader + synthesizer; 6 code_reader cases re-tuned against post-rebrand surfaces; scanner re-swept against fresh-package vault (65% deterministic SCANNER_CHECKS pass-rate accepted as "no regression vs. v1.1 baseline" — 7 SCN-002/SCN-003 failures excused as structural mismatch). MCP wire-level cancel formally re-deferred behind event-driven trigger (langchain-aws#663 merged OR aioboto3 GA/1.0) in `docs/cancellation.md §5`. Integration-gate convention codified in `docs/testing.md` + grep-enforced. `test_load_role_config_synthesizer_uses_sonnet` rewritten to assert the current Qwen synthesizer default (TRACE-FU-01, SWEEP-FU-02/03/04, MCP-CAN-01/02, MODEL-FU-01).

### Known deferred items at close

4 open items (see STATE.md `## Deferred Items`):

- 🟡 3 pending tooling todos: `fix-bedrock-count-tokens-api-shape-in-update-tokens`, `fix-workspace-repo-resolution-in-init-vault-and-detect-conta`, `rename-graph-wiki-init-command-to-init-wiki` — defer to v1.3
- 🔵 `next-milestone-planning` thread (intentional carry-forward to v1.3)

Phase 16 code review surfaced 6 warnings + 9 info findings (0 critical); not blocking but rolled into v1.3 backlog.

Phase 14 SC#4 was accepted on structural evidence (plugin loads + brand-gate clean) without a captured `/graph-wiki:query` smoke transcript from Claude Code; v1.3 should record the transcript as a regression artifact.

### v1.3 carry-forward themes

Open-source release prep (README badges, contribution guide, PyPI publish dry-run) — explicitly deferred to v2.0 GA in PROJECT.md. Nyquist compliance retroactive validation (0/5 v1.1 phases + 0/6 v1.2 phases reached `nyquist_compliant: true`) — needs a v1.3 decision (retro-validate vs. disable the toggle).

---

## v1.1 Quality Improvements (Shipped: 2026-05-17)

**Phases completed:** 5 phases, 39 plans, ~150 tasks
**Timeline:** 2026-05-15 → 2026-05-17 (~3 calendar days, dense execution)
**Git range:** `8aa21d5` → `92e26fd` (230 commits; 49 feat-prefixed)
**Diff:** 323 files changed, +37,702 / −27,672 lines
**Requirements:** 29/29 v1.1 requirements satisfied
**Audit:** `milestones/v1.1-MILESTONE-AUDIT.md` (status: tech_debt — 0 critical blockers, 6 known debt items)

**Delivered:** Closed the output-quality gap with lattice-wiki by porting its prompt content, validated the cost-frontier on Bedrock, proved host-level reliability under the DeepAgents CLI, polished trace/observability, and closed the subagent context gap.

### Key accomplishments

- **Lattice-wiki SKILL.md content ported** — librarian, ingestor, linter, scanner prompts now incorporate canonical iron rules / citation rules / ingestion patterns / lint rules / package-detection rules via 8 shared fragments under `prompts/_fragments/` with `# Source: / # Anchor: / # Source-commit:` provenance headers (PORT-01..06).
- **Divergence detection eval shipped** — 15 programmatic check rules (LIB/ING/LNT/SCN) + 4 LLM-judge rubrics + 37 unit tests + regression gate (`--accept-divergence-baseline`); 0 hard-severity divergences against the lattice-wiki baseline (EVAL-11..13).
- **Cost-frontier validated on Bedrock** — two-gate scoring (divergence vs. baseline + LLM-judge quality) across 6 in-scope roles against the post-port agent; `models.toml` defaults updated to cost-optimal picks (Qwen3-32B fan-out + Qwen3-80B synthesis) with provenance comments; full results doc under `.planning/sweep/` (SWEEP-01..05).
- **Host reliability proven** — `SubagentPool` terminates cleanly on MCP host cancel with per-item `status: cancelled` records and single `event: batch_cancelled` terminal trace; all 6 MCP tools (`wiki_init/scan/ingest/query/lint/log`) exercised via stdio subprocess E2E test against fresh tmp_path vault, gated by `GRAPH_WIKI_RUN_INTEGRATION=1`; 210-line `docs/cancellation.md` documents protocol + v1.2+ paths (MCP-09..11, DACLI-01..03).
- **Trace schema versioned + cost-aware renderer** — `schema_version: 1` stamped as first key on every JSONL record by all 3 producers; renderer surfaces per-(role,model) cost rollup with `(+K unknown)` accounting (sorted desc cost, alphabetical tie-break); collapses ≥2 consecutive same-role groups by default into single summary line, `--expand` for full per-record view; lenient consumer warns once per file on v0 or unknown future versions (OBS-04..06).
- **Subagent context completion** — `prompts/project_context.py::render_project_context(wiki_path)` reads `wiki/CLAUDE.md` (or `AGENTS.md`), parses the layout block via `wiki_io.layout_io`, returns deterministic ~30-line block of project layout + style + log format; wired through 4 prompt builders (scanner, linter, ingestor, librarian) and 3 commands at SystemMessage construction; +1500 token cap per role enforced via syrupy snapshot tests; divergence eval re-ran live (us-east-1, 193s, 4/4 PASSED), no regression (CTX-01..05).

### Known deferred items at close

4 open items (see STATE.md `## Deferred Items` and `milestones/v1.1-MILESTONE-AUDIT.md`):

- Phase 8 SC#1 + SC#2 documented scope narrowings awaiting owner sign-off (acknowledged; not blocking)
- 06-UAT.md metadata-only status mismatch (0 open scenarios)
- `next-milestone-planning` thread (intentional carry-forward to v1.2)

### v1.2 backlog filed during v1.1

TRACE-FU-01 (trace pipeline missing `usage_metadata`), SWEEP-FU-02/03/04 (sweep coverage gaps), MODEL-FU-01 (synthesizer test drift). Full text in `milestones/v1.1-REQUIREMENTS.md`.

---

## v1.0 graph-wiki-agent parity (Shipped: 2026-05-15)

**Phases completed:** 5 phases, 25 plans
**Timeline:** 2026-05-13 → 2026-05-15 (3 calendar days, ~12 sessions)
**Requirements:** 67/67 v1 requirements complete

**Delivered:** End-to-end `graph-wiki-agent` reaches full parity with the existing `lattice-wiki` Claude Code plugin, running entirely on AWS Bedrock with within-command subagent fan-out for cost and context savings.

### Key accomplishments

- **All 6 commands shipped** on both MCP (`graph-wiki-mcp` stdio server) and headless Typer CLI (`graph-wiki-agent <cmd>`) surfaces, sharing a single command-implementation module: `init`, `scan`, `ingest`, `query`, `lint`, `log` (CMD-01..08, MCP-01..08, CLI-01..07).
- **`cores/subagent-runtime` → `SubagentPool.run_all()`** with partial-failure isolation (one failure ≠ sibling cancellation), per-role semaphore throttling, explicit recursion-limit propagation, and structured JSONL trace output to `.graph-wiki/traces/` from day one (SUB-01..07, OBS-01..03). Powers fan-out for librarian (Phase 3), scanner (Phase 5), and 3-way linter (Phase 5).
- **`cores/wiki-io`** — 11 modules ported verbatim from `lattice-wiki-core` with import surgery only; round-trip golden test green on a 148-page real-vault fixture (byte-identical write-back). `python-frontmatter` for reads only; all writes route through the ported `layout_io.py` emitter to preserve hand-rolled YAML formatting (VAULT-01..07).
- **Hybrid search**: BM25 via `bm25s` 0.3.8 + Titan Embeddings v2 in SQLite (WAL mode), sha256-keyed incremental rebuild, RRF fusion with configurable weights, raw + fused scores exposed in `--json` (SEARCH-01..06).
- **`cores/model-adapter`** — `ModelRegistry` resolves logical role names (`librarian`, `scanner`, `linter`, `ingestor`, `synthesizer`, `judge_a`, `judge_b`, etc.) to `ChatBedrockConverse` instances via a single `models.toml`. No hardcoded model IDs anywhere. `BedrockAccessDenied` raised with attempted ARN + IAM verb on permission failure (BED-01..05).
- **`cores/eval-harness`** — fixture corpus (3 repos), headless `claude -p` baseline recorder with EVAL-08 reproducibility schema, `deepeval` 4.0 integration with `AmazonBedrockModel`, heterogeneous two-judge GEval panel (`claude-sonnet-4-6` + `nova-pro-v1:0`) with position-bias check, cost-frontier sweep runner via `pytest-evals`, structural metrics (cites code path / wikilinks resolve / valid frontmatter), and a regression-check AssertionError gate (EVAL-01..10).
- **MCP stdout discipline** locked at infrastructure level — `_StdoutGuard` sentinel + subprocess JSON-RPC integrity test that asserts every stdout byte is valid framing (MCP-05).
- **`ingest` ships as ONE MCP tool** (`wiki_ingest`) with `type: Literal['source', 'work-item']` discriminator rather than two tools — cleaner schema, type-narrowing server-side, matches lattice-wiki semantics.
- **CI hygiene** — ruff lint+format clean across the workspace; `uv` single shared `uv.lock`; per-member pytest isolation; GitHub Actions wired for both CI and opt-in eval workflows (INFRA-01..06).

### Outcomes against thesis

The infrastructure to measure the project's core thesis (cost-frontier on Bedrock vs current Claude-Code-hosted plugin) shipped in this milestone; *executing* the sweep — running it against all 7 roles, picking cost-optimal models, swapping `models.toml` defaults — is the v1.1 lift.

### Known deferred items (carried into v1.1)

- **BED-01 live-Bedrock gate** — code-side acceptance passed; the live `make_llm("haiku").invoke("ping")` call against real Bedrock remains blocked on a one-time AWS account onboarding form ("Anthropic use case details") that Pat needs to complete out-of-band.
- **Cost-frontier sweep execution** — harness shipped; results pending `GRAPH_WIKI_RUN_EVAL=1` runs.

For full milestone detail see [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md) and [`milestones/v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md). For lessons learned see [`RETROSPECTIVE.md`](RETROSPECTIVE.md).

---
