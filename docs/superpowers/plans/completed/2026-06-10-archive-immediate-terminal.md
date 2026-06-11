# Archive Immediate Terminal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use graph-wiki:subagent-driven-development (recommended) or graph-wiki:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the 7-day age gate from `gw work archive` sweep mode and rename the destination directory from `work/archived/` to `work/_archived/` across all layers.

**Architecture:** Two independent changes (age gate removal + directory rename) propagate from the `work-io` library layer up through `graph-wiki-core` orchestration, the `graph-wiki-cli` Typer CLI, and plugin skill docs. Task 1 owns `work-io` exclusively; Task 2 owns every layer above it.

**Tech Stack:** Python 3.11, `uv` workspace monorepo, pytest, Typer CLI, YAML frontmatter markdown.

---

### Task 1: work-io library — remove age gate, rename archive dir, fix tests

**Goal:** Update `archive.py` (drop `min_age_days`, rename dir), `lifecycle_lint.py` (Rule 14 fires immediately), `sidecar.py` (docstring), and all three affected test files so the `work-io` suite passes green.

**Files:**
- Modify: `packages/work-io/src/work_io/archive.py`
- Modify: `packages/work-io/src/work_io/lifecycle_lint.py`
- Modify: `packages/work-io/src/work_io/sidecar.py`
- Modify: `packages/work-io/tests/unit/test_archive.py`
- Modify: `packages/work-io/tests/unit/test_lifecycle_lint.py`
- Modify: `packages/work-io/tests/unit/test_sidecar.py`

**Acceptance Criteria:**
- [ ] `plan_archive()` has no `min_age_days` parameter
- [ ] Sweep mode archives any terminal item regardless of age (updated today → still archived)
- [ ] `plan_archive` uses `_archived/` as destination, not `archived/`
- [ ] Lifecycle Rule 14 fires immediately when status is terminal (0 days old)
- [ ] `test_sweep_mode_skips_terminal_under_min_age` is deleted
- [ ] `test_archive_eligible_under_7d_not_flagged` is deleted
- [ ] All `work-io` tests pass

**Verify:** `uv run --package work-io pytest tests/unit/test_archive.py tests/unit/test_lifecycle_lint.py tests/unit/test_sidecar.py -v` → all PASSED, no FAILED

**Steps:**

- [ ] **Step 1: Write the failing test for immediate sweep archiving**

In `packages/work-io/tests/unit/test_archive.py`, replace `test_sweep_mode_archives_terminal_aged_items` with a version that uses `updated_days_ago=0` to prove there's no age gate:

```python
def test_sweep_mode_archives_terminal_items_immediately(tmp_path: Path) -> None:
    work_dir = tmp_path
    _make_item(work_dir, "resolved-now", status="resolved", updated_days_ago=0)
    _make_item(work_dir, "open-item", status="open", updated_days_ago=0)

    plan = plan_archive(work_dir)

    assert len(plan.actions) == 1
    assert plan.actions[0].slug.endswith("resolved-now")
    assert len(plan.skipped) == 1
    assert plan.skipped[0]["slug"].endswith("open-item")
```

Delete `test_sweep_mode_skips_terminal_under_min_age` entirely.

Update `test_archive_dst_is_archive_subdir` to assert `_archived`:

```python
def test_archive_dst_is_archive_subdir(tmp_path: Path) -> None:
    work_dir = tmp_path
    _make_item(work_dir, "wontfix-item", status="wontfix", updated_days_ago=0)

    plan = plan_archive(work_dir)

    assert len(plan.actions) == 1
    assert plan.actions[0].dst.parent.name == "_archived"
    assert plan.actions[0].dst.name == plan.actions[0].src.name
```

Update `test_all_terminal_statuses_eligible` — drop `updated_days_ago=10` to prove age doesn't matter:

```python
def test_all_terminal_statuses_eligible(tmp_path: Path) -> None:
    work_dir = tmp_path
    for status in TERMINAL_STATUSES:
        _make_item(work_dir, f"item-{status}", status=status, updated_days_ago=0)

    plan = plan_archive(work_dir)
    assert len(plan.actions) == len(TERMINAL_STATUSES)
```

- [ ] **Step 2: Run archive tests to confirm they fail**

```bash
uv run --package work-io pytest tests/unit/test_archive.py -v
```

Expected: Several FAILED (the new test + the `_archived` assertion + all-statuses test).

