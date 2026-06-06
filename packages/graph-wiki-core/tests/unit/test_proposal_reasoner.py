from __future__ import annotations

from pathlib import Path


def _page(path: Path, **frontmatter: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml_lines = [f"{key}: {value}" for key, value in frontmatter.items()]
    path.write_text("---\n" + "\n".join(yaml_lines) + "\n---\n\nBody text for " + path.stem, encoding="utf-8")
    return path


def test_page_helper_writes_frontmatter_pages(tmp_path: Path) -> None:
    page = _page(tmp_path / "wiki" / "concepts" / "ownership.md", title="Ownership", summary="Owns sections")

    assert (
        page.read_text(encoding="utf-8")
        == "---\ntitle: Ownership\nsummary: Owns sections\n---\n\nBody text for ownership"
    )


def test_build_wiki_catalog_lists_curated_sources_entities_and_proposals(tmp_path: Path) -> None:
    from graph_wiki_core.commands.proposal_reasoner import build_wiki_catalog
    from wiki_io.proposals import upsert_proposal

    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "ownership.md", title="Ownership", summary="Owns sections")
    _page(wiki / "adrs" / "0007-md.md", title="ADR-0007: Markdown", summary="Markdown stays canonical")
    _page(wiki / "architecture" / "layers.md", title="Layers", summary="Bottom to top")
    _page(wiki / "sources" / "spec.md", title="Spec", summary="Imported source")
    _page(
        wiki / "entities" / "packages" / "graph-wiki-core.md",
        title="graph-wiki-core",
        summary="Core package",
        uri="pkg:graph-wiki-core",
        entity_kind="package",
    )
    upsert_proposal(
        wiki,
        {
            "kind": "concept",
            "mode": "create_new",
            "target_slug": "fanout",
            "title": "Fanout",
            "origin": {"ref": "sources/spec", "source": "ingest", "rationale": "Source justifies it."},
        },
    )

    catalog = build_wiki_catalog(wiki)

    assert {entry["slug"] for entry in catalog["concepts"]} == {"ownership"}
    assert {entry["slug"] for entry in catalog["adrs"]} == {"0007-md"}
    assert {entry["slug"] for entry in catalog["architecture"]} == {"layers"}
    assert {entry["slug"] for entry in catalog["sources"]} == {"spec"}
    assert [entry["uri"] for entry in catalog["entities"]] == ["pkg:graph-wiki-core"]
    assert [entry["target_slug"] for entry in catalog["proposals"]] == ["fanout"]


def test_build_source_chunks_uses_full_text_under_budget() -> None:
    from graph_wiki_core.commands.proposal_reasoner import build_source_chunks

    chunks = build_source_chunks("short text", max_chars=100, chunk_chars=20)

    assert chunks.full_text == "short text"
    assert chunks.chunks == []
    assert chunks.over_budget is False


def test_build_source_chunks_splits_when_over_budget() -> None:
    from graph_wiki_core.commands.proposal_reasoner import build_source_chunks

    chunks = build_source_chunks("abcdefghijklmnopqrstuvwxyz", max_chars=10, chunk_chars=8)

    assert chunks.chunks == ["abcdefgh", "ijklmnop", "qrstuvwx", "yz"]
    assert chunks.full_text is None
    assert chunks.over_budget is True
