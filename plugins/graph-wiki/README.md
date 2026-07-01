# graph-wiki

A Claude Code plugin that builds and maintains a persistent, cross-referenced knowledge base alongside any source-code project — single packages, monorepos, or hybrid shapes.

## What this plugin is

`graph-wiki` gives your repo a comprehensive workflow including work tracking, code graph, and acompounding markdown wiki that an LLM maintains. Every package, app, domain, and cross-cutting concept gets its own page. Ingested specs, PR summaries, articles, and design notes are integrated into the vault with citations and cross-references. The LLM keeps the wiki in sync with the code; you direct the analysis and curate what gets ingested.

By default the wiki lives at `<repo>/<workspace>/wiki/`, and `<workspace>` defaults to `graph-wiki`. Obsidian opens the workspace root (`<repo>/<workspace>/`) to see wiki, raw sources, and the work tracker as sibling directories. You can override the default wiki location by creating a `.graph-wiki.local.yaml` file in the repository root (and setting `workspace-directory: <workspace>`), or by setting the `GRAPH_WIKI_WORKSPACE` environment variable.

The plugin has two delivery surfaces that share the same wiki format:

- **Claude (default)** — Claude Code runs the wiki workflows directly via the bundled `wiki_io` Python package (this plugin).
- **Bedrock (opt-in)** — the plugin shims route the same workflows to the `gw` command from `packages/graph-wiki-cli`, running on AWS Bedrock with parallel subagents for cost savings on large vaults. Opt in per-command via the `[plugin]` block in `.graph-wiki.yaml`.

## Setup

**Prerequisites:** Python 3.11+, `uv` installed, `AGENT_RESEARCH_ROOT` pointing to the agent-research repo root.

1. Install the plugin in Claude Code:

   ```bash
   # From the agent-research repo root
   claude plugin install plugins/graph-wiki
   ```

   > **Upgrading from an older install?** Remove and reinstall the plugin to pick up the renamed `/graph-wiki:bootstrap` command (previously named `init`).

2. Initialize a workspace in your target repo:

   ```
   /graph-wiki:bootstrap
   ```

   This creates `<repo>/graph-wiki/` with `.graph-wiki.yaml`, `wiki/`, `raw/`, and `work/` subdirectories.

3. Open Obsidian at `<repo>/graph-wiki/` as a vault (not the inner `wiki/` directory). See `skills/graph-wiki/references/obsidian-setup.md` for recommended settings.

4. Run your first scan:

   ```
   /graph-wiki:scan
   ```

For direct Bedrock CLI use outside Claude Code, use the `gw` entry point:

```bash
gw --help
gw scan
```

Workspace and repo are auto-discovered; pass `--workspace <ws>` only to override. If `gw` isn't on PATH, prefix any command with `uv run --package graph-wiki-cli`.

## [plugin] block syntax

The `[plugin]` block in `.graph-wiki.yaml` controls whether each command runs on Claude (default) or routes to `gw` from `graph-wiki-cli` on Bedrock.

```yaml
plugin:
  backend_default: claude          # claude | bedrock — applies to any command not listed below
  backend_overrides:
    query: bedrock                 # route /graph-wiki:query to gw query
    lint: claude                   # explicit — same as the default
```

**All fields are optional.** When the block is absent, every command runs on Claude. When a command is not listed in `backend_overrides`, `backend_default` applies. When `backend_default` is absent, `claude` is the fallback.

The `[plugin]` block is validated on every read: unknown keys raise `RuntimeError`, and backend values must be `claude` or `bedrock`.

## Commands

| Command | What it does |
|---|---|
| `/graph-wiki:bootstrap` | Initialize a wiki workspace; create vault skeleton + schema files |
| `/graph-wiki:scan` | Build the code graph; create/update/delete one `entities/` page per admitted entity |
| `/graph-wiki:ingest <path>` | Read a source (spec, article, PR, transcript, in-repo doc); update wiki |
| `/graph-wiki:query <question>` | Answer a question from the vault; offer to file the answer back |
| `/graph-wiki:lint` | Health check: orphans, broken links, stale pages, code drift |
| `/graph-wiki:log` | Show or summarize recent wiki activity from `log.md` |

Sub-agents (`graph-wiki:scanner`, `graph-wiki:ingestor`, `graph-wiki:linter`, `graph-wiki:librarian`) are dispatched automatically by commands and can also be invoked directly.

