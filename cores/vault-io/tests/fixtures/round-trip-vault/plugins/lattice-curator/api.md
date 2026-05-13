---
title: lattice-curator (plugin) — API
category: package
summary: The Claude-Code-facing surface — UserPromptSubmit hook, PreToolUse:Skill stage tracker, /curator:init slash command, and the context.fetch MCP tool.
tags: [plugin, hooks, mcp, api]
updated: 2026-05-09
tokens: 1945
---

# lattice-curator (plugin) — API

Source of truth: `plugins/lattice-curator/.claude-plugin/plugin.json` and the script files under `hooks/`, `commands/`, `mcp/`.

## Public API

### Manifest

`plugins/lattice-curator/.claude-plugin/plugin.json`:

| Field | Value |
|---|---|
| `name` | `lattice-curator` |
| `version` | `1.0.0` |
| `description` | "Stage-aware context curator: gates UserPromptSubmit, runs a two-pass [[wiki/concepts/bedrock-langgraph-stack|Bedrock]] retriever over wiki + experts catalogs, injects compact briefs back into Claude Code." |
| `env.LATTICE_CURRATOR_ROOT` | `${CLAUDE_PLUGIN_ROOT}` |
| `commands` | `["commands/init.md"]` |
| `mcpServers["lattice-curator"]` | `python ${CLAUDE_PLUGIN_ROOT}/mcp/server.py` |

### Hooks

Registered in `plugins/lattice-curator/hooks/hooks.json`. Both hooks are dispatched through `hooks/run-hook.cmd` (a bash shim that `exec`s `python "${HOOK_DIR}/$1.py"`).

#### `UserPromptSubmit` → `curator-fire`

`async: false` — Claude Code waits for the hook to finish before processing the prompt. Implementation at `plugins/lattice-curator/hooks/curator_fire.py`.

Input (stdin JSON):

| Field | Type | Notes |
|---|---|---|
| `prompt` | string | required; empty prompts short-circuit |
| `transcript_tail` | string | recent conversation context for topic-shift gating |

Output: stdout markdown (the formatted `Brief`), or empty if the gate returns `fire=False`.

Behavior:

1. If `LATTICE_CURATOR_DISABLE=1` — return immediately.
2. Parse stdin JSON; on parse error, log a stderr warning and exit cleanly.
3. `load_config(cwd)` — reads `.lattice-curator.json` from `$PWD`.
4. Read `~/.cache/lattice-curator/state.json` for `lastFireAt` + `lastSkill`.
5. Call `gate(GateInput(...))`. On `fire=False`, write a `FireEntry(outcome="gate_only")` and exit.
6. Build sources (wiki + experts, gated by `config.sources.*.enabled`).
7. `retrieve(stage, prompt, transcript_tail, sources, model=make_bedrock(config))`.
8. `format_brief(brief, config.mode)` → stdout.
9. Persist `lastFireAt = now_ms` to `state.json`.
10. Append a `FireEntry(outcome="ok", picks=brief.diagnostics["picks"], ...)` to `~/.cache/lattice-curator/fires.jsonl`.

All exceptions are caught at the top level. Retrieval errors emit a `FireEntry(outcome="pass1_timeout")` and a stderr warning; the prompt still goes through unmodified.

#### `PreToolUse:Skill` → `stage-tracker`

`async: true` — runs in the background, never blocks. Matcher `"Skill"` filters to the Claude Code Skill tool only. Implementation at `plugins/lattice-curator/hooks/stage_tracker.py`.

Input (stdin JSON): standard PreToolUse payload (`tool_name`, `tool_input`).

Behavior:

1. If `tool_name != "Skill"` — return.
2. Read `tool_input.skill` (string).
3. Merge `{lastSkill: {name: skill, at: now_ms}}` into `~/.cache/lattice-curator/state.json` (preserves any existing keys like `lastFireAt`).

> [!warning] Naming concern
> `hooks.json` registers the hook command as `"... run-hook.cmd" stage-tracker`, and the shim invokes `python "${HOOK_DIR}/$1.py"` — i.e. it tries to load `stage-tracker.py`. The actual file is `stage_tracker.py` (underscore). Either rename the files or change the registered argument to `stage_tracker` / `curator_fire`. See [[wiki/plugins/lattice-curator/work]].

