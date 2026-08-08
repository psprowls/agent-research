"""Work command — orchestration over the work-io lifecycle primitives.

Public API:
    WorkRegenResult / WorkLintResult / WorkStatusResult / WorkArchiveResult / WorkNextResult
        — typed result dataclasses for the read/maintenance commands.
    run_work_regen_index(workspace_path)  -> WorkRegenResult
    run_work_lint(workspace_path)         -> WorkLintResult
    run_work_status(workspace_path)       -> WorkStatusResult
    run_work_archive(workspace_path, ...) -> WorkArchiveResult
    run_work_file(workspace_path, ...)    -> IngestResult
    run_work_next(workspace_path, slug, descend=False) -> WorkNextResult
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

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.append_log import append_log
from wiki_io.update_index import update_index
from work_io import archive as _archive
from work_io import body as _body
from work_io import children as _children
from work_io import doc_pointers as _doc_pointers
from work_io import filing as _filing
from work_io import frontmatter as _frontmatter
from work_io import hierarchy as _hierarchy
from work_io import lifecycle_lint as _lint
from work_io import paths as _paths
from work_io import plan_table as _plan_table
from work_io import results as _results
from work_io import sidecar as _sidecar
from work_io import workflow as _workflow
from workspace_io.paths import graph_dir

from graph_wiki_core.commands._reindex import regen_indexes_and_backlinks
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
    child_rollup: dict | None = None  # {"total", "terminal", "open_slugs"} for epics and features-with-children
    descent: dict | None = None  # {"from": requested slug, "path": [...]} when --descend switched items


@dataclass
class WorkAdvanceResult:
    """Result of run_work_advance()."""

    slug: str
    phase: str | None = None  # phase after the transition
    status: str | None = None  # status after the transition
    applied: dict = field(default_factory=dict)  # {"phase": [before, after], "status": [before, after]}
    stamped: dict = field(default_factory=dict)  # frontmatter keys written (effort/owner/resolved_in/spec_doc/plan_doc)
    findings: list[dict] = field(default_factory=list)  # lint findings for this slug after the write
    child_rollup: dict | None = None  # {"total", "terminal", "open_slugs"} for epics and features-with-children


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_run(repo: Path, *args: str) -> str | None:
    """Best-effort `git <args>` in `repo`; returns stdout, or None on any failure."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _git_head(repo: Path) -> str | None:
    """Best-effort HEAD sha of the git repo at `repo`; None when not a repo or no commits."""
    out = _git_run(repo, "rev-parse", "HEAD")
    sha = out.strip() if out is not None else ""
    return sha or None


def _git_diff_files(repo: Path, start_sha: str, end_sha: str) -> list[str] | None:
    """Best-effort list of file paths changed in `start_sha..end_sha`; None on git failure."""
    out = _git_run(repo, "diff", "--name-status", f"{start_sha}..{end_sha}")
    if out is None:
        return None
    return [line.split("\t")[-1] for line in out.splitlines() if line.strip()]


def _git_log_commits(repo: Path, start_sha: str, end_sha: str) -> list[str] | None:
    """Best-effort `git log --oneline` lines for `start_sha..end_sha`; None on git failure."""
    out = _git_run(repo, "log", "--oneline", f"{start_sha}..{end_sha}")
    if out is None:
        return None
    return [line for line in out.splitlines() if line.strip()]


def _abs_git_path(raw: str, cwd: Path) -> Path | None:
    """Resolve a `git rev-parse --git-dir`-style answer, which may be relative to cwd."""
    p = Path(raw.strip())
    if not str(p):
        return None
    try:
        return (p if p.is_absolute() else cwd / p).resolve()
    except OSError:
        return None


