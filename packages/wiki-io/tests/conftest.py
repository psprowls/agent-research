from __future__ import annotations

import os
from pathlib import Path

import pytest

from graph_io.queries import (
    DependencyDescription,
    DomainDescription,
    NodeRecord,
    PackageDescription,
    PluginDescription,
    RepoDescription,
    SuiteDescription,
)

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "round-trip-vault"


# ============================================================================
# Phase 43 Plan 02: MockGraphConn fixture for write_entities unit tests
# ============================================================================


class MockGraphConn:
    """Duck-typed stand-in for sqlite3.Connection. Holds canned per-kind data.

    Tests monkeypatch `graph_io.queries.list_*` and `describe_*` to read
    from `self._nodes` / `self._descriptions` instead of executing SQL.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, list[NodeRecord]] = {
            "repository": [],
            "domain": [],
            "package": [],
            "plugin": [],
            "dependency": [],
            "test_suite": [],
        }
        self._descriptions: dict[tuple, object] = {}

    def set_nodes(self, kind: str, nodes: list[NodeRecord]) -> None:
        self._nodes[kind] = nodes

    def set_description(self, kind: str, key: object, description: object) -> None:
        """key is `name` for most kinds, `(ecosystem, name)` for dependency."""
        self._descriptions[(kind, key)] = description

    def list_nodes(self, kind: str) -> list[NodeRecord]:
        return list(self._nodes.get(kind, []))

    def get_description(self, kind: str, key: object) -> object | None:
        return self._descriptions.get((kind, key))


@pytest.fixture
def mock_graph_conn() -> MockGraphConn:
    """Pre-populated MockGraphConn with one node per admitted kind.

    Tests can call `.set_nodes()` / `.set_description()` to override.
    """
    conn = MockGraphConn()
    conn.set_nodes("repository", [
        NodeRecord(kind="repository", name="agent-research", path=None, line=None,
                   attrs={"uri": "repo:local/agent-research", "owner": "local"}),
    ])
    conn.set_nodes("package", [
        NodeRecord(kind="package", name="graph-io", path="packages/graph-io", line=None,
                   attrs={"uri": "pkg:local/agent-research/graph-io",
                          "language": "python", "version": "0.2.1"}),
        NodeRecord(kind="package", name="wiki-io", path="packages/wiki-io", line=None,
                   attrs={"uri": "pkg:local/agent-research/wiki-io",
                          "language": "python", "version": "0.1.0"}),
    ])
    conn.set_nodes("domain", [
        NodeRecord(kind="domain", name="storage", path=None, line=None,
                   attrs={"uri": "domain:local/agent-research/storage"}),
    ])
    conn.set_nodes("test_suite", [
        NodeRecord(kind="test_suite", name="graph-io-tests",
                   path="packages/graph-io/tests", line=None,
                   attrs={"uri": "test_suite:local/agent-research/graph-io-tests",
                          "suite_kind": "pytest", "file_count": 25}),
    ])
    conn.set_nodes("dependency", [
        NodeRecord(kind="dependency", name="boto3", path=None, line=None,
                   attrs={"uri": "dependency:pypi/boto3",
                          "ecosystem": "pypi",
                          "versions_in_use": ["boto3>=1.38"]}),
    ])
    conn.set_nodes("plugin", [
        NodeRecord(kind="plugin", name="graph-wiki", path=None, line=None,
                   attrs={"uri": "plugin:graph-wiki",
                          "ecosystem": "claude-code"}),
    ])
    # Per-node descriptions (used by `write_entities` to populate scanner frontmatter)
    conn.set_description("package", "graph-io", PackageDescription(
        name="graph-io", language="python", version="0.2.1",
        files=["packages/graph-io/src/graph_io/queries.py"], counts={"function": 30},
        domains=["storage"], entry_points=[], test_suites=[],
    ))
    conn.set_description("package", "wiki-io", PackageDescription(
        name="wiki-io", language="python", version="0.1.0",
        files=["packages/wiki-io/src/wiki_io/entity_writer.py"], counts={"function": 15},
        domains=[], entry_points=[], test_suites=[],
    ))
    conn.set_description("repository", None, RepoDescription(
        name="agent-research", uri="repo:local/agent-research",
        owner="local", url=None, default_branch="main", package_count=7,
    ))
    conn.set_description("domain", "storage", DomainDescription(
        name="storage", uri="domain:local/agent-research/storage",
        parent=None, description=None,
    ))
    conn.set_description("test_suite", "graph-io-tests", SuiteDescription(
        name="graph-io-tests", uri="test_suite:local/agent-research/graph-io-tests",
        kind="pytest", file_count=25,
    ))
    conn.set_description("dependency", ("pypi", "boto3"), DependencyDescription(
        ecosystem="pypi", name="boto3", uri="dependency:pypi/boto3",
        versions_in_use=["boto3>=1.38"], used_by=["graph-io", "wiki-io"],
    ))
    conn.set_description("plugin", "graph-wiki", PluginDescription(
        name="graph-wiki", uri="plugin:graph-wiki", ecosystem="claude-code",
    ))
    return conn


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Return a fresh temp directory (pytest tmp_path variant)."""
    return tmp_path


def write_file(path: Path, content: str = "") -> Path:
    """Module-level helper (not a fixture): write content to path, creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def vault_path(tmp_path: Path) -> Path:
    """Return an empty vault directory under tmp_path."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    return wiki


@pytest.fixture
def round_trip_vault() -> Path:
    """Return the committed vault fixture, or the env-override path if set."""
    override = os.environ.get("GRAPH_WIKI_WORKSPACE")
    if override:
        return Path(override)
    return FIXTURE_VAULT
