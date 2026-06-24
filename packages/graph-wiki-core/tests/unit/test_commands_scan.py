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

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

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
    fake_fan_result = _make_fan_out_result(successes=[(fake_workspaces[0], "# Brand New Pkg\n\nA stub body.")])

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
        patch(
            "graph_wiki_core.commands.scan.load_role_config",
            return_value={"model_id": "fake-model", "max_concurrency": 2},
        ),
        patch("graph_wiki_core.commands.scan.update_index"),
        patch("graph_wiki_core.commands.scan._cg_run_build", return_value=(0, "", "")),
        patch(
            "graph_wiki_core.commands.scan.read_only_connect",
            side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError(
                "test stub"
            ),
        ),
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
    fake_fan_result = _make_fan_out_result(successes=[(fake_pkg, "stub body")])

    with (
        patch("graph_wiki_core.commands.scan.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_core.commands.scan.read_layout", return_value={}),
        patch("graph_wiki_core.commands.scan.discover_workspaces", return_value=[fake_pkg]),
        patch("graph_wiki_core.commands.scan._load_existing_pages", return_value={}),
        patch("graph_wiki_core.commands.scan.attach_changed_files"),
        patch("graph_wiki_core.commands.scan.compute_diff", return_value=fake_diff),
        patch(
            "graph_wiki_core.commands.scan.compute_state_gate",
            return_value={"allowed": True, "reason": "", "head_commit": "x"},
        ),
        patch("graph_wiki_core.commands.scan.build_file_map", return_value=None),
        patch("graph_wiki_core.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_core.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_core.commands.scan.make_llm"),
        patch(
            "graph_wiki_core.commands.scan.load_role_config",
            return_value={"model_id": "fake-model", "max_concurrency": 2},
        ),
        patch("graph_wiki_core.commands.scan.update_index"),
        patch("graph_wiki_core.commands.scan._cg_run_build", return_value=(0, "", "")),
        patch(
            "graph_wiki_core.commands.scan.read_only_connect",
            side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError(
                "test stub"
            ),
        ),
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
    fan_result = _make_fan_out_result(successes=[(fake_pkg, llm_body)])

    with (
        patch("graph_wiki_core.commands.scan.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_core.commands.scan.read_layout", return_value={}),
        patch("graph_wiki_core.commands.scan.discover_workspaces", return_value=[fake_pkg]),
        patch("graph_wiki_core.commands.scan._load_existing_pages", return_value={}),
        patch("graph_wiki_core.commands.scan.attach_changed_files"),
        patch("graph_wiki_core.commands.scan.compute_diff", return_value=fake_diff),
        patch(
            "graph_wiki_core.commands.scan.compute_state_gate",
            return_value={"allowed": True, "reason": "", "head_commit": "x"},
        ),
        patch("graph_wiki_core.commands.scan.build_file_map", return_value=fake_file_map),
        patch("graph_wiki_core.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_core.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_core.commands.scan.make_llm"),
        patch(
            "graph_wiki_core.commands.scan.load_role_config",
            return_value={"model_id": "fake-model", "max_concurrency": 2},
        ),
        patch("graph_wiki_core.commands.scan.update_index"),
        patch("graph_wiki_core.commands.scan._cg_run_build", return_value=(0, "", "")),
        patch(
            "graph_wiki_core.commands.scan.read_only_connect",
            side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError(
                "test stub"
            ),
        ),
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
        patch(
            "graph_wiki_core.commands.scan.compute_state_gate",
            return_value={"allowed": True, "reason": "", "head_commit": "x"},
        ),
        patch("graph_wiki_core.commands.scan.build_file_map", return_value=None),
        patch("graph_wiki_core.commands.scan.pick_representative", return_value=[]),
        patch("graph_wiki_core.commands.scan.SubagentPool") as MockPool,
        patch("graph_wiki_core.commands.scan.make_llm"),
        patch(
            "graph_wiki_core.commands.scan.load_role_config",
            return_value={"model_id": "fake-model", "max_concurrency": 2},
        ),
        patch("graph_wiki_core.commands.scan.update_index"),
        patch("graph_wiki_core.commands.scan._cg_run_build", return_value=(0, "", "")),
        patch(
            "graph_wiki_core.commands.scan.read_only_connect",
            side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError(
                "test stub"
            ),
        ),
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
        patch(
            "graph_wiki_core.commands.scan.read_only_connect",
            side_effect=__import__("graph_io.store", fromlist=["GraphNotInitializedError"]).GraphNotInitializedError(
                "test stub"
            ),
        ),
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


def test_run_scan_no_narrate_does_not_call_package_reader(monkeypatch, tmp_path: Path) -> None:
    import asyncio

    import graph_wiki_core.commands.scan as scan_mod
    from graph_io import exit_codes
    from graph_io.store import GraphNotInitializedError

    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    wiki.mkdir(parents=True)
    repo.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(
        scan_mod, "_cg_run_build", lambda repo, ws, *, full, scope_to_repo=True: (exit_codes.SUCCESS, "", "")
    )
    monkeypatch.setattr(
        scan_mod,
        "read_only_connect",
        lambda path: (_ for _ in ()).throw(GraphNotInitializedError("no db")),
    )
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "abc"},
    )
    monkeypatch.setattr(scan_mod, "update_index", lambda wiki: None)
    monkeypatch.setattr(scan_mod, "generate_index", lambda wiki, conn: None)
    monkeypatch.setattr(scan_mod, "regenerate_referenced_in_wiki", lambda wiki: None)
    monkeypatch.setattr(scan_mod, "append_log", lambda *args, **kwargs: None)
    assert hasattr(scan_mod, "_run_package_reader_pass")

    def explode_package_reader(*args, **kwargs):
        raise AssertionError("package_reader must not run when narrate=False")

    monkeypatch.setattr(scan_mod, "_run_package_reader_pass", explode_package_reader)

    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=False))


