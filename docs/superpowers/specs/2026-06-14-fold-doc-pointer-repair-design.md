# Fold work-item doc-pointer repair into ingest + work archive

- **Date:** 2026-06-14
- **Status:** Approved (design)
- **Supersedes:** the standalone band-aid `scripts/fix_stale_spec_doc_pointers.py`
  (commit `ceb7c3e2`) and its plan
  `docs/superpowers/plans/2026-06-14-fix-archive-support-stale-artifact-pointers.md`

## Problem

A work item's design phase stamps two ingest-bound frontmatter pointers (via
`work_io.workflow`'s `stamp_doc`):

- `spec_doc: raw/specs/<slug>.md`
- `plan_doc: raw/plans/<slug>.md`

Later, `gw ingest raw/specs/<slug>.md` writes the wiki source page and **moves**
the raw file into `raw/_archive/specs/<slug>.md`
(`graph_wiki_core/commands/ingest.py`, the archive block guarded on
`archived_to`). The move mirror is `wiki_io.ingest_source.archive_destination`:
insert `_archive` after the leading `raw/` segment.

Nothing rewrites the work item's pointer, so it now references a path that no
longer exists — a stale pointer. The same breakage applies identically to
`plan_doc` when a plan is ingested.

The current remedy is a manual, after-the-fact sweep
(`scripts/fix_stale_spec_doc_pointers.py`) that has to be remembered and run by
hand. It also only handles `spec_doc`, silently leaving `plan_doc` to rot.

## Goal

Fold pointer repair into the operations around the move so staleness **cannot
recur**, and retire the standalone script.

Decisions locked during brainstorming:

1. **Insertion point:** ingest move (root cause) **plus** a `gw work archive`
   backstop.
2. **Scope:** both `spec_doc` and `plan_doc`.
3. **Script fate:** delete it; the rule moves into `work-io`.
4. **Shape (Approach A):** a single guarded sweep function called from both
   sites — not a precise-retarget/sweep split.

### Why these sites

The staleness is *caused* by the ingest source-move, not by `gw work archive`.
Archiving a work item moves the work `.md` file but leaves `spec_doc`/`plan_doc`
(workspace-relative paths) untouched, so it never breaks pointers. Hence the
ingest move is the root-cause moment (zero staleness window), and work archive
is a convenient defensive sweep surface that catches anything moved by other
means.

## Design

### 1. New module: `work_io/doc_pointers.py`

Owns the single rewrite rule. A near-lift of the script's proven logic,
generalized to both keys and to the real archive-mirror rule.

```python
_POINTER_LINE = re.compile(
    r"^(?P<key>spec_doc|plan_doc):[ \t]*(?P<val>\S+)[ \t]*$", re.MULTILINE
)

def _frontmatter_span(text: str) -> tuple[int, int] | None:
    """(start, end) char offsets of the frontmatter block body, or None.
    Lifted verbatim from the script."""

def archived_counterpart(ws_root: Path, pointer: str) -> str | None:
    """Corrected pointer iff the current target is MISSING and its raw/_archive/…
    counterpart EXISTS, else None.

    Counterpart = insert '_archive' after the leading 'raw/' segment — the exact
    mirror of wiki_io.ingest_source.archive_destination. Pointers not under raw/
    (or already under raw/_archive/) yield None."""

def sweep(ws_root: Path, *, dry_run: bool) -> SweepReport:
    """Walk wiki/work/**/*.md; repoint stale spec_doc AND plan_doc pointers via a
    surgical in-place splice. Returns a disposition report."""
```

Design points:

- **Guard unchanged.** Only rewrites a pointer that is *both* missing *and* has
  an existing `_archive` counterpart. A pointer that still resolves (active
  item) is never touched. This is what makes `sweep` safe to call from any site,
  including mid-ingest.
- **Counterpart generalization.** `raw/specs/x.md → raw/_archive/specs/x.md` and
  `raw/plans/x.md → raw/_archive/plans/x.md` both fall out of one rule. The
  script's hardcoded `raw/_archive/specs/<name>` is replaced by the
  insert-`_archive`-after-`raw/` mirror.
