from __future__ import annotations

"""Tests for wiki_io.ingest_source — ported from lattice-wiki-core.

Requirements: CMD-03 (ingest_source port from lattice-wiki-core)
"""

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


def test_slugify_simple() -> None:
    from wiki_io.ingest_source import slugify

    assert slugify("Hello World!") == "hello-world"


def test_slugify_unicode() -> None:
    from wiki_io.ingest_source import slugify

    # Non-alphanumeric replaced with hyphens; lowercase applied
    result = slugify("Héllo Wörld")
    assert result == result.lower()
    assert "-" in result or result.replace("-", "").isalnum()


def test_slugify_multi_space_and_trailing_punct() -> None:
    from wiki_io.ingest_source import slugify

    assert slugify("  Hello   World  !  ") == "hello-world"


def test_slugify_empty_string() -> None:
    from wiki_io.ingest_source import slugify

    # Empty or whitespace-only returns "untitled"
    assert slugify("") == "untitled"
    assert slugify("   ") == "untitled"


def test_slugify_already_slug() -> None:
    from wiki_io.ingest_source import slugify

    assert slugify("hello-world") == "hello-world"


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------


def test_extract_md_returns_text_and_heading_title(tmp_path: Path) -> None:
    from wiki_io.ingest_source import extract

    md = tmp_path / "article.md"
    md.write_text("# My Article\n\nSome body text.", encoding="utf-8")
    text, title = extract(md)
    assert "My Article" in text
    assert title == "My Article"


def test_extract_md_no_heading_returns_none_title(tmp_path: Path) -> None:
    from wiki_io.ingest_source import extract

    md = tmp_path / "no-heading.md"
    md.write_text("Just some text without a heading.", encoding="utf-8")
    text, title = extract(md)
    assert "Just some text" in text
    assert title is None


def test_extract_txt(tmp_path: Path) -> None:
    from wiki_io.ingest_source import extract

    txt = tmp_path / "notes.txt"
    txt.write_text("Plain text content.", encoding="utf-8")
    text, title = extract(txt)
    assert "Plain text content" in text
    assert title is None


def test_extract_html(tmp_path: Path) -> None:
    from wiki_io.ingest_source import extract

    html = tmp_path / "page.html"
    html.write_text(
        "<html><head><title>Page Title</title></head><body><p>Hello world</p></body></html>",
        encoding="utf-8",
    )
    text, title = extract(html)
    assert "Hello world" in text
    assert title == "Page Title"


def test_extract_json(tmp_path: Path) -> None:
    from wiki_io.ingest_source import extract

    j = tmp_path / "data.json"
    j.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    text, title = extract(j)
    assert "key" in text
    assert title is None


def test_extract_csv(tmp_path: Path) -> None:
    from wiki_io.ingest_source import extract

    csv = tmp_path / "data.csv"
    csv.write_text("col1,col2\n1,2\n3,4\n", encoding="utf-8")
    text, title = extract(csv)
    assert "col1" in text
    assert title is None


# ---------------------------------------------------------------------------
# guess_source_type
# ---------------------------------------------------------------------------


def test_guess_source_type_specs() -> None:
    from wiki_io.ingest_source import guess_source_type

    assert guess_source_type(Path("raw/specs/auth.md"), None) == "spec"


def test_guess_source_type_articles() -> None:
    from wiki_io.ingest_source import guess_source_type

    assert guess_source_type(Path("raw/articles/clip.md"), None) == "article"


def test_guess_source_type_in_repo_doc() -> None:
    from wiki_io.ingest_source import guess_source_type

    # rel_to_wiki is None, rel_to_repo is provided -> doc
    assert guess_source_type(None, Path("docs/architecture.md")) == "doc"


def test_guess_source_type_note_fallback() -> None:
    from wiki_io.ingest_source import guess_source_type

    # Neither in known wiki folders nor in repo
    assert guess_source_type(None, None) == "note"


# ---------------------------------------------------------------------------
# language_for
# ---------------------------------------------------------------------------


def test_language_for_python() -> None:
    from wiki_io.ingest_source import language_for

    assert language_for(Path("foo.py")) == "python"


def test_language_for_typescript() -> None:
    from wiki_io.ingest_source import language_for

    assert language_for(Path("component.tsx")) == "typescript"


def test_language_for_rust() -> None:
    from wiki_io.ingest_source import language_for

    assert language_for(Path("main.rs")) == "rust"


def test_language_for_go() -> None:
    from wiki_io.ingest_source import language_for

    assert language_for(Path("server.go")) == "go"


def test_language_for_unknown() -> None:
    from wiki_io.ingest_source import language_for

    assert language_for(Path("file.xyz")) == "unknown"


# ---------------------------------------------------------------------------
# pick_representative
# ---------------------------------------------------------------------------


def test_pick_representative_readme_wins(tmp_path: Path) -> None:
    from wiki_io.ingest_source import pick_representative

    entries = [("README.md", 100), ("index.ts", 200), ("utils.ts", 50)]
    assert pick_representative(tmp_path, entries) == "README.md"


def test_pick_representative_index_ts(tmp_path: Path) -> None:
    from wiki_io.ingest_source import pick_representative

    entries = [("index.ts", 200), ("utils.ts", 50)]
    assert pick_representative(tmp_path, entries) == "index.ts"


def test_pick_representative_falls_back_to_largest(tmp_path: Path) -> None:
    from wiki_io.ingest_source import pick_representative

    entries = [("small.go", 10), ("large.go", 500)]
    rep = pick_representative(tmp_path, entries)
    assert rep == "large.go"


def test_pick_representative_empty(tmp_path: Path) -> None:
    from wiki_io.ingest_source import pick_representative

    assert pick_representative(tmp_path, []) is None


# ---------------------------------------------------------------------------
# Constants present
# ---------------------------------------------------------------------------


def test_constants_present() -> None:
    import wiki_io.ingest_source as m

    assert hasattr(m, "PREVIEW_CHARS")
    assert hasattr(m, "SLUG_RE")
    assert hasattr(m, "LANGUAGE_BY_EXT")
    assert hasattr(m, "REPRESENTATIVE_INDEX_NAMES")
    assert hasattr(m, "LARGE_FILE_BYTES")
    assert hasattr(m, "WARN_FILE_COUNT")
    assert hasattr(m, "ERROR_FILE_COUNT")


# ---------------------------------------------------------------------------
# No lattice_wiki_core or _version_check references
# ---------------------------------------------------------------------------


def test_no_lattice_wiki_core_imports() -> None:
    import importlib.util
    from pathlib import Path

    spec = importlib.util.find_spec("wiki_io.ingest_source")
    assert spec is not None
    src_path = Path(spec.origin)
    text = src_path.read_text(encoding="utf-8")
    assert "lattice_wiki_core" not in text
    assert "_version_check" not in text
    assert "check_for_updates" not in text
