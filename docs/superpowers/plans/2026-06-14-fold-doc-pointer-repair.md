# Fold work-item doc-pointer repair into ingest + work archive — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use graph-wiki:subagent-driven-development (recommended) or graph-wiki:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make stale `spec_doc`/`plan_doc` pointers impossible by repointing them at the moment ingest archives the source, with a `gw work archive` backstop, and retire the manual sweep script.

**Architecture:** Extract one guarded, idempotent sweep into `work_io/doc_pointers.py`. It rewrites a work item's `spec_doc`/`plan_doc` frontmatter pointer only when the current target is missing AND its `raw/_archive/…` counterpart exists. `run_ingest_source` calls it (best-effort) right after a successful archive move; `run_work_archive` calls it as a backstop and surfaces the rewrites. The standalone `scripts/fix_stale_spec_doc_pointers.py` is deleted.

**Tech Stack:** Python 3.11, `uv` workspace, pytest (`asyncio_mode = "auto"`), regex-based frontmatter splice (no YAML reserialization).

**Design spec:** `docs/superpowers/specs/2026-06-14-fold-doc-pointer-repair-design.md`

**Worktree:** `.claude/worktrees/feat+fold-doc-pointer-repair` on branch `feat/fold-doc-pointer-repair`. Use that worktree's venv: `<worktree>/.venv/bin/python` (or `uv run --package <pkg> pytest`). The venv is already `uv sync`'d.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `packages/work-io/src/work_io/doc_pointers.py` | **Create.** The single rewrite rule: `sweep()`, `archived_counterpart()`, `SweepReport`. |
| `packages/work-io/tests/unit/test_doc_pointers.py` | **Create.** Unit coverage for the sweep (both keys, guard, idempotency, dry-run, body/index exclusion). |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` | **Modify.** Call `doc_pointers.sweep` after a successful archive move (root-cause hook). |
| `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` | **Modify.** Add a test: ingesting a `raw/specs/<x>.md` repoints a work item pointing at it. |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py` | **Modify.** Add `repointed` to `WorkArchiveResult`; call `sweep` in `run_work_archive` (backstop). |
| `packages/graph-wiki-core/tests/unit/test_commands_work.py` | **Modify.** Add a test: `run_work_archive` repoints a stale pointer; `--dry-run` does not write. |
| `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py` | **Modify.** Render `repointed` lines in the `gw work archive` text output. |
| `scripts/fix_stale_spec_doc_pointers.py` | **Delete.** Logic now lives in work-io. |
| `scripts/test_fix_stale_spec_doc_pointers.py` | **Delete.** Coverage migrated to `test_doc_pointers.py`. |
| `docs/superpowers/plans/2026-06-14-fix-archive-support-stale-artifact-pointers.md` | **Modify.** Mark superseded; it references the deleted script. |

---

### Task 1: Create the guarded sweep in `work_io/doc_pointers.py`

**Goal:** A single, idempotent, formatting-preserving function that repoints stale `spec_doc`/`plan_doc` pointers, covered by unit tests.

**Files:**
- Create: `packages/work-io/src/work_io/doc_pointers.py`
- Test: `packages/work-io/tests/unit/test_doc_pointers.py`

**Acceptance Criteria:**
- [ ] `sweep(ws_root, dry_run=False)` rewrites a stale `spec_doc` to `raw/_archive/specs/<name>` and a stale `plan_doc` to `raw/_archive/plans/<name>`.
- [ ] A pointer that still resolves is reported `ok` and left byte-identical.
- [ ] A missing pointer with no archive counterpart is reported `unfixable` and left untouched.
- [ ] Both keys stale on one page are rewritten in a single pass.
- [ ] `dry_run=True` populates `report.rewrote` but writes nothing.
- [ ] A second run yields zero rewrites (idempotent).
- [ ] Body mentions and `index.md` are never matched/touched.

**Verify:** `uv run --package work-io pytest tests/unit/test_doc_pointers.py -v` → all pass.

**Steps:**

