---
title: "ADR-0016: Track pcvelz/superpowers rather than obra/superpowers upstream"
category: adr
summary: lattice-workflows tracks pcvelz/superpowers as its upstream rather than obra/superpowers. The fork's Claude-Code-native task substrate (TaskCreate/TaskUpdate/TaskList, blockedBy, .tasks.json cross-session resume), plan-mode hard-gate, and opt-in pre-commit/stop-deflection hooks are worth the cost of cross-CLI portability loss, worktree-detection regression, and non-trivial merge-back to obra/.
adr_id: "0016"
status: accepted
decision_date: 2026-05-10
deciders: [Patrick Sprowls]
supersedes: []
superseded_by:
tags: [lattice-workflows, superpowers, fork, upstream, claude-code, task-management]
updated: 2026-05-10
tokens: 1963
---

# ADR-0016: Track pcvelz/superpowers rather than obra/superpowers upstream

**Status:** accepted (2026-05-10)

## Context

[[wiki/plugins/lattice-workflows/lattice-workflows]] is descended from `obra/superpowers` (the original engineering-discipline framework) via the `pcvelz/superpowers` fork. The two upstreams diverge substantively, not cosmetically — see [[wiki/concepts/superpowers-fork-vs-upstream]] for the full lineage diagram, comparison table, and decision rubric.

The choice of which upstream to track is consequential because every skill rewrite, hook, and slash command lattice-workflows inherits flows from that decision:

- `obra/superpowers` keeps cross-CLI portability (Claude Code, Codex, Gemini, OpenCode), markdown-checklist task tracking, robust `git rev-parse`-based worktree detection, and `RELEASE-NOTES.md`.
- `pcvelz/superpowers` replaces TodoWrite with Claude Code's native `TaskCreate`/`TaskUpdate`/`TaskList` (CC v2.1.16+), adds `blockedBy` dependency enforcement, persists state to `.tasks.json` for cross-session resume, embeds metadata as a ` ```json:metadata` fence inside task descriptions, hard-gates `EnterPlanMode`/`ExitPlanMode` (swapping to `AskUserQuestion` at handoff), and ships opt-in `pre-commit-check-tasks.sh` and `stop-deflection-guard.sh` hooks plus a local `code-reviewer` subagent. It renames the namespace to `superpowers-extended-cc:*` and removes `RELEASE-NOTES.md`.

Full background and the side-by-side trade-off table are in [[wiki/sources/2026-05-superpower-fork-selection]].

## Decision

`lattice-workflows` tracks **`pcvelz/superpowers`** as its upstream. The `LICENSE` and `README` preserve attribution to `obra/superpowers` (the originating project) per MIT requirements, but ongoing skill changes, hook design, and task-substrate evolution follow the `pcvelz` fork.

Concretely:

- The native `TaskCreate`/`TaskUpdate`/`TaskList` substrate (with `blockedBy` and `.tasks.json` resume) is the canonical task-tracking model for every lattice-workflows skill.
- The "MUST NOT call `EnterPlanMode`/`ExitPlanMode`" hard-gate stays in.
- The `superpowers-extended-cc:*` namespace pattern is preserved (lattice's own skills live under `lattice-workflows:*`, but cross-references to the fork's skill set keep that namespace).
- Lattice is implicitly Claude-Code-only for the workflows plugin. Codex / Gemini / OpenCode portability is **not** a goal for this plugin.

## Consequences

**Positive:**

- **Real dependency enforcement.** `blockedBy` makes "task 2 cannot start until task 1 completes" mechanical, not vibes-based. Closes a real failure mode where agents skip ahead.
- **Cross-session resume.** A fresh subagent can pick up mid-plan by reading `.tasks.json` rather than re-parsing a plan document.
- **Plan-mode guardrail.** The hard-gate avoids the documented footgun where plan mode silently disables Write/Edit and breaks any skill that needs to save artifacts mid-flow.
- **Opt-in hooks shipped.** `pre-commit-check-tasks.sh` (blocks `git commit` while a task is `in_progress`) and `stop-deflection-guard.sh` (blocks fresh-session deflections under 50% context) are off by default, fail-open, and parse the transcript defensively.
- **Aligned with the rest of the ecosystem.** [[wiki/concepts/lattice-workflows-consumption-seam]], the curator's `stage-tracker.mjs` `PreToolUse:Skill` hook, and the workspace-aware seams all already assume Claude Code as the runtime.

