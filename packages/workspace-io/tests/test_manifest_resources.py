"""Tests for graph.resources manifest plumbing (architecture-resource-nodes)."""

from __future__ import annotations

from pathlib import Path

import pytest
from workspace_io.manifest import read, read_graph_domains, read_graph_resources


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_resources_absent_defaults_empty(tmp_path: Path) -> None:
    p = _write(tmp_path / ".graph-wiki.yaml", "version: 2\ninitialized_at: '2026-06-20'\n")
    assert read(p)["graph"] == {"domains": {}, "resources": {}}
    assert read_graph_resources(p) == {}


def test_resources_read_and_accessor(tmp_path: Path) -> None:
    p = _write(
        tmp_path / ".graph-wiki.yaml",
        "version: 2\ninitialized_at: '2026-06-20'\n"
        "graph:\n"
        "  resources:\n"
        "    location-service:\n"
        "      resource_kind: api\n"
        "      provided_by: location-aws-node-ts\n"
        "      consumed_by: [location-data-node-ts]\n",
    )
    res = read_graph_resources(p)
    assert res["location-service"]["resource_kind"] == "api"
    assert res["location-service"]["consumed_by"] == ["location-data-node-ts"]


def test_resources_coexist_with_domains(tmp_path: Path) -> None:
    p = _write(
        tmp_path / ".graph-wiki.yaml",
        "version: 2\ninitialized_at: '2026-06-20'\n"
        "graph:\n"
        "  domains:\n    core: {packages: [pkg-a]}\n"
        "  resources:\n    db: {resource_kind: database}\n",
    )
    assert read_graph_domains(p) == {"core": {"packages": ["pkg-a"]}}
    assert read_graph_resources(p) == {"db": {"resource_kind": "database"}}


def test_unknown_graph_key_still_raises(tmp_path: Path) -> None:
    p = _write(tmp_path / ".graph-wiki.yaml", "version: 2\ngraph:\n  bogus: {}\n")
    with pytest.raises(RuntimeError, match="unknown keys in graph block"):
        read(p)


def test_resources_non_mapping_raises(tmp_path: Path) -> None:
    p = _write(tmp_path / ".graph-wiki.yaml", "version: 2\ngraph:\n  resources: [1, 2]\n")
    with pytest.raises(RuntimeError, match="graph.resources must be a mapping"):
        read(p)


def test_missing_manifest_returns_empty(tmp_path: Path) -> None:
    assert read_graph_resources(tmp_path / "nope.yaml") == {}
