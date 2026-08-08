"""gw work orchestrate — IO shell around work_io.orchestrate.plan().

Resolves workspace/repo, loads items (active + archived), reads
workflow.auto_drive through the config layer, stats worktree paths, and calls
the pure planner. No dispatch-decision logic here — see work_io.orchestrate.
"""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from wiki_io._workspace import resolve_wiki_and_repo
from work_io import orchestrate as _orchestrate
from work_io.auto_drive import validate_auto_drive
from workspace_io import manifest, paths
from workspace_io.registry import resolve_key

from graph_wiki_core.commands.work import _hierarchy_view, _load_items_for_deps
from graph_wiki_core.config_catalog import CATALOG


@dataclass
class WorkOrchestrateResult:
    """Result of run_work_orchestrate(). Field shapes mirror work_io.orchestrate.OrchestratePlan."""

    slug: str
    terminal: bool = False
    max_parallel: int = 2
    permission_mode: str = "bypassPermissions"
    live: list[str] = field(default_factory=list)
    slots_free: int = 0
    dispatches: list[dict] = field(default_factory=list)
    advances: list[dict] = field(default_factory=list)
    blocked: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _default_base(repo: Path | None) -> str:
    """Best-effort repo default branch name; degrades to 'develop' on any git
    failure or missing repo — same best-effort contract as _worktree_state."""
    if repo is None:
        return "develop"
    try:
        out = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return "develop"
    if out.returncode != 0 or not out.stdout.strip():
        return "develop"
    return out.stdout.strip().rsplit("/", 1)[-1]


def _stat_worktrees(items: list[dict]) -> dict[str, bool | None]:
    result: dict[str, bool | None] = {}
    for it in items:
        wt = it.get("worktree")
        if not wt or str(wt) in result:
            continue
        try:
            result[str(wt)] = Path(str(wt)).is_dir()
        except OSError:
            result[str(wt)] = None
    return result


async def run_work_orchestrate(
    workspace_path: Path | None = None,
    *,
    slug: str,
    live: tuple[str, ...] = (),
) -> WorkOrchestrateResult:
    """Compute the auto-drive dispatch plan for slug's subtree. Read-only —
    never mutates any work item, worktree, or config."""
    wiki, repo = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent

    raw_auto_drive = manifest.read(paths.manifest_path(workspace)).get("workflow", {}).get("auto_drive", {})
    errors = validate_auto_drive(raw_auto_drive)
    if errors:
        raise RuntimeError("; ".join(f"workflow.auto_drive: {e}" for e in errors))

    max_parallel = resolve_key(CATALOG, "workflow.auto_drive.max_parallel", workspace=workspace).value
    permission_mode = resolve_key(CATALOG, "workflow.auto_drive.permission_mode", workspace=workspace).value
    auto_drive = {**raw_auto_drive, "max_parallel": max_parallel}

    items = _hierarchy_view(_load_items_for_deps(wiki / "work"))
    worktree_exists = _stat_worktrees(items)
    default_base = _default_base(repo)

    result = _orchestrate.plan(
        items,
        slug,
        auto_drive=auto_drive,
        permission_mode=str(permission_mode),
        live=tuple(live),
        worktree_exists=worktree_exists,
        workspace=str(workspace),
        default_base=default_base,
    )

    return WorkOrchestrateResult(
        slug=result.slug,
        terminal=result.terminal,
        max_parallel=result.max_parallel,
        permission_mode=result.permission_mode,
        live=list(result.live),
        slots_free=result.slots_free,
        dispatches=[asdict(d) for d in result.dispatches],
        advances=[asdict(a) for a in result.advances],
        blocked=[asdict(b) for b in result.blocked],
        warnings=list(result.warnings),
    )
