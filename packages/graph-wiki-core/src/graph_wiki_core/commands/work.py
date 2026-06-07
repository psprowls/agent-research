"""Work command — orchestration over the work-io lifecycle primitives.

Public API:
    WorkRegenResult / WorkLintResult / WorkStatusResult / WorkArchiveResult
        — typed result dataclasses for the four read/maintenance commands.
    run_work_regen_index(workspace_path)  -> WorkRegenResult
    run_work_lint(workspace_path)         -> WorkLintResult
    run_work_status(workspace_path)       -> WorkStatusResult
    run_work_archive(workspace_path, ...) -> WorkArchiveResult
    run_work_file(workspace_path, ...)    -> IngestResult

These are thin async orchestrators: they resolve the wiki/work directory from
the workspace, drive the pure work-io functions (frontmatter / plan_table /
sidecar / lifecycle_lint / archive), and shape the results for the CLI/MCP
surfaces. `run_work_file` delegates to the existing
`run_ingest_work_item` ingest path so work items are filed identically to the
`gw ingest --work-item` flow.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from wiki_io._workspace import resolve_wiki_and_repo
from work_io import archive as _archive
from work_io import frontmatter as _frontmatter
from work_io import lifecycle_lint as _lint
from work_io import plan_table as _plan_table
from work_io import sidecar as _sidecar

from graph_wiki_core.commands.ingest import IngestResult

# Stuck thresholds (mirror lifecycle_lint rules 12/13).
_STUCK_OPEN_DAYS = 30
_STUCK_ACCEPTED_DAYS = 60


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class WorkRegenResult:
    """Result of run_work_regen_index()."""

    item_count: int
    sidecar_path: str


@dataclass
class WorkLintResult:
    """Result of run_work_lint(). findings is a list of plain dicts so the
    result is JSON-serializable across the CLI/MCP boundary."""

    total_items: int
    findings: list[dict] = field(default_factory=list)


@dataclass
class WorkStatusResult:
    """Result of run_work_status()."""

    sidecar_missing: bool
    counts: dict = field(default_factory=dict)
    in_flight: list[dict] = field(default_factory=list)
    stuck: list[dict] = field(default_factory=list)


@dataclass
class WorkArchiveResult:
    """Result of run_work_archive()."""

    dry_run: bool
    moved: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vault_commit(wiki: Path) -> str | None:
    """Best-effort HEAD of the wiki's git repo; None when not a repo."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=wiki,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return None
    if out.returncode != 0:
        return None
    commit = out.stdout.strip()
    return commit or None


def _load_items(work_dir: Path) -> list[dict]:
    """Parse every work/*.md (excluding archived/) into lint-shaped item dicts.

    Each dict carries: slug, fm (frontmatter dict), plan (PlanResult).
    Unparseable pages are skipped.
    """
    items: list[dict] = []
    if not work_dir.exists():
        return items
    for md in sorted(work_dir.glob("*.md")):
        try:
            fm, body = _frontmatter.parse(md.read_text(encoding="utf-8"))
        except Exception:
            continue
        plan = _plan_table.parse_plan(body)
        items.append({"slug": md.stem, "fm": fm, "plan": plan})
    return items


# ---------------------------------------------------------------------------
# run_work_regen_index
# ---------------------------------------------------------------------------


async def run_work_regen_index(workspace_path: Path | None = None) -> WorkRegenResult:
    """Rebuild wiki/work-index.json from the on-disk work items."""
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    work_dir = wiki / "work"

    sidecar = _sidecar.build_sidecar(work_dir, _vault_commit(wiki))
    _sidecar.write_sidecar(wiki, sidecar)

    return WorkRegenResult(
        item_count=len(sidecar.get("items", [])),
        sidecar_path=str(wiki / "work-index.json"),
    )


# ---------------------------------------------------------------------------
# run_work_lint
# ---------------------------------------------------------------------------


async def run_work_lint(workspace_path: Path | None = None) -> WorkLintResult:
    """Run the lifecycle lint rules over every work item."""
    wiki, repo = resolve_wiki_and_repo(workspace_path)
    work_dir = wiki / "work"

    items = _load_items(work_dir)
    sidecar = _sidecar.load_sidecar(wiki)

    findings = _lint.run_lint(items, repo, sidecar)
    return WorkLintResult(
        total_items=len(items),
        findings=[
            {
                "rule_id": f.rule_id,
                "severity": f.severity,
                "slug": f.slug,
                "message": f.message,
            }
            for f in findings
        ],
    )


