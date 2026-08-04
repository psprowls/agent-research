"""Pure-function tests for wiki_io.package_pages.resolve_overview_path.

Moved from graph-io's sync-wiki suite when the layout conventions were
repatriated (package-layering-review R1): these pin the two filesystem
conventions. The domain glob (and its ambiguity case) was removed alongside
the domain entity kind (Task 8).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from wiki_io.package_pages import resolve_overview_path


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "graph-wiki"
    (ws / "wiki").mkdir(parents=True)
    return ws


def _make_overview(workspace: Path, rel: str) -> None:
    p = workspace / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"# {p.stem}\n")


def test_resolves_packages_convention(workspace: Path) -> None:
    _make_overview(workspace, "wiki/packages/alpha/alpha.md")
    assert resolve_overview_path("alpha", workspace) == ("wiki/packages/alpha/alpha.md", False)


def test_resolves_apps_convention(workspace: Path) -> None:
    _make_overview(workspace, "wiki/apps/web/web.md")
    assert resolve_overview_path("web", workspace) == ("wiki/apps/web/web.md", False)


def test_packages_convention_wins_over_apps(workspace: Path) -> None:
    _make_overview(workspace, "wiki/packages/dual/dual.md")
    _make_overview(workspace, "wiki/apps/dual/dual.md")
    assert resolve_overview_path("dual", workspace) == ("wiki/packages/dual/dual.md", False)


def test_missing_page_is_not_found(workspace: Path) -> None:
    assert resolve_overview_path("ghost", workspace) == (None, False)


def test_no_wiki_dir_is_not_found(tmp_path: Path) -> None:
    ws = tmp_path / "empty-ws"
    ws.mkdir()
    assert resolve_overview_path("alpha", ws) == (None, False)
