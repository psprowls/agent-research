"""Unit tests for wiki_io.scan_monorepo._discover_heuristic — workspace_dir exclusion filter.

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
    from wiki_io.scan_monorepo import _discover_heuristic

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
    from wiki_io.scan_monorepo import _discover_heuristic

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
    from wiki_io.scan_monorepo import _discover_heuristic

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
    from wiki_io.scan_monorepo import _discover_heuristic

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
# _collect_python_package() — pyproject deps + collect_external_dependencies
# ---------------------------------------------------------------------------


def test_python_package_external_deps_populated(tmp_path: Path) -> None:
    """A Python workspace member must expose ``external_deps`` + ``ecosystem``
    (`pypi`) so ``collect_external_dependencies`` can aggregate it into the
    dependencies/index.md auto-block.

    Regression for the 2026-05-23 lint finding: ``dependencies/index.md`` was
    empty despite ~12 declared third-party deps because the Python collector
    returned no ``external_deps`` / ``ecosystem`` keys.
    """
    from wiki_io.scan_monorepo import _collect_python_package, collect_external_dependencies

    repo = tmp_path
    pkg = repo / "packages" / "alpha"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        "[project]\n"
        'name = "alpha"\n'
        'version = "0.1.0"\n'
        "dependencies = [\n"
        '    "boto3>=1.38",\n'
        '    "python-frontmatter>=1.1",\n'
        '    "beta",\n'
        "]\n\n"
        "[tool.uv.sources]\n"
        "beta = { workspace = true }\n",
        encoding="utf-8",
    )

    ws = _collect_python_package(repo, pkg)
    assert ws is not None
    assert ws["ecosystem"] == "pypi"
    assert ws["external_deps"] == {"boto3": ">=1.38", "python-frontmatter": ">=1.1"}
    assert ws["depends_on"] == ["beta"]

    aggregated = collect_external_dependencies([ws])
    names = {d["name"] for d in aggregated}
    assert names == {"boto3", "python-frontmatter"}
    assert all(d["ecosystem"] == "pypi" for d in aggregated)


# ---------------------------------------------------------------------------
# build_file_map() tests — new table format (per-major-folder H3 sections)
# ---------------------------------------------------------------------------


def _bfm(pkg_name: str, files: list[str] | None, **kwargs) -> str | None:
    """Call build_file_map() with a mocked _git_ls_files."""
    from wiki_io.scan_monorepo import build_file_map

    pkg_path = Path(f"/fake/{pkg_name}")
    with patch("wiki_io.scan_monorepo._git_ls_files", return_value=files):
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

    def test_build_file_map_regression_returns_prod_block_only(self) -> None:
        """build_file_map() == build_file_maps()[0] — legacy API returns prod block only."""
        from wiki_io.scan_monorepo import build_file_maps
        files = ["README.md", "src/index.ts", "tests/test_main.py", "conftest.py"]
        prod, _test = _bfms("mypkg", files)
        legacy = _bfm("mypkg", files)
        assert legacy == prod, (
            "build_file_map() must return the prod block (same as build_file_maps()[0])"
        )


# ---------------------------------------------------------------------------
# _is_test_path() unit tests
# ---------------------------------------------------------------------------


class TestIsTestPath:
    """Tests for _is_test_path() classification helper."""

    def test_tests_dir_component_is_test(self) -> None:
        """tests/ directory component classifies as test."""
        from wiki_io.scan_monorepo import _is_test_path
        assert _is_test_path("tests/handlers.test.ts") is True
        assert _is_test_path("src/index.ts") is False

    def test_nested_tests_dir_component_is_test(self) -> None:
        """__tests__/ anywhere in path classifies as test."""
        from wiki_io.scan_monorepo import _is_test_path
        assert _is_test_path("src/__tests__/foo.spec.ts") is True

    def test_test_and_spec_dir_components(self) -> None:
        """test/ and spec/ directory components classify as test."""
        from wiki_io.scan_monorepo import _is_test_path
        assert _is_test_path("test/a.py") is True
        assert _is_test_path("spec/login.cy.ts") is True

    def test_conftest_at_root_is_test(self) -> None:
        """conftest.py at root (and any depth) is a test config file."""
        from wiki_io.scan_monorepo import _is_test_path
        assert _is_test_path("conftest.py") is True
        assert _is_test_path("src/conftest.py") is True

    def test_jest_config_is_test(self) -> None:
        """jest.config.ts at package root is a test config file."""
        from wiki_io.scan_monorepo import _is_test_path
        assert _is_test_path("jest.config.ts") is True

    def test_tested_ts_is_not_test(self) -> None:
        """tested.ts does not match — directory name match is exact."""
        from wiki_io.scan_monorepo import _is_test_path
        assert _is_test_path("tested.ts") is False

    def test_various_test_config_basenames(self) -> None:
        """Test-config basenames at any path depth classify as test."""
        from wiki_io.scan_monorepo import _is_test_path
        assert _is_test_path("pytest.ini") is True
        assert _is_test_path("tox.ini") is True
        assert _is_test_path("jest.config.js") is True
        assert _is_test_path("vitest.config.ts") is True
        assert _is_test_path("playwright.config.ts") is True
        assert _is_test_path("cypress.config.js") is True
        assert _is_test_path(".mocharc.json") is True
        assert _is_test_path("karma.conf.js") is True
        assert _is_test_path("ava.config.mjs") is True


# ---------------------------------------------------------------------------
# build_file_maps() (paired API) tests
# ---------------------------------------------------------------------------


def _bfms(pkg_name: str, files: list[str] | None, **kwargs) -> tuple[str, str] | None:
    """Helper: run build_file_maps with a mocked _git_ls_files return value."""
    from wiki_io.scan_monorepo import build_file_maps
    pkg_path = Path(f"/fake/{pkg_name}")
    with patch("wiki_io.scan_monorepo._git_ls_files", return_value=files):
        return build_file_maps(pkg_path, **kwargs)


class TestBuildFileMaps:
    """Tests for build_file_maps() paired prod/test output."""

    def test_mixed_files_splits_correctly(self) -> None:
        """prod has source files; test has test files; neither has the other's rows."""
        result = _bfms("mypkg", ["README.md", "src/index.ts", "tests/handlers.test.ts", "conftest.py"])
        assert result is not None
        prod, test = result
        # Prod block has source files
        assert "README.md" in prod
        assert "index.ts" in prod
        # Prod block has no test files
        assert "tests" not in prod
        assert "conftest.py" not in prod
        # Test block has test files
        assert "handlers.test.ts" in test
        assert "conftest.py" in test
        # Test block has no prod files
        assert "README.md" not in test
        assert "index.ts" not in test

    def test_no_test_files_returns_placeholder_test_block(self) -> None:
        """A package with no test paths returns a no-tests placeholder test block."""
        result = _bfms("mypkg", ["README.md", "src/index.ts"])
        assert result is not None
        prod, test = result
        assert "README.md" in prod
        # Placeholder contains the no-tests message
        assert "no test files detected" in test
        # Placeholder has no table
        assert "| Path | Kind | Description |" not in test
        # Has the synthetic root H3
        assert "### mypkg/" in test

    def test_none_from_no_git_returns_none(self) -> None:
        """Returns None when _git_ls_files returns None."""
        result = _bfms("mypkg", None)
        assert result is None

    def test_tests_only_package_empty_prod_block(self) -> None:
        """A tests-only package produces an empty prod block with short-circuit."""
        result = _bfms("mypkg", ["tests/test_a.py", "conftest.py"])
        assert result is not None
        prod, test = result
        assert "no tracked files" in prod or "- (no tracked files)" in prod
        assert "test_a.py" in test

    def test_h3_ordering_independent_per_block(self) -> None:
        """Root H3 first, then alphabetical per block — applied independently."""
        result = _bfms("mypkg", ["src/index.ts", "tests/a.ts", "spec/b.ts"])
        assert result is not None
        prod, test = result
        # Prod has src; test has spec + tests
        prod_h3 = [l for l in prod.splitlines() if l.startswith("### ")]
        test_h3 = [l for l in test.splitlines() if l.startswith("### ")]
        assert "### mypkg/src/" in prod_h3
        assert "### mypkg/spec/" not in prod_h3
        assert "### mypkg/tests/" not in prod_h3
        assert "### mypkg/spec/" in test_h3
        assert "### mypkg/tests/" in test_h3
        assert "### mypkg/src/" not in test_h3
        # Root section always first
        assert test_h3[0] == "### mypkg/"
        # spec/ before tests/ alphabetically
        spec_idx = test_h3.index("### mypkg/spec/")
        tests_idx = test_h3.index("### mypkg/tests/")
        assert spec_idx < tests_idx

    def test_truncation_marker_appears_on_both_blocks(self) -> None:
        """When truncation occurs (combined file count > max_entries), both blocks get marker."""
        # 3 prod files + 3 test files, max_entries=4 -> truncated=True
        files = ["a.ts", "b.ts", "c.ts", "tests/x.ts", "tests/y.ts", "tests/z.ts"]
        result = _bfms("mypkg", files, max_entries=4)
        assert result is not None
        prod, test = result
        assert "> Truncated at 4 files." in prod
        assert "> Truncated at 4 files." in test

    def test_legacy_api_equals_prod_block(self) -> None:
        """build_file_map() returns the same string as build_file_maps()[0]."""
        files = ["README.md", "src/index.ts", "tests/test_main.py"]
        prod, _test = _bfms("mypkg", files)
        legacy = _bfm("mypkg", files)
        assert legacy == prod
