"""Living Wiki M2a: commit-gate + narrative persistence + anchor stamping."""

from __future__ import annotations

import types
from pathlib import Path

import asyncio
import sqlite3

import frontmatter as _fm
import pytest
from graph_io import exit_codes
from unittest.mock import MagicMock

import graph_wiki_core.commands.scan as scan_mod
from graph_wiki_core.commands.scan import _commit_dirty_uris
from wiki_io.entity_writer import LAST_UPDATED_COMMIT_KEY, short_filename


def _node(uri: str, path: str):
    return types.SimpleNamespace(
        attrs={"uri": uri}, path=path, name=Path(path).name, kind="package"
    )


def _write_page(wiki: Path, uri: str, *, anchor: str | None) -> Path:
    page = wiki / "entities" / f"{short_filename(uri, frozenset())}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    fm = f"uri: {uri}\nkind: package\n"
    if anchor:
        fm += f"{LAST_UPDATED_COMMIT_KEY}: {anchor}\n"
    page.write_text(
        f"---\n{fm}---\n# {uri}\n\n## Narrative\nprose\n", encoding="utf-8"
    )
    return page


def _patch_list_fns(monkeypatch, nodes) -> None:
    monkeypatch.setattr(
        scan_mod,
        "_kind_list_fns",
        lambda: {"package": lambda conn: nodes, "app": lambda conn: []},
    )


def test_dirty_when_files_changed(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    uri = "pkg:org/repo/foo"
    _write_page(wiki, uri, anchor="anchor_sha")
    _patch_list_fns(monkeypatch, [_node(uri, "packages/foo")])
    monkeypatch.setattr(
        scan_mod, "changed_files_since", lambda repo, sha, sub: ["packages/foo/x.py"]
    )
    dirty = _commit_dirty_uris(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    )
    assert dirty == {uri}


def test_clean_when_no_changes(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    uri = "pkg:org/repo/foo"
    _write_page(wiki, uri, anchor="anchor_sha")
    _patch_list_fns(monkeypatch, [_node(uri, "packages/foo")])
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    assert _commit_dirty_uris(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    ) == set()


def test_skips_pages_without_anchor(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    uri = "pkg:org/repo/foo"
    _write_page(wiki, uri, anchor=None)  # pre-M2 page
    _patch_list_fns(monkeypatch, [_node(uri, "packages/foo")])
    consulted: list[int] = []
    monkeypatch.setattr(
        scan_mod, "changed_files_since", lambda *a: consulted.append(1) or []
    )
    assert _commit_dirty_uris(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    ) == set()
    assert consulted == []  # git never consulted for anchorless pages


def test_unknown_anchor_treated_as_dirty(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    uri = "pkg:org/repo/foo"
    _write_page(wiki, uri, anchor="gone_sha")
    _patch_list_fns(monkeypatch, [_node(uri, "packages/foo")])
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: None)  # SHA unknown
    assert _commit_dirty_uris(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    ) == {uri}


def test_no_head_returns_empty(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    uri = "pkg:org/repo/foo"
    _write_page(wiki, uri, anchor="anchor_sha")
    _patch_list_fns(monkeypatch, [_node(uri, "packages/foo")])
    assert _commit_dirty_uris(
        wiki, tmp_path / "repo", object(), None, frozenset()
    ) == set()


# ---------------------------------------------------------------------------
# M2a integration: narrative persistence + commit-gate stamping (Tasks 4-5)
# ---------------------------------------------------------------------------


def _seed_one_package(db_path: Path) -> None:
    """Graph with a single package node pkg-a at packages/pkg-a."""
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', 'packages/pkg-a', NULL, '{\"language\": \"python\"}', "
            "'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def m2a_workspace(tmp_path, monkeypatch):
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
        scan_mod, "_cg_run_build", lambda repo, ws, *, full: (exit_codes.SUCCESS, "", "")
    )
    monkeypatch.setattr(
        scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock()
    )
    # Minimal deterministic file map so the package page gets a File map section.
    monkeypatch.setattr(
        scan_mod,
        "build_file_map",
        lambda path, **kw: (
            "## File map - pkg-a\nTODO\n\n### pkg-a/\nTODO\n\n"
            "| Path | Kind | Description |\n|---|---|---|\n"
            "| `pyproject.toml` | file | — TODO |\n"
            if str(path).endswith("pkg-a")
            else None
        ),
    )
    return workspace


def _narrate_all_spy(prose_fn):
    """Return an async SubagentPool.run_all that narrates every item via prose_fn."""

    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        result.successes = [(it, prose_fn(it)) for it in items]
        return result

    return _run_all


_PKG_A = "pkg:org/repo/pkg-a"


def _page_for(wiki: Path):
    return next(
        p
        for p in (wiki / "entities").glob("*.md")
        if _fm.load(p).metadata.get("uri") == _PKG_A
    )


def test_narrative_survives_no_op_rescan(m2a_workspace, monkeypatch) -> None:
    """A narrated package keeps its prose on a second scan with no code change
    (the M1 wipe is fixed by snapshot+restore)."""
    workspace = m2a_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _narrate_all_spy(lambda it: f"PROSE for {it[0]}"),
    )

    # Scan 1: new page → narrated.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    text1 = _page_for(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text1
    assert _fm.load(_page_for(wiki)).metadata.get("last_updated_commit") == "head1"

    # Scan 2: no code change (files clean), so NOT re-narrated. Prose must persist.
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    text2 = _page_for(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text2  # <-- the fix
    assert "_(scanner will populate on next scan)_" not in text2
    # Anchor unchanged (not re-narrated).
    assert _fm.load(_page_for(wiki)).metadata.get("last_updated_commit") == "head1"


def test_narrative_survives_no_narrate_rescan(m2a_workspace, monkeypatch) -> None:
    """Persistence is independent of narration (D-F): a --no-narrate rescan must
    not wipe an existing narrative."""
    workspace = m2a_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _narrate_all_spy(lambda it: f"PROSE for {it[0]}"),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert "PROSE for" in _page_for(wiki).read_text(encoding="utf-8")

    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=False))
    text = _page_for(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text
    assert "_(scanner will populate on next scan)_" not in text
