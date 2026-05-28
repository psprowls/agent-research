"""Phase 46 Plan 02: tests for build_rewrite_table — three-source mapping pipeline."""
import json
from pathlib import Path

import pytest

from graph_io.queries import NodeRecord
from wiki_io import link_rewriter


def _node(kind: str, name: str, uri: str, **extra_attrs) -> NodeRecord:
    attrs = {"uri": uri, **extra_attrs}
    return NodeRecord(kind=kind, name=name, path=None, line=None, attrs=attrs)


@pytest.fixture
def fake_graph(monkeypatch):
    """Monkeypatch _LIST_FNS to return canned node lists."""
    nodes_by_kind = {
        "package": [
            _node("package", "graph-io", "pkg:agent-research/graph-io"),
            _node("package", "wiki-io", "pkg:agent-research/wiki-io"),
        ],
        "dependency": [
            _node("dependency", "click", "dependency:pypi/click", ecosystem="pypi"),
        ],
        "domain": [
            _node("domain", "billing", "domain:agent-research/billing"),
        ],
        "plugin": [
            _node("plugin", "graph-wiki", "plugin:graph-wiki"),
        ],
        "test_suite": [
            _node(
                "test_suite",
                "unit",
                "test_suite:agent-research/wiki-io/unit",
                suite_kind="unit",
                path="packages/wiki-io/tests",
            ),
        ],
    }
    for kind in nodes_by_kind:
        monkeypatch.setitem(
            link_rewriter._LIST_FNS,
            kind,
            lambda conn, k=kind: nodes_by_kind[k],
        )
    return nodes_by_kind


def _make_wiki(tmp_path: Path) -> Path:
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "adrs").mkdir(parents=True)
    (wiki / "architecture").mkdir(parents=True)
    (wiki / "sources").mkdir(parents=True)
    (tmp_path / "work").mkdir()
    return wiki


# --- Source 1 ---

def test_build_table_source1_packages(fake_graph, tmp_path):
    wiki = _make_wiki(tmp_path)
    table = link_rewriter.build_rewrite_table(conn=None, wiki_root=wiki)
    # Phase 53 D-05: filenames derived via short_filename (short form).
    # Both bare and wiki/-prefixed forms are present for each package.
    assert table["packages/graph-io/index"] == "entities/pkg_graph-io"
    assert table["wiki/packages/graph-io/index"] == "entities/pkg_graph-io"
    assert table["packages/wiki-io/index"] == "entities/pkg_wiki-io"


def test_build_table_source1_dependencies_include_ecosystem(fake_graph, tmp_path):
    wiki = _make_wiki(tmp_path)
    table = link_rewriter.build_rewrite_table(conn=None, wiki_root=wiki)
    # Phase 53 D-05: dependency short form is `dep_<name>` (no ecosystem in
    # filename); the ecosystem still appears in the bare/wiki/ source-key.
    assert table["dependencies/pypi/click/overview"] == "entities/dep_click"
    assert table["wiki/dependencies/pypi/click/overview"] == "entities/dep_click"


def test_build_table_source1_all_kinds_present(fake_graph, tmp_path):
    wiki = _make_wiki(tmp_path)
    table = link_rewriter.build_rewrite_table(conn=None, wiki_root=wiki)
    # All 5 admitted kinds represented.
    assert "domain/billing/index" in table
    assert "plugin/graph-wiki/overview" in table
    assert "test-suites/unit/index" in table


# --- Source 2 ---

def test_build_table_source2_scan_match_adds_unmapped(fake_graph, tmp_path):
    wiki = _make_wiki(tmp_path)
    # Create wiki/packages/graph-io/index.md — Source 1 already covers this; Source 2 is a no-op.
    (wiki / "packages" / "graph-io").mkdir(parents=True)
    (wiki / "packages" / "graph-io" / "index.md").write_text("body\n", encoding="utf-8")
    table = link_rewriter.build_rewrite_table(conn=None, wiki_root=wiki)
    assert table["packages/graph-io/index"] == "entities/pkg_graph-io"


def test_build_table_source2_unmatched_file_left_uncovered(fake_graph, tmp_path):
    wiki = _make_wiki(tmp_path)
    # Create wiki/packages/never-in-graph/index.md — no graph entity → not added.
    (wiki / "packages" / "never-in-graph").mkdir(parents=True)
    (wiki / "packages" / "never-in-graph" / "index.md").write_text("body\n", encoding="utf-8")
    table = link_rewriter.build_rewrite_table(conn=None, wiki_root=wiki)
    assert "packages/never-in-graph/index" not in table


# --- Source 3 ---

def test_build_table_source3_unresolvable_logged(fake_graph, tmp_path):
    wiki = _make_wiki(tmp_path)
    (wiki / "concepts" / "foo.md").write_text(
        "Refers to [[packages/totally-fake/index]] which is not in the graph.\n",
        encoding="utf-8",
    )
    log_path = tmp_path / ".graph-wiki" / "migration.log"
    table = link_rewriter.build_rewrite_table(conn=None, wiki_root=wiki, log_path=log_path)
    # Table contains the target with value None.
    assert "packages/totally-fake/index" in table
    assert table["packages/totally-fake/index"] is None
    # migration.log has an unresolved line.
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert any(
        r["phase"] == "unresolved" and r["target"] == "packages/totally-fake/index"
        for r in records
    )


def test_build_table_source3_ignores_links_inside_code(fake_graph, tmp_path):
    wiki = _make_wiki(tmp_path)
    (wiki / "concepts" / "baz.md").write_text(
        "Fenced:\n\n```\n[[packages/totally-fake/index]]\n```\n",
        encoding="utf-8",
    )
    log_path = tmp_path / ".graph-wiki" / "migration.log"
    table = link_rewriter.build_rewrite_table(conn=None, wiki_root=wiki, log_path=log_path)
    # Not added — it's inside a fenced block.
    assert "packages/totally-fake/index" not in table


def test_build_table_source3_no_log_path_still_works(fake_graph, tmp_path):
    wiki = _make_wiki(tmp_path)
    (wiki / "concepts" / "qux.md").write_text(
        "Has [[packages/missing/index]].\n", encoding="utf-8",
    )
    # log_path=None → no file should be written, but table still contains the entry.
    table = link_rewriter.build_rewrite_table(conn=None, wiki_root=wiki, log_path=None)
    assert table.get("packages/missing/index") is None


# --- Return type contract ---

def test_build_table_returns_dict_str_optional_str(fake_graph, tmp_path):
    wiki = _make_wiki(tmp_path)
    table = link_rewriter.build_rewrite_table(conn=None, wiki_root=wiki)
    assert isinstance(table, dict)
    for k, v in table.items():
        assert isinstance(k, str) and k
        assert v is None or (isinstance(v, str) and v)
