# Cross-Tool Setup

The Code Wiki plugin is tool-agnostic. The **scripts** are pure Python stdlib and run anywhere. Only the **schema loader file** (the file the tool reads to understand conventions) differs per tool.

## How different CLIs discover wiki-level instructions

| Tool | Loader file (inside the wiki) | Notes |
|---|---|---|
| Claude Code | `<workspace>/wiki/CLAUDE.md` | Loaded automatically when CC starts in the wiki dir |
| Codex CLI (OpenAI) | `<workspace>/wiki/AGENTS.md` | Loaded at session start |
| Cursor (new) | `<workspace>/wiki/AGENTS.md` | Modern Cursor reads `AGENTS.md` |
| Cursor (legacy) | `<workspace>/wiki/.cursorrules` | Older Cursor versions |
| Google Antigravity | `<workspace>/wiki/AGENTS.md` | Standard `AGENTS.md` convention |
| OpenCode / Pi | `<workspace>/wiki/AGENTS.md` | Same convention |
| Gemini CLI | `<workspace>/wiki/AGENTS.md` | Same convention |
| Aider | `CONVENTIONS.md` or `.aider.conf.yml` | Point Aider at `CLAUDE.md` with `--read` |

`<workspace>` is the lattice workspace directory (default `<repo>/lattice/`; workspace path resolved via `lattice-workspace`). The wiki always lives at `<workspace>/wiki/`.

**Recommendation:** ship **both** `CLAUDE.md` and `AGENTS.md` in every wiki. `init_vault.py --tool all` does this by default.

## Two CLAUDE.md files — the repo's and the wiki's

Monorepos usually have a root `CLAUDE.md` at the repo root (build commands, package conventions, style rules). When you initialize an lattice-wiki *inside* the repo, there's now a **second** `CLAUDE.md` at `<workspace>/wiki/CLAUDE.md` — the wiki's schema file.

Both are active when Claude Code runs from the repo root: CC loads all `CLAUDE.md` files up the tree. They don't conflict because they describe different things:

- **Root `CLAUDE.md`** — how to build, lint, test; package naming conventions; style rules
- **Wiki `CLAUDE.md`** — how the wiki is structured, ingest/scan/lint workflows, page categories

If you want to keep them visually separated, name the wiki one `CLAUDE.wiki.md` and symlink `<workspace>/wiki/CLAUDE.md` → `CLAUDE.wiki.md`. But most of the time they coexist cleanly.

## Multi-tool wiki

```bash
python scripts/init_vault.py --topic "<topic>" --tool all
```

Creates:
- `<workspace>/wiki/CLAUDE.md`
- `<workspace>/wiki/AGENTS.md`
- `<workspace>/wiki/.cursorrules`

Same content, formatted per tool. You can symlink them to keep in sync:

```bash
cd <workspace>/wiki
ln -sf CLAUDE.md AGENTS.md
```

## Per-tool quickstart

### Claude Code

```bash
cd <repo>             # /lattice-wiki:init resolves <workspace>/wiki/ via lattice-workspace
claude
> /lattice-wiki:init          # if wiki isn't initialized
> /lattice-wiki:scan          # detect packages
> /lattice-wiki:ingest lattice/wiki/raw/specs/auth-migration.md
> /lattice-wiki:query "which packages depend on common-context-node-ts?"
```

### Codex CLI

Codex reads `AGENTS.md` automatically. Then natural language:

```bash
cd <repo>/lattice/wiki
codex
> scan the monorepo and update package pages
> ingest raw/specs/auth-migration.md into the wiki
> query: which packages depend on common-context-node-ts?
```

Codex doesn't have slash commands, but the schema file teaches it the workflows — natural-language triggers work.

### Cursor

```bash
cd <repo>/lattice/wiki
cursor .
```

Open Cursor chat. Cursor auto-reads `AGENTS.md`. Same questions.

### Antigravity / OpenCode / Pi / Gemini CLI

Same as Codex — `AGENTS.md` in the wiki root, natural language.

## Running the scripts directly (any tool)

The scripts don't care which tool calls them. Run from a shell any time:

```bash
# from anywhere — workspace and repo discovered automatically via lattice-workspace
python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/scan_monorepo.py --json
python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/lint_wiki.py
python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/update_index.py
```

Handy aliases:

```bash
alias lattice-wiki-scan='python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/scan_monorepo.py'
alias lattice-wiki-lint='python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/lint_wiki.py'
alias llm-code-index='python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/update_index.py'
alias llm-code-search='python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/wiki_search.py'
```

## MCP exposure (future)

The wiki can be exposed as an MCP tool so any MCP-capable client can query it. Planned — see `engineering/mcp-design` for the pattern.
