"""Unit tests for graph_wiki_core.commands.graph_query."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes
from graph_wiki_core.commands import graph_query


def test_connect_or_error_success(tmp_path: Path) -> None:
    fake_reader = MagicMock()
    with patch.object(graph_query, "open_reader", return_value=fake_reader):
        reader, code, err = graph_query.connect_or_error(tmp_path)
    assert reader is fake_reader
    assert code == exit_codes.SUCCESS
    assert err == ""


def test_connect_or_error_not_initialized(tmp_path: Path) -> None:
    with patch.object(graph_query, "open_reader", side_effect=GraphNotInitializedError("no db")):
        reader, code, err = graph_query.connect_or_error(tmp_path)
    assert reader is None
    assert code == exit_codes.NOT_INITIALIZED
    assert err == "error: no db"


def test_connect_or_error_schema_mismatch(tmp_path: Path) -> None:
    with patch.object(graph_query, "open_reader", side_effect=SchemaMismatchError(found="v1", expected=2)):
        reader, code, err = graph_query.connect_or_error(tmp_path)
    assert reader is None
    assert code == exit_codes.SCHEMA_MISMATCH
    assert "error:" in err


def test_reexports_present() -> None:
    # Smoke test: every name the CLI migration (Task 7) needs must resolve.
    for name in (
        "exit_codes",
        "GraphNotInitializedError",
        "SchemaMismatchError",
        "SCHEMA_VERSION",
        "VALID_KINDS",
        "GraphReader",
        "NodeRecord",
        "DriftReport",
        "render",
        "open_reader",
        "run_sync_wiki",
        "update",
        "resolve_overview_path",
        "_importer_human",
        "_importer_json",
        "_is_importer_batch",
        "_to_dict",
    ):
        assert hasattr(graph_query, name), f"graph_query is missing re-export: {name}"
