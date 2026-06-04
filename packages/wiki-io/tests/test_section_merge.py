"""Unit tests for heading-aware section preservation helpers (Living Wiki M1/M2d)."""

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


def test_merge_pto_preserves_scanner_section_body_and_human_section() -> None:
    """PTO: a scanner-owned section's EXISTING body survives the merge (it is
    overwritten later only by the inject steps that regenerate it). Human
    sections are still preserved; the template placeholder is NOT re-imposed."""
    template = (
        "# T\n\n## Narrative\n_(placeholder)_\n\n## Purpose\n> TODO: fill me\n"
    )
    existing = (
        "# T\n\n## Narrative\nOLD NARRATIVE PROSE\n\n## Purpose\nReal human purpose.\n"
    )
    out = _merge_preserved_sections(template, existing)
    assert "Real human purpose." in out          # human section preserved
    assert "OLD NARRATIVE PROSE" in out           # PTO: existing scanner body kept
    assert "_(placeholder)_" not in out           # PTO: template placeholder NOT re-imposed
    assert "> TODO: fill me" not in out           # template Purpose overwritten by human


def test_merge_appends_user_added_custom_section() -> None:
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    existing = (
        "# T\n\n## Narrative\n_p_\n\n## Purpose\nKept.\n\n## My Notes\ncustom stuff\n"
    )
    out = _merge_preserved_sections(template, existing)
    assert "## My Notes" in out
    assert "custom stuff" in out


def test_merge_pto_preserves_file_map_body() -> None:
    """PTO: the existing `## File map` body is preserved across the merge."""
    template = "# T\n\n## File map - foo\n> TODO\n\n## Purpose\n> TODO\n"
    existing = "# T\n\n## File map - foo\n| a | b | c |\n\n## Purpose\nKeep me.\n"
    out = _merge_preserved_sections(template, existing)
    assert "Keep me." in out                       # human Purpose preserved
    assert "| a | b | c |" in out                  # PTO: existing file map preserved


def test_merge_pto_matches_file_map_by_type_despite_heading_suffix() -> None:
    """[spec §5 test 3] The template renders `## File map - <slug>` while the
    on-disk page carries `## File map - <basename>` (the injector's last-writer
    form). PTO must match by section TYPE, so the existing filled basename
    section is preserved and the slug-suffixed template slot is discarded."""
    template = (
        "# T\n\n## Narrative\n_(placeholder)_\n\n"
        "## File map - pkg_pkg-a\n> TODO: <Overview>\n\n"
        "### pkg_pkg-a/\n| `<file>` | file | — TODO |\n"
    )
    existing = (
        "# T\n\n## Narrative\nreal prose\n\n"
        "## File map - pkg-a\n### pkg-a/\n| `mod.py` | file | does a thing |\n"
    )
    out = _merge_preserved_sections(template, existing)
    assert "## File map - pkg-a" in out            # existing (basename) heading kept
    assert "## File map - pkg_pkg-a" not in out     # slug-suffixed template slot dropped
    assert "does a thing" in out                    # filled rows preserved
    assert "— TODO" not in out                       # template placeholder rows discarded


def test_merge_with_empty_existing_returns_template() -> None:
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    assert _merge_preserved_sections(template, "") == template


def test_reconcile_template_adds_h2() -> None:
    """A new human-owned H2 added to the template appears on the merged page."""
    existing = "# T\n\n## Narrative\nprose\n\n## Purpose\nkept\n"
    template = (
        "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n\n## Public API\n> TODO\n"
    )
    out = _merge_preserved_sections(template, existing)
    assert "## Public API" in out                 # new template section added
    assert "kept" in out                          # existing human section preserved


def test_reconcile_template_drops_scanner_h2() -> None:
    """A scanner-owned H2 dropped from the template is removed from the page
    (scanner sections are template-driven; they do not linger)."""
    existing = (
        "# T\n\n## Narrative\nprose\n\n## File map - foo\n| a | b | c |\n\n"
        "## Purpose\nkept\n"
    )
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    out = _merge_preserved_sections(template, existing)
    assert "## File map" not in out               # dropped scanner section removed
    assert "kept" in out


def test_reconcile_template_drops_human_h2_is_preserved() -> None:
    """A human-owned H2 the template no longer defines is preserved (appended as
    a user section) — human content is never silently dropped."""
    existing = "# T\n\n## Narrative\nprose\n\n## Purpose\nkept human content\n"
    template = "# T\n\n## Narrative\n_p_\n"   # template dropped ## Purpose
    out = _merge_preserved_sections(template, existing)
    assert "## Purpose" in out
    assert "kept human content" in out


def test_reconcile_template_reorders_sections() -> None:
    """Output section order follows the template order, not the page's."""
    existing = "# T\n\n## Purpose\np\n\n## Narrative\nprose\n"
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    out = _merge_preserved_sections(template, existing)
    assert out.index("## Narrative") < out.index("## Purpose")  # template order


def test_reconcile_user_added_section_trails() -> None:
    """A user-added H2 absent from the template is preserved and trails the
    template-defined sections."""
    existing = (
        "# T\n\n## Narrative\nprose\n\n## Purpose\np\n\n## My Notes\ncustom\n"
    )
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    out = _merge_preserved_sections(template, existing)
    assert "## My Notes" in out
    assert "custom" in out
    assert out.index("## Purpose") < out.index("## My Notes")   # trails template