- **Surgical splice retained.** `text[:m.start()] + f"{key}: {target}" +
  text[m.end():]` — NOT `frontmatter.emit`, which would reserialize the whole
  YAML block (reordering keys, changing quoting, dropping human-curated layout)
  and produce noisy diffs.
- **Idempotent + guarded** → safe to re-run; converges to zero rewrites.
- **Report shape.** `SweepReport` carries `rewrote` / `ok` / `unfixable` lists
  (the same disposition the script produced) so callers can surface changes.
- `index.md` is skipped; body mentions like `` - `spec_doc: …` `` never match
  (the regex is anchored to column 0 and matching is restricted to the
  frontmatter span).

### 2. Call-site wiring

**Ingest move** — `graph_wiki_core/commands/ingest.py`, immediately after
`archived_to` is set and the archive location is stamped (~line 1080):

```python
if archived_to:
    # ...existing frontmatter stamp of archive location...
    try:
        doc_pointers.sweep(workspace_root, dry_run=False)
    except Exception:
        logger.warning("failed to repoint work doc pointers after archive", exc_info=True)
```

- Gated on `archived_to` truthy — only runs when a move actually happened
  (sources outside `raw/` map to None and never trigger it).
- Best-effort `try/except`, matching the surrounding "housekeeping never poisons
  a completed ingest" contract. A repoint failure logs and is swallowed; the
  ingest still succeeds.
- The guard makes this self-targeting: the just-moved file is the only pointer
  that is both missing and has a counterpart at that instant.

**Work-archive backstop** — `graph_wiki_core/commands/work.py`,
`run_work_archive`:

```python
plan = _archive.plan_archive(work_dir, slugs=slugs)
moved = [...]
repoint = doc_pointers.sweep(wiki.parent, dry_run=dry_run)   # backstop, honors dry_run
if not dry_run and plan.actions:
    for action in plan.actions:
        _move(action)
    await run_work_regen_index(workspace_path=workspace_path)
return WorkArchiveResult(
    dry_run=dry_run, moved=moved, skipped=plan.skipped, repointed=repoint.rewrote
)
```

- Runs on every `gw work archive` (sweep or targeted), honoring `--dry-run`.
- Runs *before* the work-item moves so it reads items at their current paths;
  pointer repair is independent of where the work `.md` itself lands.
- Adds a `repointed: list[str]` field to `WorkArchiveResult`, surfaced by the
  CLI alongside `moved`/`skipped` (consistent with how archive already reports,
  and cheap).

### 3. Deletion & reference cleanup

- Delete `scripts/fix_stale_spec_doc_pointers.py` and
  `scripts/test_fix_stale_spec_doc_pointers.py`.
- Grep for lingering references (docs, `CLAUDE.md`, Makefile, CI, the
  superseded plan doc) and update/remove them so nothing points at a deleted
  file.

## Testing

**`work-io` unit tests** (`packages/work-io/tests/test_doc_pointers.py`) —
migrate the script's scenarios and extend:

- `spec_doc` stale → rewritten to `raw/_archive/specs/…`
- `plan_doc` stale → rewritten to `raw/_archive/plans/…` *(new coverage)*
- both stale on one item → both rewritten in a single pass
- pointer already resolves → `ok`, untouched
- missing with no counterpart → `unfixable`, untouched
- `dry_run=True` → reports but writes nothing
- idempotency → second run yields zero rewrites
- body mention `` - `spec_doc: …` `` and `index.md` → never matched/touched

**`graph-wiki-core` tests:**

- *Ingest hook:* after an ingest that archives `raw/specs/x.md`, a work item
  pointing at it is repointed to `raw/_archive/specs/x.md`; a swallowed sweep
  failure still returns the ingest result.
- *Archive backstop:* `run_work_archive` with a stale-pointer item present →
  result `repointed` is populated; `--dry-run` repoints nothing.

**Suites to run** (per-package, per `CLAUDE.md`): `work-io`, `graph-wiki-core`.
Plus the code-change gate from the dev-workflow spec for any touched workflow
surfaces.

## Out of scope

- Migrations / backward-compat shims (single-dev research repo; rebuilds on
  schema change).
- Repairing pointers for files moved by means *other* than ingest archival
  beyond what the guarded sweep already catches.
- Any change to how `spec_doc`/`plan_doc` are originally stamped.
