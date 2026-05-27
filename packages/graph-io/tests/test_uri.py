"""Unit coverage for graph_io.uri (Phase 28-02 D-08 sentinel)."""

from __future__ import annotations

import dataclasses

import pytest

from graph_io.uri import (
    RepoContext,
    dependency_uri,
    domain_uri,
    entry_point_uri,
    file_uri,
    package_family_uri,
    parse_remote_url,
    pkg_uri,
    plugin_uri,
    repo_uri,
    subpkg_uri,
)
from graph_io.uri import test_suite_uri as _test_suite_uri  # alias: avoid pytest collection


def test_repo_context_is_frozen() -> None:
    ctx = RepoContext("a", "b")
    assert hash(ctx) is not None
    assert dataclasses.is_dataclass(ctx)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.org = "x"  # type: ignore[misc]


def test_repo_uri() -> None:
    assert repo_uri(RepoContext("org", "repo")) == "repo:org/repo"


def test_pkg_uri() -> None:
    assert pkg_uri(RepoContext("org", "repo"), "auth-service") == "pkg:org/repo/auth-service"


def test_subpkg_uri_preserves_dotted_path() -> None:
    # D-07 lock: dotted Python import path, NOT slash-separated FS path
    result = subpkg_uri(RepoContext("local", "agent-research"), "graph-io", "graph_io.cli")
    assert result == "subpkg:local/agent-research/graph-io/graph_io.cli"
    assert "graph_io.cli" in result
    assert "graph_io/cli" not in result


def test_file_uri_preserves_forward_slashes() -> None:
    assert (
        file_uri(RepoContext("org", "repo"), "src/foo/bar.py")
        == "file:org/repo/src/foo/bar.py"
    )


def test_entry_point_uri() -> None:
    assert (
        entry_point_uri(RepoContext("org", "repo"), "pkg", "cli")
        == "entry_point:org/repo/pkg/cli"
    )


def test_test_suite_uri() -> None:
    assert _test_suite_uri(RepoContext("org", "repo"), "unit") == "test_suite:org/repo/unit"


def test_domain_uri_with_ctx() -> None:
    # Domain identity is repo-scoped per Phase 31 D-05.
    ctx = RepoContext(org="acme", repo="repo")
    assert domain_uri(ctx, "billing") == "domain:acme/repo/billing"


# v1.8 concept-level URI builders (Phase 42 D-04). These take no RepoContext
# because the entities are repo-agnostic in the graph data model.
def test_package_family_uri() -> None:
    assert package_family_uri("aws") == "package_family:aws"


def test_plugin_uri() -> None:
    assert plugin_uri("graph-wiki") == "plugin:graph-wiki"


def test_dependency_uri() -> None:
    assert dependency_uri("pypi", "boto3") == "dependency:pypi/boto3"


def test_dependency_uri_npm() -> None:
    # Multi-ecosystem coverage; ecosystem is required to avoid cross-registry
    # collision (e.g. `react` exists in npm and on PyPI as `react-py`).
    assert dependency_uri("npm", "react") == "dependency:npm/react"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("git@github.com:pat/agent-research.git", ("pat", "agent-research")),
        ("git@github.com:pat/agent-research", ("pat", "agent-research")),
        ("https://github.com/pat/agent-research.git", ("pat", "agent-research")),
        ("https://github.com/pat/agent-research", ("pat", "agent-research")),
        ("https://github.com/pat/agent-research/", ("pat", "agent-research")),
        ("https://gitlab.com/group/subgroup/repo", None),
        ("git@gitlab.com:group/subgroup/repo.git", None),
        ("git@gitlab.com:group/subgroup/repo", None),
        ("git://foo/bar", None),
        ("file:///tmp/x", None),
        ("not a url", None),
    ],
)
def test_parse_remote_url(url: str, expected: tuple[str, str] | None) -> None:
    assert parse_remote_url(url) == expected
