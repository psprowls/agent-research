"""Unit tests for cg sync-wiki logic."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from graph_io import store, sync_wiki, upsert
from source_parser.projections.graph import GraphNode, GraphRecords


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "graph-wiki"
    ws.mkdir()
    (ws / ".graph-wiki.yaml").write_text("registered_plugins: []\n")
    (ws / "wiki").mkdir()
    return ws


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def conn(workspace: Path) -> sqlite3.Connection:
    db = workspace / ".graph" / "code.db"
    c = store.connect(db, create=True)
    yield c
    c.close()


def _seed_package(conn: sqlite3.Connection, name: str, path: str) -> None:
    upsert.upsert_records(
        conn,
        GraphRecords(
            nodes=[GraphNode(kind="package", name=name, path=path, line=None, attrs={"language": "python"})],
            edges=[],
        ),
    )


def _make_overview(workspace: Path, rel: str) -> None:
    p = workspace / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"# {p.stem}\n")


def test_resolves_packages_overview(workspace: Path, repo_root: Path, conn: sqlite3.Connection) -> None:
    _seed_package(conn, "alpha", "packages/alpha")
    _make_overview(workspace, "wiki/packages/alpha/alpha.md")

    report = sync_wiki.run(workspace=workspace, conn=conn)

    assert report.newly_linked == (("alpha", "wiki/packages/alpha/alpha.md"),)
    assert report.undocumented == ()
    page = conn.execute("SELECT name, path FROM nodes WHERE kind='wiki_page'").fetchone()
    assert page == ("wiki/packages/alpha/alpha.md", "wiki/packages/alpha/alpha.md")
    edge_count = conn.execute("SELECT COUNT(*) FROM edges WHERE kind='documents'").fetchone()[0]
    assert edge_count == 1


def test_resolves_apps_overview(workspace: Path, repo_root: Path, conn: sqlite3.Connection) -> None:
    _seed_package(conn, "web", "apps/web")
    _make_overview(workspace, "wiki/apps/web/web.md")

    report = sync_wiki.run(workspace=workspace, conn=conn)

    assert report.newly_linked == (("web", "wiki/apps/web/web.md"),)


def test_resolves_domains_overview_via_glob(workspace: Path, repo_root: Path, conn: sqlite3.Connection) -> None:
    _seed_package(conn, "billing-core", "domains/billing/packages/billing-core")
    _make_overview(workspace, "wiki/domains/billing/packages/billing-core/billing-core.md")

    report = sync_wiki.run(workspace=workspace, conn=conn)

    assert report.newly_linked == (("billing-core", "wiki/domains/billing/packages/billing-core/billing-core.md"),)


def test_undocumented_package_is_reported(workspace: Path, repo_root: Path, conn: sqlite3.Connection) -> None:
    _seed_package(conn, "alpha", "packages/alpha")

    report = sync_wiki.run(workspace=workspace, conn=conn)

    assert report.undocumented == ("alpha",)
    assert report.newly_linked == ()


def test_domain_glob_collision_is_ambiguous(workspace: Path, repo_root: Path, conn: sqlite3.Connection, capsys) -> None:
    _seed_package(conn, "core", "domains/a/packages/core")
    _make_overview(workspace, "wiki/domains/a/packages/core/core.md")
    _make_overview(workspace, "wiki/domains/b/packages/core/core.md")

    report = sync_wiki.run(workspace=workspace, conn=conn)

    assert report.ambiguous == ("core",)
    assert report.newly_linked == ()
    assert "core" in capsys.readouterr().err
    edge_count = conn.execute("SELECT COUNT(*) FROM edges WHERE kind='documents'").fetchone()[0]
    assert edge_count == 0


def test_cleanup_removes_stale_wiki_page_and_edges(workspace: Path, repo_root: Path, conn: sqlite3.Connection) -> None:
    _seed_package(conn, "alpha", "packages/alpha")
    _make_overview(workspace, "wiki/packages/alpha/alpha.md")
    sync_wiki.run(workspace=workspace, conn=conn)

    (workspace / "wiki/packages/alpha/alpha.md").unlink()
    report = sync_wiki.run(workspace=workspace, conn=conn)

    assert report.stale == ("wiki/packages/alpha/alpha.md",)
    assert report.undocumented == ("alpha",)
    assert conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='wiki_page'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM edges WHERE kind='documents'").fetchone()[0] == 0


def test_run_is_idempotent(workspace: Path, repo_root: Path, conn: sqlite3.Connection) -> None:
    _seed_package(conn, "alpha", "packages/alpha")
    _make_overview(workspace, "wiki/packages/alpha/alpha.md")

    first = sync_wiki.run(workspace=workspace, conn=conn)
    second = sync_wiki.run(workspace=workspace, conn=conn)

    assert first.newly_linked == (("alpha", "wiki/packages/alpha/alpha.md"),)
    assert second.newly_linked == ()
    assert second.stale == ()
    page_count = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='wiki_page'").fetchone()[0]
    edge_count = conn.execute("SELECT COUNT(*) FROM edges WHERE kind='documents'").fetchone()[0]
    assert page_count == 1
    assert edge_count == 1


def test_no_wiki_dir_returns_all_undocumented(workspace: Path, repo_root: Path, conn: sqlite3.Connection) -> None:
    (workspace / "wiki").rmdir()
    _seed_package(conn, "alpha", "packages/alpha")
    _seed_package(conn, "beta", "packages/beta")

    report = sync_wiki.run(workspace=workspace, conn=conn)

    assert sorted(report.undocumented) == ["alpha", "beta"]
    assert report.newly_linked == ()
