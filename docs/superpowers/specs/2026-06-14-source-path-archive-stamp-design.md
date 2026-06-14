# Source `source_path` records the archive location — design

Date: 2026-06-14
Status: approved (brainstorm)

## Problem

When a source under `<workspace>/raw/` is ingested, the source file is moved to
`<workspace>/raw/_archive/<same relative path>` on success. But the generated
source page's frontmatter still records the *pre-move* path, e.g.:

```yaml
source_path: raw/specs/2026-06-09-directory-aware-skill-ingest-design.md
```

That path no longer exists on disk (the file is now under `raw/_archive/...`),
so a reader who wants the original cannot find it. `source_path` should record
where the source *currently lives* after a successful ingest.

Root cause: both ingest surfaces write the source page *before* the archive move
and never reconcile the frontmatter afterward.

- **Bedrock harness** (`graph_wiki_core/commands/ingest.py` → `_run_common_tail`):
  writes the page with the LLM-authored `source_path`, then `shutil.move`s the
  file and computes `archived_to` — but never rewrites the page.
- **CC plugin** (`agents/ingestor.md`, `references/ingest-workflow.md`): the agent
  writes `source_path: raw/<rel>`, then `mv`s to `raw/_archive/<rel>` in a later
  step — frontmatter is never touched.

In-repo docs (`source_type: doc`) are **not** archived and correctly keep their
repo-relative `source_path` + `last_sync_commit`; they are out of scope.

## Scope

- **Fix-forward only.** No backfill sweep of existing pages. (Existing stale
  pages surface through the new lint check below and can be fixed by hand.)
- Fix **both** ingest surfaces so future ingests stamp the archive location.
- Add a mechanical lint check that flags a source page whose `raw/...`
  `source_path` no longer exists on disk.

## Component 1 — Bedrock harness (code)

In `_run_common_tail`, the move already happens at the tail and produces
`archived_to` (workspace-relative, e.g. `raw/_archive/specs/x.md`). After a
**successful** move, rewrite the page's `source_path:` line to `archived_to`.

New helper, mirroring the existing `_set_source_type_in_body`:

```python
def _set_source_path_in_body(text: str, source_path: str) -> str:
    """Insert or replace the `source_path:` line in YAML frontmatter.
    Idempotent; preserves comments/order; returns text unchanged when no
    `---` block is present.
    """
```

Wiring in `_run_common_tail` (after the move succeeds, `archived_to` truthy):

```python
if archived_to:
    current = target_path.read_text(encoding="utf-8")
    stamped = _set_source_path_in_body(current, archived_to)
    if stamped != current:
        target_path.write_text(stamped, encoding="utf-8")
```

Because the rewrite is a deterministic overwrite, it also normalizes whatever the
LLM wrote (absolute path or `raw/...`) to the canonical workspace-relative archive
path.

Gating:
- Failed move / source outside `raw/` / in-repo doc → `archived_to` is `None` →
  no rewrite, page keeps its original value.

Rejected alternative: pre-compute the destination and have the LLM/synthesizer
write it up front. Fragile — the LLM can ignore the instruction, and the move can
still fail. Rewriting after the authoritative `shutil.move` is deterministic.

## Component 2 — CC plugin instructions (docs only)

The plugin agent writes the page before archiving, but the archive destination is
deterministic (`raw/<rel>` → `raw/_archive/<rel>`). Instruct the agent to record
the **post-archive** path at page-creation time.

Touch points:
- `plugins/graph-wiki/agents/ingestor.md` — source-page-write step and archive
  step 12.
- `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md` — step list
  and the source-page section.
- `plugins/graph-wiki/commands/ingest.md` — step list.
- `packages/wiki-io/src/wiki_io/assets/page-templates/source.md` — the
  `source_path:` comment.
- `plugins/graph-wiki/skills/graph-wiki/references/page-formats.md` — the source
  template `source_path:` note.

In-repo docs stay repo-relative — the instructions must keep that distinction
explicit.

## Component 3 — mechanical lint check (code)

In `_mechanical_pass` (`commands/lint.py`), iterate source pages and flag any
whose `source_path` is a workspace-relative `raw/...` path that does **not** exist
on disk (resolved against `wiki.parent`). Covers both `raw/` and `raw/_archive/`
non-existent targets, so it catches the original stale pointer *and* a rare
failed-move mismatch.

Conservative, to avoid false positives — skip:
- pages with no `source_path`,
- absolute paths,
- non-`raw/` paths (repo-relative in-repo docs).

New `LintResult` field `source_path_drift: list[str]`, wired into the report
renderer alongside the other mechanical findings (and the `run_lint` assembly that
populates `LintResult` from the `_mechanical_pass` dict).

## Testing

- `_set_source_path_in_body` unit tests: replace an existing line; insert when
  absent; idempotent on repeat; no-frontmatter passthrough.
- Ingest integration (`_run_common_tail`): after ingesting a `raw/` source, the
  written page's `source_path` equals `archived_to`; a source outside `raw/` is
  unchanged; a simulated failed move leaves the original path.
- Lint: a source page pointing at a non-existent `raw/...` path is flagged; an
  existing `raw/_archive/...` path and a repo-relative doc path are not flagged.

## Out of scope

- Backfilling existing source pages (fix-forward only).
- Any change to in-repo doc (`source_type: doc`) handling.
- Migrations — per repo policy, no migration code before v2.0.
