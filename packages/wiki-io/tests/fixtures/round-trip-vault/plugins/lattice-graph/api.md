---
title: lattice-graph (plugin) — API
category: package
summary: Slash commands, SessionStart hook contract, and exit codes for the lattice-graph plugin.
updated: 2026-05-11
tokens: 2090
---

# lattice-graph (plugin) — API

## Public API

The plugin manifest at `plugins/lattice-graph/.claude-plugin/plugin.json` declares 13 commands. Slash-command names are namespaced as `/lattice-graph:<command>` (Claude Code derives the namespace from the plugin name automatically). Each is a markdown file under `commands/` whose body shells to the `cg` console-script.

### Operations

| Slash command | Shells to | Purpose | Exit semantics |
|---|---|---|---|
| `/lattice-graph:init` | `uv tool install "git+{{REPO_URL}}@{{VERSION}}#subdirectory=packages/lattice-graph-core"` | Install the `cg` CLI on `PATH`. Placeholders filled at marketplace install time. | 0 success; bash exit if `uv` not installed. |
| `/lattice-graph:update [--full]` | `cg update {{args}}` | Refresh the graph. Default is incremental (git-diff-driven, single SQLite transaction); `--full` is a full rebuild. | 0 success; 5 not-in-git-repo; 1 generic; 6 reserved (concurrent update). |
| `/lattice-graph:status` | `cg status {{args}}` | Print cardinalities, `last_indexed_commit`, `schema_version`, staleness. `--fmt json` for machine-readable output. | 0 fresh; 2 stale; 3 not initialized; 4 reserved (schema mismatch). |
| `/lattice-graph:dump` | `cg dump` | Emit raw SQLite contents for debugging / sharing. | 0 success; 3 not initialized. |
| `/lattice-graph:sync-wiki` | `cg sync-wiki` | Link package nodes to wiki overview pages. Reports newly linked, undocumented, and stale pages. | 0 success; 3 not initialized; 4 schema mismatch. |

### Queries

Each query command guards with `test -d lattice/.graph || { echo "No code graph found. Run /lattice-graph:init first."; exit 1; }` before invoking `cg`. (See [[wiki/plugins/lattice-graph/work]] — the guard path is wrong but `cg` itself returns exit 3 on a missing graph, so the bug is cosmetic.)

| Slash command | Shells to | Args | Example |
|---|---|---|---|
| `/lattice-graph:find` | `cg find {{args}}` | `<name> [--kind class\|fn\|type]` | `MyClass --kind class` |
| `/lattice-graph:callers` | `cg callers {{args}}` | `<name>` | `process_payment` |
| `/lattice-graph:callees` | `cg callees {{args}}` | `<name>` | `process_payment` |
| `/lattice-graph:imports` | `cg imports {{args}}` | `<path>` | `src/auth.py` |
| `/lattice-graph:imported-by` | `cg imported-by {{args}}` | `<path> [--symbol NAME] [--depth N]` | `src/auth.py --symbol login --depth 2`. See [[wiki/sources/2026-05-lattice-graph-core-symmetric-commands]]. |
| `/lattice-graph:exports` | `cg exports {{args}}` | `<path>` | `src/models.py`. See [[wiki/sources/2026-05-lattice-graph-core-symmetric-commands]]. |
| `/lattice-graph:exported-by` | `cg exported-by {{args}}` | `<name>` | `DatabaseConnection`. See [[wiki/sources/2026-05-lattice-graph-core-symmetric-commands]]. |
| `/lattice-graph:describe` | `cg describe {{args}}` | `<path-or-package>` | `lattice-source-parser` or `packages/lattice-source-parser/src/main.py` |

> [!note] `describe` is one command, not two
> The architecture spec names `cg_describe_package` and `cg_describe_path` as separate MCP tools. The shipped CLI / slash command collapses these into a single `describe` subcommand that disambiguates by argument shape (path-like vs. package-name). The two-tool split returns when the MCP adapter lands at v1.1.

### Command body shape

Every command markdown file uses the same shape (example: `commands/update.md`):

```markdown
---
description: Refresh the per-repo code graph (use `--full` for a full rebuild).
allowed-tools: ["Bash"]
---

Run `cg update` against the current repo. Forward any arguments after the command (e.g. `--full`).

```bash
cg update {{args}}
```
```

`{{args}}` is Claude Code's slash-command argument-passthrough placeholder.

