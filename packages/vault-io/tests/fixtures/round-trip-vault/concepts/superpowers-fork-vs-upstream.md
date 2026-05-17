---
title: superpowers fork vs upstream (pcvelz/superpowers vs obra/superpowers)
category: concept
summary: Comparison of the pcvelz/superpowers fork against obra/superpowers upstream, plus the lineage that ties lattice-workflows to both. The fork swaps markdown-checklist task tracking for Claude Code's native TaskCreate/TaskUpdate/TaskList, adds slash-command entry points and opt-in hooks, and renames every skill cross-reference to superpowers-extended-cc:*; it gains real CC integration and blockedBy dependency enforcement at the cost of cross-CLI portability and merge-back friction.
tags: [lattice-workflows, superpowers, fork, upstream, claude-code, task-management, comparison]
sources: 1
updated: 2026-05-10
tokens: 1975
---

# superpowers fork vs upstream (pcvelz/superpowers vs obra/superpowers)

## Definition

Two engineering-discipline frameworks share a name and a core skill library, but diverge on task-management substrate, plan-mode handling, and CLI portability:

- **`obra/superpowers`** — the upstream maintained by `obra`. Markdown-checklist task tracking. Cross-CLI compatible (Claude Code, Codex, Gemini, OpenCode). Ships `RELEASE-NOTES.md`. Uses `git rev-parse --git-dir` vs `--git-common-dir` (with submodule guard) for worktree detection.
- **`pcvelz/superpowers`** — the Claude-Code-native fork. Replaces TodoWrite with native `TaskCreate`/`TaskUpdate`/`TaskList` (CC v2.1.16+) including `blockedBy` dependencies, `.tasks.json` persistence, and cross-session resume. Renames every skill from `superpowers:*` to `superpowers-extended-cc:*`. Adds opt-in `pre-commit-check-tasks.sh` and `stop-deflection-guard.sh` hooks plus a local `code-reviewer` subagent.

[[wiki/plugins/lattice-workflows/lattice-workflows]] is itself a further-downstream fork of `pcvelz/superpowers` (see lineage below).

## Lineage

```
obra/superpowers  (upstream — cross-CLI; markdown checklists)
        │
        │  fork — replace task substrate, rename namespace,
        │         add CC-native hooks
        ▼
pcvelz/superpowers  (Claude-Code-native; superpowers-extended-cc:*)
        │
        │  fork — vendor into lattice ecosystem; integrate with
        │         workspace, wiki, graph, work-tracker seams
        ▼
lattice-workflows  (this repo — plugins/lattice-workflows)
```

Each downward hop is a substantive rewrite, not just a rename:

- **`obra` → `pcvelz`** introduces `TaskCreate`/`TaskUpdate`/`TaskList`, the embedded ` ```json:metadata` fence (because `TaskGet` does not return the `metadata` parameter), the "MUST NOT call EnterPlanMode/ExitPlanMode" hard-gate (with `ExitPlanMode` → `AskUserQuestion` swap), the directory-name worktree heuristic (a known regression — see below), and the `superpowers:*` → `superpowers-extended-cc:*` rename across the session-start hook and every skill cross-reference.
- **`pcvelz` → `lattice-workflows`** keeps the CC-native substrate but adapts to the lattice ecosystem: workspace-aware hooks, the [[wiki/concepts/lattice-workflows-consumption-seam|consumption seam]] over wiki/graph/work, the [[wiki/concepts/lattice-workflows-observability-gate|observability gate]], and ecosystem-specific commands like `:next` and `:status` over the `lattice-work` sidecar.

## Shape

| Aspect | `obra/superpowers` (upstream) | `pcvelz/superpowers` (fork) |
|---|---|---|
| Task tracking | TodoWrite / markdown checklists | Native `TaskCreate`/`TaskUpdate`/`TaskList` (CC v2.1.16+) |
| Dependency enforcement | Vibes-based ("task 2 follows task 1") | Mechanical via `blockedBy` |
| Cross-session resume | Re-read the plan document | `.tasks.json` + embedded ` ```json:metadata` fence |
| Plan-mode handling | Skills may call `EnterPlanMode`/`ExitPlanMode` | Hard-gated; `ExitPlanMode` → `AskUserQuestion` at handoff |
| Slash commands | (none from upstream) | `brainstorm`, `write-plan`, `execute-plan` |
| Code-reviewer subagent | (relied on user-supplied) | `agents/code-reviewer.md` ships in-tree |
| Opt-in hooks | (none) | `pre-commit-check-tasks.sh`, `stop-deflection-guard.sh` |
| Worktree detection | `git rev-parse --git-dir` vs `--git-common-dir` + submodule guard | Directory-name heuristic (`.worktrees` / `worktrees` / `CLAUDE.md` / ask) — known regression |
| Skill namespace | `superpowers:*` | `superpowers-extended-cc:*` |
| `RELEASE-NOTES.md` | Shipped | Removed |
| Cross-CLI portability | Claude Code + Codex + Gemini + OpenCode | Claude Code only (hard-depends on `TaskCreate`) |

