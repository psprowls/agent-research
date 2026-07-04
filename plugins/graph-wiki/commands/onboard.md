---
description: "Guided setup for graph-wiki workflow's optional features. Asks short multiple-choice questions and applies each answer via the gw config CLI. Terminal equivalent: gw config init. Manual equivalent: see README.md."
---

# Graph-Wiki Workflows Onboarding

Walk the user through graph-wiki workflow's optional features one at a time.
For each feature: ask with AskUserQuestion, then immediately apply the answer
by running the matching `gw config` command — never edit a config file
directly. All writes land in the committed workspace manifest
(`<workspace>/.graph-wiki.yaml`) or the repo's `.claude/settings.local.json`;
`gw config` is the sole writer.

## Ground rules

- Run `gw` from the repo. If `gw` is not on PATH, use
  `uv run --package graph-wiki-cli gw ...`.
- Each feature is optional. "No" runs nothing and moves on.
- If a `gw config` command errors, show the user the exact stderr and stop the
  feature — do not improvise file edits.
- NEVER commit anything. `gw config` writes working-tree files only.

## Feature 1: Subagent Model Routing

One-line intro: plan execution dispatches an implementer plus reviewers per
task; by default they inherit the session model — on frontier-priced sessions
that multiplies the most expensive model across routine tasks.

AskUserQuestion (single select): "Enable model routing for plan-execution subagents?"
- "Guided tiers (recommended)" — mechanical→haiku, standard→sonnet, frontier→session model
- "One fixed model" — follow-up question: haiku / sonnet / opus / fable
- "No" — run nothing

Apply:
- Guided tiers →
  `gw config set workflow.model_routing.mechanical haiku`
  `gw config set workflow.model_routing.standard sonnet`
  `gw config set workflow.model_routing.frontier inherit`
- One fixed model `<m>` → the same three commands with `<m>` as every value.

Tell the user: the routing gates activate immediately (they read
`<workspace>/.graph-wiki/config.json`, refreshed by the set commands); the
session-start routing notice appears from the next session. Off-switch:
`gw config unset workflow.model_routing.<tier>` for each tier.

## Feature 2: User-Thrown Gate Enforcement Hooks

One-line intro: when the user asks for a verification gate, opt-in hooks force
re-validation with captured evidence at close; without them gate tags are
inert metadata.

AskUserQuestion: "Enable enforcement hooks for user-thrown verification gates?"
- "Yes (recommended)" → run `gw config hooks enable gates`
- "No" → run nothing

The command merges both hook registrations (per-task close + end-of-plan stop)
and `permissions.deny: ["EnterPlanMode"]` into `.claude/settings.local.json`,
deduplicating and confirming the write; report the path it prints.
Off-switch: `gw config hooks disable gates`.

## Feature 3: Commit Strategy

One-line intro: plan execution commits after every task by default; switching
to a single commit at plan end gives one reviewable commit per feature.

AskUserQuestion: "How should plan execution commit its work?"
- "Per-task commits (recommended)" — the default; run nothing
- "Single commit at plan end" → run `gw config set workflow.commit_strategy at-end`

Takes effect from the next session (delivered by a session-start notice).
Off-switch: `gw config unset workflow.commit_strategy`.

## Feature 4: Session Transcript Capture

One-line intro: a SessionEnd hook copies the session transcript into the
active work item's directory whenever `gw work advance` has stamped an
active-work pointer.

AskUserQuestion: "Enable session transcript capture for the active work item?"
- "Yes" → run `gw config hooks enable transcript`
- "No" → run nothing

Off-switch: `gw config hooks disable transcript`.

## Closing

Report in one short block: the exact `gw config` commands run (copy the
command lines), the settings file paths they printed, features skipped, and
each off-switch (`gw config unset workflow.model_routing.<tier>` /
`gw config unset workflow.commit_strategy` / `gw config hooks disable
gates|transcript`). Mention `gw config list` as the way to review everything
later. Do not commit. Do not re-ask any question.
