---
slug: next-milestone-planning
title: next-milestone-planning
status: in_progress
created: 2026-05-17
updated: 2026-05-17
---

# Thread: next-milestone-planning

## Goal

Capture ideas, scope, and candidate phases for the next deep-agents milestone while the current milestone audit and close-out runs in a parallel session. Promote the resulting material into ROADMAP.md once `/gsd-complete-milestone` finishes.

## Context

*Created 2026-05-17.*

Parallel-session constraint: another Claude session is currently running the milestone audit and will run `/gsd-complete-milestone`. To avoid file collisions, this thread restricts itself to capture/ideation only — no edits to ROADMAP.md, STATE.md, PROJECT.md, or the active milestone directory until that session finishes.

Project snapshot at thread creation:
- Current milestone: v1 of `graph-wiki-agent` (Bedrock-hosted port of lattice-wiki).
- Most recent commits indicate Phase 9 gap-closure verified; `cores/` renamed to `packages/`.
- Tech stack locked: `uv` workspace, Python 3.11+, deepagents 0.6.1, langchain-aws 1.4.6, mcp 1.27.1, deepeval 4.0.0, typer 0.25.1. See `CLAUDE.md` for full table.
- Wiki vault for this project: `~/Personal/wiki/deep-agents` (Qwen3-32B fan-out, Qwen3-80B synthesis).

## References

- `CLAUDE.md` — locked stack and constraints
- `.planning/ROADMAP.md` — current milestone phases (do NOT edit from this thread)
- `Skill("spike-findings-deep-agents")` — implementation blueprint and proven patterns
- `~/Personal/wiki/deep-agents` — wiki for cross-reference

## Next Steps

1. Wait for the other session to confirm `/gsd-complete-milestone` finished.
2. Run `/gsd-new-milestone`. The post-spike-002 plan below has three phases (M1, M2, M3) — break each into a phase via `/gsd-phase`.
3. `/gsd-spec-phase` and `/gsd-plan-phase` per phase. Heavy file-move work benefits from a written plan before execution.
4. M3 (plugin port) is deferred until `lattice-wiki` plugin scoping has its own pass; M4 (plugin-as-python-package) remains a spike candidate, not a committed phase.

## Decisions Log

| Date | Decision | Source |
|---|---|---|
| 2026-05-17 | Spike 002 reframed the original themes. Original T1–T5 captured below in `## Migration Themes (superseded)` — kept for provenance. Current plan lives in `## Revised Plan (post-spike-002)`. | spike 002 + user reply |
| 2026-05-17 | `vault-io` keeps its name. No rename. | user reply |
| 2026-05-17 | Bring `lattice-workspace` over as a **new** `workspace-io` package (sibling to `vault-io`). `vault-io` will depend on `workspace-io` for wiki bootstrap, mirroring how `lattice-wiki-core` depends on `lattice-workspace`. | user reply |
| 2026-05-17 | Skip the work-layer subsystem entirely. GSD covers work-item lifecycle. | user reply |
| 2026-05-17 | Skip restoring package-family monorepo support. Different approach planned. | user reply |
| 2026-05-17 | Adopt `.graph-wiki.yaml` manifest (port `lattice_workspace.manifest` as part of `workspace-io`). | user reply |
| 2026-05-17 | Ecosystem rebrand: every remaining `lattice` reference → `graph-wiki` (kebab) or `graph_wiki` (snake) as appropriate. | user reply |

## Revised Plan (post-spike-002)

Source locations (verified 2026-05-17):
- `/Users/pat/Personal/lattice/packages/lattice-workspace/` — Python pkg → source for M1
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/` — Python pkg → reference for M2 selective drift fixes
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/` — Claude Code plugin → M3 (deferred for own scoping)

Target layout in this repo (after the milestone):
- `packages/workspace-io/` — **new** package, port of `lattice-workspace`, rebranded to `graph-wiki`
- `packages/vault-io/` — stays. Depends on `workspace-io` for path/manifest/init concerns
- `agents/graph-wiki-agent/` — unchanged in structure; may need minor updates to consume `workspace-io` via vault-io
- `plugins/graph-wiki/` — populated in M3 (not in this milestone unless desired)

