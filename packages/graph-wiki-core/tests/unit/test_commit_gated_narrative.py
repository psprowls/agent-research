"""Living Wiki M2a: commit-gate + narrative persistence + anchor stamping."""

from __future__ import annotations

import types
from pathlib import Path

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
