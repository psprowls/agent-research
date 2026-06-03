---
name: bootstrap
description: Bootstrap a fresh Code Wiki in the resolved graph-wiki workspace — schema files and starter templates. Wiki is created at <workspace>/wiki/. Usage /graph-wiki:bootstrap --topic "<topic>" [--tool all|claude-code|codex|cursor|antigravity]
---

# /graph-wiki:bootstrap

Bootstrap a new Code Wiki. Discovers the workspace via `workspace_io` (walks up from cwd for `.git`, reads `.graph-wiki.yaml` for the workspace path, defaults to `<repo>/graph-wiki`). Creates the wiki at `<workspace>/wiki/`.

The wiki contains `index.md`, `log.md`, and curated subdirs (`entities/`, `adrs/`, `architecture/`, `concepts/`, `sources/`, `.templates/`) directly — there is no inner vault directory. `entities/` holds one graph-derived page per admitted entity (repository, domain, package, app, agent_plugin, dependency, test_suite); there are no separate `apps/`/`packages/`/`domains/` page folders. `raw/` and `work/` are owned by `workspace_io` and live at the workspace root as siblings of `wiki/`.

## Usage

```
/graph-wiki:bootstrap --topic "<topic>"
/graph-wiki:bootstrap --topic "<topic>" --tool <claude-code|codex|cursor|antigravity|opencode|gemini-cli|all>
/graph-wiki:bootstrap --topic "<topic>" --force
```

## Examples

```
/graph-wiki:bootstrap --topic "my-repo"
/graph-wiki:bootstrap --topic "platform monorepo" --tool all
/graph-wiki:bootstrap --topic "api monorepo" --tool codex
```

## What it creates

```
<workspace>/wiki/               # e.g. <repo>/graph-wiki/wiki/
├── index.md
├── log.md
├── entities/                   # one page per admitted entity (seeded with .gitkeep until scanned)
├── concepts/ sources/
├── architecture/ adrs/
├── .templates/                 # page templates for reference
├── CLAUDE.md                   # if --tool claude-code or all
├── AGENTS.md                   # if --tool codex|cursor|antigravity|opencode|gemini-cli|all
├── .cursorrules                # if --tool cursor or all
└── .gitignore
```

`<workspace>/raw/` and `<workspace>/work/` are siblings of `<workspace>/wiki/` and are created/managed by `workspace_io`, not by `/graph-wiki:bootstrap`.

## Next steps

After init:
1. Open `<workspace>/` in Obsidian (point Obsidian at the workspace root so the sidebar shows `wiki/`, `raw/`, `work/` as siblings)
2. Run `/graph-wiki:scan` to populate `<workspace>/wiki/entities/` (one page per admitted entity) from the code graph
3. Stage a source under `<workspace>/raw/` and run `/graph-wiki:ingest`

## Page templates

After init, `<workspace>/wiki/.templates/` holds the templates the scanner and ingest/query flows use as reference (copied from `packages/wiki-io/src/wiki_io/assets/page-templates/`):

- **Per-entity-kind:** `entity-repository.md`, `entity-domain.md`, `entity-package.md`, `entity-app.md`, `entity-agent-plugin.md`, `entity-dependency.md`, `entity-test-suite.md` — the scanner renders one `entities/` page per admitted entity from these.
- **Curated pages:** `concept.md`, `concept-pattern.md`, `source.md`, `adr.md`, `architecture.md`, `dependency.md`, `work.md`, plus `index.md`.

Entity pages are written by `/graph-wiki:scan` from the code graph (see `references/scan-workflow.md`); the curated-page templates are used by `/graph-wiki:ingest` and `/graph-wiki:query` when filing new concept/source/ADR/architecture pages.

## Script

- `${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/init_vault.py`

## Skill Reference

→ `graph-wiki/SKILL.md`