# ---------------------------------------------------------------------------
# run_work_status
# ---------------------------------------------------------------------------


def _days_since(date_str: str) -> int:
    try:
        dt = date.fromisoformat(str(date_str)[:10])
        return (date.today() - dt).days
    except (ValueError, TypeError):
        return 0


async def run_work_status(workspace_path: Path | None = None) -> WorkStatusResult:
    """Summarize work state from the sidecar: counts, in-flight, and stuck items."""
    wiki, _repo = resolve_wiki_and_repo(workspace_path)

    sidecar = _sidecar.load_sidecar(wiki)
    if sidecar is None:
        return WorkStatusResult(sidecar_missing=True)

    items = sidecar.get("items", [])
    in_flight = [i for i in items if i.get("status") == "in-progress"]
    stuck: list[dict] = []
    for i in items:
        status = i.get("status")
        age = _days_since(i.get("updated", ""))
        if status == "open" and age > _STUCK_OPEN_DAYS:
            stuck.append(i)
        elif status == "accepted" and age > _STUCK_ACCEPTED_DAYS:
            stuck.append(i)

    return WorkStatusResult(
        sidecar_missing=False,
        counts=sidecar.get("counts", {}),
        in_flight=in_flight,
        stuck=stuck,
    )


# ---------------------------------------------------------------------------
# run_work_archive
# ---------------------------------------------------------------------------


def _move(action: _archive.ArchiveAction) -> None:
    """Move a work item into archived/, preferring `git mv`, falling back to rename."""
    action.dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "mv", str(action.src), str(action.dst)],
        cwd=action.src.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        os.rename(action.src, action.dst)


async def run_work_archive(
    workspace_path: Path | None = None,
    slugs: list[str] | None = None,
    min_age_days: int = 7,
    dry_run: bool = False,
) -> WorkArchiveResult:
    """Archive terminal work items into work/archived/.

    Sweep mode (slugs=None): all terminal items aged >= min_age_days.
    Targeted mode (slugs given): named items, age check bypassed.
    Executes the moves unless dry_run; regenerates the sidecar after real moves.
    """
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    work_dir = wiki / "work"

    plan = _archive.plan_archive(work_dir, slugs=slugs, min_age_days=min_age_days)
    moved = [{"slug": a.slug, "src": str(a.src), "dst": str(a.dst)} for a in plan.actions]

    if not dry_run and plan.actions:
        for action in plan.actions:
            _move(action)
        await run_work_regen_index(workspace_path=workspace_path)

    return WorkArchiveResult(dry_run=dry_run, moved=moved, skipped=plan.skipped)


# ---------------------------------------------------------------------------
# run_work_file
# ---------------------------------------------------------------------------


async def run_work_file(
    workspace_path: Path | None = None,
    *,
    title: str,
    kind: str,
    summary: str,
    affects: list[str] | None = None,
    status: str = "open",
    body: str = "",
    force: bool = False,
) -> IngestResult:
    """File a new work item into wiki/work/.

    Builds the work-item frontmatter (category=work) and writes the page to
    wiki/work/<opened>-<slug>.md, regenerating the sidecar afterward. This is a
    direct write — it does not depend on a fully bootstrapped wiki (log.md /
    index.md), which work items predate, and returns an IngestResult shaped like
    the ingest work-item path.
    """
    affects = affects or []
    today = date.today().isoformat()
    slug = _slugify(title)

    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    work_dir = wiki / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    fm = {
        "title": title,
        "category": "work",
        "kind": kind,
        "status": status,
        "summary": summary,
        "opened": today,
        "updated": today,
        "affects": affects,
    }
    item_body = body or f"## Summary\n{summary}\n"
    if not item_body.endswith("\n"):
        item_body += "\n"
    content = _frontmatter.emit(fm) + "\n\n" + item_body

    page_path = work_dir / f"{today}-{slug}.md"
    if page_path.exists() and not force:
        raise FileExistsError(f"page already exists: {page_path}")
    page_path.write_text(content, encoding="utf-8")

    # Keep the sidecar in sync with the newly filed item.
    await run_work_regen_index(workspace_path=workspace_path)

    return IngestResult(
        status="ok",
        page_path=str(page_path.relative_to(wiki)),
        slug=slug,
        title=title,
        page_type="work",
        source_path="",
        cross_refs_updated=0,
    )


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(title: str) -> str:
    s = _SLUG_RE.sub("-", title.lower()).strip("-")
    return s or "untitled"
