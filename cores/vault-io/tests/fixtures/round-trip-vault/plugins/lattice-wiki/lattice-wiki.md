---
title: lattice-wiki
category: package
summary: Claude Code plugin that builds and maintains a persistent, cross-referenced markdown wiki alongside any source-code project — single packages, monorepos, or hybrid shapes.
status: active
package_path: plugins/lattice-wiki
package_type: plugin
domain:
language: Python
depends_on: []
tags: [plugin, claude-code, wiki, obsidian, documentation, monorepo, release]
updated: 2026-05-11
last_sync_commit: c2a5068
last_sync_at: 2026-05-10
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 2081
---

# lattice-wiki

## Purpose

lattice-wiki is a Claude Code plugin that builds and maintains a persistent, cross-referenced markdown wiki alongside any source-code project — single packages, monorepos, or hybrid shapes. Developers and Claude Code agents use it to automate the full scan/ingest/query/lint lifecycle: detecting workspace packages, ingesting design docs and specs, answering codebase questions with citations, and health-checking the vault for drift and broken links. It exposes six slash commands (`/lattice-wiki:init`, `scan`, `ingest`, `query`, `lint`, `log`) backed by four sub-agents (`ingestor`, `librarian`, `linter`, `scanner`) and a suite of pure-stdlib Python scripts; the shared library work lives in [[wiki/packages/lattice-wiki-core/lattice-wiki-core]].

## File map - lattice-wiki

Claude Code plugin root. Top-level files are the plugin manifest's metadata, contributor guidance, and the user-facing readme.

- `.gitignore` — git ignores scoped to the plugin directory
- `CLAUDE.md` — plugin-level guidance for Claude Code when working inside this plugin
- `README.md` — user-facing plugin overview

### lattice-wiki/.claude-plugin/

Claude Code plugin descriptor consumed by the marketplace and runtime.

- `plugin.json` — Claude Code plugin manifest (name, version, command/agent declarations). v0.4.0 as of 2026-05-11.

### lattice-wiki/agents/

Sub-agents the plugin exposes — each is a focused prompt that the slash commands hand off to.

- `ingestor.md` — sub-agent that drives `/lattice-wiki:ingest` (read source, discuss, update vault, log)
- `librarian.md` — read-only sub-agent for `/lattice-wiki:query` retrieval and synthesis
- `linter.md` — sub-agent for `/lattice-wiki:lint` mechanical + semantic health checks
- `scanner.md` — sub-agent for `/lattice-wiki:scan` workspace detection and stub creation. **v0.4.0:** now invokes `update_tokens.py` after `update_index.py` to keep `tokens:` frontmatter current on every touched page.

### lattice-wiki/commands/

User-facing slash commands. Each thin wrapper dispatches to a sub-agent or script.

- `init.md` — `/lattice-wiki:init` slash command: bootstrap a fresh wiki
- `scan.md` — `/lattice-wiki:scan` slash command: detect packages, refresh stubs
- `ingest.md` — `/lattice-wiki:ingest <path>` slash command: ingest a raw/ source or in-repo doc
- `query.md` — `/lattice-wiki:query <question>` slash command: answer with citations
- `lint.md` — `/lattice-wiki:lint` slash command: full health check
- `log.md` — `/lattice-wiki:log` slash command: show recent log entries

### lattice-wiki/skills/

Skill bundles loaded into agent context. The plugin ships its own `lattice-wiki` skill plus a shared `obsidian-markdown` reference skill.

#### lattice-wiki/skills/lattice-wiki/

Primary skill: schema, workflows, scripts, and templates that drive every wiki operation.

