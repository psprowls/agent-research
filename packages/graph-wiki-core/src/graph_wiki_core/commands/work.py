"""Work command — orchestration over the work-io lifecycle primitives.

Public API:
    WorkRegenResult / WorkLintResult / WorkStatusResult / WorkArchiveResult / WorkNextResult
        — typed result dataclasses for the read/maintenance commands.
    run_work_regen_index(workspace_path)  -> WorkRegenResult
    run_work_lint(workspace_path)         -> WorkLintResult
    run_work_status(workspace_path)       -> WorkStatusResult
    run_work_archive(workspace_path, ...) -> WorkArchiveResult
    run_work_file(workspace_path, ...)    -> IngestResult
    run_work_next(workspace_path, slug)   -> WorkNextResult
    run_work_advance(workspace_path, ...) -> WorkAdvanceResult

These are thin async orchestrators: they resolve the wiki/work directory from
the workspace, drive the pure work-io functions (frontmatter / plan_table /
sidecar / lifecycle_lint / archive), and shape the results for the CLI/MCP
surfaces. `run_work_file` writes the page via `work_io.filing.write_work_item`
and applies the shared sidecar/index/log side-effects via
`_apply_work_item_side_effects` (the same post-write path `run_ingest_work_item`
uses).
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.append_log import append_log
from wiki_io.update_index import update_index
from work_io import archive as _archive
from work_io import body as _body
from work_io import doc_pointers as _doc_pointers
from work_io import filing as _filing
from work_io import frontmatter as _frontmatter
from work_io import hierarchy as _hierarchy
from work_io import lifecycle_lint as _lint
from work_io import paths as _paths
from work_io import plan_table as _plan_table
from work_io import sidecar as _sidecar
from work_io import workflow as _workflow

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
    epics: list[dict] = field(default_factory=list)


@dataclass
class WorkArchiveResult:
    """Result of run_work_archive()."""

    dry_run: bool
    moved: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    repointed: list[str] = field(default_factory=list)


@dataclass
class WorkNextResult:
    """Result of run_work_next(). Field shapes match the `gw work next --json` contract."""

    slug: str
    status: str | None = None
    kind: str | None = None
    phase: str | None = None
    effort: str | None = None
    action: dict | None = None  # {"skill", "reason"}
    artifact: dict | None = None  # {"path": absolute path}
    on_dispatch: dict | None = None  # {"phase", "status", "requires"}
    on_complete: dict | None = None
    blockers: list[str] = field(default_factory=list)
    child_rollup: dict | None = None  # {"total", "terminal", "open_slugs"} for epics


@dataclass
class WorkAdvanceResult:
    """Result of run_work_advance()."""

    slug: str
    phase: str | None = None  # phase after the transition
    status: str | None = None  # status after the transition
    applied: dict = field(default_factory=dict)  # {"phase": [before, after], "status": [before, after]}
    stamped: dict = field(default_factory=dict)  # frontmatter keys written (effort/owner/resolved_in/spec_doc/plan_doc)
    findings: list[dict] = field(default_factory=list)  # lint findings for this slug after the write
    child_rollup: dict | None = None  # {"total", "terminal", "open_slugs"} for epics


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
    """Parse work items into lint-shaped item dicts: slug, fm, plan.

    The live `work/` dir is flat (`work/<slug>.md`); an `_archive` dir nests
    each item under its own subdirectory (`_archive/<slug>/00-open-work.md`,
    alongside the rest of its archived working dir) — slug then comes from the
    parent directory name, not the file stem. Unparseable pages are skipped.
    """
    items: list[dict] = []
    if not work_dir.exists():
        return items
    is_archive = work_dir.name == "_archive"
    pages = sorted(work_dir.glob("*/00-open-work.md")) if is_archive else sorted(work_dir.glob("*.md"))
    for md in pages:
        try:
            fm, body = _frontmatter.parse(md.read_text(encoding="utf-8"))
        except Exception:
            continue
        plan = _plan_table.parse_plan(body)
        slug = md.parent.name if is_archive else md.stem
        items.append({"slug": slug, "fm": fm, "plan": plan})
    return items


def _load_items_for_deps(work_dir: Path) -> list[dict]:
    """Active items plus archived ones, for depends_on / child_rollup resolution.

    A `depends_on` or `parent` reference to an item can outlive that item's
    presence in work/ — archiving moves terminal items to work/_archive/, but
    the reference itself is untouched. Dependency and rollup lookups must see
    both sets or a resolved-and-archived dependency reads back as unmet.
    """
    return _load_items(work_dir) + _load_items(work_dir / "_archive")


def _hierarchy_view(items: list[dict]) -> list[dict]:
    """Project loaded items ({slug, fm, plan}) to the {slug, status, parent} shape
    the work_io.hierarchy helpers consume."""
    return [
        {"slug": it["slug"], "status": str(it["fm"].get("status", "")), "parent": it["fm"].get("parent")}
        for it in items
    ]


def _load_item(wiki: Path, slug: str) -> tuple[Path, dict, str]:
    """Load wiki/work/<slug>.md; returns (path, frontmatter, body)."""
    path = wiki / "work" / f"{slug}.md"
    if not path.exists():
        raise FileNotFoundError(f"unknown slug {slug!r}: {path} not found")
    fm, body = _frontmatter.parse(path.read_text(encoding="utf-8"))
    return path, fm, body


def _state_from_fm(
    fm: dict,
    effort_override: str | None = None,
    *,
    items: list[dict] | None = None,
    slug: str | None = None,
) -> _workflow.WorkItemState:
    effort = effort_override or (str(fm["effort"]) if fm.get("effort") else None)
    depends_on = tuple(str(d) for d in (fm.get("depends_on") or []))
    unmet_deps: tuple[str, ...] = ()
    rollup = None
    if items is not None:
        view = _hierarchy_view(items)
        if depends_on:
            unmet_deps = _hierarchy.dep_states(view, depends_on)
        if str(fm.get("kind", "")) == "epic" and slug:
            rollup = _hierarchy.child_rollup(view, slug)
    return _workflow.WorkItemState(
        kind=str(fm.get("kind", "")),
        status=str(fm.get("status", "")),
        phase=str(fm["phase"]) if fm.get("phase") else None,
        effort=effort,
        has_plan_doc=bool(fm.get("plan_doc")),
        depends_on=depends_on,
        unmet_deps=unmet_deps,
        child_rollup=rollup,
    )


def _transition_dict(t: _workflow.Transition | None, current_status: str) -> dict | None:
    """Render a Transition for the JSON contract: status shows the post-transition value."""
    if t is None:
        return None
    return {"phase": t.phase, "status": t.status or current_status, "requires": list(t.requires)}


def _rollup_dict(rollup: _hierarchy.ChildRollup | None) -> dict | None:
    if rollup is None:
        return None
    return {"total": rollup.total, "terminal": rollup.terminal, "open_slugs": list(rollup.open_slugs)}


async def _apply_work_item_side_effects(
    wiki: Path,
    result: dict,
    *,
    workspace_path: Path | None,
) -> None:
    """Post-write effects shared by both filing paths: sidecar + index + log.

    Lives in core (not work-io) because update_index/append_log are wiki-io
    functions and work-io must stay free of a wiki-io dependency. index.md /
    log.md updates are best-effort — skipped when the file is absent — so filing
    succeeds against an un-bootstrapped wiki (work items predate bootstrap). The
    sidecar regen always runs (gw work status/next read it).
    """
    _paths.work_item_dir(wiki.parent, result["slug"]).mkdir(parents=True, exist_ok=True)
    await run_work_regen_index(workspace_path=workspace_path)
    if (wiki / "index.md").exists():
        update_index(wiki)
    if (wiki / "log.md").exists():
        append_log(
            wiki,
            "create",
            result["title"],
            detail=f"work/{Path(result['page_path']).name}",
            silent=True,
            raise_exception=True,
        )


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

    findings = _lint.run_lint(
        items, repo, sidecar, workspace_root=wiki.parent, archived_items=_load_items(work_dir / "_archive")
    )
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

    epics = [
        {
            "slug": i["slug"],
            "total": i["children"]["total"],
            "terminal": i["children"]["terminal"],
            "blocking": i["children"]["blocking"],
        }
        for i in items
        if i.get("kind") == "epic" and i.get("children")
    ]

    return WorkStatusResult(
        sidecar_missing=False,
        counts=sidecar.get("counts", {}),
        in_flight=in_flight,
        stuck=stuck,
        epics=epics,
    )


# ---------------------------------------------------------------------------
# run_work_archive
# ---------------------------------------------------------------------------


def _git_mv_or_rename(src: Path, dst: Path) -> None:
    """Move a path, preferring `git mv`, falling back to `os.rename`."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "mv", str(src), str(dst)],
        cwd=src.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        os.rename(src, dst)


