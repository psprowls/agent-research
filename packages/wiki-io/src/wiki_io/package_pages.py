"""Resolve a package's wiki overview page from the vault's layout conventions.

The vault stores one overview page per package/app, tried in order:
`wiki/packages/<name>/<name>.md`, `wiki/apps/<name>/<name>.md`, then the
domain glob `wiki/domains/*/packages/<name>/<name>.md`. A unique domain match
resolves; multiple domain matches are ambiguous and resolve to no path (the
caller decides how to report). Returned paths are workspace-relative POSIX
strings. This is the single home of these conventions — graph-io's sync-wiki
pass receives them via an injected callable (package-layering-review R1).
"""

from __future__ import annotations

from pathlib import Path


def resolve_overview_path(name: str, workspace: Path) -> tuple[str | None, bool]:
    """Return (workspace-relative wiki path, ambiguous?) for a package name.

    The path is None when no overview page exists; ambiguous is True when the
    domain glob matches more than one page (no path is returned then).
    """
    direct_candidates = [
        Path("wiki") / "packages" / name / f"{name}.md",
        Path("wiki") / "apps" / name / f"{name}.md",
    ]
    for rel in direct_candidates:
        if (workspace / rel).is_file():
            return rel.as_posix(), False

    domain_matches = (
        sorted((workspace / "wiki" / "domains").glob(f"*/packages/{name}/{name}.md"))
        if (workspace / "wiki" / "domains").is_dir()
        else []
    )
    if len(domain_matches) == 1:
        return domain_matches[0].relative_to(workspace).as_posix(), False
    if len(domain_matches) > 1:
        return None, True
    return None, False
