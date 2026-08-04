"""Resolve a package's wiki overview page from the vault's layout conventions.

The vault stores one overview page per package/app, tried in order:
`wiki/packages/<name>/<name>.md`, `wiki/apps/<name>/<name>.md`. Returned paths
are workspace-relative POSIX strings. This is the single home of these
conventions — graph-io's sync-wiki pass receives them via an injected
callable (package-layering-review R1).
"""

from __future__ import annotations

from pathlib import Path


def resolve_overview_path(name: str, workspace: Path) -> tuple[str | None, bool]:
    """Return (workspace-relative wiki path, ambiguous?) for a package name.

    The path is None when no overview page exists. The second element of the
    tuple is retained for call-site compatibility but can no longer be True:
    the domain glob was the only source of ambiguity, and it was removed
    alongside the domain entity kind (Task 8).
    """
    direct_candidates = [
        Path("wiki") / "packages" / name / f"{name}.md",
        Path("wiki") / "apps" / name / f"{name}.md",
    ]
    for rel in direct_candidates:
        if (workspace / rel).is_file():
            return rel.as_posix(), False

    return None, False
