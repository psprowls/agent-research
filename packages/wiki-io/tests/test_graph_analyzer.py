"""Tests for wiki_io.graph_analyzer — wikilink graph analysis."""

from __future__ import annotations

from pathlib import Path


def test_depends_on_block_style_list_creates_edges(tmp_path: Path) -> None:
    """Block-style YAML lists in depends_on should create graph edges."""
    from wiki_io.graph_analyzer import build_graph

    wiki = tmp_path / "wiki"
    (wiki / "packages").mkdir(parents=True)
    (wiki / "packages" / "dep-a.md").write_text("---\ntitle: dep-a\n---\n\nbody\n", encoding="utf-8")
    (wiki / "packages" / "user.md").write_text(
        "---\ntitle: user\ndepends_on:\n  - dep-a\n---\n\nbody\n", encoding="utf-8"
    )
    nodes, out, inb = build_graph(wiki)
    assert "packages/dep-a" in out["packages/user"]
    assert "packages/user" in inb["packages/dep-a"]


def test_depends_on_flow_style_list_creates_edges(tmp_path: Path) -> None:
    """Flow-style YAML lists in depends_on should create graph edges."""
    from wiki_io.graph_analyzer import build_graph

    wiki = tmp_path / "wiki"
    (wiki / "packages").mkdir(parents=True)
    (wiki / "packages" / "dep-a.md").write_text("---\ntitle: dep-a\n---\n\nbody\n", encoding="utf-8")
    (wiki / "packages" / "user.md").write_text("---\ntitle: user\ndepends_on: [dep-a]\n---\n\nbody\n", encoding="utf-8")
    nodes, out, inb = build_graph(wiki)
    assert "packages/dep-a" in out["packages/user"]
    assert "packages/user" in inb["packages/dep-a"]


def test_depends_on_string_value_wrapped_as_list(tmp_path: Path) -> None:
    """A string-valued depends_on should be tolerated and wrapped into a one-item list."""
    from wiki_io.graph_analyzer import build_graph

    wiki = tmp_path / "wiki"
    (wiki / "packages").mkdir(parents=True)
    (wiki / "packages" / "dep-a.md").write_text("---\ntitle: dep-a\n---\n\nbody\n", encoding="utf-8")
    (wiki / "packages" / "user.md").write_text("---\ntitle: user\ndepends_on: dep-a\n---\n\nbody\n", encoding="utf-8")
    nodes, out, inb = build_graph(wiki)
    assert "packages/dep-a" in out["packages/user"]
    assert "packages/user" in inb["packages/dep-a"]


def test_depends_on_with_scoped_names(tmp_path: Path) -> None:
    """Scoped names like @scope/foo should resolve to packages/foo."""
    from wiki_io.graph_analyzer import build_graph

    wiki = tmp_path / "wiki"
    (wiki / "packages").mkdir(parents=True)
    (wiki / "packages" / "foo.md").write_text("---\ntitle: foo\n---\n\nbody\n", encoding="utf-8")
    (wiki / "packages" / "user.md").write_text(
        "---\ntitle: user\ndepends_on:\n  - '@scope/foo'\n---\n\nbody\n",
        encoding="utf-8",
    )
    nodes, out, inb = build_graph(wiki)
    assert "packages/foo" in out["packages/user"]
    assert "packages/user" in inb["packages/foo"]


def test_depends_on_self_reference_ignored(tmp_path: Path) -> None:
    """A package depending on itself should not create a self-edge."""
    from wiki_io.graph_analyzer import build_graph

    wiki = tmp_path / "wiki"
    (wiki / "packages").mkdir(parents=True)
    (wiki / "packages" / "self.md").write_text("---\ntitle: self\ndepends_on: [self]\n---\n\nbody\n", encoding="utf-8")
    nodes, out, inb = build_graph(wiki)
    assert "packages/self" not in out["packages/self"]


def test_depends_on_unresolved_reference_ignored(tmp_path: Path) -> None:
    """A dependency on a non-existent page should be silently ignored."""
    from wiki_io.graph_analyzer import build_graph

    wiki = tmp_path / "wiki"
    (wiki / "packages").mkdir(parents=True)
    (wiki / "packages" / "user.md").write_text(
        "---\ntitle: user\ndepends_on: [missing]\n---\n\nbody\n", encoding="utf-8"
    )
    nodes, out, inb = build_graph(wiki)
    assert out["packages/user"] == set()


def test_wikilinks_create_edges(tmp_path: Path) -> None:
    """Wikilinks [[...]] should create graph edges."""
    from wiki_io.graph_analyzer import build_graph

    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "foo.md").write_text("---\ntitle: foo\n---\n\nbody\n", encoding="utf-8")
    (wiki / "concepts" / "bar.md").write_text(
        "---\ntitle: bar\n---\n\nSee [[concepts/foo]] for details.\n", encoding="utf-8"
    )
    nodes, out, inb = build_graph(wiki)
    assert "concepts/foo" in out["concepts/bar"]
    assert "concepts/bar" in inb["concepts/foo"]


def test_index_pages_do_not_create_outbound_edges(tmp_path: Path) -> None:
    """Wikilinks from index.md should not create outbound edges (to avoid polluting hubs)."""
    from wiki_io.graph_analyzer import build_graph

    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "foo.md").write_text("---\ntitle: foo\n---\n\nbody\n", encoding="utf-8")
    (wiki / "index.md").write_text("---\ntitle: Index\n---\n\nSee [[concepts/foo]] for details.\n", encoding="utf-8")
    nodes, out, inb = build_graph(wiki)
    # Index should not have outbound edges
    assert out["index"] == set()
    # But foo should have inbound from index
    assert "index" in inb["concepts/foo"]


def test_depends_on_non_list_scalar_does_not_crash(tmp_path: Path) -> None:
    """Non-list scalar values in depends_on should not crash build_graph (int, bool, etc.)."""
    from wiki_io.graph_analyzer import build_graph

    wiki = tmp_path / "wiki"
    (wiki / "packages").mkdir(parents=True)
    (wiki / "packages" / "user.md").write_text("---\ntitle: user\ndepends_on: 42\n---\n\nbody\n", encoding="utf-8")
    # Should not raise TypeError; simply produces no edge since "42" resolves to nothing
    nodes, out, inb = build_graph(wiki)
    assert out["packages/user"] == set()