- [ ] **Step 3: Update `packages/work-io/src/work_io/archive.py`**

Replace the entire file content:

```python
"""Plan archiving of terminal work items."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

TERMINAL_STATUSES = frozenset({"resolved", "wontfix", "superseded"})


@dataclass
class ArchiveAction:
    slug: str
    src: Path
    dst: Path


@dataclass
class ArchivePlan:
    actions: list[ArchiveAction] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


def plan_archive(
    work_dir: Path,
    slugs: list[str] | None = None,
) -> ArchivePlan:
    """Plan archiving of terminal work items.

    Sweep mode (slugs=None): all terminal items.
    Targeted mode (slugs provided): named items; non-terminal skipped.
    """
    from work_io.frontmatter import parse as fm_parse

    archived_dir = work_dir / "_archived"
    actions: list[ArchiveAction] = []
    skipped: list[dict] = []

    candidates = list(work_dir.glob("*.md"))

    if slugs is not None:
        slug_set = set(slugs)
        found_stems = {f.stem: f for f in candidates}
        candidates = [found_stems[s] for s in slug_set if s in found_stems]
        for s in slug_set:
            if s not in found_stems:
                skipped.append({"slug": s, "reason": "not found in work/"})

    for md in candidates:
        slug = md.stem
        try:
            fm, _ = fm_parse(md.read_text(encoding="utf-8"))
        except Exception as e:
            skipped.append({"slug": slug, "reason": f"parse error: {e}"})
            continue

        status = str(fm.get("status", ""))
        if status not in TERMINAL_STATUSES:
            skipped.append({"slug": slug, "reason": f"status={status!r} is not terminal"})
            continue

        actions.append(ArchiveAction(slug=slug, src=md, dst=archived_dir / md.name))

    return ArchivePlan(actions=actions, skipped=skipped)
```

- [ ] **Step 4: Run archive tests to confirm they pass**

```bash
uv run --package work-io pytest tests/unit/test_archive.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Update lifecycle lint Rule 14**

In `packages/work-io/src/work_io/lifecycle_lint.py`, find the `# 14. archive-eligible` block and replace:

```python
        # 14. archive-eligible
        if status in TERMINAL_STATUSES and _days_since(str(fm.get("updated", ""))) >= 7:
            findings.append(
                LintFinding(
                    "archive-eligible",
                    "info",
                    slug,
                    f"status={status!r} (terminal) and updated >=7 days ago; consider archiving",
                )
            )
```

with:

```python
        # 14. archive-eligible
        if status in TERMINAL_STATUSES:
            findings.append(
                LintFinding(
                    "archive-eligible",
                    "info",
                    slug,
                    f"status={status!r} (terminal); consider archiving",
                )
            )
```

- [ ] **Step 6: Update lifecycle lint tests**

In `packages/work-io/tests/unit/test_lifecycle_lint.py`:

Delete `test_archive_eligible_under_7d_not_flagged` entirely.

Update `test_archive_eligible` to fire immediately (0 days old):

```python
def test_archive_eligible() -> None:
    findings = run_lint([_item(status="resolved", updated_days_ago=0, resolved_in="pr#1")], None, None)
    assert "archive-eligible" in _rule_ids(findings)
```

- [ ] **Step 7: Update sidecar.py docstring**

In `packages/work-io/src/work_io/sidecar.py`, update the `build_sidecar` docstring line 15:

```python
def build_sidecar(work_dir: Path, vault_commit: str | None) -> dict:
    """Walk work_dir/*.md (excluding _archived/), parse each item, return sidecar dict."""
```

- [ ] **Step 8: Update test_sidecar.py**

In `packages/work-io/tests/unit/test_sidecar.py`, update `test_build_sidecar_excludes_archive`:

```python
def test_build_sidecar_excludes_archive(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    archived = work_dir / "_archived"
    archived.mkdir()
    _make_work_item(work_dir, "active", opened="2026-06-01", updated="2026-06-01")
    _make_work_item(archived, "old", opened="2026-01-01", updated="2026-01-01")

    sidecar = build_sidecar(work_dir, vault_commit=None)
    assert len(sidecar["items"]) == 1
    assert sidecar["items"][0]["slug"] == "2026-06-01-active"
```

- [ ] **Step 9: Run all work-io tests to confirm green**