def _move(action: _archive.ArchiveAction) -> None:
    """Move a work item's working dir (if present) then its page into _archive/<slug>/."""
    if action.working_dir_src is not None:
        assert action.working_dir_dst is not None
        _git_mv_or_rename(action.working_dir_src, action.working_dir_dst)
    _git_mv_or_rename(action.src, action.dst)


async def run_work_archive(
    workspace_path: Path | None = None,
    slugs: list[str] | None = None,
    dry_run: bool = False,
) -> WorkArchiveResult:
    """Archive terminal work items into work/_archive/.

    Sweep mode (slugs=None): all terminal items.
    Targeted mode (slugs given): named items, non-terminal skipped.
    Executes the moves unless dry_run; regenerates the sidecar after real moves.
    """
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    work_dir = wiki / "work"

    plan = _archive.plan_archive(work_dir, slugs=slugs)
    moved = [{"slug": a.slug, "src": str(a.src), "dst": str(a.dst)} for a in plan.actions]

    # Backstop: repoint any stale spec_doc/plan_doc whose source was archived.
    # Runs before the work-item moves (independent of where the .md itself lands).
    repoint = _doc_pointers.sweep(wiki.parent, dry_run=dry_run)

    if not dry_run and plan.actions:
        for action in plan.actions:
            _move(action)
        await run_work_regen_index(workspace_path=workspace_path)

    return WorkArchiveResult(dry_run=dry_run, moved=moved, skipped=plan.skipped, repointed=repoint.rewrote)


