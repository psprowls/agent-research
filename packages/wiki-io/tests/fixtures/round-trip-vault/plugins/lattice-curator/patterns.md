---
title: lattice-curator (plugin) — Patterns
category: package
summary: Key implementation patterns and conventions for the lattice-curator plugin surface.
tags: [plugin, patterns, conventions]
updated: 2026-05-09
tokens: 587
---

# lattice-curator (plugin) — Patterns

## Key patterns

- **Outside-the-loop placement.** `UserPromptSubmit` fires before Claude processes the prompt; the curator catches turns where Claude self-direction fails. The gate's purpose is to act where Claude's own planning would not.
- **Plugin stays thin.** No curation logic in the plugin — every interesting decision lives in [[wiki/packages/lattice-curator-core/lattice-curator-core]]. Mirrors the [[wiki/packages/lattice-source-parser/lattice-source-parser]] precedent.
- **Hook never breaks a turn.** Every `try` in `curator_fire.py` swallows exceptions; failures degrade to a stderr warning + a fire-log entry with `outcome="pass1_timeout"` (or similar). The user's prompt goes through normally, just without a brief. The MCP path differs — `mcp/server.py` does not catch exceptions; errors surface to the caller because Claude explicitly invoked the tool.
- **Stage signal is a side-channel, not a hard dep.** `stage_tracker.py` only narrows the gate's decision; if `state.json` is missing or stale, the gate falls back to action-verb / topic-shift heuristics and the curator still works.
- **Bash shim, Python hooks.** `hooks/run-hook.cmd` is a `bash` script that `exec`s `python "${HOOK_DIR}/$1.py"`. Despite the `.cmd` extension, this is not a Windows batch file — it runs under `bash` everywhere Claude Code does. The naming mirrors the lattice-workflows plugin convention.

## Conventions

- **Project-root discovery.** `curator_init.py` walks up from `$PWD` looking for `.git` or `.lattice.yaml` and bails if neither is found. This is the same convention used across lattice commands.
- **Safety hatch.** `LATTICE_CURATOR_DISABLE=1` short-circuits the `UserPromptSubmit` hook. There is currently no equivalent for the MCP path.
- **State location.** `~/.cache/lattice-curator/` — machine-local, ephemeral, never synced. Two files: `state.json` (live state) and `fires.jsonl` (append-only audit log, rotated at 10 MB).
- **Naming convention.** Hook script files use underscores (`curator_fire.py`, `stage_tracker.py`); hook registration arguments in `hooks.json` use dashes (`curator-fire`, `stage-tracker`). This mismatch is a known bug — see [[wiki/plugins/lattice-curator/work]].
