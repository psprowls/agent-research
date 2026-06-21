"""Resource node primitives: uri helper + _VALID_KINDS admission."""

from __future__ import annotations

from pathlib import Path

from graph_io import queries, store
from graph_io.uri import RepoContext, resource_uri

CTX = RepoContext(org="testorg", repo="testrepo")


def test_resource_uri() -> None:
    assert resource_uri(CTX, "aws-bedrock") == "resource:testorg/testrepo/aws-bedrock"


def test_resource_in_valid_kinds() -> None:
    assert "resource" in queries._VALID_KINDS


def test_find_kind_resource_accepted(tmp_path: Path) -> None:
    conn = store.connect(tmp_path / "code.db", create=True)
    # No resources yet — must not raise on the kind, must return empty.
    assert queries.find(conn, kind="resource") == []
