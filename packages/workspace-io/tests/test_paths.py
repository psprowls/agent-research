"""Tests for workspace_io.paths — pure path arithmetic over a workspace path."""
from workspace_io.paths import (
    manifest_path, wiki_dir, raw_dir,
    work_dir, knowledge_dir, graph_dir,
)


def test_wiki_dir(tmp_path):
    assert wiki_dir(tmp_path) == tmp_path / "wiki"


def test_work_dir(tmp_path):
    assert work_dir(tmp_path) == tmp_path / "work"


def test_graph_dir(tmp_path):
    assert graph_dir(tmp_path) == tmp_path / ".graph"


def test_raw_dir(tmp_path):
    assert raw_dir(tmp_path) == tmp_path / "raw"


def test_knowledge_dir(tmp_path):
    assert knowledge_dir(tmp_path) == tmp_path / "knowledge"


def test_manifest_path(tmp_path):
    assert manifest_path(tmp_path) == tmp_path / ".graph-wiki.yaml"


def test_string_workspace_coerced(tmp_path):
    assert wiki_dir(str(tmp_path)) == tmp_path / "wiki"
