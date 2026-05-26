from __future__ import annotations

"""Unit tests for graph_wiki_agent.uri_slug.slug_from_uri (Phase 40).

The helper is pure: given a URI, return its last segment as the canonical slug.
These tests pin the deterministic invariants in PLAN.md.
"""

import pytest

from graph_wiki_agent.uri_slug import slug_from_uri


def test_slug_from_uri_package_form() -> None:
    assert slug_from_uri("pkg:org/repo/graph-io") == "graph-io"


def test_slug_from_uri_nested_form() -> None:
    assert slug_from_uri("pkg:org/repo/sub/graph-io") == "graph-io"


def test_slug_from_uri_scheme_only_class() -> None:
    # No slash: rsplit("/")[-1] returns the full string, then rsplit(":")[-1]
    # strips the scheme. Today's class URIs from packages.refresh take this form.
    assert slug_from_uri("cls:graph_io.store.Foo") == "graph_io.store.Foo"


def test_slug_from_uri_empty_raises() -> None:
    with pytest.raises(ValueError):
        slug_from_uri("")


def test_slug_from_uri_trailing_slash_raises() -> None:
    with pytest.raises(ValueError):
        slug_from_uri("pkg:org/repo/")