## CLI

### SessionStart hook

`plugins/lattice-graph/hooks/session-start.py` (33 lines, stdlib-only). Wired in `plugin.json` as `"hooks": { "SessionStart": "hooks/session-start.py" }`.

**Behavior:**

```python
result = subprocess.run(
    ["cg", "--repo", repo, "--fmt", "json", "status"],
    capture_output=True, text=True,
)
if result.returncode == 2:
    data = json.loads(result.stdout)
    last = data.get("last_indexed_commit") or "(none)"
    head = data.get("head") or "(unknown)"
    print(
        f"[lattice-graph] graph is stale (last indexed: {last[:7]}; HEAD: {head[:7]}). "
        "Run /lattice-graph:update to refresh."
    )
return 0
```

(`plugins/lattice-graph/hooks/session-start.py:14-29`)

**Contracts** — the hook depends on three contracts from `lattice-graph-core`:

1. `cg --fmt json status` exit code 2 = stale — see ADR-0002-explicit-graph-update-lifecycle and `packages/lattice-graph-core/src/graph_io/exit_codes.py`.
2. JSON shape — top-level keys `last_indexed_commit` and `head` in stdout when invoked with `--fmt json`.
3. Repo discovery — `CLAUDE_PROJECT_DIR` env var (or `os.getcwd()` fallback).

The hook always returns exit code 0 — even when the graph is missing or `cg` is not installed. SessionStart hooks must not block startup. JSON parse errors are silently swallowed; an unparseable response simply suppresses the banner.

**Banner format:**

```
[lattice-graph] graph is stale (last indexed: 03588a7; HEAD: 7e2c1f4). Run /lattice-graph:update to refresh.
```

The hook never prints when the graph is fresh, never prints when the graph is missing, and never auto-updates.

> [!warning] No end-to-end test
> Nothing currently exercises the hook script through a real `cg` invocation. The contracts (exit code 2, JSON shape, env var) are unit-tested only in pieces. See [[work/2026-05-06-lattice-code-graph-session-start-hook-integration-test]].

### Exit codes

The `cg` CLI declares **seven stable exit codes**, of which **five are wired in v1**. They flow through unchanged when consumed by slash commands or the SessionStart hook.

| Code | Name | Status | Meaning |
|---|---|---|---|
| 0 | `SUCCESS` | wired | Normal success. |
| 1 | `GENERIC` | wired | Unclassified failure. Concurrent updates currently surface here too. |
| 2 | `STALE` | wired | `cg status` only — graph is behind HEAD. SessionStart hook keys off this. |
| 3 | `NOT_INITIALIZED` | wired | `code.db` missing. |
| 4 | `SCHEMA_MISMATCH` | reserved | `metadata.schema_version` ≠ `core.SCHEMA_VERSION`. v1 only knows version 1, so the check is a no-op. See [[work/2026-05-06-lattice-code-graph-wire-exit-codes-4-and-6]]. |
| 5 | `NOT_IN_GIT_REPO` | wired | `cg update` requires a git repo for `git diff`. |
| 6 | `UPDATE_IN_PROGRESS` | reserved | Concurrent `cg update`. Today surfaces as exit 1 via SQLite write-lock contention. See [[work/2026-05-06-lattice-code-graph-wire-exit-codes-4-and-6]]. |

Source: `plugins/lattice-graph/README.md:18-22`, `packages/lattice-graph-core/README.md`.

### Deferred to v1.1

- **MCP server adapter** — 12 named MCP tools + `cg_query` raw-SQL escape hatch. CLI-first decision puts MCP behind a stabilized library boundary. See [[wiki/concepts/code-graph-mcp-surface]].
- **Additional query subcommands**: `cg describe-type` (needs an `extends`/`inherits` edge kind not in v1 schema; bumps `schema_version`), `cg query` (raw-SQL escape hatch; lands with MCP).
- **C# parser** — committed for v1.1. v1 ships TypeScript/JavaScript and Python via [[wiki/packages/lattice-source-parser/lattice-source-parser]].

### Operations / lifecycle summary

`/lattice-graph:update` runs incrementally on `git diff prev_commit..HEAD` inside a single SQLite transaction (atomic). The SessionStart hook surfaces staleness as a banner; nothing auto-updates. See [[wiki/concepts/explicit-not-magic-update-lifecycle]] for the full lifecycle.