async def test_run_package_reader_pass_keeps_page_load_errors_best_effort(monkeypatch, tmp_path: Path) -> None:
    import graph_wiki_core.commands.scan as scan_mod

    wiki = tmp_path / "workspace" / "wiki"
    repo = tmp_path / "workspace" / "repo"
    wiki.mkdir(parents=True)
    repo.mkdir()

    missing_page = wiki / "entities" / "missing.md"
    valid_page = wiki / "entities" / "valid.md"
    valid_page.parent.mkdir(parents=True, exist_ok=True)
    valid_page.write_text(
        "---\nkind: package\nuri: package:valid\ntitle: Valid Package\n---\n\n## Narrative\nAlready filled prose.\n",
        encoding="utf-8",
    )
    seen_paths: list[Path] = []
    real_frontmatter_load = scan_mod.frontmatter.load

    def tracking_frontmatter_load(path):
        seen_paths.append(Path(path))
        return real_frontmatter_load(path)

    class _UnusedPool:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("pool should not be constructed when there are no valid TODO items")

    monkeypatch.setattr(scan_mod.frontmatter, "load", tracking_frontmatter_load)
    monkeypatch.setattr(
        scan_mod,
        "_bedrock_stack",
        lambda: (
            lambda role: {"model_id": "fake-model", "max_concurrency": 1},
            lambda role, model_override=None: object(),
            _UnusedPool,
            object,
        ),
    )

    filled, errors = await scan_mod._run_package_reader_pass(
        wiki=wiki,
        repo=repo,
        conn=None,
        model_override=None,
        candidate_pages={
            "package:missing": scan_mod._PackageReaderCandidate(page_path=missing_page),
            "package:valid": scan_mod._PackageReaderCandidate(page_path=valid_page),
        },
    )

    assert filled == set()
    assert seen_paths == [missing_page, valid_page]
    assert errors == [
        "package:missing: package_reader page load failed: FileNotFoundError(2, 'No such file or directory')"
    ]


async def test_run_package_reader_pass_uses_graph_path_for_entity_root(monkeypatch, tmp_path: Path) -> None:
    import graph_wiki_core.commands.scan as scan_mod
    from graph_wiki_core.commands.package_reader import PackageReaderResult

    wiki = tmp_path / "workspace" / "wiki"
    repo = tmp_path / "workspace" / "repo"
    wiki.mkdir(parents=True)
    repo.mkdir()

    page = wiki / "entities" / "pkg-a.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "---\n"
        "kind: package\n"
        "uri: pkg:org/repo/pkg-a\n"
        "title: pkg-a\n"
        "language: python\n"
        "---\n\n"
        "# pkg-a\n\n"
        "## Purpose\n"
        "> TODO: explain why this package exists.\n\n"
        "## Narrative\n"
        "Scanner prose.\n",
        encoding="utf-8",
    )
    captured_entity_roots: list[str] = []

    async def fake_run_package_reader(*, llm, item, repo, wiki, graph_tools):
        captured_entity_roots.append(item.entity_root)
        return PackageReaderResult(
            status="ok",
            replacements={"Purpose": "Owns package-level scan orchestration."},
            error=None,
        )

    class _FakeTaskResult:
        def __init__(self, value, response) -> None:
            self.value = value
            self.response = response

    class _FakePool:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def run_all(self, *, items, task, role, model_id, max_concurrency):
            class _Result:
                def __init__(self, successes, errors) -> None:
                    self.successes = successes
                    self.errors = errors

            successes = []
            for item in items:
                task_result = await task(item)
                payload = getattr(task_result, "value", task_result)
                successes.append((item, payload))
            return _Result(successes=successes, errors=[])

    monkeypatch.setattr(scan_mod, "run_package_reader", fake_run_package_reader)
    monkeypatch.setattr(
        scan_mod,
        "_bedrock_stack",
        lambda: (
            lambda role: {"model_id": "fake-model", "max_concurrency": 1},
            lambda role, model_override=None: object(),
            _FakePool,
            _FakeTaskResult,
        ),
    )

    filled, errors = await scan_mod._run_package_reader_pass(
        wiki=wiki,
        repo=repo,
        conn=None,
        model_override=None,
        candidate_pages={
            "pkg:org/repo/pkg-a": scan_mod._PackageReaderCandidate(
                page_path=page,
                graph_path="packages/pkg-a",
                kind="package",
                name="pkg-a",
                language="python",
            )
        },
    )

    assert captured_entity_roots == ["packages/pkg-a"]
    assert filled == {"pkg:org/repo/pkg-a"}
    assert errors == []
    assert "## Purpose\nOwns package-level scan orchestration.\n" in page.read_text(encoding="utf-8")


