---
title: Execution skills comparison (executing-plans vs subagent-driven-development vs dispatching-parallel-agents)
category: concept
summary: Three lattice-workflows execution skills that are easy to confuse — `executing-plans` and `subagent-driven-development` are alternatives for executing a written plan (separate-session vs same-session-with-quality-gates), and `dispatching-parallel-agents` is orthogonal (independent problem set, not a plan). A small decision tree picks between them.
tags: [lattice-workflows, skills, executing-plans, subagent-driven-development, dispatching-parallel-agents, decision-tree]
sources: 1
updated: 2026-05-10
tokens: 1064
---

# Execution skills comparison

## Definition

Three skills in [[wiki/plugins/lattice-workflows/lattice-workflows]] all dispatch or execute "work units" and look superficially similar:

- **`executing-plans`** — single-agent, sequential, resumed-session execution of a written plan. Main agent does the work itself, task by task; restores state from `.tasks.json`.
- **`subagent-driven-development`** (SDD) — same-session execution of a written plan, but each task runs through a fresh subagent pipeline (implementer → spec-compliance reviewer → code-quality reviewer). Tasks still run serially; each step is isolated from the previous.
- **`dispatching-parallel-agents`** — concurrent dispatch across **independent problems** (e.g. "6 failing tests across 3 unrelated subsystems"). Not plan-driven; no `.tasks.json`; no `blockedBy`. Agents work in parallel and you integrate the results.

The first two are alternatives for the same goal (plan execution); the third is for a different problem shape.

## Motivation

Picking the wrong execution skill wastes tokens, breaks isolation, or fails to use available quality gates. The source notes that `executing-plans` even tells you to prefer SDD when subagents are available — the choice between them is about **session continuity**, not about whether you want quality review.

`dispatching-parallel-agents` sits outside this choice entirely: if you don't have a plan, neither plan-execution skill applies.

## Decision tree

From `subagent-driven-development`'s own SKILL.md:

```
Have implementation plan?
  └─ yes → Tasks mostly independent?
              └─ yes → Stay in this session?
                          ├─ yes → subagent-driven-development
                          └─ no  → executing-plans
```

`dispatching-parallel-agents` is **not** in this tree. Use it when you have N independent problems, not when you have N tasks in a plan.

## Shape

| | `executing-plans` | `subagent-driven-development` | `dispatching-parallel-agents` |
|---|---|---|---|
| **Input** | Written plan on disk | Written plan on disk | Independent problem set |
| **Execution** | Sequential, main agent | Sequential, fresh subagent per task | Concurrent, one agent per domain |
| **Session** | Separate/resumed | Current | Current |
| **Quality gates** | Self-verification | Spec review + code-quality review | Post-integration conflict check |
| **Task state** | `.tasks.json` resume | `.tasks.json` sync | No `blockedBy` (by design) |
| **Primary use** | Resume a plan later | Execute a plan now, with high quality | Fix N independent failures in parallel |

## Used in

- [[wiki/plugins/lattice-workflows/lattice-workflows]] — all three skills ship in the plugin's `skills/` tree.
- [[wiki/plugins/lattice-workflows/api]] — the three skill bullets now link back here for disambiguation.
- [[wiki/plugins/lattice-workflows/patterns]] — captures the decision-tree rule as the "execution-skill selection" pattern.

## Related patterns

- [[wiki/concepts/subagent-vs-teammate]] — distinguishes the two off-main Claude Code dispatch *mechanisms* (subagents vs agent-team teammates). This page is one level up: it distinguishes the *skills* that drive subagent dispatch.

## Sources

- [[wiki/sources/2026-05-execution-skills-comparison]] — the comparison note this page synthesizes.

## Open questions / gotchas

- ==SDD can use parallel dispatch *internally*== for exploratory sub-tasks within a single plan task. That does not make SDD and `dispatching-parallel-agents` substitutes — they solve different problems at different scales.
- The "stay in this session?" branch in the decision tree is the load-bearing distinction between SDD and `executing-plans`. If you're starting from a saved plan in a fresh session, SDD is generally not applicable — use `executing-plans`.
- `executing-plans` recommends SDD when subagents are available; treat SDD as the default for same-session plan execution and fall back to `executing-plans` only when you're resuming.
