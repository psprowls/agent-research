# graph-wiki

A Claude Code plugin that builds and maintains a persistent, cross-referenced knowledge base alongside any source-code project — single packages, monorepos, or hybrid shapes.

## What this plugin is

`graph-wiki` gives your repo a compounding markdown wiki that an LLM maintains. Every package, app, domain, and cross-cutting concept gets its own page. Ingested specs, PR summaries, articles, and design notes are integrated into the vault with citations and cross-references. The LLM keeps the wiki in sync with the code; you direct the analysis and curate what gets ingested.

By default the wiki lives at `<repo>/<workspace>/wiki/`, and `<workspace>` defaults to `graph-wiki`. Obsidian opens the workspace root (`<repo>/<workspace>/`) to see wiki, raw sources, and the work tracker as sibling directories.  You can override the default wiki locaiton with either.  The workspace directory can be overriden either by creating a `.graph-wiki.local.yaml` file in the repository root (and setting `workspace-directory: <workspace>`), or by setting the `GRAPH_WIKI_WORKSPACE` environment variable.

The plugin has two delivery surfaces that share the same wiki format:

- **Claude (default)** — Claude Code runs the wiki workflows directly via the bundled `vault_io` Python package (this plugin).
- **Bedrock (opt-in)** — `graph-wiki-agent` runs the same workflows on AWS Bedrock with parallel subagents, for cost savings on large vaults. Opt in per-command via the `[plugin]` block in `.graph-wiki.yaml`.

## Setup

**Prerequisites:** Python 3.11+, `uv` installed, `DEEP_AGENTS_ROOT` pointing to the agent-research repo root.

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

   This creates `<repo>/graph-wiki/` with `.graph-wiki.yaml`, `wiki/`, `raw/`, and `work/` subdirectories. The vault layout (apps, packages, domains) is detected interactively.

3. Open Obsidian at `<repo>/graph-wiki/` as a vault (not the inner `wiki/` directory). See `skills/graph-wiki/references/obsidian-setup.md` for recommended settings.

4. Run your first scan:

   ```
   /graph-wiki:scan
   ```

## [plugin] block syntax

The `[plugin]` block in `.graph-wiki.yaml` controls whether each command runs on Claude (default) or routes to `graph-wiki-agent` on Bedrock.

```yaml
plugin:
  backend_default: claude          # claude | bedrock — applies to any command not listed below
  backend_overrides:
    query: bedrock                 # route /graph-wiki:query to graph-wiki-agent
    lint: claude                   # explicit — same as the default
```

**All fields are optional.** When the block is absent, every command runs on Claude. When a command is not listed in `backend_overrides`, `backend_default` applies. When `backend_default` is absent, `claude` is the fallback.

The `[plugin]` block is validated on every read: unknown keys raise `RuntimeError`, and backend values must be `claude` or `bedrock`.

## Commands

| Command | What it does |
|---|---|
| `/graph-wiki:bootstrap` | Initialize a wiki workspace; detect repo layout; create vault skeleton |
| `/graph-wiki:scan` | Walk the repo; create/update package and app stub pages; surface doc candidates |
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
- `packages/vault_io/` — the Python implementation behind the claude-branch shims
- `agents/graph-wiki-agent/` — the Bedrock CLI that powers the bedrock branch
