from __future__ import annotations

"""Unit tests for the scan command (Plan 05-04).

Requirements covered: CMD-02, MCP-03.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fan_out_result(successes=None, errors=None):
    """Build a FanOutResult with optional successes and errors."""
    from subagent_runtime.pool import FanOutResult

    result = FanOutResult()
    if successes:
        result.successes = successes
    if errors:
        result.errors = errors
    return result


# ---------------------------------------------------------------------------
# Test 1: ScanResult dataclass shape
# ---------------------------------------------------------------------------


def test_scan_result_dataclass_shape() -> None:
    """ScanResult has all 6 required fields with correct types."""
    from graph_wiki_agent.commands.scan import ScanResult

    result = ScanResult(
        added=["pkg-a"],
        updated=["pkg-b"],
        deleted=["pkg-c"],
        renamed=[["old", "new"]],
        errors=["pkg-d: some error"],
        state_gate={"allowed": True, "reason": "clean", "head_commit": "abc123"},
    )

    assert isinstance(result.added, list)
    assert isinstance(result.updated, list)
    assert isinstance(result.deleted, list)
    assert isinstance(result.renamed, list)
    assert isinstance(result.errors, list)
    assert isinstance(result.state_gate, dict)

    assert result.added == ["pkg-a"]
    assert result.updated == ["pkg-b"]
    assert result.deleted == ["pkg-c"]
    assert result.renamed == [["old", "new"]]
    assert result.errors == ["pkg-d: some error"]
    assert result.state_gate["allowed"] is True


# ---------------------------------------------------------------------------
# Test 2: run_scan returns ScanResult with correct diff keys
# ---------------------------------------------------------------------------


async def test_run_scan_deterministic_diff_keys(tmp_path: Path) -> None:
    """run_scan maps compute_diff keys correctly to ScanResult fields."""
    from graph_wiki_agent.commands.scan import run_scan

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    (wiki / "packages").mkdir()

    fake_diff = {
        "new": ["brand-new-pkg"],
        "unchanged": [],
        "deleted": [],
        "renamed": [],
    }
    fake_workspaces = [
        {
            "name": "brand-new-pkg",
            "path": "packages/brand-new-pkg",
            "wiki_relative_path": "packages/brand-new-pkg/brand-new-pkg.md",
            "type": "library",
            "language": "python",
            "changed_files": None,
        }
    ]
    fake_state_gate = {"allowed": True, "reason": "clean", "head_commit": "abc"}
    fake_fan_result = _make_fan_out_result(
        successes=[
            (fake_workspaces[0], "# Brand New Pkg\n\nA stub body.")
        ]
    )

    with (
        patch("graph_wiki_agent.commands.scan.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_agent.commands.scan.read_layout", return_value={}),
        patch("graph_wiki_agent.commands.scan.discover_workspaces", return_value=fake_workspaces),
        patch("graph_wiki_agent.commands.scan._load_existing_pages", return_value={}),
        patch("graph_wiki_agent.commands.scan.attach_changed_files"),
        patch("graph_wiki_agent.commands.scan.compute_diff", return_value=fake_diff),
        patch("graph_wiki_agent.commands.scan.compute_state_gate", return_value=fake_state_gate),
        patch("graph_wiki_agent.commands.scan.build_file_map", return_value="## File map - brand-new-pkg\nTODO\n"),
        patch("graph_wiki_agent.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_agent.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_agent.commands.scan.make_llm"),
        patch("graph_wiki_agent.commands.scan.load_role_config", return_value={"model_id": "fake-model", "max_concurrency": 2}),
        patch("graph_wiki_agent.commands.scan.regenerate_dependencies_index"),
        patch("graph_wiki_agent.commands.scan.update_index"),
        patch("graph_wiki_agent.commands.scan._capture_run", return_value=(0, "", "")),
        patch("graph_wiki_agent.commands.scan.read_only_connect", side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError("test stub")),
        patch("graph_wiki_agent.commands.scan.append_log"),
    ):
        mock_pool_instance = AsyncMock()
        mock_pool_instance.run_all = AsyncMock(return_value=fake_fan_result)
        MockPool.return_value = mock_pool_instance

        result = await run_scan(workspace_path=wiki)

    assert "brand-new-pkg" in result.added
    assert isinstance(result.updated, list)
    assert isinstance(result.deleted, list)
    assert isinstance(result.renamed, list)
    assert isinstance(result.state_gate, dict)
    assert result.state_gate["allowed"] is True


# ---------------------------------------------------------------------------
# Test 3: SubagentPool is called with role="scanner"
# ---------------------------------------------------------------------------


async def test_scanner_fanout_called_with_role_scanner(tmp_path: Path) -> None:
    """SubagentPool.run_all is called with role='scanner'."""
    from graph_wiki_agent.commands.scan import run_scan

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    (wiki / "packages").mkdir()

    fake_pkg = {
        "name": "new-pkg",
        "path": "packages/new-pkg",
        "wiki_relative_path": "packages/new-pkg/new-pkg.md",
        "type": "library",
        "language": "python",
        "changed_files": None,
    }
    fake_diff = {"new": ["new-pkg"], "unchanged": [], "deleted": [], "renamed": []}
    fake_fan_result = _make_fan_out_result(
        successes=[(fake_pkg, "stub body")]
    )

    with (
        patch("graph_wiki_agent.commands.scan.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_agent.commands.scan.read_layout", return_value={}),
        patch("graph_wiki_agent.commands.scan.discover_workspaces", return_value=[fake_pkg]),
        patch("graph_wiki_agent.commands.scan._load_existing_pages", return_value={}),
        patch("graph_wiki_agent.commands.scan.attach_changed_files"),
        patch("graph_wiki_agent.commands.scan.compute_diff", return_value=fake_diff),
        patch("graph_wiki_agent.commands.scan.compute_state_gate", return_value={"allowed": True, "reason": "", "head_commit": "x"}),
        patch("graph_wiki_agent.commands.scan.build_file_map", return_value=None),
        patch("graph_wiki_agent.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_agent.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_agent.commands.scan.make_llm"),
        patch("graph_wiki_agent.commands.scan.load_role_config", return_value={"model_id": "fake-model", "max_concurrency": 2}),
        patch("graph_wiki_agent.commands.scan.regenerate_dependencies_index"),
        patch("graph_wiki_agent.commands.scan.update_index"),
        patch("graph_wiki_agent.commands.scan._capture_run", return_value=(0, "", "")),
        patch("graph_wiki_agent.commands.scan.read_only_connect", side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError("test stub")),
        patch("graph_wiki_agent.commands.scan.append_log"),
    ):
        mock_pool_instance = AsyncMock()
        mock_pool_instance.run_all = AsyncMock(return_value=fake_fan_result)
        MockPool.return_value = mock_pool_instance

        await run_scan(workspace_path=wiki)

    call_kwargs = mock_pool_instance.run_all.call_args
    assert call_kwargs is not None
    kwargs = call_kwargs.kwargs
    assert kwargs.get("role") == "scanner", f"Expected role='scanner', got kwargs={kwargs}"


# ---------------------------------------------------------------------------
# Test 4: file map is appended after LLM body
# ---------------------------------------------------------------------------


async def test_file_map_appended_after_llm(tmp_path: Path) -> None:
    """Final stub page contains file map text AFTER the LLM body."""
    from graph_wiki_agent.commands.scan import run_scan

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    pkg_dir = wiki / "packages" / "test-pkg"
    pkg_dir.mkdir(parents=True)

    fake_pkg = {
        "name": "test-pkg",
        "path": "packages/test-pkg",
        "wiki_relative_path": "packages/test-pkg/test-pkg.md",
        "type": "library",
        "language": "python",
        "changed_files": None,
    }
    fake_diff = {"new": ["test-pkg"], "unchanged": [], "deleted": [], "renamed": []}
    llm_body = "# Test stub\n\nbody text here"
    fake_file_map = "## File map - test-pkg\nFAKEFILEMAP\n"
    fan_result = _make_fan_out_result(
        successes=[(fake_pkg, llm_body)]
    )

    with (
        patch("graph_wiki_agent.commands.scan.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_agent.commands.scan.read_layout", return_value={}),
        patch("graph_wiki_agent.commands.scan.discover_workspaces", return_value=[fake_pkg]),
        patch("graph_wiki_agent.commands.scan._load_existing_pages", return_value={}),
        patch("graph_wiki_agent.commands.scan.attach_changed_files"),
        patch("graph_wiki_agent.commands.scan.compute_diff", return_value=fake_diff),
        patch("graph_wiki_agent.commands.scan.compute_state_gate", return_value={"allowed": True, "reason": "", "head_commit": "x"}),
        patch("graph_wiki_agent.commands.scan.build_file_map", return_value=fake_file_map),
        patch("graph_wiki_agent.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_agent.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_agent.commands.scan.make_llm"),
        patch("graph_wiki_agent.commands.scan.load_role_config", return_value={"model_id": "fake-model", "max_concurrency": 2}),
        patch("graph_wiki_agent.commands.scan.regenerate_dependencies_index"),
        patch("graph_wiki_agent.commands.scan.update_index"),
        patch("graph_wiki_agent.commands.scan._capture_run", return_value=(0, "", "")),
        patch("graph_wiki_agent.commands.scan.read_only_connect", side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError("test stub")),
        patch("graph_wiki_agent.commands.scan.append_log"),
    ):
        mock_pool_instance = AsyncMock()
        mock_pool_instance.run_all = AsyncMock(return_value=fan_result)
        MockPool.return_value = mock_pool_instance

        await run_scan(workspace_path=wiki)

    written_page_path = wiki / "packages" / "test-pkg" / "test-pkg.md"
    assert written_page_path.exists(), "Stub page should be written to vault"
    page_text = written_page_path.read_text(encoding="utf-8")

    body_idx = page_text.find("body text here")
    filemap_idx = page_text.find("FAKEFILEMAP")

    assert body_idx != -1, "LLM body should appear in written page"
    assert filemap_idx != -1, "File map should appear in written page"
    assert filemap_idx > body_idx, "File map must come AFTER LLM body"


# ---------------------------------------------------------------------------
# Test 5: stale tag added for deleted packages
# ---------------------------------------------------------------------------


async def test_stale_tag_added_for_deleted_packages(tmp_path: Path) -> None:
    """Deleted packages get 'stale: true' added to their vault page frontmatter."""
    from graph_wiki_agent.commands.scan import run_scan

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    old_pkg_dir = wiki / "packages" / "old-pkg"
    old_pkg_dir.mkdir(parents=True)
    old_page = old_pkg_dir / "old-pkg.md"
    old_page.write_text(
        "---\ntitle: old-pkg\ncategory: package\n---\n\n# old-pkg\n\nOld content.\n",
        encoding="utf-8",
    )

    existing = {
        "old-pkg": {
            "wiki_relative_path": "packages/old-pkg/old-pkg.md",
            "package_path": "packages/old-pkg",
            "category": "package",
            "last_sync_commit": None,
        }
    }
    fake_diff = {
        "new": [],
        "unchanged": [],
        "deleted": ["old-pkg"],
        "renamed": [],
    }
    fan_result = _make_fan_out_result()

    append_log_calls: list[tuple] = []

    def _mock_append_log(wiki_, op, title, detail=None, **kwargs):
        append_log_calls.append((op, title))

    with (
        patch("graph_wiki_agent.commands.scan.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_agent.commands.scan.read_layout", return_value={}),
        patch("graph_wiki_agent.commands.scan.discover_workspaces", return_value=[]),
        patch("graph_wiki_agent.commands.scan._load_existing_pages", return_value=existing),
        patch("graph_wiki_agent.commands.scan.attach_changed_files"),
        patch("graph_wiki_agent.commands.scan.compute_diff", return_value=fake_diff),
        patch("graph_wiki_agent.commands.scan.compute_state_gate", return_value={"allowed": True, "reason": "", "head_commit": "x"}),
        patch("graph_wiki_agent.commands.scan.build_file_map", return_value=None),
        patch("graph_wiki_agent.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_agent.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_agent.commands.scan.make_llm"),
        patch("graph_wiki_agent.commands.scan.load_role_config", return_value={"model_id": "fake-model", "max_concurrency": 2}),
        patch("graph_wiki_agent.commands.scan.regenerate_dependencies_index"),
        patch("graph_wiki_agent.commands.scan.update_index"),
        patch("graph_wiki_agent.commands.scan._capture_run", return_value=(0, "", "")),
        patch("graph_wiki_agent.commands.scan.read_only_connect", side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError("test stub")),
        patch("graph_wiki_agent.commands.scan.append_log", side_effect=_mock_append_log),
    ):
        mock_pool_instance = AsyncMock()
        mock_pool_instance.run_all = AsyncMock(return_value=fan_result)
        MockPool.return_value = mock_pool_instance

        await run_scan(workspace_path=wiki)

    page_text = old_page.read_text(encoding="utf-8")
    assert "stale: true" in page_text, f"Expected 'stale: true' in page, got:\n{page_text}"

    stale_calls = [t for t in append_log_calls if "marked stale" in t[1] and "old-pkg" in t[1]]
    assert stale_calls, f"Expected append_log call mentioning 'marked stale: old-pkg', got: {append_log_calls}"


# ---------------------------------------------------------------------------
# Test 6: fan-out errors surface in ScanResult.errors
# ---------------------------------------------------------------------------


async def test_fanout_errors_surface_in_result_errors(tmp_path: Path) -> None:
    """FanOutResult errors are surfaced in ScanResult.errors list."""
    from graph_wiki_agent.commands.scan import run_scan
    from subagent_runtime.pool import PerItemError

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    (wiki / "packages").mkdir()

    fake_pkg_ok = {
        "name": "good-pkg",
        "path": "packages/good-pkg",
        "wiki_relative_path": "packages/good-pkg/good-pkg.md",
        "type": "library",
        "language": "python",
        "changed_files": None,
    }
    fake_pkg_err = {
        "name": "bad-pkg",
        "path": "packages/bad-pkg",
        "wiki_relative_path": "packages/bad-pkg/bad-pkg.md",
        "type": "library",
        "language": "python",
        "changed_files": None,
    }

    fan_result = _make_fan_out_result(
        successes=[(fake_pkg_ok, "stub body for good-pkg")],
        errors=[PerItemError(item=fake_pkg_err, exception=RuntimeError("Bedrock timeout"))],
    )

    fake_diff = {
        "new": ["good-pkg", "bad-pkg"],
        "unchanged": [],
        "deleted": [],
        "renamed": [],
    }

    with (
        patch("graph_wiki_agent.commands.scan.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_agent.commands.scan.read_layout", return_value={}),
        patch("graph_wiki_agent.commands.scan.discover_workspaces", return_value=[fake_pkg_ok, fake_pkg_err]),
        patch("graph_wiki_agent.commands.scan._load_existing_pages", return_value={}),
        patch("graph_wiki_agent.commands.scan.attach_changed_files"),
        patch("graph_wiki_agent.commands.scan.compute_diff", return_value=fake_diff),
        patch("graph_wiki_agent.commands.scan.compute_state_gate", return_value={"allowed": True, "reason": "", "head_commit": "x"}),
        patch("graph_wiki_agent.commands.scan.build_file_map", return_value=None),
        patch("graph_wiki_agent.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_agent.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_agent.commands.scan.make_llm"),
        patch("graph_wiki_agent.commands.scan.load_role_config", return_value={"model_id": "fake-model", "max_concurrency": 2}),
        patch("graph_wiki_agent.commands.scan.regenerate_dependencies_index"),
        patch("graph_wiki_agent.commands.scan.update_index"),
        patch("graph_wiki_agent.commands.scan._capture_run", return_value=(0, "", "")),
        patch("graph_wiki_agent.commands.scan.read_only_connect", side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError("test stub")),
        patch("graph_wiki_agent.commands.scan.append_log"),
    ):
        mock_pool_instance = AsyncMock()
        mock_pool_instance.run_all = AsyncMock(return_value=fan_result)
        MockPool.return_value = mock_pool_instance

        result = await run_scan(workspace_path=wiki)

    assert len(result.errors) == 1, f"Expected 1 error in result.errors, got {result.errors}"
    assert "bad-pkg" in result.errors[0]


# ---------------------------------------------------------------------------
# run_scan repo_path override (Plan 06-15 / UAT G5)
# ---------------------------------------------------------------------------


async def test_run_scan_repo_path_overrides_cwd(tmp_path: Path) -> None:
    """When repo_path is passed, discover_workspaces is called with it,
    NOT Path.cwd() and NOT whatever resolve_wiki_and_repo returns."""
    from graph_wiki_agent.commands.scan import run_scan

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    fake_repo = tmp_path / "fake-monorepo"
    fake_repo.mkdir()

    with (
        patch("graph_wiki_agent.commands.scan.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.scan.read_layout", return_value={}),
        patch("graph_wiki_agent.commands.scan.discover_workspaces") as mock_discover,
        patch("graph_wiki_agent.commands.scan._load_existing_pages", return_value={}),
        patch("graph_wiki_agent.commands.scan.attach_changed_files") as mock_attach,
        patch("graph_wiki_agent.commands.scan.compute_diff") as mock_diff,
        patch("graph_wiki_agent.commands.scan.compute_state_gate") as mock_gate,
        patch("graph_wiki_agent.commands.scan.build_file_map", return_value=None),
        patch("graph_wiki_agent.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_agent.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_agent.commands.scan.make_llm"),
        patch(
            "graph_wiki_agent.commands.scan.load_role_config",
            return_value={"model_id": "fake-model", "max_concurrency": 2},
        ),
        patch("graph_wiki_agent.commands.scan.regenerate_dependencies_index"),
        patch("graph_wiki_agent.commands.scan.update_index"),
        patch("graph_wiki_agent.commands.scan._capture_run", return_value=(0, "", "")),
        patch("graph_wiki_agent.commands.scan.read_only_connect", side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError("test stub")),
        patch("graph_wiki_agent.commands.scan.append_log"),
    ):
        mock_resolve.return_value = (wiki, None)  # repo=None forces fallback
        mock_discover.return_value = []
        mock_gate.return_value = {"allowed": False, "reason": "test", "head_commit": "abc"}
        mock_diff.return_value = {"new": [], "renamed": [], "deleted": [], "unchanged": []}
        mock_pool_instance = AsyncMock()
        mock_pool_instance.run_all = AsyncMock(return_value=_make_fan_out_result())
        MockPool.return_value = mock_pool_instance

        await run_scan(workspace_path=wiki, repo_path=fake_repo)

    # discover_workspaces called with fake_repo.resolve(), NOT Path.cwd()
    call_args = mock_discover.call_args
    passed_repo = (
        call_args.args[0]
        if call_args.args
        else call_args.kwargs.get("repo") or call_args.kwargs.get("root")
    )
    assert passed_repo == fake_repo.resolve(), (
        f"discover_workspaces expected to receive fake_repo={fake_repo.resolve()}, "
        f"got {passed_repo}"
    )
    # compute_state_gate also got fake_repo, not cwd
    assert mock_gate.call_args.args[0] == fake_repo.resolve()
    # attach_changed_files also got fake_repo as the repo arg (3rd positional)
    assert mock_attach.call_args.args[2] == fake_repo.resolve()
    # discover_workspaces called with pinned_containers=None — the vault's
    # layout block describes the ORIGINAL monorepo, not the override repo,
    # so the override must skip the layout read and use unpinned discovery
    discover_kwargs = mock_discover.call_args.kwargs
    assert discover_kwargs.get("pinned_containers") is None, (
        f"discover_workspaces expected pinned_containers=None when repo_path "
        f"override is supplied, got {discover_kwargs.get('pinned_containers')!r}"
    )
