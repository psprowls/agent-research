---
title: Claude Code hook points
category: concept
summary: The lifecycle events Claude Code fires during a session — UserPromptSubmit, SessionStart, and PreToolUse — used by lattice plugins to inject context, enforce gates, and trigger side-effects without modifying core Claude Code behavior.
tags: [claude-code, hooks, lifecycle, plugins, UserPromptSubmit, SessionStart, PreToolUse]
updated: 2026-05-09
tokens: 642
---

# Claude Code hook points

## What they are

Claude Code fires shell hooks at specific points in the session lifecycle. Plugins register these hooks in their `plugin.json` under a `hooks` key. When the event fires, Claude Code runs the registered command and optionally injects its stdout into the session context.

## The three hooks used by lattice

### `SessionStart`

Fires once when a Claude Code session begins (before the first user prompt). Used to inject persistent context into the session — workspace layout, active work items, relevant wiki pages.

- [[wiki/plugins/lattice-curator/lattice-curator]] — fires the stage-aware retriever; injects the top-scoring wiki/graph/work context for the session's project
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — can inject the wiki schema into the session

### `UserPromptSubmit`

Fires each time the user submits a prompt, before Claude processes it. Allows plugins to augment or gate the prompt.

- [[wiki/plugins/lattice-workflows/lattice-workflows]] — injects skill hints and active task state before each turn

### `PreToolUse`

Fires before Claude executes a tool call. Allows plugins to inspect, log, or block tool use.

- Used by [[wiki/plugins/lattice-work/lattice-work]] for lifecycle lint gates — blocks tool calls that would leave a work item in an invalid state

## Registration pattern

In `plugin.json`:
```json
{
  "hooks": {
    "SessionStart": "bash ${PLUGIN_ROOT}/hooks/session-start.sh",
    "UserPromptSubmit": "bash ${PLUGIN_ROOT}/hooks/prompt-submit.sh",
    "PreToolUse": "bash ${PLUGIN_ROOT}/hooks/pre-tool-use.sh"
  }
}
```

Hook scripts receive event context via stdin (JSON) and write injected context to stdout. Non-zero exit codes signal errors; Claude Code surfaces them as warnings.

## Tradeoffs

| Pro | Con |
|---|---|
| No modification to Claude Code itself | Hooks run synchronously; slow hooks delay the session |
| Plugins compose cleanly — each registers its own hooks | Hook ordering is non-deterministic when multiple plugins register the same event |
| Shell commands are language-agnostic | stdout injection is unstructured text; consumers must parse it |

## Related

- [[wiki/plugins/lattice-curator/lattice-curator]] — heaviest `SessionStart` hook (Bedrock retrieval)
- [[wiki/plugins/lattice-workflows/lattice-workflows]] — `UserPromptSubmit` for skill context injection
- [[wiki/plugins/lattice-work/lattice-work]] — `PreToolUse` for lifecycle gates
