"""Failing smoke test for graph_io.uri (Phase 28-02 Task 1 RED)."""

from __future__ import annotations


def test_uri_module_import_smoke() -> None:
    from graph_io.uri import RepoContext, pkg_uri

    assert pkg_uri(RepoContext("org", "repo"), "name") == "pkg:org/repo/name"
