"""File-map drift: ``## File map - <name>`` entries that no longer exist on disk."""

from __future__ import annotations

from pathlib import Path

from vault_io.lint.common import FILE_MAP_SECTION_RE, parse_section_entries

GROUP = "file_map"

try:
    from vault_io.scan_monorepo import _git_ls_files as _scan_git_ls_files
except ImportError:
    _scan_git_ls_files = None


def check(repo: Path, pages: dict) -> list[str]:
    """Flag ``## File map - <name>`` entries that no longer exist on disk.

    Only flags removals (entries listed in the map but not present in the
    package). Does not flag new files missing from the map — folder-bullet
    summarization is allowed by the template.

    Skipped silently when ``git`` is unavailable or the package isn't in a
    git repo (matches the scanner's gitignore-aware behavior).
    """
    if _scan_git_ls_files is None:
        return []
    issues: list[str] = []
    for key, page in pages.items():
        fm = page["fm"]
        category = fm.get("category")
        if category not in ("package", "app"):
            continue
        path_field = "app_path" if category == "app" else "package_path"
        pkg_rel = fm.get(path_field)
        if not pkg_rel:
            continue
        pkg_dir = (repo / pkg_rel).resolve()
        if not pkg_dir.exists() or not pkg_dir.is_dir():
            continue

        m = FILE_MAP_SECTION_RE.search(page["text"])
        if not m:
            continue
        pkg_name = m.group(1).strip()
        body = m.group(2)

        files = _scan_git_ls_files(pkg_dir)
        if files is None:
            continue
        actual_files = set(files)
        actual_dirs: set[str] = set()
        for f in files:
            parts = f.split("/")
            for i in range(1, len(parts)):
                actual_dirs.add("/".join(parts[:i]))

        for full_path, is_dir in parse_section_entries(body, pkg_name):
            if is_dir:
                if full_path not in actual_dirs and not (pkg_dir / full_path).is_dir():
                    issues.append(f"{key}: file map references missing directory '{full_path}/'")
            else:
                if full_path not in actual_files and not (pkg_dir / full_path).is_file():
                    issues.append(f"{key}: file map references missing path '{full_path}'")
    return issues
