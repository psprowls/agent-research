"""Living Wiki M2b: commit-gated File-map row re-description + shared anchor."""

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
from graph_wiki_core.commands.scan import _changed_rel_paths
from wiki_io.entity_writer import EntityWriteResult


# ---------------------------------------------------------------------------
# §3.3 path-namespace transform (unit)
# ---------------------------------------------------------------------------


def test_changed_rel_paths_relativizes_under_root() -> None:
    assert _changed_rel_paths(
        ["packages/pkg-a/mod.py", "packages/pkg-a/src/util.py"],
        "packages/pkg-a",
    ) == {"mod.py", "src/util.py"}


def test_changed_rel_paths_drops_paths_outside_root() -> None:
    assert _changed_rel_paths(
        ["packages/pkg-a/mod.py", "packages/pkg-b/other.py", "README.md"],
        "packages/pkg-a",
    ) == {"mod.py"}


def test_changed_rel_paths_empty() -> None:
    assert _changed_rel_paths([], "packages/pkg-a") == set()


# ---------------------------------------------------------------------------
# Integration harness (mocks fan-out at the SubagentPool.run_all boundary)
# ---------------------------------------------------------------------------

_PKG_A = "pkg:org/repo/pkg-a"

# A deterministic file map with TWO file rows so tests can change one and assert
# the other's description survives (the cost cache).
_FILE_MAP_TWO_ROWS = (
    "## File map - pkg-a\nTODO\n\n### pkg-a/\nTODO\n\n"
    "| Path | Kind | Description |\n|---|---|---|\n"
    "| `mod.py` | file | — TODO |\n"
    "| `util.py` | file | — TODO |\n"
)


def _seed_one_package(db_path: Path) -> None:
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', 'packages/pkg-a', NULL, "
            "'{\"language\": \"python\"}', 'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def m2b_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n")
    (wiki / "log.md").write_text("", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_one_package(workspace / ".graph" / "code.db")
    monkeypatch.setattr(
        scan_mod, "_cg_run_build",
        lambda repo, ws, *, full: (exit_codes.SUCCESS, "", ""),
    )
    monkeypatch.setattr(
        scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock()
    )
    monkeypatch.setattr(
        scan_mod, "build_file_map",
        lambda path, **kw: (
            _FILE_MAP_TWO_ROWS if str(path).endswith("pkg-a") else None
        ),
    )
    return workspace


def _fanout_spy(*, prose, descs):
    """Patch SubagentPool.run_all: narrator items -> prose(item) (a str);
    code_reader items -> JSON of descs(item) (a {package_root_path: desc} dict).

    The real `task` callable is never invoked — like the M2a `_narrate_all_spy`,
    this short-circuits the pool so no Bedrock/file-read work happens.
    """

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
    """Describer callback: every TODO path gets `<tag>:<path>` so a re-describe
    is distinguishable from the prior fill."""

    def _f(item) -> dict[str, str]:
        todo_paths = item[3]
        return {p: f"{tag['v']}:{p}" for p in todo_paths}

    return _f


def _page(wiki: Path, uri: str = _PKG_A) -> Path:
    return next(
        p
        for p in (wiki / "entities").glob("*.md")
        if _fm.load(p).metadata.get("uri") == uri
    )


def test_redescribe_changed_row_preserves_unchanged(m2b_workspace, monkeypatch) -> None:
    """Mutate one tracked file → its row re-describes; the other row keeps its
    prior description (cost cache intact). [spec test 1]"""
    workspace = m2b_workspace
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

    # Scan 1 at head1: describer fills both rows.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t1 = _page(wiki).read_text(encoding="utf-8")
    assert "D1:mod.py" in t1
    assert "D1:util.py" in t1

    # Scan 2 at head2: only mod.py changed since head1.
    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D2:mod.py" in t2       # changed row re-described
    assert "D1:mod.py" not in t2   # stale description gone
    assert "D1:util.py" in t2      # unchanged row preserved (cost cache)


def test_trigger_gap_commit_dirty_not_refreshed(m2b_workspace, monkeypatch) -> None:
    """A commit-dirty package that write_entities reports as structurally
    UNCHANGED (refreshed == {}) still gets its File map re-injected and the
    changed row re-described. Fails without the `refreshed | commit_dirty`
    trigger extension. [spec test 2]"""
    workspace = m2b_workspace
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
    assert "D1:mod.py" in _page(wiki).read_text(encoding="utf-8")

    # Scan 2: force write_entities to report the package as unchanged (so the
    # only thing that can re-inject it is commit_dirty). The no-op leaves the
    # scan-1 page on disk intact — exactly the "body retained, not refreshed"
    # state §3.2 describes.
    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "write_entities",
        lambda conn, wiki_arg, kinds: EntityWriteResult(unchanged=[_PKG_A]),
    )
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D2:mod.py" in t2
    assert "D1:mod.py" not in t2
    assert "D1:util.py" in t2
