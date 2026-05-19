---
created: 2026-05-19T02:54:20.946Z
title: Rename graph-wiki init command to init-wiki
area: tooling
files:
  - plugins/graph-wiki/commands/init.md
---

## Problem

The graph-wiki plugin ships a `/init` command (plugins/graph-wiki/commands/init.md) that shadows Claude Code's built-in `/init` command. With the plugin installed, running `/init` resolves to the graph-wiki version, so the native "initialize CLAUDE.md" workflow is unreachable.

## Solution

Rename the plugin command to `/init-wiki`:

1. Rename `plugins/graph-wiki/commands/init.md` → `plugins/graph-wiki/commands/init-wiki.md`.
2. Update any internal references (skill docs, README, marketplace.json, other commands) that point users at `/init` or `graph-wiki:init` so they reference `init-wiki` / `graph-wiki:init-wiki`.
3. Check `plugins/graph-wiki/skills/graph-wiki/SKILL.md` and any prompt text for hardcoded `/init` strings.
4. Verify Claude Code's built-in `/init` is reachable again after the rename.
5. Note: keep the underlying `init_vault.py` script name as-is — only the user-facing slash command changes.
