---
name: ingest
description: Ingest a source file from raw/ into the Code Wiki — read, discuss, write summary, update package/domain/concept pages, propose ADRs if decisions are captured, flag contradictions with code, update index, append to log. Usage /graph-wiki:ingest <path-to-source>
---

# /graph-wiki:ingest

Ingest a new source (spec, PR, article, ticket, transcript) into the Code Wiki.

The flow: read the source → discuss TL;DR and key claims with you → write a source summary → update every relevant package/domain/concept page → propose an ADR if the source captures a decision → flag contradictions → update `index.md` → append to `log.md`.

A typical ingest touches **5-15 vault pages**. You're in the loop.

## Usage

```
/graph-wiki:ingest <path>
/graph-wiki:ingest raw/specs/auth-migration.md
/graph-wiki:ingest raw/articles/2026-04-react-19-blog.md
/graph-wiki:ingest raw/prs/842-healthkit-retry.md
/graph-wiki:ingest raw/transcripts/2026-04-arch-review.md
/graph-wiki:ingest raw/examples/expo-tanstack-query/   # folder ingest
/graph-wiki:ingest docs/architecture.md          # in-repo doc surfaced by /graph-wiki:scan
```

## Source types

The script guesses from the raw/ subdirectory, or treats the path as an in-repo doc when it resolves under the repo's pinned `docs` container. Supported:

| Path | Source type | Typical touches |
|---|---|---|
| `raw/specs/` | `spec` | Domain/architecture pages + ADR |
| `raw/articles/` | `article` | Concept/dependency pages |
| `raw/prs/` | `pr` | Package pages for every package modified |
| `raw/tickets/` | `ticket` | Issue pages; light package touches |
| `raw/transcripts/` | `transcript` | ADRs + domain pages |
| `raw/examples/` | `example` | Concept pages (often pattern-flavored); package/domain `## Inspirations` bullets |
| `<docs-container>/*.md` | `doc` | Concept/architecture/work pages; gets `last_sync_commit` + `last_sync_at` for drift detection |

## What happens

1. **Prep** — `scripts/ingest_source.py` — metadata, preview, suggested summary path
2. **Read** — reads the source directly
3. **Discuss** — TL;DR, key claims, touched pages, contradictions with vault or code
4. **Confirm** — waits for your go-ahead
5. **Write** — creates the source summary at `<workspace>/wiki/sources/<YYYY-MM>-<slug>.md`
6. **Update** — 5-15 pages across packages/domains/concepts
7. **ADR** — if the source captures a decision, propose creating `<workspace>/wiki/adrs/<NNNN>-<slug>.md`
8. **Contradictions** — flags vault↔vault and vault↔code contradictions
9. **Index** — `scripts/update_index.py` or inline edit
10. **Log** — `scripts/append_log.py --op ingest`
11. **Report** — bulleted wikilinks to every touched page

## Sub-agent

Dispatches the `ingestor` sub-agent. See `agents/ingestor.md`.

## Rules

- The source must be either inside the wiki's `raw/` layer or an in-repo `.md` under the pinned `docs` container (e.g. `docs/architecture.md`)
- `raw/` is immutable — the ingestor reads only
- In-repo docs (`source_type: doc`) get `last_sync_commit` + `last_sync_at` recorded on the source page for `/graph-wiki:lint` drift detection — gated on clean tree + HEAD on `main`. See `agents/ingestor.md` for the full sync-state semantics.
- If a summary page exists, enters **merge mode** (appends a re-ingest section)
- Folders under `raw/examples/` are ingested as a single source summary. `ingest_source.py` warns at >50 files, errors at >200 (almost certainly the wrong directory), and warns when any file exceeds 200 KB.

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/ingest-workflow.md`
