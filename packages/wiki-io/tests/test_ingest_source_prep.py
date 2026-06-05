"""Bedrock-free ingest brief helpers for the plugin's Claude branch.

The brief must be produced WITHOUT importing model_adapter / subagent_runtime
(the Claude branch is Bedrock-free) and must carry the entity-match hint."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


def _seed_db(workspace: Path, name: str, uri: str, rel_path: str) -> None:
    from graph_io.store import connect
    from workspace_io.paths import graph_dir

    db = graph_dir(workspace) / "code.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db, create=True)
    try:
        conn.execute(
            "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
            "VALUES (1, 'package', ?, NULL, NULL, NULL, ?)",
            (name, uri),
        )
        conn.execute(
            "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
            "VALUES (2, 'file', ?, ?, NULL, NULL, NULL)",
            (Path(rel_path).name, rel_path),
        )
        conn.execute("INSERT INTO edges (src, dst, kind, attrs_json) VALUES (1, 2, 'contains', NULL)")
    finally:
        conn.close()


def test_build_ingest_brief_emits_brief_without_bedrock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Make the Bedrock stack un-importable; the prep must not need it.
    monkeypatch.setitem(sys.modules, "model_adapter", None)
    monkeypatch.setitem(sys.modules, "subagent_runtime", None)

    import wiki_io.ingest_source as prep

    importlib.reload(prep)

    workspace = tmp_path
    wiki = workspace / "wiki"
    wiki.mkdir()
    rel = "packages/graph-io/src/graph_io/store.py"
    src = workspace / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# Graph IO Store\n\nBody text.", encoding="utf-8")
    _seed_db(workspace, "graph-io", "pkg:o/r/graph-io", rel)

    brief = prep.build_ingest_brief(
        source_path=Path(rel),
        wiki=wiki,
        repo=workspace,
        workspace_root=workspace,
    )

    assert brief["title"]
    assert brief["source_type"] == "doc"
    assert brief["entity_match"]["uri"] == "pkg:o/r/graph-io"
    assert brief["entity_match"]["entity_filename"] == "pkg_graph-io"
    assert brief["suggested_summary_path"].startswith("sources/")
    assert "state_gate" in brief


def test_prep_module_exports_brief_builders(monkeypatch: pytest.MonkeyPatch) -> None:
    """The prep module exposes Bedrock-free library helpers only."""
    monkeypatch.setitem(sys.modules, "model_adapter", None)
    monkeypatch.setitem(sys.modules, "subagent_runtime", None)

    import wiki_io.ingest_source as prep

    importlib.reload(prep)
    assert callable(prep.build_ingest_brief)
    assert callable(prep.build_folder_ingest_brief)
    assert not hasattr(prep, "main")


def test_build_ingest_brief_no_entity_match_has_null_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Seed a package whose contained file is a DIFFERENT path, and whose name
    # won't match the source's title — so neither path nor name lookup hits.
    monkeypatch.setitem(sys.modules, "model_adapter", None)
    monkeypatch.setitem(sys.modules, "subagent_runtime", None)

    import wiki_io.ingest_source as prep

    importlib.reload(prep)

    workspace = tmp_path
    wiki = workspace / "wiki"
    wiki.mkdir()
    rel = "packages/graph-io/src/graph_io/store.py"
    src = workspace / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# Graph IO Store\n\nBody text.", encoding="utf-8")
    # The seeded package CONTAINS a different file, so `rel` is uncontained;
    # its name ("some-other-pkg") won't name-match the title "Graph IO Store".
    _seed_db(
        workspace,
        "some-other-pkg",
        "pkg:o/r/some-other-pkg",
        "packages/other/src/other/mod.py",
    )

    brief = prep.build_ingest_brief(
        source_path=Path(rel),
        wiki=wiki,
        repo=workspace,
        workspace_root=workspace,
    )

    assert brief["entity_match"] == {"uri": None, "entity_filename": None}


def test_build_folder_ingest_brief_emits_brief(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "model_adapter", None)
    monkeypatch.setitem(sys.modules, "subagent_runtime", None)

    import wiki_io.ingest_source as prep

    importlib.reload(prep)

    workspace = tmp_path
    wiki = workspace / "wiki"
    wiki.mkdir()
    folder = workspace / "raw" / "examples" / "demo"
    folder.mkdir(parents=True)
    (folder / "a.md").write_text("# A\n\nalpha", encoding="utf-8")
    (folder / "b.py").write_text("print('b')\n", encoding="utf-8")

    brief = prep.build_folder_ingest_brief(
        source_path=folder,
        wiki=wiki,
        repo=workspace,
    )

    assert brief["is_folder"] is True
    assert "state_gate" in brief
