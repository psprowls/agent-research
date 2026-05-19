---
title: graph-wiki
category: package
summary: Claude Code plugin that builds and maintains a persistent, cross-referenced wiki alongside any source-code project.
status: active
package_path: plugins/graph-wiki
package_type: tool
language: claude-code-plugin
exports: []
depends_on: []
depended_on_by: 0
tags: []
sources: 0
updated: 2026-05-18
tokens: 0
last_sync_commit:
last_sync_at:
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
---

# graph-wiki

## Purpose
Claude Code plugin that builds and maintains a persistent, cross-referenced wiki alongside any source-code project.

## File map - graph-wiki
TODO — describe what this directory contains.

- `CLAUDE.md` — TODO
- `README.md` — TODO

### graph-wiki/.claude-plugin/
TODO — describe what this directory contains.

- `plugin.json` — TODO

### graph-wiki/agents/
TODO — describe what this directory contains.

- `ingestor.md` — TODO
- `librarian.md` — TODO
- `linter.md` — TODO
- `scanner.md` — TODO

### graph-wiki/commands/
TODO — describe what this directory contains.

- `ingest.md` — TODO
- `init.md` — TODO
- `lint.md` — TODO
- `log.md` — TODO
- `query.md` — TODO
- `scan.md` — TODO

### graph-wiki/skills/
TODO — describe what this directory contains.


#### graph-wiki/skills/graph-wiki/
TODO — describe what this directory contains.

- `README.md` — TODO
- `SKILL.md` — TODO

##### graph-wiki/skills/graph-wiki/references/
TODO — describe what this directory contains.

- `cross-tool-setup.md` — TODO
- `detection-workflow.md` — TODO
- `ingest-workflow.md` — TODO
- `lifecycle-rules.md` — TODO
- `lint-workflow.md` — TODO
- `monorepo-principles.md` — TODO
- `obsidian-setup.md` — TODO
- `page-formats.md` — TODO
- `query-workflow.md` — TODO
- `scan-workflow.md` — TODO
- `sidecar-schema.md` — TODO
- `wiki-schema.md` — TODO

##### graph-wiki/skills/graph-wiki/scripts/
TODO — describe what this directory contains.

- `_config.py` — TODO
- `detect_containers.py` — TODO
- `ingest_source.py` — TODO
- `init_vault.py` — TODO
- `lint_wiki.py` — TODO
- `scan_monorepo.py` — TODO
- `wiki_search.py` — TODO

## Sub-pages
- [[api]]      — public API, exports, CLI subcommands
- [[patterns]] — key patterns and conventions
- [[work]]     — bugs, tech debt, features, open questions
- [[context]]  — concepts, decisions, ADRs, sources
