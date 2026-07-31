from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.tools import tool


def _page(path: Path, title: str | None = None, kind: str | None = None, **frontmatter: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, str] = {}
    if title is not None:
        metadata["title"] = title
    if kind is not None:
        metadata["kind"] = kind
    metadata.update(frontmatter)
    yaml_lines = [f"{key}: {value}" for key, value in metadata.items()]
    path.write_text("---\n" + "\n".join(yaml_lines) + "\n---\n\nBody text for " + path.stem, encoding="utf-8")
    return path


def test_build_wiki_catalog_lists_curated_sources_entities_and_proposals(tmp_path: Path) -> None:
    from graph_wiki_core.agent_tools import build_wiki_catalog
    from wiki_io.proposals import upsert_proposal

    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "ownership.md", title="Ownership", summary="Owns sections")
    _page(wiki / "adrs" / "0007-md.md", title="ADR-0007: Markdown", summary="Markdown stays canonical")
    _page(wiki / "concepts" / "layers.md", title="Layers", summary="Bottom to top", kind="architecture")
    _page(wiki / "sources" / "spec.md", title="Spec", summary="Imported source")
    _page(
        wiki / "entities" / "packages" / "graph-wiki-core.md",
        title="graph-wiki-core",
        summary="Core package",
        uri="pkg:graph-wiki-core",
        kind="package",
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

    assert {entry["slug"] for entry in catalog["concepts"]} == {"ownership", "layers"}
    assert {entry["slug"] for entry in catalog["adrs"]} == {"0007-md"}
    assert "architecture" not in catalog
    assert {entry["slug"] for entry in catalog["sources"]} == {"spec"}
    assert [entry["uri"] for entry in catalog["entities"]] == ["pkg:graph-wiki-core"]
    assert catalog["entities"][0]["entity_kind"] == "package"
    assert [entry["target_slug"] for entry in catalog["proposals"]] == ["fanout"]


def test_build_wiki_catalog_rejects_bucket_paths_outside_wiki(tmp_path: Path) -> None:
    from graph_wiki_core.agent_tools import build_wiki_catalog

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    _page(tmp_path / "outside" / "leaked.md", title="Leaked", summary="outside")

    catalog = build_wiki_catalog(wiki, buckets=("../outside",))

    assert catalog["../outside"] == []


def test_build_wiki_catalog_rejects_symlinked_pages_outside_wiki(tmp_path: Path) -> None:
    from graph_wiki_core.agent_tools import build_wiki_catalog

    wiki = tmp_path / "wiki"
    concepts = wiki / "concepts"
    concepts.mkdir(parents=True)
    outside = _page(tmp_path / "outside.md", title="Leaked", summary="outside")
    link = concepts / "leaked.md"
    try:
        link.symlink_to(outside)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks are unsupported: {exc}")

    catalog = build_wiki_catalog(wiki)

    assert {entry["slug"] for entry in catalog["concepts"]} == set()


def test_build_wiki_catalog_rejects_symlinked_proposals_outside_wiki(tmp_path: Path) -> None:
    from graph_wiki_core.agent_tools import build_wiki_catalog

    wiki = tmp_path / "wiki"
    proposals = wiki / "proposals"
    proposals.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text(
        "---\n"
        "kind: concept\n"
        "mode: create_new\n"
        "target_slug: leaked\n"
        "title: Leaked\n"
        "status: proposed\n"
        "origins:\n"
        "  - ref: outside\n"
        "    source: test\n"
        "    rationale: outside wiki\n"
        "---\n",
        encoding="utf-8",
    )
    link = proposals / "concept-leak.md"
    try:
        link.symlink_to(outside)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks are unsupported: {exc}")

    catalog = build_wiki_catalog(wiki)

    assert [entry["target_slug"] for entry in catalog["proposals"]] == []


def test_read_bounded_wiki_page_includes_title_body_and_truncates(tmp_path: Path) -> None:
    from graph_wiki_core.agent_tools import read_bounded_wiki_page

    wiki = tmp_path / "wiki"
    page = wiki / "concepts" / "ownership.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("---\ntitle: Ownership\nkind: concept\n---\n\n" + ("x" * 120) + "marker", encoding="utf-8")

    out = read_bounded_wiki_page(wiki, "concepts/ownership.md", max_chars=40)
    bounded_content = out.split("\n\n[TRUNCATED after", 1)[0]

    assert out.startswith("# Ownership\n\n")
    assert len(bounded_content) == 40
    assert "[TRUNCATED after 40 chars]" in out
    assert "marker" not in out


def test_read_bounded_wiki_page_rejects_unsafe_missing_and_non_markdown_paths(tmp_path: Path) -> None:
    from graph_wiki_core.agent_tools import read_bounded_wiki_page

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (tmp_path / "secret.md").write_text("secret", encoding="utf-8")
    (wiki / "notes.txt").write_text("not markdown", encoding="utf-8")

    assert read_bounded_wiki_page(wiki, "../secret.md").startswith("ERROR: path is outside wiki")
    assert read_bounded_wiki_page(wiki, "missing.md").startswith("ERROR: wiki page not found")
    assert read_bounded_wiki_page(wiki, "notes.txt").startswith("ERROR: only markdown wiki pages may be read")


def test_search_wiki_catalog_respects_kind_filter_and_limit(tmp_path: Path) -> None:
    from graph_wiki_core.agent_tools import build_wiki_catalog, search_wiki_catalog

    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "ownership.md", title="Ownership", summary="sections")
    _page(wiki / "sources" / "ownership-source.md", title="Ownership Source", summary="source")
    _page(wiki / "entities" / "packages" / "ownership-pkg.md", title="Ownership Package", kind="package")

    catalog = build_wiki_catalog(wiki)
    concepts = search_wiki_catalog(catalog, "ownership", kind="concept", limit=1)
    entities = search_wiki_catalog(catalog, "ownership", kind="entity", limit=10)

    assert [row["path"] for row in concepts] == ["concepts/ownership.md"]
    assert [row["path"] for row in entities] == ["entities/packages/ownership-pkg.md"]


