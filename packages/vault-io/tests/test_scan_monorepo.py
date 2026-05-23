"""Unit tests for vault_io.scan_monorepo._discover_heuristic — workspace_dir exclusion filter.

Requirements: WSRES-02.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# build_file_map() tests — new table format (per-major-folder H3 sections)
# ---------------------------------------------------------------------------


def _bfm(pkg_name: str, files: list[str] | None, **kwargs) -> str | None:
    """Call build_file_map() with a mocked _git_ls_files."""
    from vault_io.scan_monorepo import build_file_map

    pkg_path = Path(f"/fake/{pkg_name}")
    with patch("vault_io.scan_monorepo._git_ls_files", return_value=files):
        return build_file_map(pkg_path, **kwargs)


class TestBuildFileMap:
    """Tests for the new per-major-folder table format emitted by build_file_map()."""

    def test_single_file_package(self) -> None:
        """Single-file package emits one synthetic root H3 section with one table row."""
        result = _bfm("mypkg", ["README.md"])
        assert result is not None
        assert "## File map - mypkg" in result
        assert "### mypkg/" in result
        assert "| Path | Kind | Description |" in result
        assert "|---|---|---|" in result
        assert "| `README.md` | file | — TODO |" in result
        # No other H3 sections
        h3_lines = [l for l in result.splitlines() if l.startswith("### ")]
        assert h3_lines == ["### mypkg/"], f"Expected only root H3, got: {h3_lines}"

    def test_root_plus_subdir_produces_two_h3_sections(self) -> None:
        """Package with root files + src/ subdir produces exactly two H3 sections."""
        result = _bfm("mypkg", ["README.md", "src/index.ts"])
        assert result is not None
        h3_lines = [l for l in result.splitlines() if l.startswith("### ")]
        assert h3_lines == ["### mypkg/", "### mypkg/src/"], (
            f"Expected [root, src] H3 sections, got: {h3_lines}"
        )
        # Root section has README.md
        assert "| `README.md` | file | — TODO |" in result
        # src section has index.ts
        assert "### mypkg/src/" in result
        assert "| `index.ts` | file | — TODO |" in result
        # src/index.ts must not appear in root section
        root_section = result.split("### mypkg/src/")[0]
        assert "index.ts" not in root_section

    def test_nested_file_flattened_into_depth1_parent_table(self) -> None:
        """A file at src/middleware/auth.ts appears relative to src/ in that section."""
        result = _bfm("mypkg", ["src/middleware/auth.ts"])
        assert result is not None
        assert "### mypkg/src/" in result
        # Path relative to src/ — no leading src/
        assert "| `middleware/auth.ts` | file | — TODO |" in result
        # Must NOT appear as src/middleware/auth.ts (absolute relative)
        assert "| `src/middleware/auth.ts`" not in result

    def test_deep_dir_emitted_as_dir_row_in_depth1_parent(self) -> None:
        """A directory at depth > max_depth appears as a dir row, not its own H3."""
        # max_depth=1: any depth-1 dir itself is the cutoff — depth-2 dirs are dir rows
        result = _bfm("mypkg", ["a/b/c/deep.ts"], max_depth=1)
        assert result is not None
        # Should NOT have ### mypkg/a/b/ or ### mypkg/a/b/c/
        h3_lines = [l for l in result.splitlines() if l.startswith("### ")]
        # Only root and 'a' at depth 1
        assert "### mypkg/a/" in h3_lines
        # No deeper H3 sections
        for h3 in h3_lines:
            parts = h3.rstrip("/").split("/")
            # mypkg + at most 1 more part = max depth 1
            assert len(parts) <= 3, f"H3 too deep: {h3}"

    def test_truncation_marker_added(self) -> None:
        """When file count > max_entries, the truncation blockquote is appended."""
        files = [f"file{i}.ts" for i in range(5)]
        result = _bfm("mypkg", files, max_entries=3)
        assert result is not None
        assert "> Truncated at 3 files." in result

    def test_empty_package_uses_legacy_short_circuit(self) -> None:
        """Empty package (no tracked files) uses the legacy no-table format."""
        result = _bfm("mypkg", [])
        assert result is not None
        assert "## File map - mypkg" in result
        assert "- (no tracked files)" in result
        # No tables
        assert "| Path | Kind | Description |" not in result

    def test_no_git_repo_returns_none(self) -> None:
        """Returns None when _git_ls_files returns None (not a git repo)."""
        result = _bfm("mypkg", None)
        assert result is None

    def test_h3_section_ordering_root_first_then_alphabetical(self) -> None:
        """Root section comes first; depth-1 subdirs sorted alphabetically."""
        result = _bfm("mypkg", [
            "README.md",
            "zebra/z.ts",
            "apple/a.ts",
            "mango/m.ts",
        ])
        assert result is not None
        h3_lines = [l for l in result.splitlines() if l.startswith("### ")]
        assert h3_lines == [
            "### mypkg/",
            "### mypkg/apple/",
            "### mypkg/mango/",
            "### mypkg/zebra/",
        ], f"Wrong order: {h3_lines}"

    def test_path_tokens_backticked_and_kind_accurate(self) -> None:
        """Path tokens wrapped in backticks; dirs end with /; Kind is 'file' or 'dir'."""
        result = _bfm("mypkg", ["README.md", "src/index.ts"])
        assert result is not None
        # Check backtick wrapping — README.md is a file
        assert "| `README.md` | file |" in result
        # src is a dir — appears as H3 header (not a dir row since it's a standard depth-1 dir)
        assert "### mypkg/src/" in result