def _worktree_state(cwd: Path, repo: Path) -> tuple[str, str] | None:
    """(worktree_toplevel, branch) when `cwd` is a linked worktree of `repo`, else None.

    Uses the same detection the using-git-worktrees skill's Step 0 Part 2 does:
    `--git-dir` differs from `--git-common-dir` in a linked worktree — but also
    inside a submodule, so `--show-superproject-working-tree` rules that out.
    The common dir's parent must be `repo` itself, otherwise this is a worktree
    of some unrelated checkout and stamping it would point the item at code the
    workspace does not describe. A detached HEAD returns None: there is no
    branch worth recording, and the finish stage creates one anyway.

    Best-effort throughout — every git failure degrades to None (same contract
    as _git_head), because `advance` must never fail on provenance capture.
    """
    git_dir_raw = _git_run(cwd, "rev-parse", "--git-dir")
    common_raw = _git_run(cwd, "rev-parse", "--git-common-dir")
    if git_dir_raw is None or common_raw is None:
        return None
    git_dir = _abs_git_path(git_dir_raw, cwd)
    common = _abs_git_path(common_raw, cwd)
    if git_dir is None or common is None or git_dir == common:
        return None  # main checkout (or unreadable)
    if (_git_run(cwd, "rev-parse", "--show-superproject-working-tree") or "").strip():
        return None  # submodule, not a worktree
    try:
        if common.parent != Path(repo).resolve():
            return None  # linked worktree of a different repo
    except OSError:
        return None
    top = _git_run(cwd, "rev-parse", "--show-toplevel")
    branch = _git_run(cwd, "branch", "--show-current")
    if top is None or branch is None or not branch.strip():
        return None  # detached HEAD — nothing useful to stamp
    return top.strip(), branch.strip()


def _write_results_stub(workspace: Path, repo: Path, slug: str, *, phase: str, start_sha: str) -> None:
    """Best-effort: write work/<slug>/NN-<phase>-results.md as a mechanical git-facts stub.

    Silent no-op on any git failure — a provenance nice-to-have, not something
    `advance` should ever fail on (matches the `_git_head` degrade contract).
    """
    end_sha = _git_head(repo)
    if end_sha is None:
        return
    files = _git_diff_files(repo, start_sha, end_sha)
    commits = _git_log_commits(repo, start_sha, end_sha)
    if files is None or commits is None:
        return
    body = _results.render(phase=phase, start_sha=start_sha, end_sha=end_sha, files=files, commits=commits)
    _paths.artifact_path(workspace, slug, phase, "results", ext="md").write_text(body, encoding="utf-8")


def _write_active_work_pointer(workspace: Path, slug: str, phase: str) -> None:
    """Best-effort: stamp `.graph-wiki/active-work.json` with the item now in flight.

    Read by the opt-in SessionEnd transcript-capture hook to attribute a
    session's transcript to this item/phase. The call site skips invoking
    this entirely when the resulting phase is the terminal `done` — `done`
    is not a `PHASE_ORDINALS` member and `artifact_path` raises on it, so a
    `phase: "done"` pointer would make the *next* SessionEnd hook crash.

    Silent no-op on any OSError (permissions, disk full, missing parent) — a
    provenance nice-to-have, not something `advance` should ever fail on
    (matches `_write_results_stub`'s degrade contract).
    """
    pointer = {"slug": slug, "phase": phase, "updated": datetime.now(timezone.utc).isoformat()}
    pointer_path = graph_dir(workspace) / "active-work.json"
    try:
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        pointer_path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return


def _clear_active_work_pointer_if_archived(workspace: Path, archived_slugs: set[str]) -> None:
    """Delete `.graph-wiki/active-work.json` if it points at a just-archived item.

    Otherwise a later SessionEnd hook would resurrect an orphaned
    wiki/work/<slug>/ directory for an item that no longer lives there
    (its real content has moved to wiki/work/_archive/<slug>/). Fail-open
    on any missing/unreadable/malformed pointer, matching
    `_write_active_work_pointer`'s degrade contract.
    """
    pointer_path = graph_dir(workspace) / "active-work.json"
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(pointer, dict):
        return
    if pointer.get("slug") in archived_slugs:
        try:
            pointer_path.unlink()
        except OSError:
            pass


# Shared work-item loader lives in work-io so both lint surfaces (gw lint and
# the plugin's lint_wiki.py scan()) load items identically; keep the private
# alias so internal callers (incl. _load_items_for_deps) are unchanged.
_load_items = _lint.load_items


def _load_items_for_deps(work_dir: Path) -> list[dict]:
    """Active items plus archived ones, for depends_on / child_rollup resolution.

    A `depends_on` or `parent` reference to an item can outlive that item's
    presence in work/ — archiving moves terminal items to work/_archive/, but
    the reference itself is untouched. Dependency and rollup lookups must see
    both sets or a resolved-and-archived dependency reads back as unmet.
    """
    return _load_items(work_dir) + _load_items(work_dir / "_archive")