def test_chunk_text_uses_full_text_under_budget() -> None:
    from graph_wiki_core.agent_tools import chunk_text

    chunks = chunk_text("short text", max_chars=100, chunk_chars=20)

    assert chunks.full_text == "short text"
    assert chunks.chunks == []
    assert chunks.over_budget is False


def test_chunk_text_splits_over_budget_text_deterministically() -> None:
    from graph_wiki_core.agent_tools import chunk_text

    chunks = chunk_text("abcdefghijklmnopqrstuvwxyz", max_chars=10, chunk_chars=8)

    assert chunks.chunks == ["abcdefgh", "ijklmnop", "qrstuvwx", "yz"]
    assert chunks.full_text is None
    assert chunks.over_budget is True


def test_filter_graph_tools_exposes_only_allowed_names() -> None:
    from graph_wiki_core.agent_tools import filter_graph_tools

    @tool
    def cg_find(name: str) -> str:
        """Find a node."""
        return name

    @tool
    def cg_describe(kind: str, identifier: str) -> str:
        """Describe a node."""
        return f"{kind}:{identifier}"

    @tool
    def cg_callers(name: str) -> str:
        """Find callers."""
        return name

    filtered = filter_graph_tools([cg_find, cg_describe, cg_callers], {"cg_find", "cg_describe"})

    assert [graph_tool.name for graph_tool in filtered] == ["cg_find", "cg_describe"]


def test_truncate_text_lives_in_base_text_utils():
    """truncate_text must be importable without the Bedrock stack (prompts use it)."""
    from graph_wiki_core.text_utils import truncate_text as base_truncate

    assert base_truncate("abc", 10) == "abc"
    assert base_truncate("abcdef", 3) == "abc\n\n[TRUNCATED after 3 chars]"


def test_agent_tools_reexports_truncate_text():
    from graph_wiki_core import agent_tools
    from graph_wiki_core.text_utils import truncate_text as base_truncate

    assert agent_tools.truncate_text is base_truncate