- [ ] **Step 1: Write the failing tests** — `packages/work-io/tests/unit/test_doc_pointers.py`

```python
"""Unit tests for work_io.doc_pointers.sweep (stale spec_doc/plan_doc repair)."""

from __future__ import annotations

from pathlib import Path

from work_io.doc_pointers import sweep


def _ws(tmp_path: Path) -> Path:
    """Lay out an empty workspace: wiki/work + raw/{specs,plans,_archive/...}."""
    (tmp_path / "wiki" / "work").mkdir(parents=True)
    (tmp_path / "raw" / "specs").mkdir(parents=True)
    (tmp_path / "raw" / "plans").mkdir(parents=True)
    (tmp_path / "raw" / "_archive" / "specs").mkdir(parents=True)
    (tmp_path / "raw" / "_archive" / "plans").mkdir(parents=True)
    return tmp_path


def _work_item(ws: Path, slug: str, **fm: str) -> Path:
    lines = "\n".join(f"{k}: {v}" for k, v in fm.items())
    md = ws / "wiki" / "work" / f"{slug}.md"
    md.write_text(f"---\n{lines}\n---\n\nbody\n", encoding="utf-8")
    return md


def test_spec_doc_stale_rewritten_to_archive(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "foo.md").write_text("spec", encoding="utf-8")
    md = _work_item(ws, "2026-01-01-foo", status="resolved", spec_doc="raw/specs/foo.md")

    report = sweep(ws, dry_run=False)

    assert "spec_doc: raw/_archive/specs/foo.md" in md.read_text(encoding="utf-8")
    assert report.rewrote == ["wiki/work/2026-01-01-foo.md (spec_doc) -> raw/_archive/specs/foo.md"]
    assert report.ok == []
    assert report.unfixable == []


def test_plan_doc_stale_rewritten_to_archive(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "plans" / "bar.md").write_text("plan", encoding="utf-8")
    md = _work_item(ws, "2026-01-02-bar", status="resolved", plan_doc="raw/plans/bar.md")

    report = sweep(ws, dry_run=False)

    assert "plan_doc: raw/_archive/plans/bar.md" in md.read_text(encoding="utf-8")
    assert report.rewrote == ["wiki/work/2026-01-02-bar.md (plan_doc) -> raw/_archive/plans/bar.md"]


def test_both_pointers_stale_rewritten_in_one_pass(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "baz.md").write_text("s", encoding="utf-8")
    (ws / "raw" / "_archive" / "plans" / "baz.md").write_text("p", encoding="utf-8")
    md = _work_item(
        ws, "2026-01-03-baz", status="resolved",
        spec_doc="raw/specs/baz.md", plan_doc="raw/plans/baz.md",
    )

    report = sweep(ws, dry_run=False)

    text = md.read_text(encoding="utf-8")
    assert "spec_doc: raw/_archive/specs/baz.md" in text
    assert "plan_doc: raw/_archive/plans/baz.md" in text
    assert len(report.rewrote) == 2


def test_pointer_that_resolves_left_untouched(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "specs" / "live.md").write_text("s", encoding="utf-8")
    md = _work_item(ws, "2026-01-04-live", status="in_progress", spec_doc="raw/specs/live.md")
    before = md.read_text(encoding="utf-8")

    report = sweep(ws, dry_run=False)

    assert md.read_text(encoding="utf-8") == before
    assert report.rewrote == []
    assert report.ok == ["wiki/work/2026-01-04-live.md (spec_doc)"]


def test_missing_with_no_counterpart_unfixable(tmp_path):
    ws = _ws(tmp_path)
    md = _work_item(ws, "2026-01-05-gone", status="resolved", spec_doc="raw/specs/gone.md")
    before = md.read_text(encoding="utf-8")

    report = sweep(ws, dry_run=False)

    assert md.read_text(encoding="utf-8") == before
    assert report.rewrote == []
    assert report.unfixable == ["wiki/work/2026-01-05-gone.md (spec_doc=raw/specs/gone.md)"]


def test_dry_run_reports_without_writing(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "foo.md").write_text("s", encoding="utf-8")
    md = _work_item(ws, "2026-01-06-foo", status="resolved", spec_doc="raw/specs/foo.md")
    before = md.read_text(encoding="utf-8")

    report = sweep(ws, dry_run=True)

    assert md.read_text(encoding="utf-8") == before
    assert len(report.rewrote) == 1


def test_idempotent_second_run_zero_rewrites(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "foo.md").write_text("s", encoding="utf-8")
    _work_item(ws, "2026-01-07-foo", status="resolved", spec_doc="raw/specs/foo.md")

    sweep(ws, dry_run=False)
    report2 = sweep(ws, dry_run=False)

    assert report2.rewrote == []
    assert report2.ok == ["wiki/work/2026-01-07-foo.md (spec_doc)"]


def test_body_mention_and_missing_key_not_matched(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "foo.md").write_text("s", encoding="utf-8")
    md = ws / "wiki" / "work" / "2026-01-08-doc.md"
    md.write_text(
        "---\nstatus: resolved\n---\n\nWe set `- spec_doc: raw/specs/foo.md` in the body.\n",
        encoding="utf-8",
    )
    before = md.read_text(encoding="utf-8")

    report = sweep(ws, dry_run=False)

    assert md.read_text(encoding="utf-8") == before
    assert report.rewrote == []


def test_index_md_skipped(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "foo.md").write_text("s", encoding="utf-8")
    md = ws / "wiki" / "work" / "index.md"
    md.write_text("---\nspec_doc: raw/specs/foo.md\n---\n", encoding="utf-8")
    before = md.read_text(encoding="utf-8")

    report = sweep(ws, dry_run=False)

    assert md.read_text(encoding="utf-8") == before
    assert report.rewrote == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package work-io pytest tests/unit/test_doc_pointers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'work_io.doc_pointers'`.