### Slash command

#### `/curator:init`

Frontmatter declaration at `plugins/lattice-curator/commands/init.md`:

```yaml
---
description: Seed lattice/knowledge/ with bundled expert rules. Idempotent — skips existing files.
allowed-tools: ["Bash"]
---
```

The command body runs:

```bash
python "${LATTICE_CURRATOR_ROOT}/commands/curator_init.py"
```

Backing script at `plugins/lattice-curator/commands/curator_init.py`:

1. Walk up from `$PWD` until a `.git` or `.lattice.yaml` is found; error out if neither exists in any ancestor.
2. Import `lattice_workspace.init` and `lattice_workspace.paths.knowledge_dir`. If the import fails, error out with a clear message.
3. Import `lattice_curator_core.seed.seed_knowledge`. Error out on import failure.
4. `ws_init(root, plugin="lattice-curator")`.
5. `seed_knowledge(knowledge_dir(root))` — copies ~100 bundled `.md` rule files; preserves any existing files.
6. Print a count + a hint to edit `lattice/knowledge/`.

Returns `0` on success, `1` on any error (printed to stderr).

### MCP server

Server name `lattice-curator`. Run command: `python ${CLAUDE_PLUGIN_ROOT}/mcp/server.py`.

Built on `FastMCP` from the official Python `mcp` SDK. Implementation at `plugins/lattice-curator/mcp/server.py`.

#### Tool: `context.fetch`

```python
@mcp.tool(name="context.fetch")
async def context_fetch(stage: str = "generic", hint: str = "") -> str:
```

| Argument | Default | Purpose |
|---|---|---|
| `stage` | `"generic"` | Forces a stage; bypasses gate stage detection |
| `hint` | `""` | Becomes the `prompt` argument to `retrieve()` |

Behavior:

1. `load_config(cwd)`.
2. Build sources (wiki + experts, gated by config).
3. `make_bedrock(config)` → `retrieve(stage, prompt=hint, transcript_tail="", sources, model)`.
4. Return `format_brief(brief, config.mode)`.

No fail-silent here. Exceptions propagate to the MCP layer and are surfaced to the calling Claude turn — Claude explicitly invoked the tool and should see the error.

### State files

Both written by hooks under `~/.cache/lattice-curator/`:

- **`state.json`** — `{"lastSkill": {"name": "...", "at": <ms>}, "lastFireAt": <ms>}`. Created on first hook fire.
- **`fires.jsonl`** — append-only newline-delimited `FireEntry` records (camelCase keys via Pydantic alias). Rotated at 10 MB → `fires.jsonl.1`, keeping 3 files.

Schema for a fire entry (from the package's `FireEntry` Pydantic model):

```json
{
  "ts": "2026-05-09T...Z",
  "stage": "execute-plan",
  "gate": {"fire": true, "reason": "skill:lattice-workflows:executing-plans"},
  "model": "us.anthropic.claude-haiku-4-5-...",
  "picks": ["wiki/packages/.../api.md", "lattice/knowledge/react/state-lift-state.md"],
  "pass1Tokens": 412,
  "pass2Tokens": 1638,
  "briefBytes": 2104,
  "mode": "hybrid",
  "outcome": "ok",
  "transcriptTailHash": "9f1c3a..."
}
```

### Environment variables

| Variable | Read by | Purpose |
|---|---|---|
| `LATTICE_CURATOR_DISABLE` | hook | `=1` short-circuits `UserPromptSubmit` |
| `LATTICE_CURATOR_MODEL` | package | Override Bedrock model id |
| `AWS_DEFAULT_REGION` / `AWS_REGION` | package | Bedrock region (default `us-east-1`) |
| `LATTICE_CURRATOR_ROOT` | command body | Resolves to `${CLAUDE_PLUGIN_ROOT}` |
| `PWD` | hook + command | Project root resolution |

## See also

- [[wiki/plugins/lattice-curator/lattice-curator]] — plugin overview
- [[wiki/plugins/lattice-curator/context]] — why the plugin is shaped this way
- [[wiki/packages/lattice-curator-core/lattice-curator-core]] — the package primitives the hooks compose
