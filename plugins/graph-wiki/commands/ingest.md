---
name: ingest
description: Ingest a source file from raw/ into the Code Wiki — read, discuss, write summary, link relevant code entities via [[entities/...]] and update concept/ADR pages, propose ADRs if decisions are captured, flag contradictions with code, update index, append to log. Usage /graph-wiki:ingest <path-to-source>
---

# /graph-wiki:ingest

Ingest a new source (spec, PR, article, ticket, transcript) into the Code Wiki.

The flow: read the source → discuss TL;DR and key claims with you → write a source summary → link relevant code entities via `[[entities/...]]` and update concept/ADR pages → propose an ADR if the source captures a decision → flag contradictions → update `index.md` → append to `log.md`.

A typical ingest touches **5-15 vault pages**. You're in the loop.

## Usage

```
/graph-wiki:ingest <path>
/graph-wiki:ingest raw/specs/auth-migration.md
/graph-wiki:ingest raw/articles/2026-04-react-19-blog.md
/graph-wiki:ingest raw/prs/842-healthkit-retry.md
/graph-wiki:ingest raw/transcripts/2026-04-arch-review.md
/graph-wiki:ingest raw/examples/expo-tanstack-query/   # folder ingest
```

## Source types

The script guesses the source type from the raw/ subdirectory. Supported:

| Path | Source type | Typical touches |
|---|---|---|
| `raw/specs/` | `spec` | `[[entities/...]]` links + architecture/ADR pages |
| `raw/articles/` | `article` | Concept/dependency pages |
| `raw/prs/` | `pr` | `[[entities/...]]` links for every package modified |
| `raw/tickets/` | `ticket` | Source summary; light `[[entities/...]]` touches |
| `raw/transcripts/` | `transcript` | ADRs + `[[entities/...]]` links for relevant domains |
| `raw/examples/` | `example` | Concept pages (often pattern-flavored); `[[entities/...]]` `## Inspirations` bullets |

## What happens

1. **Prep** — `scripts/ingest_source.py` — metadata, preview, suggested summary path
2. **Read** — reads the source directly
3. **Discuss** — TL;DR, key claims, touched pages, contradictions with vault or code
4. **Confirm** — waits for your go-ahead
5. **Write** — creates the source summary at `<workspace>/wiki/sources/<YYYY-MM>-<slug>.md`
6. **Link entities** — add `[[entities/...]]` under `## Touches` on the source page; do not edit entity pages (scanner backfills `## Referenced in wiki`)
7. **ADR** — if the source captures a decision, propose creating `<workspace>/wiki/adrs/<NNNN>-<slug>.md`
8. **Contradictions** — flags vault↔vault and vault↔code contradictions
9. **Index** — `scripts/update_index.py` or inline edit
10. **Log** — `scripts/append_log.py --op ingest`
11. **Report** — bulleted wikilinks to every touched page

## Sub-agent

Dispatches the `ingestor` sub-agent. See `agents/ingestor.md`.

## Rules

- The source must be inside the wiki's `raw/` layer
- `raw/` is immutable — the ingestor reads only
- If a summary page exists, enters **merge mode** (appends a re-ingest section)
- Folders under `raw/examples/` are ingested as a single source summary. `ingest_source.py` warns at >50 files, errors at >200 (almost certainly the wrong directory), and warns when any file exceeds 200 KB.

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/ingest-workflow.md`