- [ ] **Step 3: Write the implementation** — `packages/work-io/src/work_io/doc_pointers.py`

```python
"""Repair stale spec_doc/plan_doc pointers in work items after source archival.

A work item's design phase stamps ``spec_doc: raw/specs/<slug>.md`` (or
``plan_doc: raw/plans/<slug>.md``). When that source is later ingested, the raw
file moves to ``raw/_archive/<...>`` (mirroring
``wiki_io.ingest_source.archive_destination``) but the frontmatter pointer is not
rewritten, leaving it stale.

``sweep`` rewrites such a pointer only when BOTH the current target is missing
AND its ``raw/_archive/`` counterpart exists, so active items are never touched
and the operation is idempotent and safe to call from any site (mid-ingest, or
as a ``gw work archive`` backstop). The rewrite is a surgical in-place splice on
the frontmatter block — it never reserializes YAML, so key order, formatting,
and comments are preserved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Frontmatter-level keys sit at column 0. Body mentions such as "- `spec_doc: …`"
# never match this anchored pattern; matching is further restricted to the
# frontmatter span by slicing it out before substitution.
_POINTER_LINE = re.compile(r"^(?P<key>spec_doc|plan_doc):[ \t]*(?P<val>\S+)[ \t]*$", re.MULTILINE)


@dataclass
class SweepReport:
    """Disposition of a sweep: which pointers were rewritten, already-ok, or unfixable."""

    rewrote: list[str] = field(default_factory=list)
    ok: list[str] = field(default_factory=list)
    unfixable: list[str] = field(default_factory=list)


def _frontmatter_span(text: str) -> tuple[int, int] | None:
    """Return (start, end) char offsets of the frontmatter block body, or None.

    The block is the region between the opening ``---\\n`` fence and the closing
    ``\\n---`` fence. Files without a leading fence have no frontmatter.
    """
    if not text.startswith("---\n"):
        return None
    close = text.find("\n---", 4)
    if close == -1:
        return None
    return 4, close + 1


def archived_counterpart(ws_root: Path, pointer: str) -> str | None:
    """Return the corrected pointer if a rewrite applies, else None.

    Rewrite iff the current target is missing AND the archive counterpart exists.
    The counterpart mirrors ``wiki_io.ingest_source.archive_destination``: insert
    ``_archive`` after the leading ``raw/`` segment. Pointers that still resolve,
    are not under ``raw/``, or are already under ``raw/_archive/`` return None.
    """
    if (ws_root / pointer).exists():
        return None
    parts = Path(pointer).parts
    if len(parts) < 2 or parts[0] != "raw" or parts[1] == "_archive":
        return None
    candidate = Path("raw", "_archive", *parts[1:]).as_posix()
    return candidate if (ws_root / candidate).exists() else None


def sweep(ws_root: Path, *, dry_run: bool) -> SweepReport:
    """Walk wiki/work/**/*.md and repoint stale spec_doc/plan_doc pointers.

    Guarded (only missing-with-counterpart), idempotent, and formatting-preserving.
    Returns a :class:`SweepReport`. ``index.md`` and body text are never touched.
    """
    report = SweepReport()
    work_dir = ws_root / "wiki" / "work"
    if not work_dir.is_dir():
        return report

    for md in sorted(work_dir.rglob("*.md")):
        if md.name == "index.md":
            continue
        text = md.read_text(encoding="utf-8")
        span = _frontmatter_span(text)
        if span is None:
            continue
        fm_start, fm_end = span
        rel = md.relative_to(ws_root).as_posix()
        frontmatter = text[fm_start:fm_end]

        def _replace(m: re.Match[str]) -> str:
            key, pointer = m.group("key"), m.group("val")
            if (ws_root / pointer).exists():
                report.ok.append(f"{rel} ({key})")
                return m.group(0)
            target = archived_counterpart(ws_root, pointer)
            if target is None:
                report.unfixable.append(f"{rel} ({key}={pointer})")
                return m.group(0)
            report.rewrote.append(f"{rel} ({key}) -> {target}")
            return f"{key}: {target}"

        new_frontmatter = _POINTER_LINE.sub(_replace, frontmatter)
        if new_frontmatter != frontmatter and not dry_run:
            md.write_text(text[:fm_start] + new_frontmatter + text[fm_end:], encoding="utf-8")

    return report
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package work-io pytest tests/unit/test_doc_pointers.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Run the full work-io suite (no regressions)**

Run: `uv run --package work-io pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/work-io/src/work_io/doc_pointers.py packages/work-io/tests/unit/test_doc_pointers.py
git commit -m "feat(work-io): guarded sweep to repoint stale spec_doc/plan_doc pointers"
```

---

### Task 2: Hook the sweep into the ingest archive move

**Goal:** After `run_ingest_source` successfully archives a raw source, stale work-item pointers to it are repointed automatically (best-effort, never poisons the ingest).

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` (import + call inside the `if archived_to:` block, ~line 1086)
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (add one test)

