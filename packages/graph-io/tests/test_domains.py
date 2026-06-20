"""Unit tests for graph_io.domains.emit (Phase 31 DOMAIN-01..05, D-15).

Phase 50 (D6): emit consumes a `domains_config` dict, not a domains.yaml file.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import pytest
from graph_io import domains, packages, store
from graph_io.uri import RepoContext

CTX = RepoContext(org="testorg", repo="testrepo")


# ---------- helpers ----------


def _setup(tmp_path: Path) -> sqlite3.Connection:
    return store.connect(tmp_path / "code.db", create=True)


def _write_pkg(root: Path, name: str, lang: str = "python") -> None:
    pkg_dir = root / "packages" / name
    if lang == "python":
        src_dir = pkg_dir / "src" / name.replace("-", "_")
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "__init__.py").write_text("")
        (pkg_dir / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.0.0"\n'
            f'requires-python = ">=3.11"\n'
            f'[build-system]\nrequires = ["uv_build"]\nbuild-backend = "uv_build"\n'
        )
    else:
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "package.json").write_text('{"name": "' + name + '", "version": "0.0.0"}')


def _refresh_packages(conn: sqlite3.Connection, repo_root: Path) -> None:
    with store.transaction(conn):
        packages.refresh(conn, repo_root=repo_root, ctx=CTX)


def _count_domains(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='domain'").fetchone()[0]


def _count_edges(conn: sqlite3.Connection, kind: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM edges WHERE kind=?", (kind,)).fetchone()[0]


# ---------- (a) None / empty config -> zero domains ----------


def test_none_config_zero_domain(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    domains.emit(conn, domains_config=None, ctx=CTX)
    assert _count_domains(conn) == 0


def test_empty_config_zero_domain(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    domains.emit(conn, domains_config={}, ctx=CTX)
    assert _count_domains(conn) == 0


# ---------- (b) valid config -> Domain + belongs_to_domain ----------


def test_emit_domain_nodes(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    domains.emit(conn, domains_config={"core": {"packages": ["mypkg"], "description": "Core domain"}}, ctx=CTX)
    assert _count_domains(conn) == 1
    assert _count_edges(conn, "belongs_to_domain") == 1
    row = conn.execute("SELECT uri, attrs_json FROM nodes WHERE kind='domain' AND name='core'").fetchone()
    assert row[0] == "domain:testorg/testrepo/core"
    attrs = json.loads(row[1])
    assert attrs.get("description") == "Core domain"


# ---------- (c) multi-domain membership ----------


def test_multi_domain_membership(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    domains.emit(conn, domains_config={"a": {"packages": ["mypkg"]}, "b": {"packages": ["mypkg"]}}, ctx=CTX)
    assert _count_edges(conn, "belongs_to_domain") == 2


# ---------- (d) length-2 cycle: skip ONLY intra-SCC, preserve outside ----------


def test_cycle_skip_only_intra_scc(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    cfg = {
        "payments": {"packages": [], "parent": "billing"},
        "billing": {"packages": ["mypkg"], "parent": "payments"},
        "outside": {"packages": [], "parent": "payments"},
    }
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, domains_config=cfg, ctx=CTX)
    assert "cycle detected involving domains: billing, payments" in caplog.text
    edges = conn.execute(
        "SELECT n1.name AS parent, n2.name AS child FROM edges e "
        "JOIN nodes n1 ON e.src=n1.id JOIN nodes n2 ON e.dst=n2.id "
        "WHERE e.kind='domain_contains_domain'"
    ).fetchall()
    edge_pairs = {(p, c) for p, c in edges}
    assert ("payments", "outside") in edge_pairs
    assert ("payments", "billing") not in edge_pairs
    assert ("billing", "payments") not in edge_pairs


# ---------- (e) length-3 cycle ----------


def test_cycle_length_3_intra_scc_only_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    cfg = {
        "a": {"packages": ["mypkg"], "parent": "b"},
        "b": {"packages": [], "parent": "c"},
        "c": {"packages": [], "parent": "a"},
    }
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, domains_config=cfg, ctx=CTX)
    assert "cycle detected involving domains: a, b, c" in caplog.text
    assert _count_edges(conn, "domain_contains_domain") == 0
    assert _count_domains(conn) == 3


# ---------- (f) self-loop ----------


def test_self_loop_skip(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, domains_config={"a": {"packages": ["mypkg"], "parent": "a"}}, ctx=CTX)
    assert "declares itself as parent" in caplog.text
    assert _count_edges(conn, "domain_contains_domain") == 0
    assert _count_domains(conn) == 1


# ---------- (g) orphan parent ----------


def test_orphan_parent_skip(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, domains_config={"a": {"packages": ["mypkg"], "parent": "nonexistent"}}, ctx=CTX)
    assert "is not a declared domain" in caplog.text
    assert _count_edges(conn, "domain_contains_domain") == 0
    assert _count_domains(conn) == 1


# ---------- (h) unknown package -> sorted known-list warning ----------


def test_unknown_package_warns_with_known_list(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    _write_pkg(tmp_path, "otherpkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, domains_config={"a": {"packages": ["bogus"]}}, ctx=CTX)
    assert "package 'bogus' (in domain 'a')" in caplog.text
    assert "mypkg" in caplog.text
    assert "otherpkg" in caplog.text
    assert _count_domains(conn) == 1
    assert _count_edges(conn, "belongs_to_domain") == 0


# ---------- (i) unknown top-level key -> warn + ignored + Domain emits ----------


def test_unknown_top_level_key_logged_and_ignored(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, domains_config={"a": {"packages": ["mypkg"], "weird_extra": "yes"}}, ctx=CTX)
    assert "has unknown key 'weird_extra'" in caplog.text
    assert _count_domains(conn) == 1


# ---------- (j) missing 'packages:' field -> skip ----------


def test_missing_packages_field_skips_domain(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, domains_config={"a": {"description": "no packages"}}, ctx=CTX)
    assert "missing required 'packages:' field" in caplog.text
    assert _count_domains(conn) == 0


# ---------- (k) non-list 'packages:' -> skip ----------


def test_non_list_packages_skips_domain(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, domains_config={"a": {"packages": "mypkg"}}, ctx=CTX)
    assert "non-list 'packages:' field" in caplog.text
    assert _count_domains(conn) == 0


# ---------- (l) non-mapping domain value -> skip ----------


def test_non_mapping_domain_value_skips(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, domains_config={"a": "notamap"}, ctx=CTX)
    assert "must be a mapping" in caplog.text
    assert _count_domains(conn) == 0


# ---------- (m) SC#5: no convention inference ----------


def test_no_convention_inference(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    (tmp_path / "tests" / "billing").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "billing" / "__init__.py").write_text("")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    domains.emit(conn, domains_config=None, ctx=CTX)
    row = conn.execute("SELECT id FROM nodes WHERE kind='domain' AND name='billing'").fetchone()
    assert row is None
    assert _count_domains(conn) == 0


# ---------- bonus: idempotency ----------


def test_idempotent_emit(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    cfg = {"core": {"packages": ["mypkg"]}}
    domains.emit(conn, domains_config=cfg, ctx=CTX)
    edges_first = conn.execute("SELECT src, dst, kind FROM edges ORDER BY src, dst, kind").fetchall()
    domains.emit(conn, domains_config=cfg, ctx=CTX)
    edges_second = conn.execute("SELECT src, dst, kind FROM edges ORDER BY src, dst, kind").fetchall()
    assert edges_first == edges_second
    assert _count_domains(conn) == 1
