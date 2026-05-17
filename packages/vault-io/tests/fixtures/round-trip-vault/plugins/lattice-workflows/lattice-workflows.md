---
title: lattice-workflows
category: package
summary: Engineering-discipline framework for Claude Code — skills, hooks, task gates, and methodology; forked from obra/superpowers via pcvelz/superpowers.
status: active
package_path: plugins/lattice-workflows
package_type: plugin
domain:
language: Markdown/Python
depends_on: []
tags: [plugin, claude-code, workflows, skills, tdd, debugging, hooks]
sources: 4
updated: 2026-05-11
last_sync_commit: 1e59687bc06b8b89b7480d866e3dab882a2381b6
last_sync_at: 2026-05-11
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 2013
---

# lattice-workflows

## Purpose

`lattice-workflows` ships an engineering-discipline framework for Claude Code: a library of [[wiki/concepts/lattice-workflows-consumption-seam|workflow skills]] covering planning, brainstorming, test-driven development, systematic debugging, code review, parallel agent dispatch, and branch lifecycle management, plus a hooks layer and slash commands that wire those skills into every session. It is used by developers who want Claude to follow a structured process rather than improvising — mandatory gates enforce brainstorming before implementation, TDD before production code, and root-cause investigation before fixes. The plugin exists to provide the process discipline that guides how Claude approaches tasks: the skills are not suggestions but behavioral constraints that shape every session from startup (via the `SessionStart` hook that injects `using-workflows`) through delivery (via `finishing-a-development-branch`). It is a Claude Code-native fork of `obra/superpowers` via `pcvelz/superpowers`, extending the upstream core with native task management, structured task metadata, and a pre-commit task gate.

## File map

- `.claude-plugin/plugin.json` — plugin manifest: name, version, description, author, license, keywords, and the `LATTICE_WORKFLOWS_ROOT` env var binding
- `CLAUDE.md` — Claude Code contributor and developer guidance, including layout, conventions, and PR requirements
- `LICENSE` — MIT license (preserving upstream obra/superpowers attribution)
- `README.md` — installation, workflow overview, feature comparison, and configuration reference

### hooks/
Hook scripts and registration manifest; dispatched through the polyglot `run-hook.cmd` wrapper so they work on both Unix and Windows.

- `hooks.json` — registers the `SessionStart` (inject `using-workflows`) and `PreToolUse:Skill` (log invocation) hooks
- `log-skill-invocation` — `PreToolUse` hook: appends a JSON-Lines record to `/tmp/workflows-skill-invocations.log` whenever the Skill tool is called; exits 0 on any error (observability, fail-open)
- `run-hook.cmd` — bash/cmd polyglot dispatcher: locates bash on Windows and Unix and forwards to the named hook script
- `session-start` — `SessionStart` hook: reads `skills/using-workflows/SKILL.md` and emits it as `hookSpecificOutput.additionalContext` to inject the bootstrap skill at session start
- `watch-transcript` — hook that watches the session transcript for observability signals
- `README.md` — documents active hooks, the `LATTICE_WORKFLOWS_OBSERVABILITY` env-var gate, conventions for adding new hooks, and the fail-open rule
- `examples/pre-commit-check-tasks.sh` — opt-in `PreToolUse:Bash` hook that blocks `git commit` when a native task is `in_progress`
- `examples/stop-deflection-guard.sh` — opt-in `Stop`-event hook that blocks context-full deflections when actual usage is below 50%

### lib/
Python library modules shared by commands and skills; added to `sys.path` via `CLAUDE_PLUGIN_ROOT`.

- `work_index.py` — read-only parser for `<vault>/work-index.json` (the `lattice-work` sidecar): `WorkIndex`, `WorkItem` dataclasses, `ranked_for_next`, `in_progress`, `stale` queries, and a `load()` convenience wrapper

### commands/
Slash command definitions; each is a thin wrapper that invokes the corresponding skill or implements a work-surface query.