async def test_run_package_reader_pass_requires_candidate_graph_path(monkeypatch, tmp_path: Path) -> None:
    import graph_wiki_core.commands.scan as scan_mod

    wiki = tmp_path / "workspace" / "wiki"
    repo = tmp_path / "workspace" / "repo"
    wiki.mkdir(parents=True)
    repo.mkdir()

    page = wiki / "entities" / "pkg-a.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "---\n"
        "kind: package\n"
        "uri: pkg:org/repo/pkg-a\n"
        "path: wiki/entities/wrong.md\n"
        "graph_path: wrong/frontmatter/value\n"
        "---\n\n"
        "# pkg-a\n\n"
        "## Purpose\n"
        "> TODO: explain why this package exists.\n\n"
        "## Narrative\n"
        "Scanner prose.\n",
        encoding="utf-8",
    )

    class _UnusedPool:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("pool should not be constructed when candidate graph_path is missing")

    monkeypatch.setattr(
        scan_mod,
        "_bedrock_stack",
        lambda: (
            lambda role: {"model_id": "fake-model", "max_concurrency": 1},
            lambda role, model_override=None: object(),
            _UnusedPool,
            object,
        ),
    )

    filled, errors = await scan_mod._run_package_reader_pass(
        wiki=wiki,
        repo=repo,
        conn=None,
        model_override=None,
        candidate_pages={
            "pkg:org/repo/pkg-a": scan_mod._PackageReaderCandidate(page_path=page),
        },
    )

    assert filled == set()
    assert errors == ["pkg:org/repo/pkg-a: package_reader missing graph path"]