def _hierarchy_view(items: list[dict]) -> list[dict]:
    """Project loaded items ({slug, fm, plan}) to the extended hierarchy view
    the work_io.hierarchy helpers consume (rollup/deps read a subset; descend
    and orchestrate read all of it)."""
    return [
        {
            "slug": it["slug"],
            "status": str(it["fm"].get("status", "")),
            "parent": it["fm"].get("parent"),
            "kind": str(it["fm"].get("kind", "")),
            "phase": str(it["fm"]["phase"]) if it["fm"].get("phase") else None,
            "depends_on": tuple(str(d) for d in (it["fm"].get("depends_on") or [])),
            "opened": str(it["fm"].get("opened", "")),
            "affects": list(it["fm"].get("affects") or []),
            "effort": str(it["fm"]["effort"]) if it["fm"].get("effort") else None,
            "worktree": it["fm"].get("worktree"),
            "branch": it["fm"].get("branch"),
            "has_plan_doc": bool(it["fm"].get("plan_doc")),
        }
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
        kind = str(fm.get("kind", ""))
        if kind in _lint.PARENT_KINDS and slug:
            rollup = _hierarchy.child_rollup(view, slug)
            if kind == "feature" and rollup.total == 0:
                # Childless features stay rollup-free: no gate, child_rollup
                # stays null in the JSON (epics keep the 0-children rollup —
                # their no-children blocker needs it).
                rollup = None
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
    """Rebuild wiki/work-index.json from the on-disk work items.

    Also refreshes parent pages' derived `children` frontmatter in place
    (work_io.children.refresh_children) before building the sidecar, so the
    list self-heals on every call — and this is the single choke point already
    invoked by file/advance/archive.
    """
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    work_dir = wiki / "work"

    _children.refresh_children(work_dir)

    sidecar = _sidecar.build_sidecar(work_dir, _git_head(wiki))
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


def _repoint_in_dir_doc(action: _archive.ArchiveAction, workspace: Path) -> list[str]:
    """Rewrite spec_doc/plan_doc on the just-moved page if they pointed into the
    item's own (now-moved) working dir. Returns human-readable repoint entries
    for every pointer that needed rewriting (may be more than one)."""
    fm, body = _frontmatter.parse(action.dst.read_text(encoding="utf-8"))
    prefix = f"wiki/work/{action.slug}/"
    entries: list[str] = []
    for key in ("spec_doc", "plan_doc"):
        pointer = fm.get(key)
        if pointer and str(pointer).startswith(prefix):
            new_pointer = f"wiki/work/_archive/{action.slug}/" + str(pointer)[len(prefix) :]
            fm[key] = new_pointer
            rel_dst = action.dst.relative_to(workspace).as_posix()
            entries.append(f"{rel_dst} ({key}) -> {new_pointer}")
    if entries:
        action.dst.write_text(_frontmatter.emit(fm) + "\n" + body, encoding="utf-8")
    return entries


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
            repoint.rewrote.extend(_repoint_in_dir_doc(action, wiki.parent))
        _clear_active_work_pointer_if_archived(wiki.parent, {a.slug for a in plan.actions})
        await run_work_regen_index(workspace_path=workspace_path)
        # Archive moves an existing linked file, so — unlike filing, which merely
        # lacks a graph-owned index.md entry until the next scan — the master
        # index and entity backlinks now dangle too. Run the full scan Step-12
        # bundle, not just update_index. Best-effort: each step logs and
        # continues on failure (see regen_indexes_and_backlinks).
        regen_indexes_and_backlinks(wiki)
        # Inbound wikilinks from other pages are intentionally left pointing at the
        # pre-archive path as a supersession-history breadcrumb; only pointers on
        # the archived item's own page (spec_doc/plan_doc) are repointed, above.
        if (wiki / "log.md").exists():
            for action in plan.actions:
                append_log(
                    wiki,
                    "update",
                    action.slug,
                    detail=f"work/_archive/{action.slug}",
                    silent=True,
                    raise_exception=True,
                )

    return WorkArchiveResult(dry_run=dry_run, moved=moved, skipped=plan.skipped, repointed=repoint.rewrote)


# ---------------------------------------------------------------------------
# run_work_next
# ---------------------------------------------------------------------------


_ARTIFACT_KIND = {"specs": "spec", "plans": "plan"}


def _next_for_slug(wiki: Path, workspace: Path, slug: str, items: list[dict]) -> WorkNextResult:
    """Compute the routing decision for one work item, given preloaded items
    (active + archived, for depends_on/child_rollup resolution)."""
    try:
        _path, fm, _body = _load_item(wiki, slug)
    except (FileNotFoundError, ValueError) as e:
        return WorkNextResult(slug=slug, blockers=[str(e)])

    state = _state_from_fm(fm, items=items, slug=slug)
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


def _child_gated_result(result: WorkNextResult) -> bool:
    """Whether --descend applies: the routed item is waiting on open children.

    Mirrors work_io.hierarchy.child_gated_node's gating rule exactly (epic at
    execute with open children, or feature at execute/finish with open
    children), but operates on the already-computed WorkNextResult (rollup
    already reduced to dict form) rather than re-deriving it from raw items.
    """
    rollup = result.child_rollup or {}
    if not rollup.get("open_slugs"):
        return False
    if result.kind == "epic":
        return result.phase == "execute"
    return result.kind == "feature" and result.phase in ("execute", "finish")


async def run_work_next(workspace_path: Path | None = None, *, slug: str, descend: bool = False) -> WorkNextResult:
    """Compute the workflow routing decision for one work item. Read-only.

    With descend=True, a child-gated item (epic waiting on children, or
    feature gated at execute/finish) resolves recursively to the next
    actionable leaf; the returned result is the leaf's, plus `descent`.
    """
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent

    items = _load_items_for_deps(wiki / "work")
    result = _next_for_slug(wiki, workspace, slug, items)
    if not descend or not _child_gated_result(result):
        return result

    d = _hierarchy.descend(_hierarchy_view(items), slug)
    if d.leaf is None or d.leaf == slug:
        result.blockers.append(f"--descend: blocked at {d.blocked_at}: {d.reason}")
        return result
    leaf_result = _next_for_slug(wiki, workspace, d.leaf, items)
    leaf_result.descent = {"from": slug, "path": list(d.path)}
    return leaf_result


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
    if "children-terminal" in t.requires:
        # state.child_rollup is always set here: the gate string is only ever emitted
        # by _feature_children_requires when rollup is non-None (see workflow.py) —
        # the `else ""` is defensive only, not a reachable branch.
        open_slugs = ", ".join(state.child_rollup.open_slugs) if state.child_rollup else ""
        raise ValueError(
            f"waiting on children: {open_slugs}; finish them (try --descend) or detach (delete the child's parent key)"
        )
    if "owner" in t.requires and not (owner or fm.get("owner")):
        raise ValueError("owner required to advance: pass --owner <handle>")
    if "resolved_in" in t.requires and not (resolved_in or fm.get("resolved_in")):
        raise ValueError("resolved-in required to advance: pass --resolved-in <pr/commit>")

    _paths.work_item_dir(workspace, slug).mkdir(parents=True, exist_ok=True)

    applied: dict = {}
    stamped: dict = {}

    old_phase = fm.get("phase")
    if repo is not None and state.kind != "epic" and t.phase and t.phase != old_phase:
        if old_phase in ("execute", "finish") and fm.get("phase_started_commit"):
            _write_results_stub(workspace, repo, slug, phase=str(old_phase), start_sha=str(fm["phase_started_commit"]))
        if t.phase in ("execute", "finish"):
            head = _git_head(repo)
            if head is not None:
                fm["phase_started_commit"] = head
                stamped["phase_started_commit"] = head

    # Worktree provenance: stamp only when the recorded path is unset or gone,
    # so running `advance` from an unrelated worktree cannot silently repoint a
    # live item. The execute stage's session is cd'd into its worktree when it
    # calls advance, so this populates itself with no skill change.
    if repo is not None:
        recorded = fm.get("worktree")
        if not recorded or not Path(str(recorded)).is_dir():
            detected = _worktree_state(Path.cwd(), repo)
            if detected is not None:
                fm["worktree"], fm["branch"] = detected
                stamped["worktree"], stamped["branch"] = detected

    if t.phase:
        applied["phase"] = [fm.get("phase"), t.phase]
        fm["phase"] = t.phase
    if t.status:
        applied["status"] = [fm.get("status"), t.status]
        fm["status"] = t.status

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

    resulting_phase = fm.get("phase")
    if resulting_phase and resulting_phase != "done":
        _write_active_work_pointer(workspace, slug, str(resulting_phase))

    if t.sync_plan_table:
        body = _plan_table.ensure_plan_row(
            body,
            action=f"Execute implementation plan: {fm['plan_doc']}",
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


def _resolve_parent_epic_child(wiki: Path, parent: str, *, label: str = "--parent") -> bool:
    """Validate that `parent` names an existing PARENT_KINDS work item; return whether it's an epic.

    Shared by run_work_file (the CLI/MCP structured-file surface) and
    run_ingest_work_item in commands/ingest.py (the raw-frontmatter ingest
    surface, which imports this locally to avoid a cycle — see that module's
    Step 4) so both surfaces enforce identical parent-kind gating: the parent
    page must exist at wiki/work/<parent>.md and its kind must be one of
    _lint.PARENT_KINDS (epic, feature). `label` customizes the error-message
    prefix — "--parent" for the CLI-flag context, "parent" for the
    frontmatter-field context.

    Raises:
        ValueError: parent page missing, or its kind is not in PARENT_KINDS.
    """
    parent_path = wiki / "work" / f"{parent}.md"
    if not parent_path.exists():
        raise ValueError(f"{label} {parent!r}: no work item at {parent_path}")
    parent_fm, _parent_body = _frontmatter.parse(parent_path.read_text(encoding="utf-8"))
    parent_kind = str(parent_fm.get("kind", ""))
    allowed = sorted(_lint.PARENT_KINDS)
    if parent_kind not in allowed:
        raise ValueError(
            f"{label} {parent!r}: kind is {parent_kind!r}, not one of "
            f"{allowed}; children attach to an {' or '.join(allowed)}"
        )
    return parent_kind == "epic"


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
    slug_words: str | None = None,
    body: str = "",
    force: bool = False,
) -> IngestResult:
    """File a new work item into wiki/work/.

    Builds the work-item frontmatter (category=work) and writes the page to
    wiki/work/<opened>-<slug>.md, regenerating the sidecar afterward. index.md /
    log.md are updated best-effort — only when present — so filing still succeeds
    against an un-bootstrapped wiki (which work items predate). Returns an
    IngestResult shaped like the ingest work-item path.

    When slug_words is set, the slug is composed explicitly via
    work_io.filing.compose_slug(kind, slug_words, epic_child=<parent kind == "epic">)
    and any word-count warnings land on the returned IngestResult.warnings. When
    omitted, write_work_item falls through to its own default-slug composition
    (kind prefix + first 4 words of the title).
    """
    affects = affects or []
    today = date.today().isoformat()

    wiki, _repo = resolve_wiki_and_repo(workspace_path)

    # Validate the parent before writing anything: --parent must point at an
    # existing work item whose kind allows children (PARENT_KINDS: epic or
    # feature). `parent` is the parent's full file stem by construction.
    parent_is_epic = False
    if parent:
        parent_is_epic = _resolve_parent_epic_child(wiki, parent)

    # Validate --depends-on before writing anything: every value must exact-match
    # a known slug (active or archived), same fail-safe exact-match convention as
    # work_io.hierarchy.dep_states. A bare title-slug missing its date prefix gets
    # a hint when exactly one known slug matches by title.
    if depends_on:
        unresolved = _hierarchy.unresolved_depends_on(_load_items_for_deps(wiki / "work"), depends_on)
        if unresolved:
            parts = [f"{v!r} (did you mean {h!r}?)" if h else repr(v) for v, h in unresolved.items()]
            raise ValueError(
                "--depends-on: no work item matches "
                + ", ".join(parts)
                + "; pass the full slug from `gw work file --json`'s `slug` field"
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
        if parent_is_epic:
            pointer = f"Designed as part of epic `{parent}` — see its spec for the seed design."
        else:
            pointer = f"Filed as a child of `{parent}` — see its spec for the seed design."
        item_body = item_body.rstrip("\n") + "\n\n" + pointer + "\n"

    warnings: list[str] = []
    slug: str | None = None
    if slug_words:
        slug, warnings = _filing.compose_slug(kind, slug_words, epic_child=parent_is_epic)

    result = _filing.write_work_item(wiki, fm, item_body, slug=slug, epic_child=parent_is_epic, force=force)
    await _apply_work_item_side_effects(wiki, result, workspace_path=workspace_path)

    return IngestResult(
        status="ok",
        page_path=str(Path(result["page_path"]).relative_to(wiki)),
        slug=result["slug"],
        title=title,
        page_type="work",
        source_path="",
        cross_refs_updated=0,
        warnings=warnings,
    )
