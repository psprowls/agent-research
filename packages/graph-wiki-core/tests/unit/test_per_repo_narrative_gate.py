"""Task 6: per-repo narrative-refresh gating in _commit_dirty_changes.

A change in member repo B must not flag member repo A's entities dirty. The
dirty check resolves each node's OWNING member repo path (via the
``repo_paths`` map the scan front-half builds from workspace members) and runs
``changed_files_since`` against that repo.
"""

from __future__ import annotations

import types
from pathlib import Path

import graph_wiki_core.commands.scan as scan_mod
from wiki_io.entity_writer import LAST_UPDATED_COMMIT_KEY, short_filename


def _node(uri: str, path: str):
    return types.SimpleNamespace(attrs={"uri": uri}, path=path, name=Path(path).name, kind="package")


def _write_page(wiki: Path, uri: str, *, anchor: str | None) -> Path:
    page = wiki / "entities" / f"{short_filename(uri, frozenset())}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    fm = f"uri: {uri}\nkind: package\n"
    if anchor:
        fm += f"{LAST_UPDATED_COMMIT_KEY}: {anchor}\n"
    page.write_text(f"---\n{fm}---\n# {uri}\n\n## Narrative\nprose\n", encoding="utf-8")
    return page


def _patch_list_fns(monkeypatch, nodes) -> None:
    monkeypatch.setattr(
        scan_mod,
        "_kind_list_fns",
        lambda: {"package": lambda conn: nodes, "app": lambda conn: []},
    )


def test_only_changed_repo_is_dirty(monkeypatch, tmp_path) -> None:
    wiki = tmp_path / "wiki"
    uri_a = "pkg:local/alpha/alpha"
    uri_b = "pkg:local/beta/beta"
    _write_page(wiki, uri_a, anchor="anchor_a")
    _write_page(wiki, uri_b, anchor="anchor_b")
    _patch_list_fns(monkeypatch, [_node(uri_a, "packages/alpha"), _node(uri_b, "packages/beta")])

    repo_paths = {"local/alpha": tmp_path / "alpha", "local/beta": tmp_path / "beta"}
    gates = {
        "local/alpha": {"allowed": True, "reason": "", "head_commit": "aaaaaaa"},
        "local/beta": {"allowed": True, "reason": "", "head_commit": "bbbbbbb"},
    }

    # Only repo A's path reports a changed file; repo B is clean. If the dirty
    # check ran against the single ``repo`` arg for both, B would be flagged too.
    monkeypatch.setattr(
        scan_mod,
        "changed_files_since",
        lambda repo, anchor, sub: ["x.py"] if repo == repo_paths["local/alpha"] else [],
    )

    dirty = scan_mod._commit_dirty_changes(
        wiki,
        tmp_path / "fallback-repo",
        object(),
        "fallback_head",
        frozenset(),
        gates=gates,
        repo_paths=repo_paths,
    )
    assert set(dirty) == {uri_a}


def test_anchor_resolved_against_owning_repo_head(monkeypatch, tmp_path) -> None:
    """Each node's owning HEAD/repo is passed to changed_files_since, not the
    fallback single-repo ``repo``/``head``."""
    wiki = tmp_path / "wiki"
    uri_a = "pkg:local/alpha/alpha"
    _write_page(wiki, uri_a, anchor="anchor_a")
    _patch_list_fns(monkeypatch, [_node(uri_a, "packages/alpha")])

    repo_paths = {"local/alpha": tmp_path / "alpha"}
    gates = {"local/alpha": {"allowed": True, "reason": "", "head_commit": "aaaaaaa"}}

    seen: list[Path] = []

    def _changed(repo, anchor, sub):
        seen.append(repo)
        return ["x.py"]

    monkeypatch.setattr(scan_mod, "changed_files_since", _changed)

    scan_mod._commit_dirty_changes(
        wiki,
        tmp_path / "fallback-repo",
        object(),
        "fallback_head",
        frozenset(),
        gates=gates,
        repo_paths=repo_paths,
    )
    assert seen == [repo_paths["local/alpha"]]


def test_single_repo_unchanged(monkeypatch, tmp_path) -> None:
    """Empty repo_paths/gates -> the single-repo ``repo``/``head`` is used for
    every entity (byte-identical to pre-Task-6 behavior)."""
    wiki = tmp_path / "wiki"
    uri = "pkg:org/repo/foo"
    _write_page(wiki, uri, anchor="anchor_sha")
    _patch_list_fns(monkeypatch, [_node(uri, "packages/foo")])

    seen: list[Path] = []

    def _changed(repo, anchor, sub):
        seen.append(repo)
        return ["packages/foo/x.py"]

    monkeypatch.setattr(scan_mod, "changed_files_since", _changed)
    dirty = scan_mod._commit_dirty_changes(wiki, tmp_path / "repo", object(), "head_sha", frozenset())
    assert dirty == {uri: ["packages/foo/x.py"]}
    assert seen == [tmp_path / "repo"]
