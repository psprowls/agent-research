---
title: "Execution Skills Comparison: executing-plans vs. subagent-driven-development vs. dispatching-parallel-agents"
category: source
summary: Side-by-side comparison of three lattice-workflows execution skills — clarifies that executing-plans and subagent-driven-development are alternatives for the same goal (plan execution; separate-session vs same-session, with quality gates), while dispatching-parallel-agents is orthogonal (independent problem set, not a plan).
source_path: raw/articles/execution-skills-comparison.md
source_type: article
ingested: 2026-05-10
updated: 2026-05-10
tags: [lattice-workflows, skills, executing-plans, subagent-driven-development, dispatching-parallel-agents, decision-tree]
tokens: 888
---

# Execution Skills Comparison

## What the source is

A short comparative note distinguishing three [[wiki/plugins/lattice-workflows/lattice-workflows]] execution-oriented skills that are easy to confuse: `executing-plans`, `subagent-driven-development`, and `dispatching-parallel-agents`. Lives at `raw/articles/execution-skills-comparison.md`.

## TL;DR

- `executing-plans` and `subagent-driven-development` both **execute a written plan** but differ on **session** and **quality gates**: `executing-plans` is single-agent, resumed-session, self-verifying; `subagent-driven-development` is same-session, dispatches a fresh subagent per task, and runs an implementer → spec-compliance → code-quality pipeline.
- `dispatching-parallel-agents` is **orthogonal** — it is not a plan-execution skill at all; it splits an independent problem set (e.g. "6 tests failing across 3 unrelated subsystems") across concurrent agents.
- The choice is encoded in a small decision tree owned by `subagent-driven-development`: plan? → tasks mostly independent? → stay in this session? → SDD vs `executing-plans`.

## Key claims

- **`executing-plans` is for resumed sessions.** Loads a plan from disk, restores task state from `.tasks.json`, and the main agent does the work sequentially. Designed for picking a plan back up in a new/separate session.
- **`subagent-driven-development` is for same-session plan execution with quality gates.** Each task: implementer subagent → spec-compliance reviewer → code-quality reviewer. Tasks run serially but each step is isolated.
- **`dispatching-parallel-agents` is for independent problem sets, not plans.** No `.tasks.json`, no `blockedBy` (by design), concurrent agents, post-integration conflict check. Sits outside the SDD decision tree entirely.
- **`executing-plans` defers to SDD when available** — its own text says "If subagents are available, use `subagent-driven-development` instead."
- **SDD can use parallel dispatch internally** for exploratory sub-tasks; the two solve different problems at different scales and are not substitutes.

## Decision tree (from the source)

```
Have implementation plan?
  └─ yes → Tasks mostly independent?
              └─ yes → Stay in this session?
                          ├─ yes → subagent-driven-development
                          └─ no  → executing-plans
```

`dispatching-parallel-agents` is **not** in this tree — different problem shape.

## Relationship to existing pages

- Distinguishes three skills documented at [[wiki/plugins/lattice-workflows/api]]; that page now points each of the three at the new comparison concept.
- The "execution-skill selection pattern" added to [[wiki/plugins/lattice-workflows/patterns]] captures the decision-tree rule.
- Related conceptually to [[wiki/concepts/subagent-vs-teammate]] — both pages clarify Claude Code dispatch mechanisms; that page distinguishes subagents from agent-team teammates, this one distinguishes the skills that drive subagent dispatch.

## Synthesis

See [[wiki/concepts/execution-skills-comparison]] for the canonical concept page that absorbs this source's contents and is linked from the workflow skills' API entries.

## Contradictions

None with code or other vault pages. The source is a clarification, not a divergence.
