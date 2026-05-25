"""Source sync drift: in-repo source pages whose underlying file has changed
since ``last_sync_commit``."""

from __future__ import annotations

from pathlib import Path

from wiki_io.lint.common import parse_frontmatter

GROUP = "source_sync"


def check(repo: Path, wiki: Path) -> list[str]:
    """Flag in-repo source pages whose underlying file has changed since
    last_sync_commit.

    Walks `wiki/sources/*.md` for pages with `category: source` that
    record both `source_path` and `last_sync_commit`. raw/-staged sources
    are immutable by design and don't carry `last_sync_commit`, so they're
    skipped via the empty-SHA filter. Missing source files are flagged.
    """
    from wiki_io.git_state import changed_files_since

    issues: list[str] = []
    sources_dir = wiki / "sources"
    if not sources_dir.exists():
        return issues
    for page in sorted(sources_dir.rglob("*.md")):
        text = page.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        if fm.get("category") != "source":
            continue
        sp = fm.get("source_path") or ""
        sha = (fm.get("last_sync_commit") or "").strip()
        if not sp or not sha:
            continue
        # Resolve repo-relative first, then wiki-relative as a fallback.
        candidates = [repo / sp, wiki / sp]
        source = next((c for c in candidates if c.exists()), None)
        if source is None:
            issues.append(f"source page {page.name}: source '{sp}' missing")
            continue
        changed = changed_files_since(repo, sha, sp)
        if changed is None:
            issues.append(f"source page {page.name}: last_sync_commit {sha[:8]} not reachable from HEAD")
            continue
        if changed:
            issues.append(f"source page {page.name}: '{sp}' changed since {sha[:8]}")
    return issues
