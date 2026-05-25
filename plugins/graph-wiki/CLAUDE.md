# CLAUDE.md

This file scopes guidance to the `graph-wiki` plugin tree. The marketplace-level `CLAUDE.md` two directories up covers cross-plugin conventions; don't duplicate that here.

## What lives here

```
plugins/graph-wiki/
├── .claude-plugin/           # plugin.json — name, version, keywords, env
├── skills/
│   ├── graph-wiki/      # maintainer skill: SKILL.md + references/ + scripts/
│   └── obsidian-markdown/    # formatting reference invoked when writing vault pages
├── agents/                   # ingestor, librarian, linter, scanner
└── commands/                 # init, scan, ingest, query, lint, log
```

## Source-of-truth split with `packages/vault-io/`

Real implementation lives in `packages/vault-io/` — IO, scan, ingest, lint, layout detection, page templates (under `src/assets/`), and tests.

The plugin's `skills/graph-wiki/scripts/*.py` are **thin shims**: each one imports `main()` from `vault_io.<name>` (claude branch) or shells out to `graph-wiki-agent <cmd>` (bedrock branch, opt-in). There is also `_config.py` for backend selection between Claude (default) and the optional `graph-wiki-agent` Bedrock CLI.

Distribution: shims reference `vault_io` via the `uv` workspace (`uv run --project "$AGENT_RESEARCH_ROOT"`), so installed users need `AGENT_RESEARCH_ROOT` set and `uv` installed — no `vendor/` directory required.

**When changing behavior:** edit `packages/vault-io/` and write tests there. Only edit plugin-side files for skill content, command/agent markdown, hook wiring, or `_config.py`.

## Tests

Pytest, in the package — not in the plugin tree:

```bash
# From repo root (preferred — uv workspace)
uv run pytest packages/vault-io/

# Single test
uv run pytest packages/vault-io/tests/test_layout_io.py::TestX::test_y
```

`packages/vault-io/tests/helpers.py` provides `tmp_repo`, `write_pkg`, `write_file`, `write_claude_plugin` for inline throwaway repos. Larger shared shapes live in the repo-root `fixtures/` directory (`single-package/`, `mono-shaped/`, `non-standard/`); tests resolve them via `Path(__file__).resolve().parents[N] / "fixtures"`.

## Script paths must use `${CLAUDE_PLUGIN_ROOT}`

Every command and agent that invokes a bundled script must reference it as `${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<name>.py`. Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` with the absolute path to the installed plugin directory at load time. Hardcoded absolute or relative paths break installs.

The shim under that path resolves the implementation from `vault_io` via the `uv` workspace.

## Wiki layout invariants

The wiki lives at `<workspace>/wiki/`. The workspace path is resolved by `workspace_io` (defaults to `<repo>/graph-wiki/`; override with `.graph-wiki.local.yaml`'s `workspace-directory` path key). The Obsidian vault opens at the workspace root, so `<workspace>/raw/`, `<workspace>/work/`, and `<workspace>/knowledge/` (managed by `workspace_io` and other plugins) are siblings of `<workspace>/wiki/`, not subdirectories of it.

- `<workspace>/raw/` — immutable ingested sources. The LLM never edits files here. Owned by `workspace_io`.
- `<workspace>/work/` — unified work tracker. Schema owned by `workspace_io`; lifecycle (lint, sidecar, archive, status) owned by this plugin.
- `<workspace>/wiki/` — the LLM-curated knowledge base. Subdirs (`apps/`, `packages/`, `domains/`, `concepts/`, `dependencies/`, `sources/`, `architecture/`, `adrs/`, `.templates/`) live directly inside; there is no inner vault directory.
- `<workspace>/wiki/CLAUDE.md` and `<workspace>/wiki/AGENTS.md` are pinned by `init_vault` and record the detected container layout (apps / packages / domains / docs / package-family). Container detection runs through `detect_containers` and is interactive when classifications are ambiguous. `package-family` is the new (2026-05) classification for containers whose packages are several directory levels below their `source` — see `scan-workflow.md` for the worked example.

Inside `<workspace>/wiki/`, `apps/`, `packages/`, and `domains/` are **conditional** — created only when the detector finds matching containers. A single-package repo has none of those subtrees.

When changing how layout is detected, classified, or written, update `init_vault` in `packages/vault-io/` together with the matching reference docs under `plugins/graph-wiki/skills/graph-wiki/references/` — `detection-workflow.md`, `scan-workflow.md`, `ingest-workflow.md`, `lint-workflow.md`, `query-workflow.md`, `wiki-schema.md`, `monorepo-principles.md`, `page-formats.md`, `obsidian-setup.md`, `cross-tool-setup.md`. The skill's behavior is defined by the union of the script and its reference doc; changing one without the other produces drift.

## Iron rules the skill enforces

These are load-bearing for the skill's contract — preserve them when editing scripts or references:

1. The code is the source of truth. If the vault contradicts the code, update the vault.
2. The LLM never writes to `<workspace>/raw/`; all LLM writes for the wiki go under `<workspace>/wiki/`.
3. Every vault page has YAML frontmatter with `title`, `category`, `summary`, `updated`.
4. Every ingest or scan touches ≥3 files: the changed/new page(s), `index.md`, `log.md`.
5. Every claim on a package/domain page cites either a source page (`[[sources/xxx]]`) or a code path.

## Namespacing after install

Slash commands and agents are namespaced by plugin name automatically:

- Commands: `/graph-wiki:bootstrap`, `/graph-wiki:scan`, `/graph-wiki:ingest`, `/graph-wiki:query`, `/graph-wiki:lint`, `/graph-wiki:log`
- Agents: `graph-wiki:ingestor`, `graph-wiki:librarian`, `graph-wiki:linter`, `graph-wiki:scanner`

Don't try to encode the namespace into command or agent filenames — Claude Code adds it automatically from the plugin name in `.claude-plugin/plugin.json`.