## See also

- `skills/graph-wiki/references/` — detailed workflow references for each command
- `skills/graph-wiki/references/wiki-schema.md` — frontmatter schema and naming conventions
- `skills/graph-wiki/references/obsidian-setup.md` — recommended Obsidian configuration
- `skills/graph-wiki/references/monorepo-principles.md` — why this pattern works for monorepos
- `packages/wiki-io/` — the Python implementation behind the Claude-branch shims
- `packages/graph-wiki-cli/` — the Bedrock `gw` CLI that powers the Bedrock branch

## Recommended Workflow Configuration

### Disable Auto Plan Mode

Claude Code may automatically enter Plan mode during planning tasks, which conflicts with the structured skill workflows in this plugin. To prevent this, add `EnterPlanMode` to your permission deny list.

**In your project's `.claude/settings.json`:**

```json
{
  "permissions": {
    "deny": ["EnterPlanMode"]
  }
}
```

This blocks the model from calling `EnterPlanMode`, ensuring the brainstorming and writing-plans skills operate correctly in normal mode. See [upstream discussion](https://github.com/anthropics/claude-code/issues/23384) for context.

### Block Commits With Incomplete Tasks

Optional `PreToolUse` hook that blocks `git commit` while a native task is `in_progress`. Pending tasks pass through, so per-task commit flows work as intended.

Opt in via `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/plugins/marketplaces/agent-research/hooks/examples/pre-commit-check-tasks.sh"
          }
        ]
      }
    ]
  }
}
```

See the header of `hooks/examples/pre-commit-check-tasks.sh` for how it parses the session transcript and which task states count as open.

### Force Re-Validation on User-Thrown Gate Close

Optional `PostToolUse` hook that blocks when Claude closes a **user-thrown gate** task without capturing concrete evidence for every acceptance criterion. A user-thrown gate is any task that carries `"userGate": true` or a `"user-gate"` entry in `tags` inside its `json:metadata` fence — set by `writing-plans` when the user explicitly asked for a verification step ("make sure to verify X", "add a gate", "prove it on one, then all").

Non-gate tasks pass through silently. The hook only fires when `TaskUpdate` sets status to `completed`.

Opt in via `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "TaskUpdate",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/plugins/marketplaces/agent-research/hooks/examples/post-task-complete-revalidate.sh"
          }
        ]
      }
    ]
  }
}
```

See the header of `hooks/examples/post-task-complete-revalidate.sh` for how it parses `json:metadata` and the `USER-ORDERED GATE` banner, and how the `GRAPH_WIKI_USERGATE_GUARD=0` escape hatch works.

### Re-Validate Gates on "Plan Complete" Claims

Optional `Stop` hook that complements the PostToolUse hook above. It fires when Claude signals plan completion ("plan complete", "both gates passed", "implementation complete", etc.) but the transcript shows user-thrown gate tasks were closed without subsequent per-criterion proof. Requires Claude to post evidence in the form `AC: <criterion> — PROVEN BY <evidence>` before it can stop.

Opt in via `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/plugins/marketplaces/agent-research/hooks/examples/stop-revalidate-user-gates.sh"
          }
        ]
      }
    ]
  }
}
```

See the header of `hooks/examples/stop-revalidate-user-gates.sh` for the full list of completion keywords and the `GRAPH_WIKI_USERGATE_STOP_GUARD=0` escape hatch.

### Capture Session Transcripts for the Active Work Item

Optional `SessionEnd` hook that copies the session's transcript (plus any subagent sidechain transcripts) into the active work item's `work/<slug>/` directory, so a finished item accumulates its own session history instead of it being scattered across `~/.claude/projects/*/*.jsonl`. Reads `.graph-wiki/active-work.json` — the pointer `gw work advance` stamps on every design/plan/execute/finish transition. No pointer (a session that never touched `gw work advance`) → silent no-op.

Opt in via `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/plugins/marketplaces/agent-research/hooks/examples/session-end-transcript-capture.sh"
          }
        ]
      }
    ]
  }
}
```

See the header of `hooks/examples/session-end-transcript-capture.sh` for the naming convention and the `GRAPH_WIKI_TRANSCRIPT_CAPTURE_GUARD=0` escape hatch. Traces to the same `/tmp/claude-hooks/` family of logs (override via `GRAPH_WIKI_TRANSCRIPT_CAPTURE_TRACE_LOG`).

### Enforce blockedBy Ordering on in_progress

Optional `PreToolUse` hook on `TaskUpdate` that refuses to move a task into `status=in_progress` while its `blockedBy` list still points at tasks that are not yet `completed`. Motivation: observed failure mode — a coordinator jumps to a later task ("this one is simpler, zero setup") even though its declared prerequisites feed it. The plan meant V0.x to catalog state before V1.x replays consume it; without the catalog, the replay runs blind.

The hook does not silently refuse. Its stderr invites self-assessment first ("is this a hallucination — did you already do this work informally?"), offers three escalation paths (do the blocker, cancel it if truly obsolete, or raise the ordering to the user with AskUserQuestion), and explicitly warns against the bypass move of closing the blocker with status=completed without doing the work.

Opt in via `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "TaskUpdate",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/plugins/marketplaces/agent-research/hooks/examples/pre-task-blockedby-enforce.sh"
          }
        ]
      }
    ]
  }
}
```

See the header of `hooks/examples/pre-task-blockedby-enforce.sh` for the transcript-walking logic and the `GRAPH_WIKI_BLOCKEDBY_GUARD=0` escape hatch.

### Enforce per-task LLM/dispatch requirements

Optional `PreToolUse` hook on `Agent` that reads the currently in_progress task's `json:metadata` fence and refuses Agent calls that disagree with its `subagentType`, `model`, or `dispatchBrief`. Use when a plan's tasks are sensitive to which tier runs them — empirical measurements, coordinator-quality work, zero-cost batches.

If a task's metadata carries `{"model": "haiku"}` and the coordinator dispatches `model: "opus"`, this hook blocks the call with a stderr explaining the mismatch and three response options (retry with the required params, update metadata transparently, or escalate via AskUserQuestion).

When the task has no dispatch requirement in metadata, the hook passes silently.

Opt in via `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Agent",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/plugins/marketplaces/agent-research/hooks/examples/pre-agent-task-dispatch-validate.sh"
          }
        ]
      }
    ]
  }
}
```

See the header of `hooks/examples/pre-agent-task-dispatch-validate.sh` for the transcript-walking logic and the `GRAPH_WIKI_DISPATCH_GUARD=0` escape hatch. Metadata keys are documented in `skills/shared/task-format-reference.md`.

### Force Subagent Evidence on Return

Optional `PostToolUse` hook on `Agent` that fires the moment a subagent's `tool_result` arrives — before the coordinator absorbs it and reports upward. If the in_progress task carries `requireEvidenceTokens` (multi-axis evidence requirement) or the `requireABCompare: true` shortcut, the hook checks that the subagent's report contains at least one token from each axis. Missing axes → block with stderr naming them, forcing immediate re-dispatch rather than "looks good" at close time.

When the task has no evidence requirement in metadata, the hook passes silently.

Opt in via `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Agent",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/plugins/marketplaces/agent-research/hooks/examples/post-agent-return-validate.sh"
          }
        ]
      }
    ]
  }
}
```

See the header of `hooks/examples/post-agent-return-validate.sh` for the metadata schema and the `GRAPH_WIKI_AGENT_RETURN_GUARD=0` escape hatch.

### Hook trace log

All three user-gate hooks (post-complete revalidate, stop revalidate, pre-blockedby enforce) write one-line decision traces to `/tmp/claude-hooks/user-gate-trace.log` (override via `GRAPH_WIKI_USERGATE_TRACE_LOG`). Tail during development with:

```
tail -F /tmp/claude-hooks/user-gate-trace.log
```

Each line is pipe-separated: `TIMESTAMP | hook-name | task=N | event | reason`. Events include `enter`, `skip`, `parsed`, `scanned`, `pass`, `block`, `error`. Skip reasons identify the short-circuit (e.g. `tool=Bash`, `status=pending`, `graph-wiki-active`, `guard=0`). This is the fastest way to see why a hook did or did not fire on a specific task.

### Block Low-Context Stop Excuses

Optional `Stop`-event hook that blocks "fresh session later" / "context is full" deflections when real context usage is below 50%.

Opt in via `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/plugins/marketplaces/agent-research/hooks/examples/stop-deflection-guard.sh"
          }
        ]
      }
    ]
  }
}
```

See the header of `hooks/examples/stop-deflection-guard.sh` for the full list of blocked phrases, configuration environment variables, and fail-open behavior.

