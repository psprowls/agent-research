---
title: "ADR-0003: Observability as a single category-gate env var (opt-out)"
category: adr
summary: Adopt a single opt-out env var `LATTICE_WORKFLOWS_OBSERVABILITY` to gate the entire observability category in lattice-workflows; all observability hooks check the same var and are fail-open.
adr_id: "0003"
status: accepted
decision_date: 2026-05-04
deciders: [Patrick Sprowls]
supersedes:
superseded_by:
tags: [architecture, observability, hooks, env-vars, lattice-workflows]
updated: 2026-05-04
tokens: 1011
---

# ADR-0003: Observability as a single category-gate env var (opt-out)

**Status:** accepted (2026-05-04)

## Context

`lattice-workflows` is adding its first observability hook — a `PreToolUse` skill-invocation logger that appends JSON lines to `/tmp/workflows-skill-invocations.log`. Foreseeable follow-ups include tool-use logging and slash-command logging — three to five hooks of similar shape. The disable surface needs deciding before the first one ships, because the convention will lock in once users start setting it.

## Decision

**Use a single opt-out environment variable, `LATTICE_WORKFLOWS_OBSERVABILITY`, as a category gate for every observability hook in `lattice-workflows`.**

- **Opt-out:** unset = enabled. Disabling values: `0`, `false`, `off`.
- **Category gate:** every hook in the observability category checks the same variable. Adding a new logging hook does not add a new env var.
- **Fail-open invariant:** every observability hook exits `0` on every error path — missing `jq`, unwritable log, malformed stdin, empty required field. A broken hook never breaks a session.
- **Three disable locations** documented in `plugins/lattice-workflows/hooks/README.md`: `~/.claude/settings.json` (global), `.claude/settings.local.json` (per project), shell `export` (per session).

The first adopter is `plugins/lattice-workflows/hooks/log-skill-invocation`, registered via `plugins/lattice-workflows/hooks/hooks.json`.

## Consequences

**Positive:**
- One env var for users to learn — disable the whole category with one toggle.
- Adding a new observability hook is a code-only change; no new disable surface to document.
- Fail-open invariant means observability bugs degrade silently, never breaking user sessions.
- Aligns with `${LATTICE_<NAME>_ROOT}` env-var naming (see [[wiki/concepts/lattice-cross-plugin-contract]] and [[wiki/concepts/lattice-naming-convention]]).

**Negative:**
- Coarse granularity — users can't disable just one observability hook (e.g. keep skill logging but turn off tool-use logging). Mitigated by deferring per-hook gates until a real need shows up.
- Opt-out means logs accrue in `/tmp` for users who never read the README. Mitigated by `/tmp` semantics (ephemeral / debug-grade) and clear README disable instructions.

## Alternatives considered

- **Opt-in** (default off, env var enables) — rejected: observability disappears for users who never read the README, defeating the purpose. The data is more valuable than the small privacy cost of `/tmp` logs.
- **Per-hook env vars** (`LATTICE_WORKFLOWS_LOG_SKILLS`, `LATTICE_WORKFLOWS_LOG_TOOLS`, ...) — rejected: proliferates fast for no real benefit. Three to five env-vars covering one category is harder to teach than one. Per-hook gates can land later as `LATTICE_WORKFLOWS_OBSERVABILITY_<name>` if and only if a concrete need appears.
- **Shared cross-plugin `LATTICE_OBSERVABILITY`** — rejected: premature. Only `lattice-workflows` ships observability hooks today. Revisit when at least one other plugin in the ecosystem does the same.

## Impact

- [[wiki/plugins/lattice-workflows/lattice-workflows]] — first adopter; future observability hooks will reuse the gate.
- [[wiki/concepts/lattice-workflows-observability-gate]] — captures the convention.
- [[wiki/concepts/lattice-cross-plugin-contract]] — sibling env-var convention to `${LATTICE_<NAME>_ROOT}`.

## Follow-ups

- First adopter shipped: `plugins/lattice-workflows/hooks/log-skill-invocation` + `hooks.json` registration + `hooks/README.md`.
- Revisit per-hook gates only if a real need surfaces (e.g. one logger producing far more volume than others).

## Related

- [[wiki/concepts/lattice-workflows-observability-gate]]