- `brainstorm.md` — invokes `lattice-workflows:brainstorming`; must run before any creative or implementation work
- `execute-plan.md` — invokes `lattice-workflows:executing-plans`; executes a written plan in batches with review checkpoints
- `file-work-item.md` — interactive form for filing a structured work page into the lattice workspace `work/` directory
- `next.md` — shows the top-N prioritised work items from the `work-index.json` sidecar; degrades gracefully when `lattice-work` is absent
- `status.md` — reports overall work-surface status (counts, in-flight, stuck-open items) from the `work-index.json` sidecar
- `write-plan.md` — invokes `lattice-workflows:writing-plans`; creates a detailed implementation plan with bite-sized tasks

### agents/
Subagent definitions dispatched by skills during review phases.

- `code-reviewer.md` — senior code reviewer subagent: verifies working directory and branch, then works through five review dimensions (plan alignment, code quality, architecture and design, testing, production readiness) and emits a structured report with Strengths / Issues (Critical / Important / Minor) / Assessment sections

### skills/
One subdirectory per skill; each contains a `SKILL.md` frontmatter-driven prompt and optional supporting files.

- `using-workflows/SKILL.md` — bootstrap skill injected at session start; establishes skill-first conventions
- `brainstorming/SKILL.md` — explores user intent, requirements, and design before implementation; requires design approval before writing plans
- `writing-plans/SKILL.md` — produces detailed, no-placeholder implementation plans with native task integration
- `executing-plans/SKILL.md` — batch-executes a written plan in a separate session with review checkpoints
- `test-driven-development/SKILL.md` — RED-GREEN-REFACTOR cycle; use before writing implementation code
- `systematic-debugging/SKILL.md` — four-phase root-cause debugging; use before proposing fixes
- `subagent-driven-development/SKILL.md` — executes plans via per-task fresh subagents with two-stage review
- `dispatching-parallel-agents/SKILL.md` — concurrent subagent dispatch across independent problem domains
- `requesting-code-review/SKILL.md` — dispatches the `code-reviewer` subagent via Agent tool (inline prompt, no external template file); when and how to request review, how to act on feedback
- `receiving-code-review/SKILL.md` — processes incoming code review feedback with technical rigour
- `finishing-a-development-branch/SKILL.md` — guides branch completion: verify tests, present merge/PR/keep/discard options
- `verification-before-completion/SKILL.md` — enforces evidence-before-claims before committing or creating PRs
- `using-git-worktrees/SKILL.md` — creates isolated git worktrees with smart directory selection and safety verification
- `writing-skills/SKILL.md` — creates and tests new skills following TDD-for-documentation principles
- `pre-explore/SKILL.md` — reads wiki narrative context before any grep or file-search storm
- `prefer-graph-over-grep/SKILL.md` — substitutes targeted code-graph queries for grep loops when `lattice-graph` is installed
- `file-work-item/SKILL.md` — files structured work pages into the lattice workspace `work/` directory
- `shared/task-format-reference.md` — canonical task description template and metadata schema shared across planning/execution skills

## Sub-pages

- [[wiki/plugins/lattice-workflows/api]]      — slash commands, available skills, and public API surface
- [[wiki/plugins/lattice-workflows/patterns]] — key patterns, conventions, and downstream consumers
- [[wiki/plugins/lattice-workflows/work]]     — bugs, tech debt, features, open questions
- [[wiki/plugins/lattice-workflows/context]]  — concepts, decisions, and ingested sources

## Appears in sources

- [[wiki/sources/2026-05-execution-skills-comparison]] — disambiguates `executing-plans`, `subagent-driven-development`, and `dispatching-parallel-agents`; synthesized into [[wiki/concepts/execution-skills-comparison]].
- [[wiki/sources/2026-05-model-selection-guidelines]] — three-tier rubric (Opus / Sonnet / Haiku) for per-skill / per-agent model selection via `model:` frontmatter; synthesized into [[wiki/concepts/model-selection-per-skill]]. Flags a code-side gap: `code-scanner` is referenced in the rubric but does not exist in the codebase.
- [[wiki/sources/2026-05-superpower-fork-selection]] — side-by-side comparison of `pcvelz/superpowers` vs `obra/superpowers`; synthesized into [[wiki/concepts/superpowers-fork-vs-upstream]] and the decision recorded as [[wiki/adrs/0016-track-pcvelz-superpowers-fork]].