**Acceptance Criteria:**
- [ ] Ingesting `raw/specs/foo.md` (which archives it to `raw/_archive/specs/foo.md`) repoints a work item whose `spec_doc` pointed at `raw/specs/foo.md`.
- [ ] A `doc_pointers.sweep` exception is swallowed (logged) and the ingest still returns its `IngestResult`.

**Verify:** `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k repoint -v` → pass.

**Steps:**

- [ ] **Step 1: Write the failing test** — append to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`

```python
# ---------------------------------------------------------------------------
# test_run_ingest_source_repoints_work_doc_pointer (doc-pointer repair)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_repoints_work_doc_pointer(tmp_path: Path) -> None:
    """Ingesting a raw/specs source archives it and repoints a work item's spec_doc."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    wiki = tmp_path / "wiki"
    (wiki / "work").mkdir(parents=True)
    (wiki / "log.md").write_text("", encoding="utf-8")

    # Source lives under raw/specs so the archive move triggers.
    source_file = tmp_path / "raw" / "specs" / "foo.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("# Foo\n\nSpec content.", encoding="utf-8")

    # A resolved work item still points at the pre-archive location.
    work_item = wiki / "work" / "2026-01-01-foo.md"
    work_item.write_text(
        "---\nstatus: resolved\nspec_doc: raw/specs/foo.md\n---\n\nbody\n",
        encoding="utf-8",
    )

    fake_llm_response = "---\ntarget_slug: foo\ntitle: Foo\nsummary: A spec\n---\n\nBody."

    _seed_graph_db_for_ingest_tests(wiki, packages=[])

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, tmp_path)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, wiki)

    # The source moved to the archive, and the work pointer followed it.
    assert (tmp_path / "raw" / "_archive" / "specs" / "foo.md").exists()
    assert result.archived_to == "raw/_archive/specs/foo.md"
    assert "spec_doc: raw/_archive/specs/foo.md" in work_item.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k repoint -v`
Expected: FAIL — `spec_doc: raw/_archive/specs/foo.md` not found (pointer still says `raw/specs/foo.md`).

- [ ] **Step 3: Add the import** — `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`

Add alongside the existing `from workspace_io.paths import graph_dir, raw_dir` (line 66):

```python
from work_io import doc_pointers
```

- [ ] **Step 4: Add the repoint call** inside the existing `if archived_to:` block (after the `_set_source_path_in_body` stamp, ~line 1090)

Existing block:

```python
    if archived_to:
        current_page = target_path.read_text(encoding="utf-8")
        stamped_page = _set_source_path_in_body(current_page, archived_to)
        if stamped_page != current_page:
            target_path.write_text(stamped_page, encoding="utf-8")
```

becomes:

```python
    if archived_to:
        current_page = target_path.read_text(encoding="utf-8")
        stamped_page = _set_source_path_in_body(current_page, archived_to)
        if stamped_page != current_page:
            target_path.write_text(stamped_page, encoding="utf-8")
        # Repoint any work item whose spec_doc/plan_doc pointed at the just-moved
        # source. Best-effort: housekeeping never poisons a completed ingest.
        try:
            doc_pointers.sweep(wiki.parent, dry_run=False)
        except Exception:
            logger.warning("failed to repoint work doc pointers after archive", exc_info=True)
```

- [ ] **Step 5: Run the new test + the full ingest suite**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -v`
Expected: PASS (existing tests + the new one).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(graph-wiki-core): repoint work doc pointers on ingest archive move"
```

---

### Task 3: Add the `gw work archive` backstop and surface rewrites

**Goal:** `run_work_archive` runs the sweep as a defensive backstop (honoring `--dry-run`), exposes the rewrites via a new `repointed` field, and the CLI prints them.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py` (import; `WorkArchiveResult.repointed`; call in `run_work_archive`)
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py` (render `repointed`)
- Test: `packages/graph-wiki-core/tests/unit/test_commands_work.py` (add one test)

**Acceptance Criteria:**
- [ ] `WorkArchiveResult` has `repointed: list[str]` defaulting to `[]`.
- [ ] `run_work_archive` repoints a stale pointer and returns it in `result.repointed`.
- [ ] With `dry_run=True`, the work item is left byte-identical but `result.repointed` is populated.
- [ ] The CLI text output prints a `repointed:` line per rewrite; `--json` includes the field (via `dataclasses.asdict`).

**Verify:** `uv run --package graph-wiki-core pytest tests/unit/test_commands_work.py -k archive -v` → pass.

**Steps:**

- [ ] **Step 1: Write the failing test** — append to `packages/graph-wiki-core/tests/unit/test_commands_work.py`

```python
# ---------------------------------------------------------------------------
# test_run_work_archive_repoints_stale_doc_pointer (backstop)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_work_archive_repoints_stale_doc_pointer(tmp_path: Path) -> None:
    """The archive backstop repoints a stale spec_doc whose source was archived."""
    from graph_wiki_core.commands.work import run_work_archive

    wiki = tmp_path / "wiki"
    (wiki / "work").mkdir(parents=True)
    (tmp_path / "raw" / "_archive" / "specs").mkdir(parents=True)
    (tmp_path / "raw" / "_archive" / "specs" / "foo.md").write_text("s", encoding="utf-8")

    # An in-progress item (NOT terminal — so it is repointed but not moved).
    work_item = wiki / "work" / "2026-01-01-foo.md"
    work_item.write_text(
        "---\nstatus: in_progress\nspec_doc: raw/specs/foo.md\n---\n\nbody\n",
        encoding="utf-8",
    )

    with patch("graph_wiki_core.commands.work.resolve_wiki_and_repo") as mock_resolve:
        mock_resolve.return_value = (wiki, tmp_path)
        result = await run_work_archive(workspace_path=tmp_path, dry_run=False)

    assert "spec_doc: raw/_archive/specs/foo.md" in work_item.read_text(encoding="utf-8")
    assert result.repointed == ["wiki/work/2026-01-01-foo.md (spec_doc) -> raw/_archive/specs/foo.md"]


@pytest.mark.asyncio
async def test_run_work_archive_dry_run_does_not_write_repoint(tmp_path: Path) -> None:
    """dry_run reports the would-be repoint but leaves the work item untouched."""
    from graph_wiki_core.commands.work import run_work_archive

    wiki = tmp_path / "wiki"
    (wiki / "work").mkdir(parents=True)
    (tmp_path / "raw" / "_archive" / "specs").mkdir(parents=True)
    (tmp_path / "raw" / "_archive" / "specs" / "foo.md").write_text("s", encoding="utf-8")

    work_item = wiki / "work" / "2026-01-01-foo.md"
    work_item.write_text(
        "---\nstatus: in_progress\nspec_doc: raw/specs/foo.md\n---\n\nbody\n",
        encoding="utf-8",
    )
    before = work_item.read_text(encoding="utf-8")

    with patch("graph_wiki_core.commands.work.resolve_wiki_and_repo") as mock_resolve:
        mock_resolve.return_value = (wiki, tmp_path)
        result = await run_work_archive(workspace_path=tmp_path, dry_run=True)

    assert work_item.read_text(encoding="utf-8") == before
    assert len(result.repointed) == 1
```

> Note: `test_commands_work.py` already imports `pytest`, `Path`, and `patch`. If a lint check flags a missing import, add it — do not duplicate an existing one.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_work.py -k "repoint or dry_run_does_not_write_repoint" -v`
Expected: FAIL — `AttributeError: 'WorkArchiveResult' object has no attribute 'repointed'`.

- [ ] **Step 3: Add the import** — `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py`

Add alongside the existing `from work_io import archive as _archive` (line 32):

```python
from work_io import doc_pointers as _doc_pointers
```

- [ ] **Step 4: Add the `repointed` field** to `WorkArchiveResult` (line 78-84)

```python
@dataclass
class WorkArchiveResult:
    """Result of run_work_archive()."""

    dry_run: bool
    moved: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    repointed: list[str] = field(default_factory=list)
```

- [ ] **Step 5: Call the sweep in `run_work_archive`** (replace the body from `plan = ...` to the `return`)

```python
    plan = _archive.plan_archive(work_dir, slugs=slugs)
    moved = [{"slug": a.slug, "src": str(a.src), "dst": str(a.dst)} for a in plan.actions]

    # Backstop: repoint any stale spec_doc/plan_doc whose source was archived.
    # Runs before the work-item moves (independent of where the .md itself lands).
    repoint = _doc_pointers.sweep(wiki.parent, dry_run=dry_run)

    if not dry_run and plan.actions:
        for action in plan.actions:
            _move(action)
        await run_work_regen_index(workspace_path=workspace_path)

    return WorkArchiveResult(
        dry_run=dry_run, moved=moved, skipped=plan.skipped, repointed=repoint.rewrote
    )
```

- [ ] **Step 6: Render `repointed` in the CLI** — `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py`, after the `skipped` loop (line 131)

```python
        for skipped in result.skipped:
            typer.echo(f"  skipped: {skipped['slug']} — {skipped['reason']}")
        for repointed in result.repointed:
            typer.echo(f"  repointed: {repointed}")
```

- [ ] **Step 7: Run the new tests + the full work-command suite**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_work.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/work.py packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py packages/graph-wiki-core/tests/unit/test_commands_work.py
git commit -m "feat(graph-wiki-core): gw work archive repoints stale doc pointers as backstop"
```

---

### Task 4: Delete the standalone sweep script and clean up references

**Goal:** Remove the retired band-aid script and its test; update the one doc that references it. No code references the script anymore.

**Files:**
- Delete: `scripts/fix_stale_spec_doc_pointers.py`
- Delete: `scripts/test_fix_stale_spec_doc_pointers.py`
- Modify: `docs/superpowers/plans/2026-06-14-fix-archive-support-stale-artifact-pointers.md` (mark superseded)

**Acceptance Criteria:**
- [ ] Both script files are gone.
- [ ] `grep -rn "fix_stale_spec_doc_pointers" .` returns no hits outside the (now-updated) superseded plan and this plan's history.
- [ ] The superseded plan doc carries a "Superseded by" note pointing at the new spec.

**Verify:** `grep -rn "fix_stale_spec_doc_pointers" --include="*.py" .` → no output.

**Steps:**

- [ ] **Step 1: Confirm the only non-doc references are the deleted files**

Run: `grep -rn "fix_stale_spec_doc_pointers" . --include="*.py" --include="*.toml" --include="*.yaml" --include="*.yml"`
Expected: only the two `scripts/…` files themselves.

- [ ] **Step 2: Delete the script and its test**

```bash
git rm scripts/fix_stale_spec_doc_pointers.py scripts/test_fix_stale_spec_doc_pointers.py
```

- [ ] **Step 3: Mark the superseded plan** — prepend a note at the top of `docs/superpowers/plans/2026-06-14-fix-archive-support-stale-artifact-pointers.md`

```markdown
> **SUPERSEDED (2026-06-14)** by `docs/superpowers/specs/2026-06-14-fold-doc-pointer-repair-design.md`.
> The standalone `scripts/fix_stale_spec_doc_pointers.py` was deleted; the rewrite
> rule now lives in `work_io/doc_pointers.py` and runs automatically on ingest and
> as a `gw work archive` backstop.

```

- [ ] **Step 4: Verify no dangling references**

Run: `grep -rn "fix_stale_spec_doc_pointers" . --include="*.py"`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add -A scripts/ docs/superpowers/plans/2026-06-14-fix-archive-support-stale-artifact-pointers.md
git commit -m "chore: retire fix_stale_spec_doc_pointers script; logic lives in work-io"
```

---

## Final verification (after all tasks)

- [ ] `uv run --package work-io pytest -q` → PASS
- [ ] `uv run --package graph-wiki-core pytest -q` → PASS
- [ ] `uv run --package graph-wiki-cli pytest -m "not integration" -q` → PASS
- [ ] `uv run ruff check packages/work-io/src/work_io/doc_pointers.py packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/src/graph_wiki_core/commands/work.py` → clean
- [ ] `grep -rn "fix_stale_spec_doc_pointers" . --include="*.py"` → no output

Then hand off to `graph-wiki:finishing-a-development-branch`.

## Self-Review

- **Spec coverage:** Section 1 (module) → Task 1; Section 2 ingest hook → Task 2; Section 2 work-archive backstop + `repointed` + CLI → Task 3; Section 3 deletion/cleanup → Task 4; Section 4 testing → tests in Tasks 1-3 + Final verification. All covered.
- **Type consistency:** `sweep(ws_root, *, dry_run) -> SweepReport`; `SweepReport.rewrote/ok/unfixable`; `archived_counterpart(ws_root, pointer)`; `WorkArchiveResult.repointed` — names consistent across all tasks and tests.
- **No placeholders:** every code/test step shows complete content.
