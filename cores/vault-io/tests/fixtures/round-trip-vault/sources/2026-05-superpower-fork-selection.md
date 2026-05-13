---
title: "Superpowers Fork Selection: pcvelz/superpowers vs obra/superpowers"
category: source
summary: Concise comparison of the pcvelz/superpowers fork against obra/superpowers upstream — what changed (native TaskCreate/TaskUpdate/TaskList integration, slash-command entry points, opt-in hooks, renamed skill namespace), pros (real Claude Code integration, blockedBy dependency enforcement, plan-mode guardrails), and cons (drift cost, worktree-skill regression, vendor lock-in, brittle metadata channel, no release notes). Recommends the fork for Claude-Code-only users willing to accept divergence.
source_path: raw/articles/superpower-fork-selection.md
source_type: article
source_date: 2026-05
authors: []
ingested: 2026-05-10
updated: 2026-05-10
tags: [lattice-workflows, superpowers, fork, upstream, claude-code, task-management, hooks]
tokens: 1600
---

# Superpowers Fork Selection: pcvelz/superpowers vs obra/superpowers

## TL;DR

A side-by-side comparison of the `pcvelz/superpowers` fork (which `lattice-workflows` is itself forked from) against the upstream `obra/superpowers`. The fork makes a defensible Claude-Code-native bet — replacing markdown-checklist task tracking with native `TaskCreate`/`TaskUpdate`/`TaskList`, adding plan-mode guardrails, and shipping opt-in pre-commit and stop-deflection hooks — at the cost of substantial drift from upstream and loss of cross-CLI portability.

## Key claims

1. **What the fork adds** — `agents/code-reviewer.md` (local subagent), three slash commands (`brainstorm`, `write-plan`, `execute-plan`) wired to the renamed `superpowers-extended-cc:*` skills, `skills/shared/task-format-reference.md` (canonical task description schema with embedded ` ```json:metadata` fence), and two opt-in hooks (`pre-commit-check-tasks.sh`, `stop-deflection-guard.sh`).
2. **What the fork modifies** — `brainstorming`, `writing-plans`, `executing-plans`, `subagent-driven-development` and similar skills are rewritten to:
   - replace TodoWrite tracking with Claude Code v2.1.16+ native `TaskCreate`/`TaskUpdate`/`TaskList` (including `blockedBy` dependencies, `.tasks.json` persistence, cross-session resume)
   - add an explicit "MUST NOT call EnterPlanMode/ExitPlanMode" hard-gate (with `ExitPlanMode` → `AskUserQuestion` swap at handoff)
   - embed metadata as a ` ```json:metadata` fence inside task descriptions because `TaskGet` returns `description` but not the `metadata` parameter
   - rename the session-start hook and every skill cross-reference from `superpowers:*` to `superpowers-extended-cc:*`
3. **What the fork removes** — `assets/` and `RELEASE-NOTES.md`.
4. **Worktree-skill regression** — `using-git-worktrees` is rewritten to a simpler "check `.worktrees`/`worktrees`/`CLAUDE.md`/ask" directory-name heuristic, replacing upstream's `git rev-parse --git-dir` vs `--git-common-dir` detection with a submodule guard. The heuristic misidentifies isolation in any repo that doesn't follow that naming.
5. **Lineage matters** — `pcvelz/superpowers` itself is described as tracking `obra/superpowers` main, but the rename to `superpowers-extended-cc:*` plus inline native-task code makes upstream merges non-trivial. `lattice-workflows` sits one further hop downstream.

## Pros (the fork's value proposition)

- **Real CC integration.** `TaskCreate`/`TaskUpdate`/`TaskList` are genuine Claude Code tools that upstream explicitly scoped out for cross-platform reasons. The fork's value proposition is legitimate.
- **Dependency enforcement.** `blockedBy` makes "Task 2 can't start until Task 1 completes" mechanical rather than vibes-based — fixes a real failure mode where agents skip ahead.
- **Cross-session resume.** The `.tasks.json` + embedded ` ```json:metadata` pattern is a reasonable workaround for the documented `TaskGet`-doesn't-return-metadata quirk; lets a fresh subagent pick up mid-plan.
- **Plan-mode guardrails.** The hard "no EnterPlanMode/ExitPlanMode" rule addresses a known footgun: plan mode disables Write/Edit, which silently breaks any skill that needs to save artifacts mid-flow.
- **Hooks are well-scoped opt-ins.** Both shell hooks are off by default, fail-open, and parse the transcript defensively (e.g. the git-commit regex avoids matching `gh issue create --body "... git commit ..."`).

## Cons / risks

- **Drift cost.** Every modified skill is now substantially diverged from upstream. The README claim "tracks `obra/superpowers` main branch" is only true if the maintainer keeps merging, and the rename + inline native-task code makes those merges non-trivial.
- **Worktree skill regressed.** See key claim #4 — the directory-name heuristic is less robust than upstream's `git rev-parse`-based detection. Recorded as content (lineage note), not a wiki↔wiki contradiction.
- **Vendor lock-in.** Skills now hard-depend on `TaskCreate` etc. Run them under Codex / Gemini / OpenCode (which upstream supports) and they break, despite the README saying "core workflow remains compatible."
- **Brittle metadata channel.** Embedding ` ```json:metadata` in prose descriptions works, but a single agent that rewrites the description without preserving the fence loses the structured data silently. Upstream's plan-document-as-source-of-truth is harder to corrupt.
- **Stop-deflection hook is opinionated.** Fixed English phrase list against a 50% context threshold; false positives ("the next session of meetings") and easy to evade ("I'll continue tomorrow"). Enforces a workflow rule rather than catching a bug — more "preference enforcement" than safety.
- **No release notes.** Upstream ships `RELEASE-NOTES.md`; the fork removed it, so users updating the plugin don't see what changed.

## Bottom line

The fork makes a defensible bet: CC-native task management is meaningfully better than markdown checklists, and upstream won't absorb it. If you're a Claude-Code-only user willing to accept divergence from upstream, the task-tracking and plan-mode guardrails are real upgrades. If you switch between CC and other CLIs, or you want to ride upstream changes with low maintenance, stick with `obra/superpowers`.

## Touches

- [[wiki/plugins/lattice-workflows/lattice-workflows]]
- [[wiki/plugins/lattice-workflows/context]]
- [[wiki/concepts/superpowers-fork-vs-upstream]]
- [[wiki/adrs/0016-track-pcvelz-superpowers-fork]]

## Decisions triggered

- [[wiki/adrs/0016-track-pcvelz-superpowers-fork]] — track `pcvelz/superpowers` rather than `obra/superpowers` upstream

## Where it's cited in this wiki

- [[wiki/plugins/lattice-workflows/lattice-workflows]]
- [[wiki/plugins/lattice-workflows/context]]
- [[wiki/concepts/superpowers-fork-vs-upstream]]
- [[wiki/adrs/0016-track-pcvelz-superpowers-fork]]