### Known regression: worktree detection

Upstream's `using-git-worktrees` skill detects existing-worktree state via `git rev-parse --git-dir` vs `--git-common-dir` with a submodule guard — a robust, naming-agnostic check. The fork replaces that with a directory-name heuristic that looks for `.worktrees` / `worktrees` and falls back to asking. This misidentifies isolation in any repo that does not follow that naming. Recorded here as a content note on the fork's tradeoff surface, not as a wiki↔wiki contradiction — the fork's own README acknowledges the divergence.

### Brittle metadata channel

`TaskGet` returns `description` but not the `metadata` parameter, so the fork embeds metadata as a ` ```json:metadata` fence inside the task description. A single agent that rewrites the description without preserving the fence loses the structured data silently. Upstream's plan-document-as-source-of-truth is harder to corrupt because the canonical state lives in a versioned file outside the task object.

## Decision criteria

Pick **`pcvelz/superpowers`** (or its lattice-workflows descendant) when:

- You're a Claude-Code-only user.
- You want `blockedBy` enforcement so a fresh subagent cannot skip a dependency.
- You want cross-session resume via `.tasks.json` (not re-parsing a plan document).
- You want the plan-mode hard-gate (avoids the silent Write/Edit-disabled footgun).
- You accept the worktree-detection regression and the loss of `RELEASE-NOTES.md` visibility.

Pick **`obra/superpowers`** (upstream) when:

- You switch between Claude Code and other CLIs (Codex, Gemini, OpenCode).
- You want low-maintenance upstream tracking (the fork's drift makes merges non-trivial).
- You rely on the robust `git rev-parse`-based worktree detection.
- You depend on `RELEASE-NOTES.md` to track what changed between versions.

`lattice-workflows` has already committed to the fork — see [[wiki/adrs/0016-track-pcvelz-superpowers-fork]] for the recorded decision and its revisit triggers.

## Used in

- [[wiki/plugins/lattice-workflows/lattice-workflows]] — the lattice fork of `pcvelz/superpowers`; the LICENSE and README preserve attribution back to `obra/superpowers`.
- [[wiki/plugins/lattice-workflows/context]] — lists `obra/superpowers` and `pcvelz/superpowers` under "Related dependencies".

## Related patterns

- [[wiki/concepts/execution-skills-comparison]] — `executing-plans` vs `subagent-driven-development` vs `dispatching-parallel-agents`; all three are downstream consumers of whichever superpowers substrate is in use.
- [[wiki/concepts/lattice-workflows-consumption-seam]] — how `lattice-workflows` consumes the rest of the lattice ecosystem (wiki, graph, work).
- [[wiki/concepts/shape-a-vs-shape-b]] — another `<a>-vs-<b>` comparison covering team-layout choices inside `lattice-workflows`.

## Sources

- [[wiki/sources/2026-05-superpower-fork-selection]]

## Open questions / gotchas

- The fork's README claim "tracks `obra/superpowers` main branch" is only as true as the maintainer's last merge — confirm currency before relying on upstream parity.
- The worktree-detection regression is the most concrete reason a non-`.worktrees`-naming repo might want to override the fork's `using-git-worktrees` skill locally.
- If Claude Code ever exposes a richer `TaskGet` (returning the `metadata` parameter natively), the brittle ` ```json:metadata` fence becomes obsolete — a revisit trigger for [[wiki/adrs/0016-track-pcvelz-superpowers-fork]].