```bash
uv run --package work-io pytest tests/unit/test_archive.py tests/unit/test_lifecycle_lint.py tests/unit/test_sidecar.py -v
```

Expected: all PASSED.

- [ ] **Step 10: Commit**

```bash
git add packages/work-io/src/work_io/archive.py \
        packages/work-io/src/work_io/lifecycle_lint.py \
        packages/work-io/src/work_io/sidecar.py \
        packages/work-io/tests/unit/test_archive.py \
        packages/work-io/tests/unit/test_lifecycle_lint.py \
        packages/work-io/tests/unit/test_sidecar.py
git commit -m "feat(work-io): archive terminal items immediately, rename dir to _archived"
```

---

### Task 2: Orchestration, CLI, and plugin docs — propagate directory rename and remove min_age_days

**Goal:** Remove `min_age_days` from `run_work_archive` and the CLI, update the `_archived` path filter in `graph-wiki-core/lint.py`, update the graph-wiki-core integration tests, and remove age-gate documentation from all plugin skill files.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py`
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_commands_work.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py`
- Modify: `plugins/graph-wiki/commands/archive.md`
- Modify: `plugins/graph-wiki/skills/graph-wiki/references/lifecycle-rules.md`
- Modify: `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md`

**Acceptance Criteria:**
- [ ] `run_work_archive` has no `min_age_days` parameter
- [ ] `gw work archive --help` shows no `--min-age-days` option
- [ ] `graph-wiki-core/lint.py` filters `_archived/` (not `archived/`)
- [ ] Integration tests for archive assert `_archived/` exists after a move
- [ ] `plugins/graph-wiki/commands/archive.md` describes no age gate
- [ ] `lifecycle-rules.md` and `wiki-schema.md` describe `_archived/`
- [ ] All graph-wiki-cli non-integration tests pass

**Verify:** `uv run --package graph-wiki-cli pytest -m "not integration" -v` → all PASSED

**Steps:**

- [ ] **Step 1: Write the failing integration tests**

In `packages/graph-wiki-core/tests/unit/test_commands_work.py`, find the two archive tests and update them to assert `_archived` (they currently assert `archived`):

```python
def test_run_work_archive_dry_run(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_archive

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "resolved-item", status="resolved", updated_days_ago=0, resolved_in="pr#1")

    result = asyncio.run(run_work_archive(workspace_path=workspace, dry_run=True))

    assert result.dry_run is True
    assert len(result.moved) == 1
    assert not (work_dir / "_archived").exists()


def test_run_work_archive_executes_move(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_archive

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "resolved-item", status="resolved", updated_days_ago=0, resolved_in="pr#1")

    result = asyncio.run(run_work_archive(workspace_path=workspace, dry_run=False))

    assert len(result.moved) == 1
    assert (work_dir / "_archived").exists()
```

- [ ] **Step 2: Run graph-wiki-core tests to confirm they fail**

```bash
uv run --package graph-wiki-core pytest tests/unit/test_commands_work.py -v -k "archive"
```

Expected: FAILED on the `_archived` assertions.

- [ ] **Step 3: Update `run_work_archive` in `commands/work.py`**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py`, replace the `run_work_archive` signature and body:

```python
async def run_work_archive(
    workspace_path: Path | None = None,
    slugs: list[str] | None = None,
    dry_run: bool = False,
) -> WorkArchiveResult:
    """Archive terminal work items into work/_archived/.

    Sweep mode (slugs=None): all terminal items.
    Targeted mode (slugs given): named items, non-terminal skipped.
    Executes the moves unless dry_run; regenerates the sidecar after real moves.
    """
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    work_dir = wiki / "work"

    plan = _archive.plan_archive(work_dir, slugs=slugs)
    moved = [{"slug": a.slug, "src": str(a.src), "dst": str(a.dst)} for a in plan.actions]

    if not dry_run and plan.actions:
        for action in plan.actions:
            _move(action)
        await run_work_regen_index(workspace_path=workspace_path)

    return WorkArchiveResult(dry_run=dry_run, moved=moved, skipped=plan.skipped)
