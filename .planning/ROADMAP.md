# Roadmap: deep-agents / graph-wiki-agent

**Project:** deep-agents (v1 = graph-wiki-agent)
**Created:** 2026-05-13
**Current milestone:** none — v1.3 shipped 2026-05-20; v1.4 not yet scoped (run `/gsd-new-milestone`)

---

## Milestones

- ✅ **v1.0 — graph-wiki-agent parity** — Phases 1-5 (shipped 2026-05-15) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 — Quality Improvements** — Phases 6-10 (shipped 2026-05-17) — [archive](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 — Graph-Wiki Port & Debt Cleanup** — Phases 11-16 (shipped 2026-05-19) — [archive](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 — Tooling Cleanup** — Phases 17-21 (shipped 2026-05-20) — [archive](milestones/v1.3-ROADMAP.md) · [audit](milestones/v1.3-MILESTONE-AUDIT.md)

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

- [x] Phase 17: vault-io Bug Fixes (5/5 plans) — completed 2026-05-20
- [x] Phase 18: Plugin Command Rename (6/6 plans) — completed 2026-05-20
- [x] Phase 20: Workspace Manifest Model Config (4/4 plans) — completed 2026-05-20
- [x] Phase 21: Rename graph-wiki-agent → graph-wiki-agent (5/5 plans) — completed 2026-05-20
- [x] Phase 19: Phase 16 Code Review Burndown (5/5 plans) — completed 2026-05-20

Full detail: [`milestones/v1.3-ROADMAP.md`](milestones/v1.3-ROADMAP.md)
Audit: [`milestones/v1.3-MILESTONE-AUDIT.md`](milestones/v1.3-MILESTONE-AUDIT.md)

</details>

---

## Phase Details

> v1.0–v1.3 phase details live in the milestone archives under `.planning/milestones/`. Active phase details will appear here when the next milestone is scoped via `/gsd-new-milestone`.

<!--

### Phase 17: vault-io Bug Fixes
**Goal**: All three vault-io behavioral bugs are fixed so scan reports accurate diffs, token counts are stamped correctly, and repo/container resolution works at the v2 workspace layout
**Depends on**: Phase 16 (prior milestone)
**Requirements**: SCAN-01, SCAN-02, TOK-01, TOK-02, TOK-03, WSRES-01, WSRES-02, WSRES-03
**Success Criteria** (what must be TRUE):
  1. `/graph-wiki:scan` on a healthy 7-package vault reports 0 deleted entries for the four companion pages per package (was 28)
  2. After scan, all 35 wiki pages previously at `tokens: 0` show a non-zero token count in their frontmatter
  3. `detect_containers --json` returns the repo-root containers (not an empty list) when the wiki lives at `<workspace>/wiki/`
  4. The workspace directory itself does not appear in its own layout block as a `docs` container
  5. Unit and integration tests for scan companion folding and CountTokens API shape pass under `uv run --package vault-io pytest`
**Plans**: 5 plans
Plans:
- [x] 17-01-PLAN.md — SCAN companion-page fold in `_load_existing_pages` + unit tests (SCAN-01, SCAN-02)
- [x] 17-02-PLAN.md — Bedrock CountTokens API shape fix in `update_tokens.py` + mocked unit tests + gated integration test (TOK-01, TOK-02)
- [x] 17-03-PLAN.md — Workspace/repo resolution fixes in `init_vault.py` and `detect_containers.py` + synthetic-fixture tests (WSRES-01, WSRES-02, WSRES-03)
- [x] 17-04-PLAN.md — TOK-03 live re-stamp against `~/Personal/wiki/deep-agents` + populate `17-VERIFICATION.md` (TOK-03)
- [x] 17-05-PLAN.md — Gap closure: plumb `workspace_path` through `init_vault._resolve_pinned_containers` and `scan_monorepo._discover_heuristic` to close WSRES-02 BLOCKER on SC#4 (WSRES-02)

### Phase 18: Plugin Command Rename
**Goal**: Claude Code's built-in `/init` command is reachable again by renaming the conflicting plugin command to `/graph-wiki:bootstrap` with all references updated
**Depends on**: Phase 17
**Requirements**: CMD-01, CMD-02, CMD-03
**Success Criteria** (what must be TRUE):
  1. `plugins/graph-wiki/commands/bootstrap.md` exists; `init.md` is gone from that directory
  2. All internal plugin references (`marketplace.json`, `SKILL.md`, command bodies, READMEs) use `/graph-wiki:bootstrap` — no stale references to the old slug remain
  3. With the plugin installed, typing `/init` in Claude Code invokes the native "initialize CLAUDE.md" workflow, not the graph-wiki command
**Plans**: 6 plans
Plans:
**Wave 1**
- [x] 18-01-PLAN.md — Rename slash command file plugins/graph-wiki/commands/init.md → bootstrap.md (CMD-01)
- [x] 18-02-PLAN.md — Rename MCP tool surface wiki_init → wiki_bootstrap + Pydantic models + tests (CMD-02 MCP)
- [x] 18-03-PLAN.md — Rename Typer CLI subcommand init → bootstrap + git mv test file + help-text assertions (CMD-02 CLI)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 18-04-PLAN.md — Sweep 11 active-source references to the old slug → `/graph-wiki:bootstrap`; add README reinstall note (CMD-03 active)
- [x] 18-05-PLAN.md — Sweep 18 historical .planning/ references (single bundled commit) (CMD-03 historical)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 18-06-PLAN.md — Extend scripts/check-brand.sh + .brand-grep-allow + red-then-green sanity; fold todo to resolved/ (CMD-03 gate)

### Phase 20: Workspace Manifest Model Config
**Goal**: All wiki model-override configuration lives in the `<workspace>/.graph-wiki.yaml` `plugins[].roles[]` block, with the packaged `models.toml` in `model-adapter` as per-role fallback; the orphan `wiki-config.toml` pathway (`WikiConfig.models_path`, `set_models_path`, `--config`, `GRAPH_WIKI_CONFIG`) is removed.
**Depends on**: Phase 17
**Requirements**: WMC-01, WMC-02, WMC-03, WMC-04, WMC-05a, WMC-05b
**Success Criteria** (what must be TRUE):
  1. `workspace-io.manifest` round-trips a populated `plugins[].roles[]` block (read → write → re-read preserves nested structure) with PyYAML
  2. `model-adapter.make_llm(role)` resolves to workspace-defined role config when present and falls back to the packaged `models.toml` per-role (per-role fallback, not all-or-nothing) when absent
  3. `WikiConfig.models_path`, `set_models_path()`, and the `--config` / `GRAPH_WIKI_CONFIG` plumbing are removed from `graph_wiki_agent/config.py`, `graph_wiki_agent/cli.py`, and `graph_wiki_mcp/server.py`; no code path remains that reads a `wiki-config.toml`
  4. `~/Personal/deep-agents/graph-wiki/.graph-wiki.yaml` carries the full default `roles[]` set (preflight, librarian, scanner, linter, ingestor, synthesizer, code_reader, judge_a, judge_b — 9 entries mirroring packaged defaults)
  5. `packages/workspace-io/README.md` documents the `roles:` schema; `graph-wiki-agent` CLI help text and docs drop all `--config` references; the workspace-io wiki page's "no PyYAML" claim is corrected
**Out of scope**:
  - Per-machine model selection inside `.graph-wiki.local.yaml` (Option A chosen — redirect to a different workspace directory instead)
  - Migration tooling for the deleted `wiki-config.toml` / `wiki-config-claude.toml` (already `git rm`'d)
**Requirement → SC map**:
  - WMC-01 (`workspace-io.manifest` round-trips populated `roles[]`) → SC#1
  - WMC-02 (`make_llm` workspace-override + per-role fallback) → SC#2
  - WMC-03 (delete `WikiConfig.models_path` / `set_models_path` / `--config` / `GRAPH_WIKI_CONFIG`) → SC#3
  - WMC-04 (populate `graph-wiki/.graph-wiki.yaml` with full role block) → SC#4
  - WMC-05a (workspace-io README documents `roles:` schema) → SC#5 (docs portion)
  - WMC-05b (workspace-io wiki page "no PyYAML" claim corrected; CLI help drops `--config`) → SC#5 (docs portion)
**Plans**: 4 plans
Plans:
- [x] 20-01-PLAN.md — Extend `workspace-io.manifest` with `roles[]` round-trip + `read_roles` accessor + README schema docs (WMC-01, WMC-05a)
- [x] 20-02-PLAN.md — Wire workspace-override layer into `model-adapter.loader.make_llm` with per-role fallback + tests; delete `set_models_path` (WMC-02)
- [x] 20-03-PLAN.md — Delete `WikiConfig.models_path` / `--config` / `GRAPH_WIKI_CONFIG` plumbing + update `test_config.py` (WMC-03)
- [x] 20-04-PLAN.md — Populate `graph-wiki/.graph-wiki.yaml` with full 9-role block + docs sweep (wiki page, intel JSON, CLAUDE.md) + live verify (WMC-04, WMC-05b)

### Phase 21: Rename graph-wiki-agent → graph-wiki-agent
**Goal**: Mechanical rename of the agent package from `graph-wiki-agent` to `graph-wiki-agent` across the full repository — directory names, Python module names, console scripts, internal symbols, user-facing strings, trace dir, plugin shell-out invocations, tests, and planning docs — landed across staged commits with `scripts/check-brand.sh` extended to enforce the new brand.
**Depends on**: Phase 20
**Requirements**: TBD (assigned during planning)
**Success Criteria** (what must be TRUE):
  1. `agents/graph-wiki-agent/` is gone; `agents/graph-wiki-agent/` exists with full git history preserved via `git mv`
  2. Python packages `graph_wiki_agent` / `graph_wiki_mcp` are renamed to `graph_wiki_agent` / `graph_wiki_mcp`; all imports in src + tests updated; `uv sync && uv run pytest agents/graph-wiki-agent/tests/ -m "not integration"` passes
  3. Console scripts `graph-wiki-agent` / `graph-wiki-mcp` are gone; `graph-wiki-agent` / `graph-wiki-mcp` work end-to-end (CLI help renders, MCP `python -c "from graph_wiki_mcp import server"` succeeds)
  4. Plugin shell-out scripts (`plugins/graph-wiki/skills/graph-wiki/scripts/*.py`) invoke `graph-wiki-agent`, not `graph-wiki-agent`; trace directory is `.graph-wiki/traces/`, not `.graph-wiki/traces/`
  5. `scripts/check-brand.sh` greps for the old slugs and fails CI on any reintroduction; `.brand-grep-allow` is updated; full-repo grep for `graph-wiki-agent` / `graph_wiki_agent` / `graph-wiki-mcp` / `graph_wiki_mcp` returns 0 hits outside the allowlist
**Out of scope**:
  - `graph-wiki/wiki/` content (companion pages, agent dir naming) — wiki is regenerated by `/graph-wiki:scan`
  - Raw spike sources under `.planning/spikes/{001,002}/sources/**` — historical material
  - Backwards-compat shims (no console-script alias, no deprecation stub) — hard cut per D-10
  - `models.toml` / config file renames — unrelated to package identity
**Plans**: 5 plans
Plans:
- [x] 21-01-PLAN.md — Worktree setup + `git mv` directory moves (agents/ + src/ subdirs)
- [x] 21-02-PLAN.md — pyproject.toml `name` + console scripts + `uv.lock` regeneration
- [x] 21-03-PLAN.md — Sweep imports + identifier renames + kebab strings + trace-dir inside agents/graph-wiki-agent/
- [x] 21-04-PLAN.md — Plugin shellouts + GRAPH_WIKI_* env-var rename + integration-gate test + cross-package .graph-wiki/ trace-dir sweep
- [x] 21-05-PLAN.md — Full .planning/ sweep (live + current-milestone + archives) + repo/plugin docs + spike-findings skill + extend `scripts/check-brand.sh` + `.brand-grep-allow` Phase 21 section + SP-2 final two-stage gate

### Phase 19: Phase 16 Code Review Burndown
**Goal**: Every Phase 16 code review finding has a documented disposition (fixed, dismissed with rationale, or converted to a follow-up todo) so the trace pipeline + eval harness refactor lands without carried-forward debt
**Depends on**: Phase 21 (rename ships first so the burndown doesn't have to chase moving files)
**Requirements**: REVIEW-01, REVIEW-02
**Note**: Moved to end of execution queue (2026-05-20) so the rename in Phase 21 happens before triaging review findings on the renamed package surface.
**Success Criteria** (what must be TRUE):
  1. All 6 warning-level findings are triaged — each has one of: a code fix committed, a written rationale for dismissal, or a filed follow-up todo
  2. All 9 info-level findings are triaged with the same fix / dismiss / follow-up disposition
  3. Triage outcomes are recorded in the phase REVIEW.md so future code review can verify the debt is not re-accumulating
**Plans**: 5 plans
Plans:
**Wave 1** *(parallel — no file-level conflicts)*
- [x] 19-01-PLAN.md — Divergence eval regex fixes: D-01 (WR-01) `_SLUG_ONLY_RE` replacement in synthesizer.py + D-02/D-03 (WR-02/WR-03) regex tweaks in code_reader.py (REVIEW-01)
- [x] 19-02-PLAN.md — Core runtime fixes: D-05 (WR-05) hoist `inspect.signature` in pool.py + D-06 (WR-06) `Path.is_relative_to` in ingest.py (REVIEW-01)
- [x] 19-03-PLAN.md — Test + integration fixes: D-04 (WR-04) trace-coverage exemption + D-09/D-10/D-13 (IN-03/IN-04/IN-07) (REVIEW-01, REVIEW-02)
- [x] 19-04-PLAN.md — Query trace + docs cleanup: D-07 (IN-01) docstring + D-12 (IN-06) synth filename qualifier + D-14 (IN-08) cancellation.md schema_version + D-15 (IN-09) G1 dedup (REVIEW-02)

**Wave 2** *(blocked on Wave 1 — needs commit SHAs from plans 01-04)*
- [x] 19-05-PLAN.md — Author 19-REVIEW-BURNDOWN.md disposition table (D-17); record D-08 (IN-02) + D-11 (IN-05) as `no-action — review self-corrected on re-scan` (REVIEW-01, REVIEW-02)

-->

---

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 graph-wiki-agent parity | 5 | 25/25 | ✅ Shipped | 2026-05-15 |
| v1.1 Quality Improvements | 5 | 39/39 | ✅ Shipped | 2026-05-17 |
| v1.2 Graph-Wiki Port & Debt | 6 | 21/21 | ✅ Shipped | 2026-05-19 |
| v1.3 Tooling Cleanup | 5 | 25/25 | ✅ Shipped | 2026-05-20 |

---

*Last updated: 2026-05-20 — v1.3 shipped (5 phases, 25 plans, 19/19 requirements satisfied). Next milestone TBD — run `/gsd-new-milestone` when ready.*