### M1 — Port `lattice-workspace` → `workspace-io` with `graph-wiki` rebrand

**Scope:**
- New workspace member: `packages/workspace-io/` with `pyproject.toml`, `src/workspace_io/`, `tests/`.
- Port the 8 source modules:
  - `config.py` (`LatticeConfig` → `GraphWikiConfig`, `resolve(cwd)` discovery)
  - `init.py` (workspace bootstrap: git init + manifest + `.gitignore`)
  - `manifest.py` (read/write — file becomes `.graph-wiki.yaml`)
  - `paths.py` (composed paths over a resolved workspace)
  - `render.py` (workspace `CLAUDE.md` rendering)
  - `schema.py` (work-item schema writer — keep if it has non-work-layer uses; drop if purely work-layer)
  - `versions.py` (asset-template drift warnings)
  - `assets/CLAUDE.md.template` (workspace template)
  - `_local_config.py` (local config reader)
- Rename across the port:
  - `LATTICE_WORKSPACE` env var → `GRAPH_WIKI_WORKSPACE`
  - `.lattice.yaml` manifest filename → `.graph-wiki.yaml`
  - All `LatticeConfig` / `lattice_*` symbols → `GraphWikiConfig` / `graph_wiki_*`
  - Module path `lattice_workspace.*` → `workspace_io.*`
