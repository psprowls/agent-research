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
/graph-wiki:ingest raw/specs/                           # batch: whole kind folder
```

## Source types

The script guesses the source type from the raw/ subdirectory. Supported:

| Path | Source type | Typical touches |
|---|---|---|
| `raw/specs/` | `spec` | `[[entities/...]]` links + concept pages (`kind: architecture`) / ADR pages |
| `raw/articles/` | `article` | Concept/dependency pages |
| `raw/prs/` | `pr` | `[[entities/...]]` links for every package modified |
| `raw/tickets/` | `ticket` | Source summary; light `[[entities/...]]` touches |
| `raw/transcripts/` | `transcript` | ADRs + `[[entities/...]]` links for relevant domains |
| `raw/examples/` | `example` | Concept pages (often pattern-flavored); `[[entities/...]]` `## Inspirations` bullets |
| skill dir (`SKILL.md`) | `skill` | Guidance pages under `guidance/<topic>/`; a `## Generates` source page |

## Batch mode

Pointing the command at a **top-level kind folder** ingests everything inside:
`raw/specs/`, `raw/articles/`, `raw/prs/`, `raw/tickets/`, `raw/transcripts/`,
`raw/examples/`, `raw/skills/`. The prep script returns `is_batch: true` with
the unit list — flat kinds: one unit per file (recursive); `skills/`: one per
immediate subdirectory (a loose file directly in `raw/skills/` is NOT a unit —
ingest it individually); `examples/`: one per immediate subdirectory plus loose
files; `_archive/`, `assets/`, and dotfiles are excluded. Pass the prep script the
**absolute path** to the kind folder (resolve `raw/<kind>` against the
workspace, not the repo cwd).

1. **Detect + one confirm** — run the prep script. If `unit_count` is 0: report
   "nothing to ingest" and stop. Otherwise show the unit list and ask ONCE:
   _"raw/<kind>: N units. Will ingest all; NEW concept/ADR pages
   become proposals in `wiki/proposals/`, not real pages. Proceed?"_ After the
   go-ahead, run autonomously — no further questions.
2. **Fan out** — dispatch one `ingestor` sub-agent per unit, **at most 4
   concurrent**. Each dispatch prompt starts with **BATCH MODE** and includes
   the unit path, the workspace path, and the unit type. Workers follow the
   "Batch mode" contract in `agents/ingestor.md` and return a fenced JSON
   report. A worker that crashes, returns no parseable report, or reports
   `"status": "failed"` marks its unit **failed**; the batch continues.
3. **Serial commit phase** — for each successful unit, in unit order:
   - file each `proposals[]` entry:
     `uv run --project "$AGENT_RESEARCH_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/file_proposal.py --kind <kind> --target-slug <slug> --title "<title>" --ref "<the unit report's source_page minus .md>" --rationale "<rationale>" --evidence "<bullet>" [--evidence ...]`
     (duplicate targets across units merge into one ledger note's `origins[]`)
   - apply the reported `existing_page_updates[]` (contradiction callouts on
     shared pages arrive inside these; `contradictions[]` is summary-only —
     surface it in the final report, don't apply it)
   - update `index.md`; refresh `guidance/index.md` + `guidance/<topic>/index.md`
     when the unit wrote guidance pages
   - append the unit's `log_line` as its own `## [YYYY-MM-DD] ingest | <title>`
     entry in `log.md` (one entry per unit); compose the entry body from the
     report fields — source page, guidance pages, proposal ledger paths,
     contradictions — matching single-mode log entries
   - archive the unit to `raw/_archive/<same relative path>`
   A **failed** unit gets none of this — its source stays in `raw/` (still
   un-ingested, re-runnable).
4. **Report** — source pages written, guidance pages, proposals filed (with
   ledger paths), existing pages updated, contradictions flagged, failed units.

## What happens

1. **Prep** — `scripts/ingest_source.py` — metadata, preview, suggested summary path
2. **Read** — reads the source directly
3. **Discuss** — TL;DR, key claims, touched pages, contradictions with vault or code
4. **Confirm** — waits for your go-ahead
5. **Write** — creates the source summary at `<workspace>/wiki/sources/<YYYY-MM>-<slug>.md` (for a **skill** directory: breaks it into guidance pages under `wiki/guidance/<topic>/`, plus a `## Generates` source page — see `references/ingest-workflow.md`)
6. **Link entities** — add `[[entities/...]]` under `## Touches` on the source page; do not edit entity pages (scanner backfills `## Referenced in wiki`)
7. **ADR** — if the source captures a decision, propose creating `<workspace>/wiki/adrs/<NNNN>-<slug>.md`
8. **Contradictions** — flags vault↔vault and vault↔code contradictions
9. **Index** — command-layer ingest updates this automatically; manual plugin edits update relevant sections inline
10. **Log** — append a `## [YYYY-MM-DD] ingest | <title>` entry for manual plugin edits
11. **Archive** — moves the raw source to `raw/_archive/<same relative path>` (skill directories move wholesale; an existing destination is replaced; sources outside `raw/` are never touched)
12. **Report** — bulleted wikilinks to every touched page

## Sub-agent

Dispatches the `ingestor` sub-agent. See `agents/ingestor.md`.

## Rules

- The source must be inside the wiki's `raw/` layer
- `raw/` file contents are never edited — after a successful ingest the source is moved to `raw/_archive/<same relative path>`, so anything left under `raw/` is un-ingested
- If a summary page exists, enters **merge mode** (appends a re-ingest section)
- Folders under `raw/examples/` are ingested as a single source summary. `ingest_source.py` warns at >50 files, errors at >200 (almost certainly the wrong directory), and warns when any file exceeds 200 KB.
- Batch mode: new curated pages are NEVER created directly — they become `wiki/proposals/` ledger notes; the per-unit ≥3-file-touches rule is split between worker (source page) and commit phase (index + log)

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/ingest-workflow.md`
