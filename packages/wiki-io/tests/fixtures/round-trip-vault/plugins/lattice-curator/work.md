---
title: lattice-curator (plugin) — Work
category: package
summary: Open issues, tech debt, and discrepancies for the plugin surface.
tags: [plugin, work, tech-debt]
updated: 2026-05-09
tokens: 648
---

# lattice-curator (plugin) — Work

## Bugs

- **Hook shim filename mismatch (suspected — unverified).** `hooks/hooks.json` registers the hook commands as `"... run-hook.cmd" stage-tracker` and `"... run-hook.cmd" curator-fire`. The shim invokes `python "${HOOK_DIR}/$1.py"` — i.e. it tries to load `stage-tracker.py` and `curator-fire.py`. The actual files are `stage_tracker.py` and `curator_fire.py` (underscores). Either rename the script files to use dashes, change `hooks.json` to pass `stage_tracker` and `curator_fire`, or update the shim to translate dashes to underscores. Worth running the hooks live to confirm — they may currently silently fail and the fail-silent posture would mask it.

## Tech debt

- **README is stale.** `plugins/lattice-curator/README.md` references `hooks/curator-fire.mjs`, `hooks/stage-tracker.mjs`, `mcp/server.ts`. Should be updated to match the Python files.
- **Plugin doesn't declare its package dep.** Hooks `import lattice_curator_core` and `commands/curator_init.py` imports `lattice_workspace`, but neither package is declared in `.claude-plugin/plugin.json`. Claude Code's plugin schema doesn't currently support Python deps — but a `requires` or `keywords`-style hint plus README guidance would help users get the install right.
- **No tests in the plugin tree.** Hook behavior is exercised only through the package's pytest suite. Earlier wiki revisions claimed test files exist; they do not.
- **`run-hook.cmd` looks like Windows but isn't.** The `.cmd` extension is a lattice-workflows convention but the file is a bash script (`#!/usr/bin/env bash`). Won't run on actual Windows. Worth a comment in the file or a docs note.
- **No `LATTICE_CURATOR_DISABLE` for the MCP path.** The env var only short-circuits the hook. If a user wants to disable everything, they must also unregister the MCP server. A cleaner kill switch (env var that disables both surfaces) would help debugging.

## Features

- **`/curator:init` starter config.** Should `/curator:init` also write a starter `.lattice-curator.json` next to `.lattice.yaml`? Currently config is implicit-defaults only until the user creates the file by hand.
- **`/curator:status` command.** A second slash command for inspecting the fire log would be useful when debugging why a turn did or didn't fire.

## Open questions

- Should the MCP tool name be `context_fetch` (snake_case) for consistency with Python conventions, vs the current `context.fetch` (which is the dotted style other MCP tools use)?