```

Also update the `_load_items` docstring (line ~139):

```python
def _load_items(work_dir: Path) -> list[dict]:
    """Parse every work/*.md (excluding _archived/) into lint-shaped item dicts.
```

- [ ] **Step 4: Update `_archived` path filter in `commands/lint.py`**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py`, update both occurrences of `"archived"` in the path filter check:

Line ~143:
```python
        # Skip work/_archived/ — lifecycle is owned by graph-wiki work
        if top == "work" and len(rel.parts) >= 2 and rel.parts[1] == "_archived":
            continue
```

Line ~201:
```python
        if top == "work" and len(rel.parts) >= 2 and rel.parts[1] == "_archived":
            continue
```

- [ ] **Step 5: Run graph-wiki-core tests to confirm archive tests pass**

```bash
uv run --package graph-wiki-core pytest tests/unit/test_commands_work.py -v -k "archive"
```

Expected: all PASSED.

- [ ] **Step 6: Remove `--min-age-days` from the CLI**

In `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py`, update the `archive` command — remove the `min_age_days` option and its kwarg:

```python
@work_app.command()
def archive(
    slugs: Optional[list[str]] = typer.Argument(None, help="Specific slugs to archive"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without moving files"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Archive terminal work items (sweep or targeted)."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(
            run_work_archive(
                workspace_path=workspace_path,
                slugs=slugs or None,
                dry_run=dry_run,
            )
        )
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        label = "[dry-run]" if dry_run else "[ok]"
        typer.echo(f"{label} Archived {len(result.moved)} item(s).")
        for item in result.moved:
            typer.echo(f"  moved: {item['src']} -> {item['dst']}")
        for skipped in result.skipped:
            typer.echo(f"  skipped: {skipped['slug']} — {skipped['reason']}")
```

- [ ] **Step 7: Verify CLI option removed**

```bash
uv run --package graph-wiki-cli gw work archive --help
```

Expected: output does NOT contain `--min-age-days`.

- [ ] **Step 8: Run all non-integration graph-wiki-cli tests**

```bash
uv run --package graph-wiki-cli pytest -m "not integration" -v
```

Expected: all PASSED.

- [ ] **Step 9: Update `plugins/graph-wiki/commands/archive.md`**

Replace the entire file content:

```markdown
---
name: archive
description: Archive terminal-status work items (resolved/wontfix/superseded) — sweep mode by default, or target specific slugs. Presents the plan and asks for confirmation before executing. Invokes `gw work archive`. Usage /graph-wiki:archive [slug...]
---

# /graph-wiki:archive

Move terminal work items from `wiki/work/` to `wiki/work/_archived/`.

## Usage

```
/graph-wiki:archive
/graph-wiki:archive 2026-01-15-fix-parser-bug 2026-02-03-drop-old-api
```

Without arguments: sweep mode — all terminal-status items.
With slug arguments: targeted mode — those items only.

## What happens

1. Run `gw work archive --dry-run [SLUGS...]` to build the plan.
2. Present the plan: items to move, items skipped (with reasons), any wikilink referrers that will become broken.
3. Ask for confirmation before executing.
4. On confirmation, run `gw work archive [SLUGS...]` (without `--dry-run`).
5. Report moved items and regenerated sidecar.

Terminal statuses: `resolved`, `wontfix`, `superseded`.

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/lifecycle-rules.md`
```

- [ ] **Step 10: Update `plugins/graph-wiki/skills/graph-wiki/references/lifecycle-rules.md`**

Find line 84 (the archive-eligible remedy text) and update it:

Old:
```
**Remedy:** run `/graph-wiki:archive` to move eligible items into `<vault>/work/archived/`. Pass `--dry-run` first to see what would move; pass a slug to override the age check for a specific item.
```

New:
```
**Remedy:** run `/graph-wiki:archive` to move eligible items into `<vault>/work/_archived/`. Pass `--dry-run` first to see what would move; pass slugs to target specific items.
```

- [ ] **Step 11: Update `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md`**

Find the `#### The work/archived/ sub-namespace` heading (around line 218) and update the section heading and any `work/archived/` references to `work/_archived/`:

Change heading:
```markdown
#### The `work/_archived/` sub-namespace
```

Change any body text referencing `work/archived/` to `work/_archived/`.

- [ ] **Step 12: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/work.py \
        packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py \
        packages/graph-wiki-core/tests/unit/test_commands_work.py \
        packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py \
        plugins/graph-wiki/commands/archive.md \
        plugins/graph-wiki/skills/graph-wiki/references/lifecycle-rules.md \
        plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md
git commit -m "feat(archive): remove --min-age-days, rename archived/ to _archived/ across upper layers"
```
