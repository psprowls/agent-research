"""Unit tests for heading-aware section preservation helpers (Living Wiki M1/M2d)."""

from __future__ import annotations

import frontmatter

from wiki_io.entity_writer import (
    SCANNER_DATA_HEADINGS,
    _is_scanner_owned_heading,
    _merge_preserved_sections,
    _split_h2_sections,
    _template_path_for_kind,
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


# ---------------------------------------------------------------------------
# Living Wiki agent_plugin M2 parity (D1): SCANNER_DATA_HEADINGS tests
# ---------------------------------------------------------------------------

# A minimal agent_plugin-style template body carrying the six data tables.
_AGENT_PLUGIN_TEMPLATE = (
    "# TestPlugin\n\n"
    "## Narrative\n_(scanner will populate on next scan)_\n\n"
    "## Referenced in wiki\n_(scanner will populate on next scan)_\n\n"
    "## Purpose\n> TODO: fill me\n\n"
    "## Commands\n| Command | Description |\n| --- | --- |\n| cmd-A | desc-A |\n| cmd-B | desc-B |\n\n"
    "## Agents\n| Agent | Model | Tools | Description |\n| --- | --- | --- | --- |\n| agent-1 | sonnet | t1 | Agent one |\n\n"
    "## Skills\n| Skill | Description |\n| --- | --- |\n| skill-X | Skill X desc |\n\n"
    "## Scripts\n| Script | Language |\n| --- | --- |\n| run.sh | bash |\n\n"
    "## Hooks\n| Event | Matchers |\n| --- | --- |\n| PostToolUse | foo |\n\n"
    "## MCP servers\n| Server | Command |\n| --- | --- |\n| srv | npx srv |\n\n"
    "## How it fits together\n> TODO: relationships\n"
)

# Stale existing page: Commands has rows X,Y instead of A,B.
_AGENT_PLUGIN_EXISTING_STALE = (
    "# TestPlugin\n\n"
    "## Narrative\nold prose\n\n"
    "## Referenced in wiki\n- [[some-page]]\n\n"
    "## Purpose\nHuman-written purpose.\n\n"
    "## Commands\n| Command | Description |\n| --- | --- |\n| cmd-X | desc-X |\n| cmd-Y | desc-Y |\n\n"
    "## Agents\n| Agent | Model | Tools | Description |\n| --- | --- | --- | --- |\n| agent-old | haiku | t0 | Old agent |\n\n"
    "## Skills\n| Skill | Description |\n| --- | --- |\n| skill-OLD | stale |\n\n"
    "## Scripts\n| Script | Language |\n| --- | --- |\n| old.sh | bash |\n\n"
    "## Hooks\n| Event | Matchers |\n| --- | --- |\n| OldEvent | bar |\n\n"
    "## MCP servers\n| Server | Command |\n| --- | --- |\n| old-srv | npx old |\n\n"
    "## How it fits together\n> TODO: relationships\n"
)


def test_scanner_data_regenerates_discards_stale_body() -> None:
    """D1 test 1: scanner-data sections take the fresh template body; stale
    on-disk rows are discarded."""
    out = _merge_preserved_sections(_AGENT_PLUGIN_TEMPLATE, _AGENT_PLUGIN_EXISTING_STALE)
    # Fresh rows from template
    assert "cmd-A" in out
    assert "cmd-B" in out
    # Stale rows must NOT survive
    assert "cmd-X" not in out
    assert "cmd-Y" not in out


def test_scanner_data_human_section_still_preserved() -> None:
    """D1 test 2: human-owned sections (## Purpose) are preserved even when
    scanner-data sections are refreshed."""
    out = _merge_preserved_sections(_AGENT_PLUGIN_TEMPLATE, _AGENT_PLUGIN_EXISTING_STALE)
    assert "Human-written purpose." in out
    assert "> TODO: fill me" not in out  # template placeholder overwritten by human


def test_scanner_data_user_added_h2_still_trails() -> None:
    """D1 test 3: a user-added H2 not in the template survives and trails
    the template sections even alongside scanner-data headings."""
    existing_with_extra = _AGENT_PLUGIN_EXISTING_STALE + "## Notes\nmy notes here\n"
    out = _merge_preserved_sections(_AGENT_PLUGIN_TEMPLATE, existing_with_extra)
    assert "## Notes" in out
    assert "my notes here" in out
    # Must trail the last template section
    assert out.index("## How it fits together") < out.index("## Notes")


def test_scanner_data_idempotent() -> None:
    """D1 test 4: merge(t, t) == t for an agent_plugin-style template body
    carrying all six data tables."""
    assert _merge_preserved_sections(_AGENT_PLUGIN_TEMPLATE, _AGENT_PLUGIN_TEMPLATE) == _AGENT_PLUGIN_TEMPLATE


def test_scanner_data_headings_constant_and_in_template() -> None:
    """D1 test 5: SCANNER_DATA_HEADINGS covers exactly the six table headings,
    and every member is present as an H2 in the real agent_plugin template."""
    assert SCANNER_DATA_HEADINGS == frozenset({
        "## Commands", "## Agents", "## Skills",
        "## Scripts", "## Hooks", "## MCP servers",
    })
    # Cross-check against the real template on disk.
    template_path = _template_path_for_kind("agent_plugin")
    template_body = frontmatter.load(template_path).content
    template_h2s = {
        line.strip()
        for line in template_body.splitlines()
        if line.startswith("## ")
    }
    for heading in SCANNER_DATA_HEADINGS:
        assert heading in template_h2s, (
            f"{heading!r} is in SCANNER_DATA_HEADINGS but not found as an H2 "
            f"in the agent_plugin template. Template H2s: {template_h2s}"
        )
