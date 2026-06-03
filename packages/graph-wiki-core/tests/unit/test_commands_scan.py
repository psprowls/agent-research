from __future__ import annotations

"""Unit tests for the scan command (Plan 05-04).

Requirements covered: CMD-02, MCP-03.

Phase 45 note: Several tests in this file validated the legacy scanner
fan-out path (SubagentPool with role='scanner', writes to
wiki/packages/<n>/<n>.md, populating ScanResult.added/updated/errors).
Phase 45 D-08 removes that path as a hard cutover — only entity pages
under wiki/entities/ are written now, the narrator pool replaces the
scanner pool, and the legacy ScanResult fields are always empty lists.
Those tests are skipped with `_PHASE_45_LEGACY_REMOVED`; the v1.8
equivalents live in `tests/integration/test_scan_entity_integration.py`
(Plan 45-03 Task 4).
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_PHASE_45_LEGACY_REMOVED = pytest.mark.skip(
    reason=(
        "Phase 45 D-08: legacy scanner fan-out removed; this test validated "
        "v1.7 behavior (role='scanner' pool, wiki/packages/<n>/<n>.md writes, "
        "result.added/updated/errors population). v1.8 equivalents live in "
        "tests/integration/test_scan_entity_integration.py."
    )
)


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
    """ScanResult has the entity reporting fields with correct types."""
    from graph_wiki_core.commands.scan import ScanResult

    result = ScanResult(
        state_gate={"allowed": True, "reason": "clean", "head_commit": "abc123"},
        entities_created=["pkg:a"],
        entities_updated=["pkg:b"],
        entities_deleted=["pkg:c"],
        entities_narrated=["pkg:a"],
        entity_errors=["pkg:d: some error"],
    )

    assert isinstance(result.state_gate, dict)
    assert isinstance(result.entities_created, list)
    assert isinstance(result.entities_updated, list)
    assert isinstance(result.entities_deleted, list)
    assert isinstance(result.entities_narrated, list)
    assert isinstance(result.entity_errors, list)

    assert result.entities_created == ["pkg:a"]
    assert result.entities_updated == ["pkg:b"]
    assert result.entities_deleted == ["pkg:c"]
    assert result.entities_narrated == ["pkg:a"]
    assert result.entity_errors == ["pkg:d: some error"]
    assert result.state_gate["allowed"] is True


# ---------------------------------------------------------------------------
# Test 2: run_scan returns ScanResult with correct diff keys
# ---------------------------------------------------------------------------


@_PHASE_45_LEGACY_REMOVED
async def test_run_scan_deterministic_diff_keys(tmp_path: Path) -> None:
    """run_scan maps compute_diff keys correctly to ScanResult fields."""
    from graph_wiki_core.commands.scan import run_scan

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
        patch("graph_wiki_core.commands.scan.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_core.commands.scan.read_layout", return_value={}),
        patch("graph_wiki_core.commands.scan.discover_workspaces", return_value=fake_workspaces),
        patch("graph_wiki_core.commands.scan._load_existing_pages", return_value={}),
        patch("graph_wiki_core.commands.scan.attach_changed_files"),
        patch("graph_wiki_core.commands.scan.compute_diff", return_value=fake_diff),
        patch("graph_wiki_core.commands.scan.compute_state_gate", return_value=fake_state_gate),
        patch("graph_wiki_core.commands.scan.build_file_map", return_value="## File map - brand-new-pkg\nTODO\n"),
        patch("graph_wiki_core.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_core.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_core.commands.scan.make_llm"),
        patch("graph_wiki_core.commands.scan.load_role_config", return_value={"model_id": "fake-model", "max_concurrency": 2}),
        patch("graph_wiki_core.commands.scan.update_index"),
        patch("graph_wiki_core.commands.scan._cg_run_build", return_value=(0, "", "")),
        patch("graph_wiki_core.commands.scan.read_only_connect", side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError("test stub")),
        patch("graph_wiki_core.commands.scan.append_log"),
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


@_PHASE_45_LEGACY_REMOVED
async def test_scanner_fanout_called_with_role_scanner(tmp_path: Path) -> None:
    """SubagentPool.run_all is called with role='scanner'."""
    from graph_wiki_core.commands.scan import run_scan

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
        patch("graph_wiki_core.commands.scan.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_core.commands.scan.read_layout", return_value={}),
        patch("graph_wiki_core.commands.scan.discover_workspaces", return_value=[fake_pkg]),
        patch("graph_wiki_core.commands.scan._load_existing_pages", return_value={}),
        patch("graph_wiki_core.commands.scan.attach_changed_files"),
        patch("graph_wiki_core.commands.scan.compute_diff", return_value=fake_diff),
        patch("graph_wiki_core.commands.scan.compute_state_gate", return_value={"allowed": True, "reason": "", "head_commit": "x"}),
        patch("graph_wiki_core.commands.scan.build_file_map", return_value=None),
        patch("graph_wiki_core.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_core.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_core.commands.scan.make_llm"),
        patch("graph_wiki_core.commands.scan.load_role_config", return_value={"model_id": "fake-model", "max_concurrency": 2}),
        patch("graph_wiki_core.commands.scan.update_index"),
        patch("graph_wiki_core.commands.scan._cg_run_build", return_value=(0, "", "")),
        patch("graph_wiki_core.commands.scan.read_only_connect", side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError("test stub")),
        patch("graph_wiki_core.commands.scan.append_log"),
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


@_PHASE_45_LEGACY_REMOVED
async def test_file_map_appended_after_llm(tmp_path: Path) -> None:
    """Final stub page contains file map text AFTER the LLM body."""
    from graph_wiki_core.commands.scan import run_scan

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
        patch("graph_wiki_core.commands.scan.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_core.commands.scan.read_layout", return_value={}),
        patch("graph_wiki_core.commands.scan.discover_workspaces", return_value=[fake_pkg]),
        patch("graph_wiki_core.commands.scan._load_existing_pages", return_value={}),
        patch("graph_wiki_core.commands.scan.attach_changed_files"),
        patch("graph_wiki_core.commands.scan.compute_diff", return_value=fake_diff),
        patch("graph_wiki_core.commands.scan.compute_state_gate", return_value={"allowed": True, "reason": "", "head_commit": "x"}),
        patch("graph_wiki_core.commands.scan.build_file_map", return_value=fake_file_map),
        patch("graph_wiki_core.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_core.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_core.commands.scan.make_llm"),
        patch("graph_wiki_core.commands.scan.load_role_config", return_value={"model_id": "fake-model", "max_concurrency": 2}),
        patch("graph_wiki_core.commands.scan.update_index"),
        patch("graph_wiki_core.commands.scan._cg_run_build", return_value=(0, "", "")),
        patch("graph_wiki_core.commands.scan.read_only_connect", side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError("test stub")),
        patch("graph_wiki_core.commands.scan.append_log"),
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
# Test 6: fan-out errors surface in ScanResult.errors
# ---------------------------------------------------------------------------


@_PHASE_45_LEGACY_REMOVED
async def test_fanout_errors_surface_in_result_errors(tmp_path: Path) -> None:
    """FanOutResult errors are surfaced in ScanResult.errors list."""
    from graph_wiki_core.commands.scan import run_scan
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
        patch("graph_wiki_core.commands.scan.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_core.commands.scan.read_layout", return_value={}),
        patch("graph_wiki_core.commands.scan.discover_workspaces", return_value=[fake_pkg_ok, fake_pkg_err]),
        patch("graph_wiki_core.commands.scan._load_existing_pages", return_value={}),
        patch("graph_wiki_core.commands.scan.attach_changed_files"),
        patch("graph_wiki_core.commands.scan.compute_diff", return_value=fake_diff),
        patch("graph_wiki_core.commands.scan.compute_state_gate", return_value={"allowed": True, "reason": "", "head_commit": "x"}),
        patch("graph_wiki_core.commands.scan.build_file_map", return_value=None),
        patch("graph_wiki_core.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_core.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_core.commands.scan.make_llm"),
        patch("graph_wiki_core.commands.scan.load_role_config", return_value={"model_id": "fake-model", "max_concurrency": 2}),
        patch("graph_wiki_core.commands.scan.update_index"),
        patch("graph_wiki_core.commands.scan._cg_run_build", return_value=(0, "", "")),
        patch("graph_wiki_core.commands.scan.read_only_connect", side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError("test stub")),
        patch("graph_wiki_core.commands.scan.append_log"),
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
    """When repo_path is passed, it flows to compute_state_gate and the graph
    build, NOT Path.cwd() and NOT whatever resolve_wiki_and_repo returns."""
    from graph_wiki_core.commands.scan import run_scan

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    fake_repo = tmp_path / "fake-monorepo"
    fake_repo.mkdir()

    with (
        patch("graph_wiki_core.commands.scan.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.scan.compute_state_gate") as mock_gate,
        patch("graph_wiki_core.commands.scan.build_file_map", return_value=None),
        patch("graph_wiki_core.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_core.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_core.commands.scan.make_llm"),
        patch(
            "graph_wiki_core.commands.scan.load_role_config",
            return_value={"model_id": "fake-model", "max_concurrency": 2},
        ),
        patch("graph_wiki_core.commands.scan.update_index"),
        patch("graph_wiki_core.commands.scan._cg_run_build", return_value=(0, "", "")) as mock_build,
        patch("graph_wiki_core.commands.scan.read_only_connect", side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError("test stub")),
        patch("graph_wiki_core.commands.scan.append_log"),
    ):
        mock_resolve.return_value = (wiki, None)  # repo=None forces fallback
        mock_gate.return_value = {"allowed": False, "reason": "test", "head_commit": "abc"}
        mock_pool_instance = AsyncMock()
        mock_pool_instance.run_all = AsyncMock(return_value=_make_fan_out_result())
        MockPool.return_value = mock_pool_instance

        await run_scan(workspace_path=wiki, repo_path=fake_repo)

    # compute_state_gate got fake_repo, not cwd
    assert mock_gate.call_args.args[0] == fake_repo.resolve()
    # the graph build's repo argument (1st positional) is the override repo
    assert mock_build.call_args.args[0] == fake_repo.resolve()