async def test_run_scan_passes_node_path_to_package_reader_candidates(monkeypatch, tmp_path: Path) -> None:
    from types import SimpleNamespace

    import graph_wiki_core.commands.scan as scan_mod

    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    wiki.mkdir(parents=True)
    repo.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    uri = "pkg:org/repo/pkg-a"
    node = SimpleNamespace(
        name="pkg-a",
        path="packages/pkg-a",
        kind="package",
        attrs={"uri": uri, "language": "python"},
    )
    captured_candidates: dict[str, object] = {}

    class _FakeConn:
        def close(self) -> None:
            return None

    class _FakePool:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def run_all(self, *, items, task, role, model_id, max_concurrency):
            class _Result:
                def __init__(self, successes, errors) -> None:
                    self.successes = successes
                    self.errors = errors

            if role == "narrator":
                return _Result(successes=[(items[0], "Narrated prose.")], errors=[])
            raise AssertionError(f"unexpected role: {role}")

    class _FakeTaskResult:
        def __init__(self, value, response) -> None:
            self.value = value
            self.response = response

    def fake_inject_narrative(page_path: Path, prose: str) -> None:
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(
            "---\n"
            f"uri: {uri}\n"
            "kind: package\n"
            "path: wiki/entities/wrong.md\n"
            "graph_path: wrong/frontmatter/value\n"
            "---\n\n"
            "# pkg-a\n\n"
            "## Purpose\n"
            "> TODO: explain why this package exists.\n\n"
            "## Narrative\n"
            f"{prose}\n",
            encoding="utf-8",
        )

    async def fake_package_reader_pass(*, wiki, repo, conn, model_override, candidate_pages):
        captured_candidates.update(candidate_pages)
        return set(), []

    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(scan_mod, "_cg_run_build", lambda repo, ws, *, full, scope_to_repo=True: (0, "", ""))
    # The split contract opens its own read-only conn (DB-existence guarded), so a
    # placeholder code.db must exist for the FakeConn to be used.
    from workspace_io.paths import graph_dir as _graph_dir

    (_graph_dir(workspace)).mkdir(parents=True, exist_ok=True)
    (_graph_dir(workspace) / "code.db").write_bytes(b"")
    monkeypatch.setattr(scan_mod, "read_only_connect", lambda path: _FakeConn())
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "abc"},
    )

    def _fake_write_entities(conn, wiki, admitted_kinds):
        # The contract builds its worklist (and package_reader candidates) from
        # on-disk entity pages, so write_entities must leave a real page behind.
        from wiki_io.entity_writer import short_filename

        page = wiki / "entities" / f"{short_filename(uri, frozenset())}.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            f"---\nuri: {uri}\nkind: package\n---\n\n# pkg-a\n\n"
            "## Purpose\n> TODO: explain why this package exists.\n\n"
            "## Narrative\n_(scanner will populate on next scan)_\n",
            encoding="utf-8",
        )
        return SimpleNamespace(
            created={uri},
            updated=set(),
            deleted=set(),
            needs_narrative={uri},
            errors=[],
        )

    monkeypatch.setattr(scan_mod, "write_entities", _fake_write_entities)
    monkeypatch.setattr(scan_mod, "_commit_dirty_changes", lambda *args, **kwargs: {})
    monkeypatch.setattr(scan_mod, "_kind_list_fns", lambda: {"package": lambda conn: [node]})
    monkeypatch.setattr(scan_mod, "scanner_frontmatter_for_node", lambda conn, kind, node: {"uri": uri, "kind": kind})
    monkeypatch.setattr(scan_mod, "_compute_collision_set", lambda *args, **kwargs: frozenset())
    monkeypatch.setattr(scan_mod, "inject_narrative", fake_inject_narrative)
    monkeypatch.setattr(scan_mod, "build_file_map", lambda *args, **kwargs: None)
    monkeypatch.setattr(scan_mod.queries, "list_test_suites", lambda conn: [])
    monkeypatch.setattr(scan_mod, "_run_package_reader_pass", fake_package_reader_pass)
    monkeypatch.setattr(scan_mod, "_drift_flag_pass", AsyncMock())
    monkeypatch.setattr(scan_mod, "_drift_clear_pass", lambda wiki: None)
    monkeypatch.setattr(scan_mod, "update_index", lambda wiki: None)
    monkeypatch.setattr(
        scan_mod,
        "generate_index",
        lambda conn, wiki, display_name: SimpleNamespace(changed=False, bytes_written=0),
    )
    monkeypatch.setattr(scan_mod, "regenerate_referenced_in_wiki", lambda wiki: [])
    monkeypatch.setattr(scan_mod, "append_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(scan_mod, "file_map_todo_paths", lambda page_path: [])
    monkeypatch.setattr(
        scan_mod,
        "_bedrock_stack",
        lambda: (
            lambda role: {"model_id": "fake-model", "max_concurrency": 1},
            lambda role, model_override=None: object(),
            _FakePool,
            _FakeTaskResult,
        ),
    )

    await scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)

    candidate = captured_candidates[uri]
    assert candidate.graph_path == "packages/pkg-a"


def test_package_reader_errors_join_scan_result(monkeypatch, tmp_path: Path) -> None:
    import asyncio
    import sqlite3

    import graph_wiki_core.commands.scan as scan_mod
    from graph_io import exit_codes, schema
    from workspace_io.paths import graph_dir

    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    wiki.mkdir(parents=True)
    repo.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    graph_path = graph_dir(workspace) / "code.db"
    graph_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(graph_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('repository', 'repo', NULL, NULL, '{\"uri\": \"repo:org/repo\"}', 'repo:org/repo')"
        )
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', 'packages/pkg-a', NULL, '{\"language\":\"python\"}', 'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setattr(
        scan_mod, "_cg_run_build", lambda repo, ws, *, full, scope_to_repo=True: (exit_codes.SUCCESS, "", "")
    )
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "abc"},
    )
    monkeypatch.setattr(scan_mod, "build_file_map", lambda *args, **kwargs: None)

    async def fake_run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "narrator":
            result.successes = [(it, f"PROSE for {it[0]}") for it in items]
        elif role == "drift_judge":
            result.successes = [(it, {"stale": False, "reason": ""}) for it in items]
        return result

    async def fake_package_reader_pass(**kwargs):
        return set(), ["pkg:org/repo/pkg-a: invalid JSON"]

    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", fake_run_all)
    monkeypatch.setattr(scan_mod, "_run_package_reader_pass", fake_package_reader_pass)

    result = asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    assert result.entity_errors == ["pkg:org/repo/pkg-a: invalid JSON"]