- `README.md` — skill overview
- `SKILL.md` — main skill body (the plugin's primary instructions)

> Bootstrap templates and page templates live in [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] at `packages/lattice-wiki-core/src/assets/`. They were extracted from the plugin tree into the core package and are now vendored into the plugin at build time.

##### lattice-wiki/skills/lattice-wiki/references/

Long-form reference docs the skill loads on demand — one file per workflow plus the schema/format canon.

- `cross-tool-setup.md` — Codex / Cursor / Antigravity setup notes
- `detection-workflow.md` — container detection workflow
- `ingest-workflow.md` — ingest workflow reference
- `lint-workflow.md` — lint workflow reference
- `monorepo-principles.md` — monorepo handling principles
- `obsidian-setup.md` — Obsidian setup guide
- `page-formats.md` — per-category page format reference (canonical body shapes)
- `query-workflow.md` — query workflow reference
- `scan-workflow.md` — scan workflow reference
- `wiki-schema.md` — full wiki schema reference

##### lattice-wiki/skills/lattice-wiki/scripts/

Pure-stdlib Python that does the actual work behind every slash command — scan, ingest, lint, search, log, and bootstrap. The per-check lint modules and unittest suite live in `lattice-wiki-core` ([[wiki/packages/lattice-wiki-core/lattice-wiki-core]]).

- `append_log.py` — appends a standardized log entry to `log.md`
- `detect_containers.py` — classifies top-level repo dirs as app / package / domain / docs / skip
- `export_marp.py` — renders a vault page as a Marp slide deck
- `git_state.py` — clean/dirty + branch detection for sync-state gating
- `graph_analyzer.py` — link-graph statistics
- `ingest_source.py` — preps a source for `/lattice-wiki:ingest` (metadata + preview)
- `ingest_work_item.py` — strict, non-interactive entry point lattice-workflows calls into
- `init_vault.py` — bootstraps a fresh wiki
- `layout_io.py` — read/write the pinned layout block in CLAUDE.md/AGENTS.md
- `lint_wiki.py` — dispatcher for mechanical + drift checks
- `scan_monorepo.py` — walks the repo, emits diff, refreshes package pages
- `update_index.py` — regenerates `index.md`
- `update_tokens.py` — **new in v0.4.0.** Counts tokens in every wiki page and writes `tokens:` frontmatter; called by the scanner agent after `update_index.py` so the field stays current after each scan.
- `wiki_search.py` — BM25 search fallback

#### lattice-wiki/skills/obsidian-markdown/

Shared reference skill for Obsidian-flavored markdown — wikilinks, callouts, embeds, frontmatter properties.

- `SKILL.md` — Obsidian-flavored markdown reference skill (wikilinks, callouts, embeds, properties)

##### lattice-wiki/skills/obsidian-markdown/references/

Per-feature deep-dive references the skill loads on demand.

- `CALLOUTS.md` — Obsidian callout syntax reference
- `EMBEDS.md` — Obsidian embed syntax reference
- `PROPERTIES.md` — Obsidian frontmatter properties reference

## Sub-pages

- [[wiki/plugins/lattice-wiki/api]]      — slash commands, sub-agents, ingest source types, CLI scripts
- [[wiki/plugins/lattice-wiki/patterns]] — key patterns, conventions, downstream consumers
- [[wiki/plugins/lattice-wiki/work]]     — bugs, tech debt, features, open questions
- [[wiki/plugins/lattice-wiki/context]]  — concepts, decisions, sources

## Appears in sources

- [[wiki/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite]] — schema docs (`CLAUDE.md`, `AGENTS.md`) and page templates document the workspace-root-relative wikilink form (`[[work/<slug>]]`, `[[wiki/<category>/...]]`); decision in [[wiki/adrs/0015-workspace-root-wikilink-form]].
- [[wiki/sources/2026-05-per-plugin-version-tracking-in-lattice-yaml]] — `lattice-wiki` is the **reference plugin** for the v0.3.0 per-plugin version-tracking integration. Every user-facing slash command (`/lattice-wiki:scan`, `/lattice-wiki:ingest`, `/lattice-wiki:query`, `/lattice-wiki:lint`, `/lattice-wiki:log`) gates on `lattice_workspace.warn_if_stale` via `lattice_wiki_core._version_check.check_for_updates` at script entry; `/lattice-wiki:init` passes `version=__version__` into `workspace_init`. See [[wiki/concepts/plugin-versioning-and-update-mechanism]] for the cross-plugin pattern.
- [[wiki/sources/2026-05-lattice-release-wiki-sync]] — repo-level `/release` slash command (`.claude/commands/release.md`) dispatches the `lattice-wiki:scanner` sub-agent as an optional post-release Step 9 once HEAD is on `main` and the tree is clean, then commits any resulting wiki edits as a follow-up `docs: post-release wiki sync for <TAG>` commit. The shipped flow runs `cg update` + `cg sync-wiki` before the scanner.
