"""Unit tests for vault_io.scan_monorepo._discover_heuristic — workspace_dir exclusion filter.

Requirements: WSRES-02.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PYPROJECT_MINIMAL = '[project]\nname="{name}"\nversion="0.0.1"\n'
_PLUGIN_MINIMAL = '{{"name": "{name}", "version": "0.0.1"}}'


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_discover_heuristic_v2_skips_workspace_pyproject(tmp_path: Path) -> None:
    """_discover_heuristic with workspace_dir skips pyproject.toml under the workspace dir."""
    from vault_io.scan_monorepo import _discover_heuristic

    repo = tmp_path / "repo"
    # Stray manifest under workspace — must be excluded
    _write(repo / "graph-wiki" / "pyproject.toml", _PYPROJECT_MINIMAL.format(name="stray-pkg"))
    # Real package outside workspace — must be included
    _write(repo / "packages" / "pkg-a" / "pyproject.toml", _PYPROJECT_MINIMAL.format(name="pkg-a"))

    workspaces = _discover_heuristic(repo, workspace_dir=repo / "graph-wiki")
    names = {w["name"] for w in workspaces}

    assert "pkg-a" in names, f"Expected 'pkg-a' in discovered workspaces, got: {names}"
    # No workspace under graph-wiki/ should appear
    for w in workspaces:
        pkg_path = Path(w["path"]).resolve() if Path(w["path"]).is_absolute() else (repo / w["path"]).resolve()
        gw_resolved = (repo / "graph-wiki").resolve()
        assert not str(pkg_path).startswith(str(gw_resolved)), (
            f"Workspace at {w['path']} resolves under graph-wiki/ — must be excluded"
        )


def test_discover_heuristic_v2_skips_workspace_plugin_manifest(tmp_path: Path) -> None:
    """_discover_heuristic with workspace_dir skips .claude-plugin/plugin.json under workspace."""
    from vault_io.scan_monorepo import _discover_heuristic

    repo = tmp_path / "repo"
    # Stray plugin manifest under workspace — must be excluded
    _write(
        repo / "graph-wiki" / ".claude-plugin" / "plugin.json",
        _PLUGIN_MINIMAL.format(name="stray-plugin"),
    )
    # Real plugin outside workspace — must be included
    _write(
        repo / "plugins" / "real-plugin" / ".claude-plugin" / "plugin.json",
        _PLUGIN_MINIMAL.format(name="real-plugin"),
    )

    workspaces = _discover_heuristic(repo, workspace_dir=repo / "graph-wiki")
    names = {w["name"] for w in workspaces}

    assert "real-plugin" in names, f"Expected 'real-plugin' in discovered workspaces, got: {names}"
    # No workspace under graph-wiki/ should appear
    for w in workspaces:
        pkg_path = Path(w["path"]).resolve() if Path(w["path"]).is_absolute() else (repo / w["path"]).resolve()
        gw_resolved = (repo / "graph-wiki").resolve()
        assert not str(pkg_path).startswith(str(gw_resolved)), (
            f"Workspace at {w['path']} resolves under graph-wiki/ — must be excluded"
        )


def test_discover_heuristic_v1_guard_workspace_eq_repo(tmp_path: Path) -> None:
    """D-11 guard: when workspace_dir == repo, no over-exclusion occurs.

    Passing workspace_dir=repo must return identical results to workspace_dir=None.
    """
    from vault_io.scan_monorepo import _discover_heuristic

    repo = tmp_path / "repo"
    _write(repo / "packages" / "pkg-a" / "pyproject.toml", _PYPROJECT_MINIMAL.format(name="pkg-a"))

    workspaces_v1 = _discover_heuristic(repo, workspace_dir=repo)
    workspaces_none = _discover_heuristic(repo, workspace_dir=None)

    names_v1 = {w["name"] for w in workspaces_v1}
    names_none = {w["name"] for w in workspaces_none}

    assert names_v1 == names_none, (
        f"v1 guard failed: workspace_dir==repo must not change results.\n"
        f"  with workspace_dir=repo: {names_v1}\n"
        f"  with workspace_dir=None: {names_none}"
    )
    assert "pkg-a" in names_v1, f"Expected 'pkg-a' in results, got: {names_v1}"


def test_discover_heuristic_default_workspace_dir_none(tmp_path: Path) -> None:
    """Without workspace_dir, stray manifests under graph-wiki/ ARE included.

    This proves the new param is additive — callers MUST opt in.
    """
    from vault_io.scan_monorepo import _discover_heuristic

    repo = tmp_path / "repo"
    # Same v2 fixture: stray manifest under graph-wiki/
    _write(repo / "graph-wiki" / "pyproject.toml", _PYPROJECT_MINIMAL.format(name="stray-pkg"))
    _write(repo / "packages" / "pkg-a" / "pyproject.toml", _PYPROJECT_MINIMAL.format(name="pkg-a"))

    # No workspace_dir — old behavior; both manifests should be found
    workspaces = _discover_heuristic(repo)
    names = {w["name"] for w in workspaces}

    assert "pkg-a" in names, f"Expected 'pkg-a' in default results, got: {names}"
    assert "stray-pkg" in names, (
        f"Without workspace_dir, 'stray-pkg' must appear (additive default). Got: {names}"
    )
