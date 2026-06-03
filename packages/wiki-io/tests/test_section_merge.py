"""Unit tests for heading-aware section preservation helpers (Living Wiki M1)."""

from __future__ import annotations

from wiki_io.entity_writer import (
    _is_scanner_owned_heading,
    _merge_preserved_sections,
    _split_h2_sections,
)


def test_is_scanner_owned_heading_true_cases() -> None:
    assert _is_scanner_owned_heading("## Narrative")
    assert _is_scanner_owned_heading("## File map")
    assert _is_scanner_owned_heading("## File map - graph-io")
    assert _is_scanner_owned_heading("## Referenced in wiki")


def test_is_scanner_owned_heading_false_cases() -> None:
    assert not _is_scanner_owned_heading("## Purpose")
    assert not _is_scanner_owned_heading("## Public API")
    assert not _is_scanner_owned_heading("## Field Notes")


def test_split_h2_sections_round_trips() -> None:
    body = "# Title\n\nintro\n\n## A\na body\n\n## B\nb body\n"
    preamble, sections = _split_h2_sections(body)
    assert preamble == "# Title\n\nintro\n\n"
    assert [h for h, _ in sections] == ["## A", "## B"]
    # Lossless: preamble + all chunks reconstruct the original exactly.
    assert preamble + "".join(chunk for _, chunk in sections) == body


def test_split_h2_sections_no_headings() -> None:
    body = "# Title\n\njust an intro, no H2\n"
    preamble, sections = _split_h2_sections(body)
    assert preamble == body
    assert sections == []


def test_merge_identity_is_stable() -> None:
    """merge(t, t) == t — guarantees a no-edit re-scan is byte-identical."""
    body = "# T\n\n## Narrative\n_(placeholder)_\n\n## Purpose\n> TODO\n"
    assert _merge_preserved_sections(body, body) == body


def test_merge_preserves_human_section_and_regenerates_scanner_section() -> None:
    template = (
        "# T\n\n## Narrative\n_(placeholder)_\n\n## Purpose\n> TODO: fill me\n"
    )
    existing = (
        "# T\n\n## Narrative\nOLD NARRATIVE PROSE\n\n## Purpose\nReal human purpose.\n"
    )
    out = _merge_preserved_sections(template, existing)
    assert "Real human purpose." in out          # human section preserved
    assert "_(placeholder)_" in out               # scanner section from template
    assert "OLD NARRATIVE PROSE" not in out       # scanner section NOT preserved
    assert "> TODO: fill me" not in out           # template Purpose overwritten by human


def test_merge_appends_user_added_custom_section() -> None:
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    existing = (
        "# T\n\n## Narrative\n_p_\n\n## Purpose\nKept.\n\n## My Notes\ncustom stuff\n"
    )
    out = _merge_preserved_sections(template, existing)
    assert "## My Notes" in out
    assert "custom stuff" in out


def test_merge_file_map_is_scanner_owned() -> None:
    template = "# T\n\n## File map - foo\n> TODO\n\n## Purpose\n> TODO\n"
    existing = "# T\n\n## File map - foo\n| a | b | c |\n\n## Purpose\nKeep me.\n"
    out = _merge_preserved_sections(template, existing)
    assert "Keep me." in out                       # human Purpose preserved
    assert "| a | b | c |" not in out              # file map regenerated, not preserved


def test_merge_with_empty_existing_returns_template() -> None:
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    assert _merge_preserved_sections(template, "") == template
