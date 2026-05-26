"""Unit tests for graph_io.domains.emit (Phase 31 DOMAIN-01..05, D-15)."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import pytest

from graph_io import domains, packages, store
from graph_io.domains import DomainYamlError
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
        (pkg_dir / "package.json").write_text(
            '{"name": "' + name + '", "version": "0.0.0"}'
        )


def _refresh_packages(conn: sqlite3.Connection, repo_root: Path) -> None:
    with store.transaction(conn):
        packages.refresh(conn, repo_root=repo_root, ctx=CTX)


def _count_domains(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE kind='domain'"
    ).fetchone()[0]


def _count_edges(conn: sqlite3.Connection, kind: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM edges WHERE kind=?", (kind,),
    ).fetchone()[0]


# ---------- (a) missing yaml ----------


def test_missing_yaml_zero_domain(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    assert _count_domains(conn) == 0


# ---------- (b) valid yaml -> Domain + belongs_to_domain ----------


def test_emit_domain_nodes(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    (tmp_path / "domains.yaml").write_text(
        "core:\n  packages: [mypkg]\n  description: 'Core domain'\n"
    )
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    assert _count_domains(conn) == 1
    assert _count_edges(conn, "belongs_to_domain") == 1
    row = conn.execute(
        "SELECT uri, attrs_json FROM nodes WHERE kind='domain' AND name='core'"
    ).fetchone()
    assert row[0] == "domain:testorg/testrepo/core"
    attrs = json.loads(row[1])
    assert attrs.get("description") == "Core domain"


# ---------- (c) multi-domain membership ----------


def test_multi_domain_membership(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    (tmp_path / "domains.yaml").write_text(
        "a:\n  packages: [mypkg]\n"
        "b:\n  packages: [mypkg]\n"
    )
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    assert _count_edges(conn, "belongs_to_domain") == 2


# ---------- (d) length-2 cycle: skip ONLY intra-SCC, preserve outside ----------


def test_cycle_skip_only_intra_scc(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    # Two-domain cycle + a third domain outside the cycle
    (tmp_path / "domains.yaml").write_text(
        "payments:\n  packages: []\n  parent: billing\n"
        "billing:\n  packages: [mypkg]\n  parent: payments\n"
        "outside:\n  packages: []\n  parent: payments\n"
    )
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    assert "cycle detected involving domains: billing, payments" in caplog.text
    # outside->payments is NOT in the SCC; it should still be emitted
    edges = conn.execute(
        "SELECT n1.name AS parent, n2.name AS child FROM edges e "
        "JOIN nodes n1 ON e.src=n1.id JOIN nodes n2 ON e.dst=n2.id "
        "WHERE e.kind='domain_contains_domain'"
    ).fetchall()
    edge_pairs = {(p, c) for p, c in edges}
    assert ("payments", "outside") in edge_pairs
    # Intra-cycle edges are skipped
    assert ("payments", "billing") not in edge_pairs
    assert ("billing", "payments") not in edge_pairs


# ---------- (e) length-3 cycle ----------


def test_cycle_length_3_intra_scc_only_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    (tmp_path / "domains.yaml").write_text(
        "a:\n  packages: [mypkg]\n  parent: b\n"
        "b:\n  packages: []\n  parent: c\n"
        "c:\n  packages: []\n  parent: a\n"
    )
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    assert "cycle detected involving domains: a, b, c" in caplog.text
    assert _count_edges(conn, "domain_contains_domain") == 0
    assert _count_domains(conn) == 3  # all 3 nodes still emit


# ---------- (f) self-loop ----------


def test_self_loop_skip(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    (tmp_path / "domains.yaml").write_text(
        "a:\n  packages: [mypkg]\n  parent: a\n"
    )
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    assert "declares itself as parent" in caplog.text
    assert _count_edges(conn, "domain_contains_domain") == 0
    assert _count_domains(conn) == 1


# ---------- (g) orphan parent ----------


def test_orphan_parent_skip(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    (tmp_path / "domains.yaml").write_text(
        "a:\n  packages: [mypkg]\n  parent: nonexistent\n"
    )
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    assert "is not a declared domain" in caplog.text
    assert _count_edges(conn, "domain_contains_domain") == 0
    assert _count_domains(conn) == 1


# ---------- (h) unknown package -> sorted known-list warning ----------


def test_unknown_package_warns_with_known_list(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    _write_pkg(tmp_path, "otherpkg")
    (tmp_path / "domains.yaml").write_text(
        "a:\n  packages: [bogus]\n"
    )
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    assert "package 'bogus' (in domain 'a')" in caplog.text
    # Full sorted known-package list must appear (SC#4)
    assert "mypkg" in caplog.text
    assert "otherpkg" in caplog.text
    # Domain node still emits, but no belongs_to_domain edge
    assert _count_domains(conn) == 1
    assert _count_edges(conn, "belongs_to_domain") == 0


# ---------- (i) unknown top-level key -> warn + ignored + Domain emits ----------


def test_unknown_top_level_key_logged_and_ignored(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    (tmp_path / "domains.yaml").write_text(
        "a:\n  packages: [mypkg]\n  weird_extra: yes\n"
    )
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    assert "has unknown key 'weird_extra'" in caplog.text
    assert _count_domains(conn) == 1  # Domain still emits


# ---------- (j) missing 'packages:' field -> skip ----------


def test_missing_packages_field_skips_domain(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    (tmp_path / "domains.yaml").write_text(
        "a:\n  description: 'no packages'\n"
    )
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    assert "missing required 'packages:' field" in caplog.text
    assert _count_domains(conn) == 0


# ---------- (k) non-list 'packages:' -> skip ----------


def test_non_list_packages_skips_domain(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_pkg(tmp_path, "mypkg")
    (tmp_path / "domains.yaml").write_text(
        "a:\n  packages: 'mypkg'\n"
    )
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.domains"):
        domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    assert "non-list 'packages:' field" in caplog.text
    assert _count_domains(conn) == 0


# ---------- (l) yaml parse error -> DomainYamlError(exit_code=4) ----------


def test_yaml_parse_error_raises_domain_yaml_error(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    (tmp_path / "domains.yaml").write_text(
        "a: { invalid: yaml: payload\n"
    )
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    with pytest.raises(DomainYamlError) as exc_info:
        domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    assert exc_info.value.exit_code == 4
    assert "YAML parse error" in str(exc_info.value)


# ---------- (m) SC#5: no convention inference from tests/billing/ ----------


def test_no_convention_inference_from_test_dir(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    # Create a tests/billing/ directory — this should NOT produce a Domain('billing')
    (tmp_path / "tests" / "billing").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "billing" / "__init__.py").write_text("")
    # No domains.yaml — explicit-config-only (DOMAIN-05)
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    # SC#5: no Domain node named 'billing' should exist
    row = conn.execute(
        "SELECT id FROM nodes WHERE kind='domain' AND name='billing'"
    ).fetchone()
    assert row is None
    assert _count_domains(conn) == 0


# ---------- bonus: idempotency ----------


def test_idempotent_emit(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    (tmp_path / "domains.yaml").write_text(
        "core:\n  packages: [mypkg]\n"
    )
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    edges_first = conn.execute(
        "SELECT src, dst, kind FROM edges ORDER BY src, dst, kind"
    ).fetchall()
    domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    edges_second = conn.execute(
        "SELECT src, dst, kind FROM edges ORDER BY src, dst, kind"
    ).fetchall()
    assert edges_first == edges_second
    assert _count_domains(conn) == 1   # not duplicated
