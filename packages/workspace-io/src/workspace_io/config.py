"""Workspace resolution: cwd -> GraphWikiConfig.

Discovery walks up from cwd looking for `.git`. Once the repo root is
found, the workspace defaults to `<repo>/graph-wiki` — there is no
repo-side pointer file consulted anymore. `GRAPH_WIKI_WORKSPACE` is the
only external-workspace pointer: it is normally injected via the repo's
`.claude/settings.local.json` env block (written by `gw config`), and it
overrides discovery outright, pinning a workspace directory directly. In
a bare terminal (no settings.local.json in play — a raw shell, CI, etc.)
the equivalent options are passing `--workspace` explicitly, exporting
`GRAPH_WIKI_WORKSPACE` in the shell, or using direnv to set it per-directory.

A legacy repo-side `.graph-wiki.local.yaml` carrying a `workspace-directory:`
key is inert (ignored entirely) but `resolve()` emits a `UserWarning`
pointing at the fix when it finds one, so stale pointers don't fail silently.

The workspace manifest (`.graph-wiki.yaml`, layered with the workspace-side
`.graph-wiki.local.yaml` on top — a different file, living inside the
workspace, not the repo) may also declare a `repo-directory:` key to pin the
repo root explicitly — useful when the workspace itself lives in its own git
repo (e.g. a separate wiki repo describing a source repo elsewhere on disk),
where `.git`-discovery would otherwise bind to the wiki's own repo.
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from pathlib import Path

from workspace_io import _local_config

LOCAL_CONFIG_FILENAME = ".graph-wiki.local.yaml"
WORKSPACE_DIRECTORY_KEY = "workspace-directory"
REPO_DIRECTORY_KEY = "repo-directory"
DEFAULT_WORKSPACE_NAME = "graph-wiki"
MULTI_REPO_KEY = "multi-repo"
REPOS_ROOT_KEY = "repos-root"
REPOS_ALLOW_KEY = "repos"
REPOS_EXCLUDE_KEY = "exclude"
_TRUTHY = {"true", "1", "yes", "on"}
# Dirs that can never be member repos, regardless of a nested `.git`.
_MEMBER_SKIP_DIRS = frozenset({".git", "node_modules", ".venv", "__pycache__", ".graph-wiki"})


@dataclass(frozen=True)
class GraphWikiConfig:
    workspace: Path
    repo_root: Path
    members: tuple[Path, ...] = ()


def _find_repo_root(start: Path) -> Path | None:
    start = Path(start).resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _repo_directory_override(workspace: Path, repo_root_default: Path) -> Path:
    """Consult `<workspace>/.graph-wiki.yaml` + `.graph-wiki.local.yaml` for `repo-directory:`.

    Local overrides committed manifest (same precedence as `workspace-directory`).
    `~` is expanded; relative paths resolve against `workspace`. Returns
    `repo_root_default` unchanged when the key is absent or blank.
    """
    committed = _local_config.read(workspace / ".graph-wiki.yaml")
    local = _local_config.read(workspace / LOCAL_CONFIG_FILENAME)
    merged = {**committed, **local}
    raw = merged.get(REPO_DIRECTORY_KEY, "").strip()
    if not raw:
        return repo_root_default
    expanded = Path(raw).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (workspace / expanded).resolve()


def discover_members(
    repos_root: Path,
    *,
    workspace: Path,
    allow: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
) -> tuple[Path, ...]:
    """Immediate child dirs of `repos_root` that are git repos, as member repos.

    Excludes the workspace dir itself and `_MEMBER_SKIP_DIRS`. When `allow` is
    non-empty, only those names are kept (intersection); `exclude` names are
    then removed. Result is sorted by directory name for stable ordering.
    """
    repos_root = Path(repos_root).resolve()
    workspace = Path(workspace).resolve()
    allow_set = set(allow)
    exclude_set = set(exclude)
    out: list[Path] = []
    for child in sorted(repos_root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        if child.resolve() == workspace:
            continue
        if child.name in _MEMBER_SKIP_DIRS:
            continue
        if not (child / ".git").exists():
            continue
        if allow_set and child.name not in allow_set:
            continue
        if child.name in exclude_set:
            continue
        out.append(child.resolve())
    return tuple(out)


def _to_name_list(val: object) -> tuple[str, ...]:
    """Coerce a manifest value to a tuple of names.

    `_local_config.read` is a flat parser returning `dict[str, str]`, so a
    `repos: alpha,beta` line arrives as the string `"alpha,beta"` (and indented
    YAML-list lines are dropped entirely). Accept either a real list (defensive)
    or a comma-separated string.
    """
    if not val:
        return ()
    if isinstance(val, list):
        return tuple(str(v).strip() for v in val if str(v).strip())
    return tuple(s.strip() for s in str(val).split(",") if s.strip())


def _multi_repo_members(workspace: Path) -> tuple[Path, ...]:
    """Read multi-repo config from the workspace manifest and discover members.

    Returns () when `multi-repo` is absent/false. `repos-root` defaults to the
    workspace's parent; `repos:`/`exclude:` are optional allow/deny lists.
    """
    committed = _local_config.read(workspace / ".graph-wiki.yaml")
    local = _local_config.read(workspace / LOCAL_CONFIG_FILENAME)
    merged = {**committed, **local}
    if str(merged.get(MULTI_REPO_KEY, "")).strip().lower() not in _TRUTHY:
        return ()
    raw_root = str(merged.get(REPOS_ROOT_KEY, "") or "").strip()
    if raw_root:
        expanded = Path(raw_root).expanduser()
        repos_root = expanded.resolve() if expanded.is_absolute() else (workspace / expanded).resolve()
    else:
        repos_root = workspace.parent.resolve()
    allow = _to_name_list(merged.get(REPOS_ALLOW_KEY))
    exclude = _to_name_list(merged.get(REPOS_EXCLUDE_KEY))
    return discover_members(repos_root, workspace=workspace, allow=allow, exclude=exclude)


def resolve_workspace(repo_root: Path) -> Path:
    """Default workspace location for a repo.

    The repo-side `.graph-wiki.local.yaml` pointer is dead — `GRAPH_WIKI_WORKSPACE`
    (normally injected via the repo's `.claude/settings.local.json` env block) is
    the only external-workspace pointer.
    """
    return (repo_root / DEFAULT_WORKSPACE_NAME).resolve()


def _warn_if_legacy_repo_pointer(repo_root: Path) -> None:
    """Warn when a repo-side `.graph-wiki.local.yaml` still carries `workspace-directory:`.

    The key is ignored (dead) — this only surfaces the stale file so it doesn't
    fail silently.
    """
    legacy = repo_root / LOCAL_CONFIG_FILENAME
    if not legacy.exists():
        return
    if WORKSPACE_DIRECTORY_KEY in _local_config.read(legacy):
        warnings.warn(
            f"{legacy}: the repo-side 'workspace-directory:' pointer is ignored. "
            "Move the pointer to the repo's .claude/settings.local.json env block "
            '("env": {"GRAPH_WIKI_WORKSPACE": "<workspace>"}) and delete the key.',
            UserWarning,
            stacklevel=3,
        )


def resolve(cwd: Path | None = None, require_manifest: bool = True) -> GraphWikiConfig:
    """Resolve the GraphWikiConfig for the given working directory.

    Checks GRAPH_WIKI_WORKSPACE env var first for explicit override (used by tests).
    Falls back to discovery from cwd; raises RuntimeError if no `.graph-wiki.yaml`
    is found in the resolved workspace (D-03: strict).
    """
    # Check env var override first (does NOT enforce strict-manifest check;
    # env override must work even before a manifest is written so tests can
    # use it).
    env_workspace = os.environ.get("GRAPH_WIKI_WORKSPACE", "").strip()
    if env_workspace:
        workspace = Path(env_workspace).expanduser().resolve()
        # Default: walk up from workspace for .git, then let the workspace
        # manifest's `repo-directory:` (if set) override.
        repo_root = _find_repo_root(workspace) or workspace.parent.resolve()
        repo_root = _repo_directory_override(workspace, repo_root)
        members = _multi_repo_members(workspace)
        if members:
            repo_root = members[0]
        _warn_if_legacy_repo_pointer(repo_root)
        return GraphWikiConfig(workspace=workspace, repo_root=repo_root, members=members)

    # Normal discovery path
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    repo_root = _find_repo_root(cwd) or cwd.resolve()
    _warn_if_legacy_repo_pointer(repo_root)
    workspace = resolve_workspace(repo_root)
    # D-03: strict — raise if no .graph-wiki.yaml present in the resolved workspace.
    manifest = workspace / ".graph-wiki.yaml"
    if not manifest.exists():
        if require_manifest is True:
            raise RuntimeError(f"No .graph-wiki.yaml found in {workspace}. Run: gw bootstrap <path>")
    # Workspace manifest may pin a different repo_root explicitly.
    repo_root = _repo_directory_override(workspace, repo_root)
    members = _multi_repo_members(workspace)
    if members:
        repo_root = members[0]
    return GraphWikiConfig(workspace=workspace, repo_root=repo_root, members=members)