# ---------------------------------------------------------------------------
# run_work_next
# ---------------------------------------------------------------------------


_ARTIFACT_KIND = {"specs": "spec", "plans": "plan"}


async def run_work_next(workspace_path: Path | None = None, *, slug: str) -> WorkNextResult:
    """Compute the workflow routing decision for one work item. Read-only."""
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent

    try:
        _path, fm, _body = _load_item(wiki, slug)
    except (FileNotFoundError, ValueError) as e:
        return WorkNextResult(slug=slug, blockers=[str(e)])

    state = _state_from_fm(fm, items=_load_items_for_deps(wiki / "work"), slug=slug)
    r = _workflow.route(state)
    phase = state.phase or (r.on_dispatch.phase if r.on_dispatch else None)
    artifact = None
    if r.artifact_slot:
        assert phase is not None, "artifact_slot implies a known phase (see work_io.workflow.route)"
        kind = _ARTIFACT_KIND[r.artifact_slot]
        artifact = {"path": str(_paths.artifact_path(workspace, slug, phase, kind, ext="md"))}

    return WorkNextResult(
        slug=slug,
        status=state.status,
        kind=state.kind,
        phase=phase,
        effort=state.effort,
        action={"skill": r.skill, "reason": r.reason} if r.skill else None,
        artifact=artifact,
        on_dispatch=_transition_dict(r.on_dispatch, state.status),
        on_complete=_transition_dict(r.on_complete, state.status),
        blockers=list(r.blockers),
        child_rollup=_rollup_dict(state.child_rollup),
    )


# ---------------------------------------------------------------------------
# run_work_advance
# ---------------------------------------------------------------------------


