"""Unit tests for the scan command (Plan 05-04).

Requirements covered: CMD-02, MCP-03. Post-flip, the four prose fan-outs
(narrator / code_reader / synthesizer / package_reader) are ONE
``role == "prose_refresher"`` dispatch whose items are ProseRefreshTasks.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

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
        patch("graph_wiki_core.commands.scan_bedrock.SubagentPool") as MockPool,
        patch("graph_wiki_core.commands.scan_bedrock.make_llm"),
        patch(
            "graph_wiki_core.commands.scan_bedrock.load_role_config",
            return_value={"model_id": "fake-model", "max_concurrency": 2},
        ),
        patch("graph_wiki_core.commands.scan.update_index"),
        patch("graph_wiki_core.commands.scan._cg_run_build", return_value=(0, "", "")) as mock_build,
        patch(
            "graph_wiki_core.commands.scan.open_reader",
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


def test_run_scan_no_narrate_does_not_run_prose_refresh(monkeypatch, tmp_path: Path) -> None:
    import asyncio

    import graph_wiki_core.commands.scan as scan_mod
    from graph_io import exit_codes
    from graph_io.store import GraphNotInitializedError
    from graph_wiki_core.commands import scan_bedrock as scan_bedrock_mod

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
        "open_reader",
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
    assert hasattr(scan_bedrock_mod, "run_prose_refresh")

    def explode_prose_refresh(*args, **kwargs):
        raise AssertionError("prose_refresher must not run when narrate=False")

    monkeypatch.setattr(scan_bedrock_mod, "run_prose_refresh", explode_prose_refresh)

    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=False))


# ---------------------------------------------------------------------------
# Provider fan-out: ProseRefreshTask shape (entity_root / graph_path routing)
# ---------------------------------------------------------------------------


def _awaiting_fake_pool():
    """FakePool whose run_all actually awaits task(item) — so the provider's
    refresh coroutine (and the patched run_prose_refresh) runs."""

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

            if role != "prose_refresher":
                return _Result(successes=[], errors=[])
            successes = []
            for item in items:
                task_result = await task(item)
                payload = getattr(task_result, "value", task_result)
                successes.append((item, payload))
            return _Result(successes=successes, errors=[])

    return _FakePool, _FakeTaskResult


async def _run_scan_capturing_tasks(monkeypatch, tmp_path: Path, *, node_path: str, uri: str) -> list:
    """Drive run_scan over one faked package node; return the ProseRefreshTasks
    handed to run_prose_refresh."""
    from types import SimpleNamespace

    import graph_wiki_core.commands.scan as scan_mod
    from graph_wiki_core.commands import scan_bedrock as scan_bedrock_mod
    from graph_wiki_core.commands.scan_contract import ProseRefreshResult

    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    wiki.mkdir(parents=True)
    repo.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    node = SimpleNamespace(
        name="pkg-a",
        path=node_path,
        kind="package",
        attrs={"uri": uri, "language": "python"},
    )
    captured_tasks: list = []

    class _FakeConn:
        def close(self) -> None:
            return None

        def list_test_suites(self):
            return []

    fake_pool_cls, fake_task_result = _awaiting_fake_pool()

    async def fake_run_prose_refresh(*, llm, task, repo, wiki, graph_tools):
        captured_tasks.append(task)
        return ProseRefreshResult(uri=task.uri, sections={"## Narrative": "Narrated prose."})

    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(scan_mod, "_cg_run_build", lambda repo, ws, *, full, scope_to_repo=True: (0, "", ""))
    # The split contract opens its own read-only conn (DB-existence guarded), so a
    # placeholder code.db must exist for the FakeConn to be used.
    from workspace_io.paths import graph_dir as _graph_dir

    (_graph_dir(workspace)).mkdir(parents=True, exist_ok=True)
    (_graph_dir(workspace) / "code.db").write_bytes(b"")
    monkeypatch.setattr(scan_mod, "open_reader", lambda path: _FakeConn())
    monkeypatch.setattr(scan_bedrock_mod, "open_reader", lambda path: _FakeConn())
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "abc"},
    )

    def _fake_write_entities(conn, wiki, admitted_kinds):
        # The contract builds its worklist from on-disk entity pages, so
        # write_entities must leave a real (placeholder) page behind.
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
    monkeypatch.setattr(scan_mod, "build_file_map", lambda *args, **kwargs: None)
    monkeypatch.setattr(scan_bedrock_mod, "build_graph_tools", lambda reader: [])
    monkeypatch.setattr(scan_bedrock_mod, "run_prose_refresh", fake_run_prose_refresh)
    monkeypatch.setattr(scan_mod, "_drift_clear_pass", lambda wiki: None)
    monkeypatch.setattr(scan_mod, "update_index", lambda wiki: None)
    monkeypatch.setattr(
        scan_mod,
        "generate_index",
        lambda conn, wiki, display_name: SimpleNamespace(changed=False, bytes_written=0),
    )
    monkeypatch.setattr(scan_mod, "regenerate_referenced_in_wiki", lambda wiki: [])
    monkeypatch.setattr(scan_mod, "regen_indexes_and_backlinks", lambda wiki: None)
    monkeypatch.setattr(scan_mod, "append_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        scan_bedrock_mod,
        "_bedrock_stack",
        lambda: (
            lambda role: {"model_id": "fake-model", "max_concurrency": 1},
            lambda role, model_override=None: object(),
            fake_pool_cls,
            fake_task_result,
        ),
    )

    await scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)
    return captured_tasks


async def test_run_scan_passes_node_path_to_prose_refresh_task(monkeypatch, tmp_path: Path) -> None:
    uri = "pkg:org/repo/pkg-a"
    tasks = await _run_scan_capturing_tasks(monkeypatch, tmp_path, node_path="packages/pkg-a", uri=uri)
    task = next(t for t in tasks if t.uri == uri)
    assert task.graph_path == "packages/pkg-a"
    assert task.entity_root == "packages/pkg-a"
    assert task.trigger == "first_fill"
    assert "## Narrative" in task.prose_sections


async def test_run_scan_passes_root_path_sentinel_to_prose_refresh_task(monkeypatch, tmp_path: Path) -> None:
    """A root-path package (node.path == "") keeps the empty-string sentinel as
    graph_path/entity_root (tool-rooting at the repo root)."""
    uri = "pkg:org/repo/root"
    tasks = await _run_scan_capturing_tasks(monkeypatch, tmp_path, node_path="", uri=uri)
    task = next(t for t in tasks if t.uri == uri)
    assert task.graph_path == ""
    assert task.entity_root == ""


def test_prose_refresher_errors_join_scan_result(monkeypatch, tmp_path: Path) -> None:
    import asyncio
    import sqlite3

    import graph_wiki_core.commands.scan as scan_mod
    from graph_io import exit_codes, schema
    from graph_wiki_core.commands import scan_bedrock as scan_bedrock_mod
    from graph_wiki_core.commands.scan_contract import ProseRefreshResult
    from subagent_runtime.pool import SubagentPool as _SubagentPool
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
        if role == "prose_refresher":
            result.successes = [(t, ProseRefreshResult(uri=t.uri, error="invalid JSON")) for t in items]
        elif role == "drift_judge":
            result.successes = [(it, {"stale": False, "reason": ""}) for it in items]
        return result

    monkeypatch.setattr(_SubagentPool, "run_all", fake_run_all)
    monkeypatch.setattr(scan_bedrock_mod, "make_llm", lambda role, *, model_override=None: object())

    result = asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    assert result.entity_errors == [
        "pkg:org/repo/pkg-a: invalid JSON",
        "repo:org/repo: invalid JSON",
    ]