- Update `vault-io/_workspace.py::resolve_wiki_and_repo` so it **delegates to** `workspace_io.config.resolve()` instead of the env-var-only stub. Keep the explicit-path argument override path (don't regress the MCP boundary contract).
- Tests: port `lattice-workspace/tests/`, rewrite imports + manifest filename expectations.

**Verify schema.py before porting.** If it only writes work-item schemas, drop it (we're skipping the work layer). If it writes anything else, keep it.

**Open questions:**
- Existing user-level config file: `~/Personal/wiki/deep-agents/wiki-config.toml` (from memory `project_wiki_setup`). Does it become `~/Personal/wiki/deep-agents/.graph-wiki.yaml`? Migration script needed if yes.
- Does the workspace bootstrap (`init.py`) also create the wiki tree, or only the workspace shell? If only shell, `vault-io.init_vault.init_wiki` still runs after to populate `wiki/`.

### M2 — Selective drift backport from `lattice-wiki-core` into `vault-io` + `graph-wiki` rebrand

**Scope — backport drift only for overlapping modules that have meaningful upstream changes:**

Per spike 002 §Investigation A, these are the candidates. For each, decide port-back or leave-alone:

| Module | Δ LOC | Status | Action |
|---|---|---|---|
| `git_state.py` | 0 | byte-identical | **leave** |
| `append_log.py` | +30 | vault-io is ahead (MCP lib-ification) | **leave**; upstream is older |
| `update_index.py` | +29 | vault-io is ahead (lib API) | **leave** |
| `update_tokens.py` | +6 | vault-io is ahead (no tiktoken) | **leave** |
| `ingest_work_item.py` | -1 | API divergence | Decide: vault-io's `file_work_item` lib shape vs lattice's `_run_helper` dispatcher. **Recommend leave** — vault-io's shape fits MCP. |
| `init_vault.py` | -15 | minor diff | **body-diff and decide.** Probably leave. |
| `lint/*` (8 files) | small | identical contracts | **body-diff per file**; backport substantive changes only. |
| `layout_io.py` | -98 | vault-io stripped `ensure_package_pages` | **leave** (we skipped package-family — user decision above) |
| `detect_containers.py` | -129 | vault-io stripped package-family helpers | **leave** (same reason) |
| `scan_monorepo.py` | -151 | vault-io stripped package-family helpers | **leave** (same reason) |
| `ingest_source.py` | -181 | vault-io is library-only (CLI moved to commands/) | **leave** — architectural choice |

**The ecosystem rebrand happens here too:**
- Grep `lattice` / `LATTICE` / `lattice_wiki_core` everywhere in `packages/vault-io/`, `agents/graph-wiki-agent/`, `.planning/`, `CLAUDE.md`.
- Rename to `graph-wiki` (kebab) or `graph_wiki` (snake) per context.
- Stale references already flagged: `.planning/spikes/CONVENTIONS.md` still says `cores/` (was renamed to `packages/`); `~/Personal/lattice/` paths in commit-history-only references can stay.

**Modules explicitly NOT ported:**
- Whole `work/` subsystem (per decision: GSD handles this)
- `archive_work.py`, `work_status.py`, `lint_work.py`, `regenerate_work_index.py` (same reason)
- `export_marp.py` (no Marp use case yet)
- `wiki_search.py` (already covered + improved in `commands/query.py`)
- `lint_wiki.py` (already covered in `commands/lint.py`)
- Package-family helpers in detect_containers/scan_monorepo/layout_io (user decision)

**Dependency:** after M1 (vault-io will use workspace-io's path/manifest API).

### M3 — Bring `lattice-wiki` plugin into `plugins/graph-wiki/` (deferred to own scoping)

**Status:** scope this in a follow-up `/gsd-spike` or `/gsd-spec-phase`. Pre-spike-002 capture below remains valid in shape; the rename targets are now `graph-wiki` (plugin id), `/graph-wiki:*` (command namespace), and plugin scripts must consume `vault-io` (which itself uses `workspace-io`).

**Open question carried forward:** what do the plugin's slash commands actually shell out to? Need to answer before committing this to the milestone.

### Cross-cutting

- **Naming consistency sweep:** at the end of M1 + M2, grep for `lattice`, `LATTICE`, `lattice_workspace`, `lattice_wiki_core` across `packages/`, `agents/`, `plugins/`, `.planning/`, `CLAUDE.md` — anything remaining is a bug.
- **Wiki self-update:** project's own wiki at `~/Personal/wiki/deep-agents` will need to absorb new package names and the new `.graph-wiki.yaml` manifest. Run a wiki scan after M1 + M2 land.
- **Spike findings:** `Skill("spike-findings-deep-agents")` is still the implementation blueprint for graph-wiki-agent itself; spike 002's drift map is the planning artifact for this milestone's port work.

## Migration Themes (superseded — kept for provenance)

> The original 5-theme breakdown below was superseded by the Revised Plan above after spike 002 + the 2026-05-17 decisions. Kept here so a future reader can see why the plan changed shape.

Source locations (verified 2026-05-17):
- `/Users/pat/Personal/lattice/packages/lattice-workspace/` — Python pkg (pyproject + src/tests)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/` — Python pkg (pyproject + src/tests)
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/` — Claude Code plugin (agents/commands/skills, `.claude-plugin/plugin.json`) — **not Python**

Target layout in this repo:
- `packages/vault-io/` → renamed to `packages/workspace-io/`
- `agents/graph-wiki-agent/` — existing target for wiki-core logic
- `plugins/` — currently empty; will host `plugins/graph-wiki/`

### T1 — Rename `vault-io` → `workspace-io` (rebrand step 1)

**Scope:** mechanical rename. Directory move, `pyproject.toml` `name`, all `from vault_io` imports, workspace member entry in root `pyproject.toml`, any references in `graph-wiki-agent` and in `.planning/`.

**Why first:** every later theme writes into this package. Renaming first avoids merging into a name that's about to change.

**Open questions:**
- Module name: `workspace_io` (snake_case) — confirm.
- Do we keep a transitional re-export shim, or hard-rename in one commit? Project is single-developer with no external consumers — hard-rename is cleaner.

### T2 — Merge `lattice-workspace` into `workspace-io` + ecosystem rebrand to `graph-wiki`

**Scope:**
- Port `lattice-workspace/src/` into `packages/workspace-io/src/workspace_io/` (folder this work post-T1).
- Drop the `lattice` prefix everywhere in code, docstrings, error messages.
- Rebrand ecosystem terminology `lattice` → `graph-wiki`.
- Rename config files: any `lattice-*.toml` or `lattice-*.yaml` → `graph-wiki-*.{toml,yaml}` (and update their schema validators / loaders).
- Tests: port `lattice-workspace/tests/` and rewrite imports.

**Dependency:** after T1.

**Open questions:**
- Are there config files at the *user* level (e.g., `~/Personal/wiki/deep-agents/wiki-config.toml` per the project_wiki_setup memory) that need renaming? If yes, ship a one-shot migration script and document the move.
- Does "rebrand" also apply to skill/command names exposed externally (e.g., `lattice-wiki:query` → `graph-wiki:query`)? — answered by T4 below, but worth aligning vocab now.
- Resolve overlapping functionality: `vault-io` already has its own implementation. Define the merge strategy per module (replace, merge field-by-field, or wrap).

### T3 — Migrate `lattice-wiki` + `lattice-wiki-core` changes into `graph-wiki-agent` and `workspace-io`

**Scope:**
- Port `lattice-wiki-core/src/` (the agent logic) into `agents/graph-wiki-agent/` where it belongs by responsibility; spill anything filesystem/vault-layer into `workspace-io`.
- This is "the spike findings, applied" — see `Skill("spike-findings-deep-agents")` for the implementation blueprint already gathered.
- Rebrand to `graph-wiki` terminology as you port (same rules as T2).

**Dependency:** after T2 (workspace-io must be settled before downstream code targets it).

**Open questions:**
- How much of `lattice-wiki-core` is already reimplemented in `graph-wiki-agent`? Need a diff/inventory pass before scoping the port — candidate for a dedicated `/gsd-spec-phase` ambiguity-scoring pass, or a short spike.
- Bedrock-only constraint: any `lattice-wiki-core` Anthropic-direct calls must be rewritten through `langchain-aws` (see `CLAUDE.md` Tech Stack §3).

### T4 — Bring `lattice-wiki` plugin into `deep-agents/plugins/graph-wiki/`

**Scope:**
- Copy `/Users/pat/Personal/lattice/plugins/lattice-wiki/` → `plugins/graph-wiki/`.
- Rename plugin id, slash command namespace (`/lattice-wiki:*` → `/graph-wiki:*`), agent names, skill names.
- Rewrite plugin scripts so vault I/O goes through `workspace-io` (post-rename).
- Update `.claude-plugin/plugin.json` metadata.

**Dependency:** after T2 (needs `workspace-io`) and T3 (needs core logic available for any plugin scripts that invoke it).

**Open questions:**
- Where do the plugin's slash commands shell out to? If they call the deep-agents CLI / MCP server, the contract surface needs to be locked before the plugin port. If they shell out to lattice CLIs, those calls must be rewritten.
- The plugin still ships as a Claude Code plugin at this stage — that's the v1 endpoint of T4. T5 is the optional follow-on.

**Open questions:**
- Does Pat want the plugin to remain Claude-Code-only, or run on Bedrock through the deep-agents CLI / MCP server?
- If (b): what's the host runtime — `deepagents` SubAgentMiddleware, a sibling agent under `agents/`, or a new top-level package?
- uv workspace mechanics for (a) are straightforward: add `plugins/graph-wiki/` as a workspace member with `uv_build` backend and a non-Python `data_files` block.

### Cross-cutting

- **Naming consistency sweep:** at the end of T1–T4, grep for `lattice`, `vault-io`, `vault_io` across `packages/`, `agents/`, `plugins/`, `.planning/`, `CLAUDE.md` — anything remaining is a bug.
- **Wiki self-update:** the project's own wiki at `~/Personal/wiki/deep-agents` will need to absorb the new package names. Run `/lattice-wiki:scan` (or its renamed successor) after T1+T2 land.
- **Spike findings already cover this surface:** `Skill("spike-findings-deep-agents")` is the implementation blueprint. Re-read it before planning T2/T3 to avoid relitigating decisions.
