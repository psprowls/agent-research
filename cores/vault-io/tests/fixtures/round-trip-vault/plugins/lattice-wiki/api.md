---
title: lattice-wiki (plugin) — API
category: package
summary: Slash commands, sub-agents, and ingest source types exposed by lattice-wiki
updated: 2026-05-09
tokens: 961
---

# lattice-wiki (plugin) — API

## Public API

Six slash commands plus four sub-agents (`scanner`, `ingestor`, `linter`, `librarian`). After install, commands and agents are namespaced — `/lattice-wiki:scan`, `lattice-wiki:ingestor`, etc.

### Sub-agents

- `lattice-wiki:ingestor` — drives `/lattice-wiki:ingest` (read source, discuss, update vault, log)
- `lattice-wiki:librarian` — read-only retrieval and synthesis for `/lattice-wiki:query`
- `lattice-wiki:linter` — mechanical + semantic health checks for `/lattice-wiki:lint`
- `lattice-wiki:scanner` — workspace detection and stub creation for `/lattice-wiki:scan`

### Ingest source types

`ingest_source.py` infers `source_type` from the `raw/` subdirectory or treats the path as an in-repo doc when it resolves under the pinned `docs` container. Per [[wiki/concepts/code-wiki-pattern]] the supported types are:

| Source path | `source_type` | Notes |
|---|---|---|
| `raw/specs/` | `spec` | Touches domain/architecture pages, often produces an ADR |
| `raw/articles/` | `article` | Concept/dependency pages |
| `raw/prs/` | `pr` | Package pages for every package modified |
| `raw/tickets/` | `ticket` | Issue pages; light package touches |
| `raw/transcripts/` | `transcript` | ADRs + domain pages |
| `raw/examples/` | `example` | Concept (often pattern-flavored) + `## Inspirations` bullets on packages/domains. Folder ingest supported. |
| `<docs-container>/*.md` | `doc` | Concept/architecture/work; gets `last_sync_commit` + `last_sync_at` for drift detection (gated on clean-on-main) |

`source_type: example` is the headline addition in 0.3.0 — see `## Key patterns` in [[wiki/plugins/lattice-wiki/patterns]].

## CLI

Slash commands declared in `plugin.json` and implemented under `commands/`:

- `/lattice-wiki:init` — bootstrap a fresh wiki with schema and starter structure
- `/lattice-wiki:scan` — walk the repo, detect packages/apps/workspaces, create/update stub pages; surfaces in-repo `docs/*.md` as ingest candidates
- `/lattice-wiki:ingest <path>` — read a source from `raw/` (or an in-repo doc), discuss, update vault, log it
- `/lattice-wiki:query <question>` — search vault, synthesize answer with citations
- `/lattice-wiki:lint` — health check including code drift detection
- `/lattice-wiki:log` — show recent log entries

Pure-stdlib Python scripts under `skills/lattice-wiki/scripts/` back the commands:

- `scan_monorepo.py` — walks the repo, emits diff, refreshes package pages
- `ingest_source.py` — preps a source for `/lattice-wiki:ingest` (metadata + preview)
- `ingest_work_item.py` — strict, non-interactive cross-plugin entry point (exit codes: 0 success, 2 schema rejection, 3 runtime/IO failure)
- `lint_wiki.py` — dispatcher for mechanical + drift checks
- `update_index.py` — regenerates `index.md`
- `append_log.py` — appends a standardized log entry to `log.md`
- `init_vault.py` — bootstraps a fresh wiki
- `wiki_search.py` — BM25 search fallback
- `graph_analyzer.py` — link-graph statistics
- `export_marp.py` — renders a vault page as a Marp slide deck
- `detect_containers.py` — classifies top-level repo dirs as app / package / domain / docs / skip
- `git_state.py` — clean/dirty + branch detection for sync-state gating
- `layout_io.py` — read/write the pinned layout block in CLAUDE.md/AGENTS.md
