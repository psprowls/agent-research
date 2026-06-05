"""Living Wiki M4: drift propagation to backlinks (spec §5)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from graph_io.store import read_only_connect


# --- fixture helpers -------------------------------------------------------

def _seed_one_package(db_path: Path, *, uri: str, node_path: str) -> None:
    """One package node so _entity_paths_by_uri maps uri -> node_path."""
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', ?, NULL, '{\"language\": \"python\"}', ?)",
            (node_path, uri),
        )
        conn.commit()
    finally:
        conn.close()


def _write_entity_page(
    wiki: Path,
    *,
    stem: str,
    uri: str,
    last_updated_commit: str,
    drift_propagated_commit: str | None = None,
    narrative: str = "Now uses async fan-out.",
) -> Path:
    fm = [f"uri: {uri}", "kind: package", f"last_updated_commit: {last_updated_commit}"]
    if drift_propagated_commit is not None:
        fm.append(f"drift_propagated_commit: {drift_propagated_commit}")
    page = wiki / "entities" / f"{stem}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "---\n" + "\n".join(fm) + "\n---\n"
        f"## Narrative\n\n{narrative}\n\n## Purpose\n\nTODO\n",
        encoding="utf-8",
    )
    return page


def _write_curated(wiki: Path, category: str, slug: str, body: str, title: str = "T") -> Path:
    page = wiki / category / f"{slug}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"---\ntitle: {title}\n---\n{body}\n", encoding="utf-8")
    return page


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """workspace/{wiki, repo} + one-package graph DB + GRAPH_WIKI_WORKSPACE."""
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / "entities").mkdir(parents=True)
    (wiki / ".graph-wiki").mkdir(parents=True)
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_one_package(
        workspace / ".graph-wiki" / "code.db",
        uri="pkg:org/repo/pkg-a",
        node_path="packages/pkg-a",
    )
    return workspace


@pytest.fixture
def conn(ws):
    c = read_only_connect(ws / ".graph-wiki" / "code.db")
    yield c
    c.close()


# --- candidate-gate tests --------------------------------------------------

def test_candidate_when_anchors_differ(ws, conn, monkeypatch):
    """[§5 test 3] drift_propagated_commit != last_updated_commit -> candidate;
    changed_files come from changed_files_since(repo, drift_propagated_commit, path)."""
    import graph_wiki_core.commands.propagate_drift as pd

    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(
        wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a",
        last_updated_commit="head2", drift_propagated_commit="head1",
    )
    monkeypatch.setattr(
        pd, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/pool.py"] if sha == "head1" else None,
    )

    cands = pd.propagation_candidates(wiki, repo, conn)
    assert len(cands) == 1
    c = cands[0]
    assert c.uri == "pkg:org/repo/pkg-a"
    assert c.stem == "pkg_a"
    assert c.last_updated_commit == "head2"
    assert c.drift_propagated_commit == "head1"
    assert c.changed_files == ["packages/pkg-a/pool.py"]


def test_not_a_candidate_when_anchors_equal(ws, conn):
    """[§5 test 3] equal anchors -> already propagated at this narrative -> skip."""
    import graph_wiki_core.commands.propagate_drift as pd

    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(
        wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a",
        last_updated_commit="head2", drift_propagated_commit="head2",
    )
    assert pd.propagation_candidates(wiki, repo, conn) == []


def test_absent_anchor_is_candidate(ws, conn, monkeypatch):
    """[§5 test 3] absent drift_propagated_commit -> candidate; empty since_sha
    yields no specific changed files (None -> [])."""
    import graph_wiki_core.commands.propagate_drift as pd

    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(
        wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="head2",
    )
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: None)
    cands = pd.propagation_candidates(wiki, repo, conn)
    assert len(cands) == 1
    assert cands[0].drift_propagated_commit is None
    assert cands[0].changed_files == []
