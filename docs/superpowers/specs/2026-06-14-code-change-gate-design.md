# Code-Change Gate for the Dev-Workflow Suite — Design

**Date:** 2026-06-14
**Status:** Approved
**Scope:** `plugins/graph-wiki/skills/{using-git-worktrees,executing-plans,subagent-driven-development,test-driven-development}/SKILL.md`. `writing-plans` and the subagent implementer prompts are deliberately untouched.

## Problem

The vendored superpowers dev-workflow skills can write source code without the
two protections the user wants:

1. **No isolation guarantee.** `using-git-worktrees` is *consent-based* — it asks
   "Would you like me to set up an isolated worktree?" and silently works in the
   main checkout if the user declines or stays quiet. Code changes can land
   directly on the working branch.
2. **No authorization gate.** Nothing requires an explicit instruction to write
   code. Approving a design or plan, or simply asking a question, can flow into
   the execution skills and produce edits.

The user wants both rules enforced for every code-writing path in the suite:

- **Rule A (isolation, strengthened):** every code change happens in an isolated
  worktree on an inferred `feat/`/`fix/`-style branch. The main worktree is used
  **only** when the user explicitly says to.
- **Rule B (authorization, strictest):** the skills write code **only** after a
  direct implement directive. Approving a design/plan is not, by itself, enough.

## Decision summary

Make `using-git-worktrees` the single canonical **Code-Change Gate** that every
code-writing path runs first. The three execution skills route through it as a
required Step 0; `writing-plans` is left as the (already-explicit) handoff point.

- **D-1 — Two-part gate in `using-git-worktrees`.** Its opening becomes a gate
  with two ordered checks. The skill announces itself as the Code-Change Gate.

  - **Part 1 — Authorization (new).** Before creating anything or writing code,
    assert the user has given a *direct implement directive* — e.g. "implement
    this", "make the change", "execute the plan", "fix it in code", or selecting
    an execution-handoff option. If no such directive exists → **STOP**: do not
    create a worktree, do not Write/Edit code, stay read-only/planning and ask.
    Approving a design or plan does **not** by itself satisfy this.
  - **Part 2 — Isolation (mandatory).** Keep the existing detection (already in a
    linked worktree → proceed; submodule guard unchanged). In the main checkout,
    creating an isolated worktree is **required** — the consent question is
    removed. The **only** exception is an explicit user instruction to work in
    the main worktree; in that case work in place and say so.

- **D-2 — Branch naming by inference.** Replace the unspecified `$BRANCH_NAME`
  with: infer the prefix from the work (`feat/` for features, `fix/` for
  bugfixes, etc., matching this repo's existing convention) plus a short
  kebab-case name, then state the chosen branch. No per-time prompt.

- **D-3 — `executing-plans` Step 0.** Promote the current Step 0.5 worktree
  check into an explicit **"Step 0: Code-Change Gate (REQUIRED)"** that invokes
  `using-git-worktrees` before any task runs — no Write/Edit until the gate
  passes. The existing later worktree-detection logic stays.

- **D-4 — `subagent-driven-development` Step 0.** Add an explicit
  **"Step 0: Code-Change Gate (REQUIRED)"** at the start of The Process (before
  "Read plan, extract tasks"), invoking `using-git-worktrees`. Today the skill
  only lists it under Integration.

- **D-5 — `test-driven-development` gate note.** Add a short Code-Change Gate
  note near the top (before the Iron Law) routing through `using-git-worktrees`,
  so a *standalone* TDD invocation also gates. When nested under an execution
  skill the gate is idempotent (isolation already detected).

- **D-6 — Red-flag / table sync.** Update the stale "without explicit user
  consent" red flags (`executing-plans:108`, `subagent-driven-development:246`)
  and the `using-git-worktrees` Quick Reference / Common Mistakes / Red Flags
  tables to the stronger rule: isolation mandatory, main only on explicit
  request, no code without an explicit implement directive.

## Deliberate non-changes

- **`writing-plans`:** its Execution Handoff already forces an `AskUserQuestion`;
  the user selecting an execution option is the explicit go-ahead, and the
  execution skill it invokes runs the gate. Neither handoff option implies
  in-place/main work. Editing it would be scope creep.
- **Subagent implementer prompts:** the implementer subagent inherits the
  orchestrator's worktree cwd. The gate is enforced one level up, at the
  orchestrator, so the prompts need no change.
- **`finishing-a-development-branch`, `dispatching-parallel-agents`:** not
  code-write entry points; out of scope.

## Verification

These are markdown behavior skills, not executable code, so verification is by
inspection:

- `using-git-worktrees` contains the two-part gate; the consent question
  ("Would you like me to set up an isolated worktree?") is gone; the explicit
  main-worktree opt-out and branch-name inference are documented.
- Each of `executing-plans`, `subagent-driven-development`,
  `test-driven-development` opens with a Code-Change Gate step that invokes
  `using-git-worktrees` before any code is written.
- No remaining "without explicit user consent" phrasing in the touched skills;
  Quick Reference / Red Flags tables reflect mandatory isolation.
- `writing-plans` and the subagent prompts are unchanged.
