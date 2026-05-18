---
slug: next-milestone-planning
title: next-milestone-planning
status: open
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
- Current milestone: v1 of `code-wiki-agent` (Bedrock-hosted port of lattice-wiki).
- Most recent commits indicate Phase 9 gap-closure verified; `cores/` renamed to `packages/`.
- Tech stack locked: `uv` workspace, Python 3.11+, deepagents 0.6.1, langchain-aws 1.4.6, mcp 1.27.1, deepeval 4.0.0, typer 0.25.1. See `CLAUDE.md` for full table.
- Wiki vault for this project: `~/Personal/wiki/deep-agents` (Qwen3-32B fan-out, Qwen3-80B synthesis).

## References

- `CLAUDE.md` — locked stack and constraints
- `.planning/ROADMAP.md` — current milestone phases (do NOT edit from this thread)
- `Skill("spike-findings-deep-agents")` — implementation blueprint and proven patterns
- `~/Personal/wiki/deep-agents` — wiki for cross-reference

## Next Steps

1. Pressure-test the five migration themes captured below (especially the dependency ordering and the plugin-as-Python-package question).
2. Wait for the other session to confirm `/gsd-complete-milestone` finished.
3. Then run `/gsd-new-milestone`, decide phase split (one big rebrand+merge phase, or split T1+T2 from T3+T4), and break each theme into a phase via `/gsd-phase`.
4. `/gsd-spec-phase` and `/gsd-plan-phase` per phase. Heavy file-move work benefits from a written plan before execution.

## Migration Themes for Next Milestone

Source locations (verified 2026-05-17):
- `/Users/pat/Personal/lattice/packages/lattice-workspace/` — Python pkg (pyproject + src/tests)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/` — Python pkg (pyproject + src/tests)
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/` — Claude Code plugin (agents/commands/skills, `.claude-plugin/plugin.json`) — **not Python**

Target layout in this repo:
- `packages/vault-io/` → renamed to `packages/workspace-io/`
- `agents/code-wiki-agent/` — existing target for wiki-core logic
- `plugins/` — currently empty; will host `plugins/graph-wiki/`

### T1 — Rename `vault-io` → `workspace-io` (rebrand step 1)

**Scope:** mechanical rename. Directory move, `pyproject.toml` `name`, all `from vault_io` imports, workspace member entry in root `pyproject.toml`, any references in `code-wiki-agent` and in `.planning/`.

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

### T3 — Migrate `lattice-wiki` + `lattice-wiki-core` changes into `code-wiki-agent` and `workspace-io`

**Scope:**
- Port `lattice-wiki-core/src/` (the agent logic) into `agents/code-wiki-agent/` where it belongs by responsibility; spill anything filesystem/vault-layer into `workspace-io`.
- This is "the spike findings, applied" — see `Skill("spike-findings-deep-agents")` for the implementation blueprint already gathered.
- Rebrand to `graph-wiki` terminology as you port (same rules as T2).

**Dependency:** after T2 (workspace-io must be settled before downstream code targets it).

**Open questions:**
- How much of `lattice-wiki-core` is already reimplemented in `code-wiki-agent`? Need a diff/inventory pass before scoping the port — candidate for a dedicated `/gsd-spec-phase` ambiguity-scoring pass, or a short spike.
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

### T5 — (Consider) Make the plugin a first-class Python package in the uv workspace

**Status:** exploratory. Not a commitment. Worth a `/gsd-spike` before committing to a phase.

**Architectural question:** the plugin today is markdown + JSON config (agents/commands/skills) — there is no Python to compile. Two interpretations:

**(a) Package the plugin assets** — bundle the markdown/JSON tree as a distributable wheel that installs into Claude Code's plugin path (or analogous deep-agents loader). Mechanical packaging exercise; minimal architectural change. The "package" is essentially `data_files` + a tiny installer entry point.

**(b) Reimplement the plugin as Python code** that the deep-agents MCP server / CLI loads as runnable agent logic. This is a re-architecture: the plugin stops being Claude-Code-shaped and becomes a Python module that can be invoked from any MCP host. Aligns with the project's Bedrock-only, MCP-first thesis.

**Recommended next move:** a small spike to compare (a) vs (b) against the project's "run on Bedrock at lower cost" core value. If the plugin is only ever consumed via Claude Code, (a) is enough. If it should be invokable from the DeepAgents CLI on Bedrock too, (b) is required.

**Open questions:**
- Does Pat want the plugin to remain Claude-Code-only, or run on Bedrock through the deep-agents CLI / MCP server?
- If (b): what's the host runtime — `deepagents` SubAgentMiddleware, a sibling agent under `agents/`, or a new top-level package?
- uv workspace mechanics for (a) are straightforward: add `plugins/graph-wiki/` as a workspace member with `uv_build` backend and a non-Python `data_files` block.

### Cross-cutting

- **Naming consistency sweep:** at the end of T1–T4, grep for `lattice`, `vault-io`, `vault_io` across `packages/`, `agents/`, `plugins/`, `.planning/`, `CLAUDE.md` — anything remaining is a bug.
- **Wiki self-update:** the project's own wiki at `~/Personal/wiki/deep-agents` will need to absorb the new package names. Run `/lattice-wiki:scan` (or its renamed successor) after T1+T2 land.
- **Spike findings already cover this surface:** `Skill("spike-findings-deep-agents")` is the implementation blueprint. Re-read it before planning T2/T3 to avoid relitigating decisions.