async def run_work_advance(
    workspace_path: Path | None = None,
    *,
    slug: str,
    effort: str | None = None,
    owner: str | None = None,
    resolved_in: str | None = None,
) -> WorkAdvanceResult:
    """Apply the routing table's next transition for one work item.

    The single mutation point of the workflow: applies on_dispatch when the
    current state has an unmet dispatch precondition, otherwise on_complete.
    Stamps `updated`, writes passed field flags, stamps spec_doc/plan_doc as
    artifacts land, syncs the ## Plan table on acceptance, regenerates the
    sidecar, and re-lints the item. Raises ValueError on blockers or missing
    required flags.
    """
    wiki, repo = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent
    path, fm, body = _load_item(wiki, slug)

    items_before = _load_items_for_deps(wiki / "work")
    state = _state_from_fm(fm, effort_override=effort, items=items_before, slug=slug)
    r = _workflow.route(state)
    if r.blockers:
        raise ValueError("; ".join(r.blockers))
    t = r.on_dispatch or r.on_complete
    if t is None:
        raise ValueError(f"nothing to advance: {r.reason}")
    if "effort" in t.requires:
        raise ValueError("effort required to advance: pass --effort xtra-small|small|medium|large|xtra-large")
    if "owner" in t.requires and not (owner or fm.get("owner")):
        raise ValueError("owner required to advance: pass --owner <handle>")
    if "resolved_in" in t.requires and not (resolved_in or fm.get("resolved_in")):
        raise ValueError("resolved-in required to advance: pass --resolved-in <pr/commit>")

    _paths.work_item_dir(workspace, slug).mkdir(parents=True, exist_ok=True)

    applied: dict = {}
    if t.phase:
        applied["phase"] = [fm.get("phase"), t.phase]
        fm["phase"] = t.phase
    if t.status:
        applied["status"] = [fm.get("status"), t.status]
        fm["status"] = t.status

    stamped: dict = {}
    for key, value in (("effort", effort), ("owner", owner), ("resolved_in", resolved_in)):
        if value:
            fm[key] = value
            stamped[key] = value
    if t.stamp_doc:
        phase = "design" if t.stamp_doc == "spec_doc" else "plan"
        kind = "spec" if t.stamp_doc == "spec_doc" else "plan"
        rel = _paths.artifact_path(workspace, slug, phase, kind, ext="md").relative_to(workspace).as_posix()
        fm[t.stamp_doc] = rel
        stamped[t.stamp_doc] = rel
    fm["updated"] = date.today().isoformat()

    if t.sync_plan_table:
        body = _plan_table.ensure_plan_row(
            body,
            action=f"Execute implementation plan: raw/plans/{slug}.md",
            done_when="Implementation lands and the item is resolved",
            rationale="Workflow plan stage complete",
        )

    # parse() consumed the closing fence plus one newline; emit() + "\n" + body round-trips.
    path.write_text(_frontmatter.emit(fm) + "\n" + body, encoding="utf-8")
    await run_work_regen_index(workspace_path=workspace_path)

    items = _load_items(wiki / "work")
    sidecar = _sidecar.load_sidecar(wiki)
    findings = _lint.run_lint(
        items, repo, sidecar, workspace_root=workspace, archived_items=_load_items(wiki / "work" / "_archive")
    )
    return WorkAdvanceResult(
        slug=slug,
        phase=str(fm["phase"]) if fm.get("phase") else None,
        status=str(fm.get("status")) if fm.get("status") else None,
        applied=applied,
        stamped=stamped,
        findings=[
            {"rule_id": f.rule_id, "severity": f.severity, "slug": f.slug, "message": f.message}
            for f in findings
            if f.slug == slug
        ],
        child_rollup=_rollup_dict(state.child_rollup),
    )


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
    severity: str | None = None,
    effort: str | None = None,
    blast_radius: str | None = None,
    target: str | None = None,
    owner: str | None = None,
    tags: list[str] | None = None,
    parent: str | None = None,
    depends_on: list[str] | None = None,
    body: str = "",
    force: bool = False,
) -> IngestResult:
    """File a new work item into wiki/work/.

    Builds the work-item frontmatter (category=work) and writes the page to
    wiki/work/<opened>-<slug>.md, regenerating the sidecar afterward. index.md /
    log.md are updated best-effort — only when present — so filing still succeeds
    against an un-bootstrapped wiki (which work items predate). Returns an
    IngestResult shaped like the ingest work-item path.
    """
    affects = affects or []
    today = date.today().isoformat()

    wiki, _repo = resolve_wiki_and_repo(workspace_path)

    # Validate the parent epic before writing anything: --parent must point at an
    # existing work item whose kind is "epic" (the integrity guard the lint rules
    # also enforce). `parent` is the epic's full file stem by construction.
    if parent:
        parent_path = wiki / "work" / f"{parent}.md"
        if not parent_path.exists():
            raise ValueError(f"--parent {parent!r}: no work item at {parent_path}")
        parent_fm, _parent_body = _frontmatter.parse(parent_path.read_text(encoding="utf-8"))
        if str(parent_fm.get("kind", "")) != "epic":
            raise ValueError(
                f"--parent {parent!r}: kind is {parent_fm.get('kind')!r}, "
                "not 'epic'; children may only attach to an epic"
            )

    # Build frontmatter in wiki-schema.md ("Work pages") key order. Optional
    # scalars are omitted when unset rather than emitted as null placeholders;
    # list keys (affects, tags) are always present. Lifecycle-transition keys
    # (resolved_in, mitigation, …) are added on status change, not at filing.
    fm: dict = {
        "title": title,
        "category": "work",
        "kind": kind,
        "summary": summary,
        "status": status,
    }
    if severity:
        fm["severity"] = severity
    if effort:
        fm["effort"] = effort
    if blast_radius:
        fm["blast_radius"] = blast_radius
    fm["affects"] = affects
    if parent:
        fm["parent"] = parent
    if depends_on:
        fm["depends_on"] = depends_on
    if target:
        fm["target"] = target
    if owner:
        fm["owner"] = owner
    fm["opened"] = today
    fm["updated"] = today
    fm["tags"] = tags or []

    item_body = body or _body.render_default_work_body(summary, kind)
    if parent:
        pointer = f"Designed as part of epic `{parent}` — see its spec for the seed design."
        item_body = item_body.rstrip("\n") + "\n\n" + pointer + "\n"

    result = _filing.write_work_item(wiki, fm, item_body, force=force)
    await _apply_work_item_side_effects(wiki, result, workspace_path=workspace_path)

    return IngestResult(
        status="ok",
        page_path=str(Path(result["page_path"]).relative_to(wiki)),
        slug=result["slug"],
        title=title,
        page_type="work",
        source_path="",
        cross_refs_updated=0,
    )