**Negative:**

- **No cross-CLI portability.** Anyone running these skills under Codex / Gemini / OpenCode hits a wall — `TaskCreate` etc. simply don't exist there. Lattice does not paper over this; users who want cross-CLI workflows should adopt `obra/superpowers` directly.
- **Drift cost from upstream.** Every modified skill is substantially diverged from `obra/superpowers`. The fork's claim "tracks `obra/superpowers` main" is only as true as `pcvelz`'s last merge.
- **Worktree-detection regression.** The fork's `using-git-worktrees` skill uses a directory-name heuristic (`.worktrees` / `worktrees` / `CLAUDE.md` / ask) rather than upstream's `git rev-parse --git-dir` vs `--git-common-dir` check. Misidentifies isolation in repos that don't follow that naming. Lattice inherits the regression; concrete enough to warrant a local override if a non-`.worktrees`-naming repo adopts the plugin.
- **No `RELEASE-NOTES.md`.** The fork removed it. Lattice users tracking what changed between plugin versions rely on git log and ADRs.
- **Brittle metadata channel.** Embedded ` ```json:metadata` is rewritten silently if an agent edits the description without preserving the fence.

## Alternatives considered

- **Track `obra/superpowers` directly.** Rejected: we lose `blockedBy`, native task state, cross-session resume, and the plan-mode hard-gate — all of which materially improve agent reliability. Cross-CLI portability is not a current goal for the workflows plugin.
- **Maintain a separate lattice fork that re-merges `obra/superpowers` periodically and re-applies the CC-native patches.** Rejected: the maintenance cost replicates `pcvelz`'s work without producing different output. Better to let `pcvelz` carry that load and pull from there.
- **Adopt `pcvelz/superpowers` without preserving the lineage in attribution.** Rejected: MIT attribution requires the upstream chain be preserved, and the `obra/superpowers` lineage is genuinely informative to users debugging skill behavior.

## Impact

- [[wiki/plugins/lattice-workflows/lattice-workflows]] — the plugin's identity is "Claude-Code-native fork of `pcvelz/superpowers`"; the description and `## Purpose` already say so.
- [[wiki/plugins/lattice-workflows/context]] — lists both `obra/superpowers` and `pcvelz/superpowers` under Related dependencies with the lineage made explicit.
- [[wiki/concepts/superpowers-fork-vs-upstream]] — the comparison concept this ADR rests on.

## Revisit triggers

Reopen this ADR if any of the following hold:

- **Claude Code exposes a richer `TaskGet`** that returns the `metadata` parameter natively. The brittle ` ```json:metadata` fence becomes obsolete; the fork's main metadata-channel hack disappears; the obra-vs-pcvelz delta narrows.
- **Upstream `obra/superpowers` adopts native task management.** The maintainer has scoped this out for cross-platform reasons; if that posture changes, lattice should re-evaluate.
- **Cross-CLI portability becomes a goal for the workflows plugin.** Today it is explicitly not; if Codex / Gemini / OpenCode users become a target audience, the fork's TaskCreate dependency forces a rethink.
- **`pcvelz/superpowers` stops merging upstream.** If the fork drifts far enough that "tracks `obra/superpowers` main" is no longer even directionally true, lattice may need to take direct ownership or migrate.
- **The worktree-detection regression bites a real user.** A user reports `using-git-worktrees` mis-detecting isolation in a non-`.worktrees`-naming repo. Either contribute a fix upstream-of-lattice or override the skill locally.

## Follow-ups

- Watch the `pcvelz/superpowers` merge cadence relative to `obra/superpowers`; if it stalls, surface that on `lattice-workflows`' work surface.
- If Claude Code releases a richer `TaskGet`, file a work item to migrate off the embedded ` ```json:metadata` fence and revisit this ADR.
