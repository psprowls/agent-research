---
title: lattice-workflows (plugin) — Patterns
category: package
summary: Key patterns and conventions for lattice-workflows
sources: 3
updated: 2026-05-10
tokens: 1358
---

# lattice-workflows (plugin) — Patterns

## Key patterns

- **Session-start hook injects `using-workflows` automatically** — `hooks/session-start` reads `skills/using-workflows/SKILL.md` and emits it as `hookSpecificOutput.additionalContext`, so every session begins with the bootstrap skill loaded without any user action.

- **Bash/cmd polyglot hook dispatcher** — `hooks/run-hook.cmd` locates bash on Windows and Unix and forwards to the named hook script. Hooks work cross-platform without extension-based dispatch or shell-specific wrappers.

- **Observability category gated by one opt-out env var** — `LATTICE_WORKFLOWS_OBSERVABILITY` (accepts `0`/`false`/`off`) gates every observability hook in the plugin; see [[wiki/concepts/lattice-workflows-observability-gate]]. Every observability hook is fail-open (exits 0 on any error). First adopter: `hooks/log-skill-invocation` (PreToolUse / matcher `"Skill"`), registered via `hooks/hooks.json`, logs JSON lines to `/tmp/workflows-skill-invocations.log`.

- **Consumer, not writer** (per [[wiki/concepts/lattice-workflows-consumption-seam]]) — workflows reads the wiki vault, queries the graph, reads the work-tracker sidecar. New work pages go through `${LATTICE_WIKI_ROOT}/scripts/ingest_work_item.py`, not direct vault edits. Status transitions are direct frontmatter edits (lower risk).

- **Five integration patterns, all shipping in 0.3.0** — pre-explore, grep replacement, work-item filing, prioritization, and status reporting. Pre-explore and grep replacement are skill-only (agent-time); the other three are slash commands (`/lattice-workflows:file-work-item`, `:next`, `:status`).

- **Shared `lib/` for cross-plugin invocation** (per [[wiki/concepts/lattice-cross-plugin-contract]]) — `lib/work_index.py` parses the work-tracker sidecar consumed by `:next` and `:status`; `lib/lattice_invoke.py` resolves `${LATTICE_WIKI_ROOT}` / `${LATTICE_WORK_ROOT}` and shells out to sibling-plugin scripts. Pattern: subprocess-not-import, env-var discovery, fail-soft on missing plugins.

- **Version bumps via `bump-version.sh` + `.version-bump.json`** — never edit version strings by hand. `--check` validates consistency; `--audit` scans for undeclared strings.

- **Specs and plans land in `<workspace>/{specs,plans}/`, not `docs/`** (per [[wiki/adrs/0013-plans-and-specs-in-lattice-workspace]]) — `brainstorming` writes to `<workspace>/specs/YYYY-MM-DD-<prefix>-<topic>-design.md`; `writing-plans` writes to `<workspace>/plans/YYYY-MM-DD-<prefix>-<feature-name>.md` plus a co-located `.tasks.json`. Workspace resolution is shared via `plugins/lattice-workflows/skills/shared/workspace-resolution.md`: shell out to `python -m lattice_workspace.config`, fall back to `Path("lattice").resolve()`, then assert `.lattice.yaml` exists or error out pointing at `/lattice-wiki:init`. Filename `<prefix>` is inferred from cwd/affected paths: `packages/<x>/` → `<x>`; `plugins/<x>/` → `<x>`; multi-container or repo-root → `Path(workspace).name`.

- **Opt-in example hooks** — `hooks/examples/` contains `pre-commit-check-tasks.sh` and `stop-deflection-guard.sh` which are NOT auto-registered. Users add them individually to `.claude/settings.local.json`.

- **Per-skill model selection** (per [[wiki/concepts/model-selection-per-skill]] and [[wiki/sources/2026-05-model-selection-guidelines]]) — most `plugins/lattice-workflows/skills/<skill>/SKILL.md` and `plugins/lattice-workflows/agents/<agent>.md` files declare a `model: opus|sonnet|haiku` frontmatter field. Sonnet is the default; Opus for open-ended / high-stakes work (`brainstorming`, `code-reviewer`); Haiku for mechanical routers / lookups (`pre-explore`, `prefer-graph-over-grep`). The dispatch layer honors the declaration; the field is independent of `subagent_type`. The `using-workflows` bootstrap skill intentionally omits `model:` because it runs in the caller's main loop and must not override the loop's model. Repo-walking / review work has progressively migrated from skills into agents (e.g. `code-reviewer`, `lattice-wiki:scanner`) so each unit pins its own model independent of its caller.

- **Execution-skill selection: plan-driven vs problem-driven** (per [[wiki/concepts/execution-skills-comparison]]) — `executing-plans` and `subagent-driven-development` are alternatives for executing a *written plan*: pick SDD for same-session work with quality gates (implementer → spec-compliance → code-quality), `executing-plans` for resumed/separate sessions. `dispatching-parallel-agents` is orthogonal — use it for independent problem sets (e.g. unrelated test failures), not for plan execution. The decision tree lives in `subagent-driven-development`'s SKILL.md; `executing-plans` defers to SDD when subagents are available.

## Conventions

- Skills are mandatory behavioral constraints, not suggestions — the `using-workflows` bootstrap makes this explicit at session start.
- Skill naming follows bare-name-first resolution: `writing-plans` and `subagent-driven-development` look up `<role>-<tech>` as a bare name first, then fall back to `lattice-experts:<role>-<tech>` as namespaced default if installed.
- Plugin is zero-dependency by design — no runtime package dependencies, making installation friction-free.
- Upstream changes from `obra/superpowers` are reconciled manually; `LICENSE` and `README` preserve attribution.
- Test fixtures and non-distributed assets belong outside the plugin dir — they would otherwise ship to users.
