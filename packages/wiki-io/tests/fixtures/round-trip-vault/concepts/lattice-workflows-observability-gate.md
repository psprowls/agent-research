---
title: lattice-workflows observability gate
category: concept
summary: A single opt-out env-var (`LATTICE_WORKFLOWS_OBSERVABILITY`) gates the whole observability category in lattice-workflows; every hook under the category is fail-open so a broken hook never breaks a session.
tags: [observability, hooks, env-vars, lattice-workflows, conventions]
updated: 2026-05-04
tokens: 918
---

# lattice-workflows observability gate

## Definition
The `lattice-workflows` plugin treats observability hooks (skill-invocation logging, tool-use logging, slash-command logging) as a single category controlled by one environment variable: `LATTICE_WORKFLOWS_OBSERVABILITY`. The variable is **opt-out** — unset means enabled. Disabling values are `0`, `false`, `off`. Every hook in the category is **fail-open**: any error (missing dependency, unwritable path, malformed stdin) results in `exit 0` with no message so observability never breaks a user session.

## Motivation
- **One toggle for the whole category** so users don't have to learn N env-var names as observability grows. Per-hook gates (`LATTICE_WORKFLOWS_OBSERVABILITY_<name>`) are deferred until a real need shows up.
- **Opt-out over opt-in** so data exists by default for users who never read the README; the disable path is documented in three locations (`~/.claude/settings.json`, `.claude/settings.local.json`, shell `export`).
- **Fail-open** because a hook that breaks a session is strictly worse than no hook at all. Observability is best-effort.

## Shape

```bash
# plugins/lattice-workflows/hooks/log-skill-invocation
case "${LATTICE_WORKFLOWS_OBSERVABILITY:-}" in
  0|false|off) exit 0 ;;
esac
# ... extract via jq, append JSON line, exit 0 on every error path ...
```

Hook registration:

```json
// plugins/lattice-workflows/hooks/hooks.json
{ "PreToolUse": [{ "matcher": "Skill", "hooks": [{ "command": "run-hook.cmd log-skill-invocation" }] }] }
```

## Disable mechanism

| Variable | Disabling values | Default |
|---|---|---|
| `LATTICE_WORKFLOWS_OBSERVABILITY` | `0`, `false`, `off` | unset = enabled |

Three places to set it:

- **Globally** — `~/.claude/settings.json` `env` block.
- **Per project** — `.claude/settings.local.json` `env` block.
- **Per shell** — `export LATTICE_WORKFLOWS_OBSERVABILITY=0`.

## Fail-open invariant
Every error path in every observability hook exits `0` silently:

- `jq` missing → exit 0.
- Log path unwritable → exit 0.
- Malformed JSON on stdin → exit 0.
- Required field empty (e.g. `skill` empty under matcher `"Skill"`) → exit 0.

A failing observability hook must never propagate a non-zero exit code to Claude Code.

## Used in
- [[wiki/plugins/lattice-workflows/lattice-workflows]] — first hook adopting the gate is `log-skill-invocation` (see `plugins/lattice-workflows/hooks/log-skill-invocation`).

## Related patterns
- [[wiki/concepts/lattice-cross-plugin-contract]] — `${LATTICE_<NAME>_ROOT}` discovery; the observability gate is a sibling convention naming env-vars `LATTICE_<PLUGIN_UPPER>_OBSERVABILITY`.
- [[wiki/concepts/lattice-naming-convention]] — `lattice-` prefix extends to env-var naming.

## Decisions
- [[wiki/adrs/0003-observability-as-category-gate]]

## Open questions / gotchas
- Per-hook gates (`LATTICE_WORKFLOWS_OBSERVABILITY_<name>`) deferred — only add if a real need shows up.
- Cross-plugin observability gate (`LATTICE_OBSERVABILITY` shared across plugins) deferred as premature; revisit if multiple plugins ship observability hooks.
- No log rotation / retention policy for `/tmp/workflows-skill-invocations.log` — `/tmp` semantics signal "ephemeral / debug-grade".
