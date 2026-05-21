"""Idempotent workspace bootstrapping.

Creates the workspace directory (default `<repo_root>/graph-wiki`, override
via `workspace=`), writes `.graph-wiki.yaml`, ensures `.graph-wiki.local.yaml`
is gitignored. If the workspace is outside any git repo, runs `git init`
before writing the manifest.
"""
from __future__ import annotations

import datetime
import subprocess
from pathlib import Path

from workspace_io import manifest
from workspace_io import paths as _paths
from workspace_io.render import render_workspace_claude_md
from workspace_io.config import resolve_workspace

_GITIGNORE_ENTRY = ".graph-wiki.local.yaml"


def init(
    repo_root: Path,
    *,
    plugin: str,
    version: str,
    workspace: Path | None = None,
) -> None:
    """Create the workspace and `.graph-wiki.yaml` if absent. Append/update plugin entry. Idempotent."""
    repo_root = Path(repo_root).resolve()
    if workspace is None:
        workspace = resolve_workspace(repo_root=repo_root)
    workspace = Path(workspace).resolve()

    workspace.mkdir(parents=True, exist_ok=True)

    if not _is_inside_git_repo(workspace):
        _git_init(workspace)

    mpath = _paths.manifest_path(workspace)
    if mpath.exists():
        data = manifest.read(mpath)
    else:
        data = {
            "version": 2,
            "initialized_at": datetime.date.today().isoformat(),
            "plugins": [],
        }

    data.setdefault("plugins", [])

    entry = next((p for p in data["plugins"] if p["name"] == plugin), None)
    if entry is None:
        data["plugins"].append(
            {"name": plugin, "installed_version": version, "applied_version": version}
        )
        changed = True
    else:
        changed = (
            entry.get("installed_version") != version
            or entry.get("applied_version") != version
        )
        entry["installed_version"] = version
        entry["applied_version"] = version

    if changed or not mpath.exists():
        manifest.write(mpath, data)

    render_workspace_claude_md(workspace)   # render <workspace>/CLAUDE.md

    # NOTE: D-06 — work-layer schema bootstrap intentionally not ported.
    _ensure_gitignore_entry(repo_root)


def _is_inside_git_repo(path: Path) -> bool:
    """True if `path` (or any parent) contains a `.git` directory."""
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return True
    return False


def _git_init(path: Path) -> None:
    """Run `git init` at `path`. Propagates errors with stderr."""
    result = subprocess.run(
        ["git", "init", "-q", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git init failed at {path}: {result.stderr.strip()}")


def _ensure_gitignore_entry(repo_root: Path) -> None:
    """Append `.graph-wiki.local.yaml` to `<repo_root>/.gitignore` if not present."""
    gitignore = repo_root / ".gitignore"
    if gitignore.exists():
        text = gitignore.read_text(encoding="utf-8")
        existing_lines = {line.strip() for line in text.splitlines()}
        if _GITIGNORE_ENTRY in existing_lines:
            return
        sep = "" if text.endswith("\n") or text == "" else "\n"
        gitignore.write_text(text + sep + _GITIGNORE_ENTRY + "\n", encoding="utf-8")
    else:
        gitignore.write_text(_GITIGNORE_ENTRY + "\n", encoding="utf-8")
