# CLAUDE.md

This file scopes guidance to the `graph-wiki` plugin tree.

## What lives here

```
plugins/graph-wiki/
├── .claude-plugin/           # plugin.json — name, version, keywords, env
├── skills/
│   └── graph-wiki/           # maintainer skill: SKILL.md + references/ + scripts/
├── agents/                   # ingestor, librarian, linter, scanner
└── commands/                 # bootstrap, scan, ingest, query, lint, log
```

## Source-of-truth split with `packages/wiki-io/` and `packages/graph-wiki-cli/`

Real Claude-hosted implementation lives in `packages/wiki-io/` — IO, scan, ingest, lint, page templates (under `src/assets/`), and tests. Bedrock-facing runtime commands are exposed by `packages/graph-wiki-cli/` as the `gw` Typer CLI, backed by `packages/graph-wiki-core/`.

The plugin's `skills/graph-wiki/scripts/*.py` are **thin shims**: each one imports `main()` from `wiki_io.<name>` for the Claude branch or shells out to `gw` for the Bedrock branch (opt-in). There is also `_config.py` for backend selection between Claude (default) and the optional Bedrock CLI path.

Current Bedrock shim mapping:

| Plugin shim | Backend selector key | Bedrock argv prefix |
|---|---:|---|
| `scan_monorepo.py` | `scan` | `gw scan` |
| `init_vault.py` | `init` | `gw bootstrap` |
| `ingest_source.py` | `ingest` | `gw ingest` |
| `lint_wiki.py` | `lint` | `gw wiki lint` |
| `wiki_search.py` | `query` | `gw query` |

Each shim preserves the user's original trailing arguments after the mapped prefix. Package-local regression coverage for this contract lives in `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`.

**Scan-specific note:** The Claude branch of `scan_monorepo.py` defaults to a commit-gated **emit → fan-out → apply** pipeline (NOT structural-only by default). `--emit-worklist <path>` drives the emit phase (writes entity pages + serializes `worklist.json`); `--apply-worklist <results.json> --short-head <sha>` drives the apply phase (injects prose results, stamps anchors, writes drift flags, regenerates indexes). A bare invocation is the `--no-narrate` structural-only fast path (no worklist written, no prose generated).

Distribution: shims reference `wiki_io` via the `uv` workspace (`uv run --project "$AGENT_RESEARCH_ROOT"`), so installed users need `AGENT_RESEARCH_ROOT` set and `uv` installed — no `vendor/` directory required. Bedrock users also need the `gw` console script from `graph-wiki-cli` on PATH (e.g. via `uv tool install`), so commands run as bare `gw ...`; where it isn't installed, fall back to `uv run --package graph-wiki-cli gw ...` in this workspace.

**When changing behavior:** edit `packages/wiki-io/` and write tests there for Claude-hosted behavior; edit `packages/graph-wiki-cli/` / `packages/graph-wiki-core/` and their tests for Bedrock CLI behavior. Only edit plugin-side files for skill content, command/agent markdown, hook wiring, or `_config.py`.

## Tests

Pytest, in the package — not in the plugin tree:

```bash
# From repo root (preferred — uv workspace)
uv run pytest packages/wiki-io/

# Single test
uv run pytest packages/wiki-io/tests/test_scan_monorepo.py::TestX::test_y

# Bedrock shim argv contract
uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py
```

`packages/wiki-io/tests/helpers.py` provides `tmp_repo`, `write_pkg`, `write_file`, `write_claude_plugin` for inline throwaway repos. Larger shared shapes live in the repo-root `fixtures/` directory (`single-package/`, `mono-shaped/`, `non-standard/`); tests resolve them via `Path(__file__).resolve().parents[N] / "fixtures"`.

## Script paths must use `${CLAUDE_PLUGIN_ROOT}`

