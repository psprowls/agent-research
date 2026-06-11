# Archive raw sources after ingest — design

**Date:** 2026-06-09
**Status:** approved

## Problem

`raw/<kind>/` in the graph-wiki workspace is an inbox of source material awaiting
ingestion, but ingested files stay where they are. Nothing distinguishes
un-ingested sources from already-ingested ones, so the inbox accumulates clutter
and loses its meaning.

## Goal / invariant

Anything under `<workspace>/raw/` (outside `_archived/`) is **un-ingested**. A
successful ingest moves its source to `raw/_archived/<same relative path>`:

- `raw/specs/x.md` → `raw/_archived/specs/x.md`
- `raw/skill/foo/` (directory source) → `raw/_archived/skill/foo/` (moved wholesale)

This mirrors the existing work-item archive convention
(`work/<slug>.md` → `work/archived/<slug>.md` via `work_io/archive.py`).

## Decisions

| Decision | Choice |
| --- | --- |
| Trigger | Automatic, inside `run_ingest_source` — atomic with the ingest, identical for CLI/MCP/plugin callers. No opt-out flag. |
| Directory sources | Skill directories move wholesale. |
| Collision (destination exists) | Overwrite the archived copy. Matches re-ingest semantics where `sources/<slug>.md` is also overwritten. Old versions recoverable only via workspace git. |
| Sources outside `raw/` | Never touched (in-repo docs, loose notes, eval fixtures). |
| Failure posture | A failed move logs a warning; the ingest still returns `status="ok"` and `archived_to` stays `None`. Housekeeping never poisons a completed ingest. |
| Plugin parity | The Claude Code plugin ingestor gets the same behavior via instruction edits. |

## Design

### 1. Pure helper — `wiki_io/ingest_source.py`

Next to `guess_source_type` (which already owns raw-layout knowledge):

```python
def archive_destination(raw: Path, unit: Path) -> Path | None
```

Returns `raw / "_archived" / unit.relative_to(raw)` when `unit` is under `raw/`
and not already under `raw/_archived/`; otherwise `None`. Pure path math, no I/O.

### 2. Move-unit selection and move — `graph_wiki_core/commands/ingest.py`

- `run_ingest_source` already resolves the skill anchor (`resolve_skill_anchor`
  returns the `SKILL.md` path or `None`). The **move unit** is:
  - `anchor.parent` when an anchor exists — *unless* the anchor sits directly in
    a kind folder (its parent's path relative to `raw/` has fewer than 2 parts,
    e.g. `raw/skill/SKILL.md`), in which case move just the file, never the kind
    folder;
  - otherwise `source_path` itself.
- The unit is passed into `_run_common_tail` as a new
  `archive_unit: Path | None` parameter. The tail derives the raw dir from the
  workspace root (`wiki.parent`, matching `workspace_io.paths.raw_dir`) and
  performs the move right before `append_log`:
  1. compute `dest = archive_destination(raw_dir, archive_unit)`; no-op when `None`
  2. `dest.parent.mkdir(parents=True, exist_ok=True)`
  3. delete any existing destination (`unlink` for files, `shutil.rmtree` for dirs)
  4. `shutil.move(unit, dest)`
- The ingest log detail gains `; archived: raw/_archived/...` so `wiki/log.md`
  records both the original path and the destination.
- The whole move is wrapped in try/except per the failure posture above.

### 3. Result and surfaces

- `IngestResult` gains `archived_to: str | None = None` — the
  workspace-relative destination string. `source_path` keeps the original path.
- CLI (`gw wiki ingest`): prints `[ok] Archived source → raw/_archived/...` when
  set; included in `--json` automatically.
- MCP: `WikiIngestOutput` gains the mirrored `archived_to` field.
- `run_ingest_work_item` is untouched (work items have no raw source).

### 4. Plugin parity — `plugins/graph-wiki/`

The ingestor agent and `/graph-wiki:ingest` command docs get a final step: after
writing pages, if the source lives under `<workspace>/raw/` (and not under
`_archived/`), `mkdir -p` the mirrored `_archived` parent and `mv` the source
there. Skill directories move wholesale; an existing destination is replaced.

### 5. Existing callers — verified safe

- eval-harness ingest corpora come from `wiki/entities/` and `wiki/concepts/`;
  sweep fixtures use tmp paths. Neither is under `raw/`, so the guard makes
  archiving a no-op there. No opt-out parameter needed.
- Caveat for the future: a sweep case pointing into `raw/` with `repeats > 1`
  would fail on repeat 2 (file already moved). Acceptable; fixtures should not
  live in the inbox.

## Testing

- **Unit (`wiki-io`)** — `archive_destination`: kind file, nested file, file
  directly in `raw/`, path outside `raw/` → `None`, already under `_archived/`
  → `None`.
- **Integration (`graph-wiki-core`, mocked LLM like existing ingest tests):**
  - raw spec file: moved, `archived_to` set, original gone, log detail records it
  - re-ingest of a recreated same-name file: archived copy overwritten
  - loose file outside `raw/`: untouched, `archived_to is None`
  - skill branch: `raw/skill/<name>/` directory moved wholesale
  - `SKILL.md` directly in `raw/skill/`: only the file moves
  - simulated move failure: ingest still `status="ok"`, `archived_to is None`
- **CLI/MCP:** existing surface tests extended for the new field/output line.

## Out of scope

- Manual sweep/batch archive command (`gw wiki archive-source`) — can mirror
  `gw work archive` later if a need appears.
- Recording the raw path in source-page frontmatter — the log entry plus the
  deterministic path mapping suffice.
- Un-archive / restore tooling.
