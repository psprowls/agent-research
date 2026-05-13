---
title: lattice-curator
category: package
summary: Claude Code plugin wrapping packages/lattice-curator-core — UserPromptSubmit hook, PreToolUse:Skill stage tracker, /curator:init command, and an MCP server exposing context.fetch.
status: active
package_path: plugins/lattice-curator
package_type: plugin
domain:
language: Python
version: 0.2.0
depends_on:
  - packages/lattice-curator-core/lattice-curator-core
  - packages/lattice-workspace/lattice-workspace
tags:
  - plugin
  - context-curation
  - hooks
  - mcp
  - rag
  - bedrock
updated: 2026-05-11
last_sync_commit: 97a27ff7e874647009710d9a9aee18be97bc924c
last_sync_at: 2026-05-10
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 928
---

# lattice-curator (plugin)

## Purpose

Thin Claude Code plugin wrapping [[wiki/packages/lattice-curator-core/lattice-curator-core]]. The plugin owns the surfaces that touch Claude Code — two hooks, one slash command, and one MCP server — and delegates all curation logic to the package. This is the only piece of the curator that knows Claude Code exists; the package is reusable from CI, evals, and future plugins without it. Two hooks are registered: `UserPromptSubmit` (synchronous, fires the curator before Claude processes a prompt) and `PreToolUse:Skill` (async, records which workflow skill was just invoked to improve stage routing on the next turn). Install this plugin when you want stage-aware context briefs injected automatically at the start of each Claude Code turn.

## File map - lattice-curator

- `README.md` — user-facing overview (stale: references `.mjs` hooks and `mcp/server.ts`; current code is Python)

### lattice-curator/.claude-plugin/

- `plugin.json` — Claude Code plugin manifest. Declares `name: "lattice-curator"`, `version: "0.2.0"`, the `LATTICE_CURRATOR_ROOT` env var, the `commands/init.md` command, and the `lattice-curator` MCP server (`python mcp/server.py`)

### lattice-curator/commands/

- `curator_init.py` — backing script for `/curator:init`. Walks up to find project root; runs `lattice_workspace.init(root, plugin="lattice-curator")`; calls `seed_knowledge(knowledge_dir(root))`; reports written-file count to stdout
- `init.md` — slash-command frontmatter declaration; `allowed-tools: ["Bash"]`; runs `python "${LATTICE_CURRATOR_ROOT}/commands/curator_init.py"`

### lattice-curator/hooks/

- `curator_fire.py` — `UserPromptSubmit` hook. Reads JSON payload from stdin; calls package `gate()`; on fire, runs `retrieve()`, prints `format_brief()` to stdout, persists `lastFireAt`, appends a `FireEntry` to `fires.jsonl`. All exceptions caught.
- `hooks.json` — hook registration: `PreToolUse` matcher `"Skill"` async, `UserPromptSubmit` synchronous
- `run-hook.cmd` — bash shim (despite the `.cmd` extension); `exec python "${HOOK_DIR}/$1.py"`
- `stage_tracker.py` — `PreToolUse:Skill` hook. Writes `{lastSkill: {name, at}}` to `~/.cache/lattice-curator/state.json`

### lattice-curator/mcp/

- `server.py` — `FastMCP("lattice-curator")` server with one tool, `context.fetch(stage="generic", hint="")`; errors surface to the caller (no fail-silent)

## Sub-pages

- [[wiki/plugins/lattice-curator/api]]      — hook surface, slash command, MCP server contract
- [[wiki/plugins/lattice-curator/context]]  — plugin deployment shape, relationship to the package, why two hooks
- [[wiki/plugins/lattice-curator/patterns]] — key patterns and conventions
- [[wiki/plugins/lattice-curator/work]]     — bugs, tech debt, features, open questions
