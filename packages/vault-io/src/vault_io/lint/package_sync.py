"""Package sync drift: package/app pages whose source has changed since
``last_sync_commit``."""

from __future__ import annotations

from pathlib import Path

from vault_io.lint.common import parse_frontmatter

GROUP = "package_sync"


def check(repo: Path, wiki: Path) -> list[str]:
    """Flag package/app pages whose source has changed since last_sync_commit.

    Reads `last_sync_commit` and `package_path` (or `app_path`) from each
    page's frontmatter. For each, runs `git diff --name-only <sha>..HEAD --
    <path>`; if the result is non-empty, surfaces the package and the count
    of changed files. Pages without `last_sync_commit` are surfaced as
    'never synced'.
    """
    from vault_io.git_state import changed_files_since

    issues: list[str] = []
    vault = wiki
    for md in vault.rglob("*.md"):
        rel = md.relative_to(vault)
        if rel.name in {"index.md", "log.md"}:
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        category = fm.get("category")
        if category not in ("package", "app"):
            continue
        path_field = "app_path" if category == "app" else "package_path"
        pkg_rel = fm.get(path_field)
        if not pkg_rel:
            continue
        sha = (fm.get("last_sync_commit") or "").strip()
        key = str(rel).replace("\\", "/")[:-3]
        if not sha:
            issues.append(f"{key}: never synced (no last_sync_commit)")
            continue
        changed = changed_files_since(repo, sha, pkg_rel)
        if changed is None:
            issues.append(f"{key}: last_sync_commit {sha[:8]} not reachable from HEAD")
            continue
        if changed:
            issues.append(f"{key}: {len(changed)} file(s) changed since {sha[:8]} (e.g. {changed[0]})")
    return issues
