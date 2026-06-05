"""Living Wiki M2c #4: commit-gated File-map row re-description for test_suite
entities (package/app parity)."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter as _fm
import graph_wiki_core.commands.scan as scan_mod
import pytest
from graph_io import exit_codes
from wiki_io.entity_writer import EntityWriteResult

_SUITE = "test_suite:org/repo/pkg-a/tests"

# A suite file map with TWO rows (keyed suite-root-relative).
_SUITE_MAP_TWO_ROWS = (
    "## File map - unit_tests_pkg-a\nTODO\n\n### tests/\nTODO\n\n"
    "| Path | Kind | Description |\n|---|---|---|\n"
    "| `test_mod.py` | file | — TODO |\n"
    "| `test_util.py` | file | — TODO |\n"
)


def _seed_one_suite(db_path: Path) -> None:
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('test_suite', 'pkg-a-unit-tests', 'packages/pkg-a/tests', NULL, "
            "'{\"suite_kind\": \"unit\", \"path\": \"packages/pkg-a/tests\", "
            "\"owner_kind\": \"package\"}', 'test_suite:org/repo/pkg-a/tests')"
        )
        conn.commit()
    finally:
        conn.close()


def _fanout_spy(*, prose, descs):
    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "narrator":
            result.successes = [(it, prose(it)) for it in items]
        else:  # code_reader — item == (uri, ws_dict, page_path, todo_paths)
            result.successes = [(it, json.dumps(descs(it))) for it in items]
        return result

    return _run_all


def _descs_tagged(tag: dict):
    def _f(item) -> dict[str, str]:
        return {p: f"{tag['v']}:{p}" for p in item[3]}

    return _f


@pytest.fixture
def suite_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n")
    (wiki / "log.md").write_text("", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_one_suite(workspace / ".graph-wiki" / "code.db")
    monkeypatch.setattr(
        scan_mod, "_cg_run_build",
        lambda repo, ws, *, full: (exit_codes.SUCCESS, "", ""),
    )
    monkeypatch.setattr(
        scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock()
    )
    # Step 10b-ts uses build_dir_file_map for suites (not build_file_map).
    monkeypatch.setattr(
        scan_mod, "build_dir_file_map",
        lambda path, **kw: (
            _SUITE_MAP_TWO_ROWS if str(path).endswith("tests") else None
        ),
    )
    return workspace


def _page(wiki: Path, uri: str = _SUITE) -> Path:
    return next(
        p for p in (wiki / "entities").glob("*.md")
        if _fm.load(p).metadata.get("uri") == uri
    )


def test_suite_redescribe_on_change(suite_workspace, monkeypatch) -> None:
    """[spec test 1] A changed file under the suite root re-describes that row;
    unchanged suite rows keep their prior descriptions."""
    workspace = suite_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    desc_tag = {"v": "D1"}
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged(desc_tag)),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t1 = _page(wiki).read_text(encoding="utf-8")
    assert "D1:test_mod.py" in t1
    assert "D1:test_util.py" in t1

    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/tests/test_mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D2:test_mod.py" in t2        # changed row re-described
    assert "D1:test_mod.py" not in t2
    assert "D1:test_util.py" in t2       # unchanged row preserved
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head2"


def test_suite_trigger_gap_commit_dirty_not_refreshed(suite_workspace, monkeypatch) -> None:
    """[spec test 2] A commit-dirty suite that write_entities reports as
    `unchanged` still gets its file map re-injected and the changed row
    re-described. Fails without the `commit_dirty` extension on the suite
    branch."""
    workspace = suite_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    desc_tag = {"v": "D1"}
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged(desc_tag)),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert "D1:test_mod.py" in _page(wiki).read_text(encoding="utf-8")

    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "write_entities",
        lambda conn, wiki_arg, kinds: EntityWriteResult(unchanged=[_SUITE]),
    )
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/tests/test_mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D2:test_mod.py" in t2
    assert "D1:test_mod.py" not in t2
    assert "D1:test_util.py" in t2


def test_suite_path_namespace_nested_file(suite_workspace, monkeypatch) -> None:
    """[spec test 3] A changed file nested under the suite root matches and
    re-describes (guards the repo-relative vs suite-root-relative transform)."""
    workspace = suite_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    # Suite map with a NESTED row so the transform must strip the suite root.
    nested_map = (
        "## File map - unit_tests_pkg-a\nTODO\n\n### tests/\nTODO\n\n"
        "| Path | Kind | Description |\n|---|---|---|\n"
        "| `sub/test_deep.py` | file | — TODO |\n"
        "| `test_util.py` | file | — TODO |\n"
    )
    monkeypatch.setattr(
        scan_mod, "build_dir_file_map",
        lambda path, **kw: (nested_map if str(path).endswith("tests") else None),
    )
    desc_tag = {"v": "D1"}
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged(desc_tag)),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert "D1:sub/test_deep.py" in _page(wiki).read_text(encoding="utf-8")

    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/tests/sub/test_deep.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D2:sub/test_deep.py" in t2     # nested changed row re-described
    assert "D1:test_util.py" in t2         # sibling preserved


def test_suite_no_narrate_keeps_cost_cache_and_anchor(suite_workspace, monkeypatch) -> None:
    """[spec test 4] A --no-narrate rescan refreshes suite file-map structure but
    re-describes no row and stamps no suite anchor."""
    workspace = suite_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    desc_tag = {"v": "D1"}
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged(desc_tag)),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"

    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/tests/test_mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=False))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D1:test_mod.py" in t2          # NOT re-described (cost cache intact)
    assert "D2:test_mod.py" not in t2
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"
