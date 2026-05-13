---
title: Lead-nudge protocol
category: concept
summary: The pattern of `SendMessage` "your dependency cleared, claim task #N" issued by the team lead to a downstream teammate at every task-dependency transition. Compensates for the fact that idle teammates do not auto-wake when their `blockedBy` clears.
tags: [agent-teams, coordination, lead, sendmessage, lattice-workflows]
sources: 0
updated: 2026-05-09
tokens: 1145
---

# Lead-nudge protocol

## Definition

The **lead-nudge protocol** is a small, reliable pattern: at every task-dependency transition in an agent team, the lead `SendMessage`s the downstream teammate (the one whose task just unblocked) with a "your dependency cleared, claim task #N" message. This wakes the teammate from idle so they can claim and process their now-unblocked task.

Without the nudge, the workflow stalls — the dependency flag clears in the task list, but the idle teammate sees nothing and remains idle.

## Motivation

The agent-teams documentation states "blocked tasks unblock without manual intervention" — true at the task-list level. The empirical finding (2026-05-04 spike, smoke tests 3 and 4) is that *teammates* don't get woken by the auto-unblock; only the task's flag changes. Reviewers configured to "wait for unblock then claim" stay idle indefinitely without an explicit message.

The protocol's whole purpose is to fill that gap with a small, predictable lead action.

See adrs/0013-reviewer-teammates-require-explicit-sendmessage-on-unblock for the empirical justification and decision.

## Shape

For a 2-deep dependency chain (e.g. `launching-plan-teams` Shape B):

```
T0  Lead spawns: implementer, spec-reviewer, code-quality-reviewer
T0  Lead creates tasks: implement (no deps), review-spec (blockedBy: implement),
                        review-quality (blockedBy: review-spec)
T0  spec-reviewer goes idle (task blocked); code-quality-reviewer goes idle.

T1  implementer marks "implement" completed.
    review-spec auto-unblocks in task list, BUT spec-reviewer stays idle.

T2  ★ Lead sends: SendMessage(spec-reviewer, "your dependency cleared, claim review-spec")
    spec-reviewer wakes, claims review-spec, proceeds.

T3  spec-reviewer marks "review-spec" completed.
    review-quality auto-unblocks, BUT code-quality-reviewer stays idle.

T4  ★ Lead sends: SendMessage(code-quality-reviewer, "...claim review-quality")
    code-quality-reviewer wakes, claims, proceeds.
```

The two ★ steps are the lead-nudge protocol. They're not optional; without them the workflow halts at T1→T2 and again at T3→T4.

The nudge message can carry useful state (branch SHA, worktree path, upstream verdict). This makes the downstream teammate's job easier — they don't need to `TaskGet` to learn what just happened.

## Used in

- `.claude/skills/launching-plan-teams/SKILL.md` — Steps 8 and 9 enforce the protocol with `> REQUIRED` callouts and Red Flags. Verified end-to-end in smoke tests 3 (Shape A, 1 nudge per plan) and 4 (Shape B, 2 nudges per plan).
- **2026-05-04 PM production run** (2026-05-04-real-world-parallel-plan-team-run) — fired correctly twice in Shape A (one impl→reviewer ping per plan, both required, both worked). The protocol holds at production scale.
- Any future skill using agent teams with task dependencies should encode the same protocol; see 2026-05-04-promote-launching-plan-teams.

## Related patterns

- [[wiki/concepts/subagent-vs-teammate]] — the broader teammate-specific gotchas, of which this is one.
- [[wiki/concepts/shape-a-vs-shape-b]] — Shape A needs 1 nudge per plan, Shape B needs 2; both depend on this protocol.
- knowledge-skills-pattern — same family of "tell the model explicitly, don't expect auto-discovery" findings.

## Open questions / gotchas

- **Hook automation.** A `TaskCompleted` hook that reads the completed task's `blocks` field and auto-emits the nudge `SendMessage` would remove the entire pattern from the human/lead surface. Tracked as a follow-up under 2026-05-04-promote-launching-plan-teams. If the hook lands, this protocol becomes invisible — but until then, leads must do it manually.
- **Cross-process teammates** (split-pane via tmux/iTerm2) were not tested in the 2026-05-04 spike. The same idle-doesn't-auto-wake behavior is *expected* in cross-process mode (the in-process backend isn't doing anything special), but should be confirmed before the protocol's claim is generalized.
- **Cap on review-loop rounds.** The reviewer prompts in `launching-plan-teams` cap `changes_requested → fix → re-review` loops at 3 rounds before escalating to the lead. This is a separate protocol — distinct from the lead-nudge — but interacts with it: the lead may re-issue a nudge after the cap is hit if it decides to override and proceed.
