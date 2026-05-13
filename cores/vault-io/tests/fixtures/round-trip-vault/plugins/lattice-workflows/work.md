---
title: lattice-workflows (plugin) — Work
category: package
summary: Bugs, tech debt, features, and open questions for lattice-workflows
updated: 2026-05-09
tokens: 282
---

# lattice-workflows (plugin) — Work

## Bugs

(none tracked)

## Tech debt

(none tracked)

## Features

- `open` — update `writing-plans` and `subagent-driven-development` to resolve `<role>-<tech>` via bare-name → `lattice-experts:<role>-<tech>` → other plugins, instead of hardcoding the `lattice-experts:` namespace.
- `accepted` — enable Claude Code Agent Teams for parallel plan execution. Plan committed; enablement + first parallel run pending. Crystallize-as-skill decision deferred until post-first-run.
- `resolved` — `PreToolUse` hook that JSON-lines-logs every `Skill` invocation to `/tmp/workflows-skill-invocations.log`, gated by `LATTICE_WORKFLOWS_OBSERVABILITY` (opt-out, fail-open). First adopter of the observability category gate.

## Open questions

- Upstream PRs from obra/superpowers — what is the reconciliation cadence?
- After the first parallel-plan run, do the orchestrator + teammate templates earn a `:parallel-plan-execution` skill?
