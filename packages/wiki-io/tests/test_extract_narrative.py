"""Unit tests for extract_narrative (Living Wiki M2a)."""

from __future__ import annotations

from wiki_io.entity_writer import extract_file_map, extract_narrative


def test_returns_real_prose_stripped() -> None:
    text = "# P\n\n## Narrative\nReal prose about the package.\n\n## Purpose\nx\n"
    assert extract_narrative(text) == "Real prose about the package."


def test_placeholder_returns_none() -> None:
    text = "# P\n\n## Narrative\n_(scanner will populate on next scan)_\n\n## Purpose\nx\n"
    assert extract_narrative(text) is None


def test_empty_section_returns_none() -> None:
    text = "# P\n\n## Narrative\n\n## Purpose\nx\n"
    assert extract_narrative(text) is None


def test_missing_heading_returns_none() -> None:
    assert extract_narrative("# P\n\n## Purpose\nx\n") is None


def test_narrative_at_eof() -> None:
    text = "# P\n\n## Narrative\nProse with no trailing section.\n"
    assert extract_narrative(text) == "Prose with no trailing section."


def test_extract_file_map_returns_stripped_section() -> None:
    body = (
        "# pkg:a\n\n"
        "## Narrative\nThe package does async fan-out.\n\n"
        "## File map - a\n\n| Path | Kind | Description |\n|---|---|---|\n"
        "| `x.py` | file | core |\n\n"
        "## Referenced in wiki\n- [[entities/foo]]\n"
    )
    assert "| `x.py` |" in extract_file_map(body)


def test_extract_file_map_returns_none_when_absent() -> None:
    no_fm = "# t\n\n## Narrative\nn\n\n## Purpose\np\n"
    assert extract_file_map(no_fm) is None