Every command and agent that invokes a bundled script must reference it as `${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<name>.py`. Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` with the absolute path to the installed plugin directory at load time. Hardcoded absolute or relative paths break installs.

The shim under that path resolves the implementation from `wiki_io` via the `uv` workspace.

## Wiki layout invariants

The wiki lives at `<workspace>/wiki/`. The workspace path is resolved by `workspace_io` (defaults to `<repo>/graph-wiki/`; the repo-side `.graph-wiki.local.yaml` `workspace-directory` pointer is dead — `GRAPH_WIKI_WORKSPACE`, normally injected via the repo's `.claude/settings.local.json` env block, is the only external-workspace pointer). The Obsidian vault opens at the workspace root, so `<workspace>/raw/`, `<workspace>/work/`, and `<workspace>/knowledge/` (managed by `workspace_io` and other plugins) are siblings of `<workspace>/wiki/`, not subdirectories of it.

- `<workspace>/raw/` — staging inbox for sources. The LLM never edits file contents here; a successful ingest moves the source to `raw/_archive/<same relative path>`. Owned by `workspace_io`.
- `<workspace>/work/` — unified work tracker. Schema owned by `workspace_io`; lifecycle (lint, sidecar, archive, status) owned by this plugin.
- `<workspace>/wiki/` — the LLM-curated knowledge base. Subdirs (`entities/`, `concepts/`, `sources/`, `adrs/`, `.templates/`) live directly inside; there is no inner vault directory. `entities/` holds one graph-derived page per admitted entity kind (repository, domain, package, app, agent_plugin, dependency, test_suite); there are no separate `apps/`/`packages/`/`domains/` page folders. Architecture syntheses live in `concepts/` as pages with `kind: architecture`.
- `<workspace>/wiki/CLAUDE.md` and `<workspace>/wiki/AGENTS.md` are written by `init_vault` and carry the wiki schema + conventions for the host tool. They are not derived from the repo's folder shape — entity discovery is purely graph-driven, so nothing about the repo's structure is pinned into them.

Inside `<workspace>/wiki/`, every workspace package/app/domain is rendered as a page under the single `entities/` folder, named `<prefix>_<name>[__hex].md`. Bootstrap seeds `entities/.gitkeep`, which `write_entities` removes once real pages exist and restores if all are swept.

When changing how entity pages are discovered, rendered, or written, update `run_scan` / `write_entities` in `packages/wiki-io/` and `packages/graph-wiki-core/` together with the matching reference docs under `plugins/graph-wiki/skills/graph-wiki/references/` — `scan-workflow.md`, `ingest-workflow.md`, `lint-workflow.md`, `query-workflow.md`, `wiki-schema.md`, `monorepo-principles.md`, `page-formats.md`, `obsidian-setup.md`, `cross-tool-setup.md`. The skill's behavior is defined by the union of the script and its reference doc; changing one without the other produces drift.

## Iron rules the skill enforces

These are load-bearing for the skill's contract — preserve them when editing scripts or references:

1. The code is the source of truth. If the vault contradicts the code, update the vault.
2. The LLM never edits file contents under `<workspace>/raw/`; all LLM writes for the wiki go under `<workspace>/wiki/`. Single exception: after a successful ingest the source is *moved* to `<workspace>/raw/_archive/<same relative path>`.
3. Every vault page has YAML frontmatter with `title`, `category`, `summary`, `updated`.
4. Every ingest or scan touches ≥3 files: the changed/new page(s), `index.md`, `log.md`.
5. Every claim on a package/domain page cites either a source page (`[[sources/xxx]]`) or a code path.

## Namespacing after install

Slash commands and agents are namespaced by plugin name automatically:

- Commands: `/graph-wiki:bootstrap`, `/graph-wiki:scan`, `/graph-wiki:ingest`, `/graph-wiki:query`, `/graph-wiki:lint`, `/graph-wiki:log`
- Agents: `graph-wiki:ingestor`, `graph-wiki:librarian`, `graph-wiki:linter`, `graph-wiki:scanner`

Don't try to encode the namespace into command or agent filenames — Claude Code adds it automatically from the plugin name in `.claude-plugin/plugin.json`.
