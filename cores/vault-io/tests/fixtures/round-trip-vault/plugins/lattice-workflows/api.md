---
title: lattice-workflows (plugin) — API
category: package
summary: Slash commands, available skills, and public API surface for lattice-workflows
updated: 2026-05-10
sources: 3
tokens: 1225
---

# lattice-workflows (plugin) — API

## Public API

### Slash commands

| Command | Description |
|---|---|
| `/lattice-workflows:brainstorm` | Invokes `lattice-workflows:brainstorming`; must run before any creative or implementation work |
| `/lattice-workflows:write-plan` | Invokes `lattice-workflows:writing-plans`; creates a detailed implementation plan with bite-sized tasks |
| `/lattice-workflows:execute-plan` | Invokes `lattice-workflows:executing-plans`; executes a written plan in batches with review checkpoints |
| `/lattice-workflows:file-work-item` | Interactive: build frontmatter, optional `## Plan`, invoke `ingest_work_item.py`, regenerate work-index, append to log |
| `/lattice-workflows:next` | Read `<vault>/work-index.json`, rank `accepted` first then high-severity `open`, tie-break by `updated:` (oldest first), cap 10. Args: `--kind`, `--severity`, `--package`, `--limit`, `--json` |
| `/lattice-workflows:status` | Read sidecar's `counts` block plus `in-progress` items and stuck-open / stuck-accepted call-outs |

### Skills

Skills are triggered contextually and are namespaced `lattice-workflows:<skill>`. Most skill `SKILL.md` files carry a `model: opus|sonnet|haiku` frontmatter field that the dispatch layer honors when spawning the work — Sonnet is the default; Opus for open-ended/high-stakes skills (`brainstorming`); Haiku for mechanical lookups (`pre-explore`, `prefer-graph-over-grep`). See [[wiki/concepts/model-selection-per-skill]] for the rubric. Agents in `agents/` (e.g. `code-reviewer`) carry the same field. The `using-workflows` bootstrap skill intentionally omits `model:` — it runs in the caller's main loop and must not override the loop's model.

**Inherited from upstream (obra/superpowers):**
- `using-workflows` — bootstrapped at session start via `SessionStart` hook; establishes skill-first conventions
- `brainstorming` — Socratic design dialogue; 2-3 approaches proposed; design approval required before implementation. Writes the approved spec to `<workspace>/specs/YYYY-MM-DD-<prefix>-<topic>-design.md`; requires `<workspace>/.lattice.yaml` to exist or hard-fails per [[wiki/adrs/0013-plans-and-specs-in-lattice-workspace]].
- `writing-plans` — detailed, no-placeholder implementation plans with native task integration. Writes to `<workspace>/plans/YYYY-MM-DD-<prefix>-<feature-name>.md` plus a co-located `.tasks.json`; same workspace resolution + hard-fail rules as `brainstorming`.
- `executing-plans` — sequential, single-agent execution of a written plan in a *resumed/separate* session; restores task state from `.tasks.json`. Prefer `subagent-driven-development` when subagents are available and you're staying in the current session. See [[wiki/concepts/execution-skills-comparison]].
- `test-driven-development` — RED-GREEN-REFACTOR cycle; use before writing implementation code
- `systematic-debugging` — four-phase root-cause debugging; use before proposing fixes
- `subagent-driven-development` — same-session execution of a written plan with a per-task fresh-subagent pipeline (implementer → spec-compliance reviewer → code-quality reviewer). Tasks still run serially. See [[wiki/concepts/execution-skills-comparison]].
- `dispatching-parallel-agents` — concurrent subagent dispatch across independent problems (e.g. "6 failing tests across 3 unrelated subsystems"); orthogonal to plan execution — no plan, no `.tasks.json`, no `blockedBy`. See [[wiki/concepts/execution-skills-comparison]].
- `requesting-code-review` — dispatches code review between tasks via `code-reviewer` subagent
- `receiving-code-review` — processes incoming feedback with technical rigour; no blind implementation
- `finishing-a-development-branch` — branch completion: verify tests, present merge/PR/keep/discard options, clean up worktree
- `verification-before-completion` — evidence-before-claims: run the command, read output, then make the claim
- `using-git-worktrees` — isolated git worktrees with smart directory selection and safety verification
- `writing-skills` — creates and tests new skills following TDD-for-documentation principles

**Lattice-aware additions:**
- `pre-explore` — reads `<vault>/index.md` and relevant package pages before grep/Read storms
- `prefer-graph-over-grep` — substitutes `cg_callers` / `cg_callees` / `cg_find` / `cg_describe_package` for common grep loops when `lattice-graph` is installed
- `file-work-item` — files structured work pages into the lattice workspace `work/` directory

## CLI

The plugin ships no standalone CLI binary. All commands are accessed through the Claude Code slash-command interface (`/lattice-workflows:<command>`) or via the Skill tool (`lattice-workflows:<skill>`).

The `scripts/bump-version.sh` script is a developer/release tool, not a user-facing CLI:
- `--check` mode: validates version consistency across declared files
- `--audit` mode: scans for undeclared version strings in the repo
