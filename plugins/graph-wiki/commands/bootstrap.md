---
name: bootstrap
description: Bootstrap a fresh Code Wiki in the resolved graph-wiki workspace — schema files and starter templates. Wiki is created at <workspace>/wiki/. Usage /graph-wiki:bootstrap --topic "<topic>" [--tool all|claude-code|codex|cursor|antigravity]
---

# /graph-wiki:bootstrap

Bootstrap a new Code Wiki. Discovers the workspace via `workspace_io` (walks up from cwd for `.git`, reads `.graph-wiki.yaml` for the workspace path, defaults to `<repo>/graph-wiki`). Creates the wiki at `<workspace>/wiki/`.

The wiki contains `index.md`, `log.md`, and curated subdirs (`adrs/`, `architecture/`, `concepts/`, `dependencies/`, `sources/`, `.templates/`, plus conditional `apps/`, `packages/`, `domains/`) directly — there is no inner vault directory. `raw/` and `work/` are owned by `workspace_io` and live at the workspace root as siblings of `wiki/`.

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

## Container detection

Before initializing the wiki, run the container classifier so the user can confirm or override the detected layout:

1. Run the detector for a JSON snapshot:

   ```bash
   uv run --project "$DEEP_AGENTS_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/detect_containers.py --json
   ```

2. Show the user the detected table — one row per top-level dir, with `source`, `classification`, `children_count`, and `reason`.

3. For each row whose `classification` is `ambiguous`, ask the user: "What is `<source>`? Pick: package / app / domain / package-family / docs / skip." Default to `skip` if they don't answer. Use `package-family` when the dir's children are wiki packages but their manifests live 2+ levels below — see `references/scan-workflow.md`.

4. Once classifications are settled, run `init_vault.py` (it re-runs the detector internally; passing `--non-interactive` lets you skip its prompt loop if you've already collected confirmations). Show the user the resulting layout block from `<workspace>/wiki/CLAUDE.md`.

## What it creates

```
<workspace>/wiki/               # e.g. <repo>/graph-wiki/wiki/
├── index.md
├── log.md
├── packages/ domains/ apps/    # conditional, based on detected containers
├── concepts/ dependencies/
├── sources/ architecture/ adrs/
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
2. Run `/graph-wiki:scan` to populate `<workspace>/wiki/packages/` (one folder per package) from workspace manifests
3. Stage a source under `<workspace>/raw/` and run `/graph-wiki:ingest`

## Sub-page templates

After init, `<workspace>/wiki/.templates/package/` contains five templates for package sub-pages:

- `overview.md` — overview stub with `workflow_hints`
- `api.md` — public API, exports, CLI
- `patterns.md` — key patterns and conventions
- `work.md` — bugs, tech debt, features, open questions
- `context.md` — concepts, decisions, ADRs, sources

`/graph-wiki:scan` now scaffolds the full set of sub-pages eagerly via `ensure_package_pages()` and `ensure_domain_pages()` (in `layout_io.py`), so all five sub-page stubs exist after a scan. `ensure_subpage()` remains available for legacy packages and for on-demand creation during ingest and work-item filing.

## Script

- `${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/init_vault.py`

## Skill Reference

→ `graph-wiki/SKILL.md`
