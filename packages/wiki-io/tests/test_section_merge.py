"""Unit tests for the two-class (deterministic vs prose) section merge.

Two-class contract: if the graph can compute a section, it is deterministic;
if a model (or human) wrote it, it is prose. The six agent_plugin data tables
are template-authoritative at merge; `## Referenced in wiki` and `## File map`
are deterministic but inject-refreshed, so the merge carries the on-disk copy;
everything else is prose, carried from disk verbatim.
"""

from __future__ import annotations

import frontmatter
from wiki_io.entity_writer import (
    _TEMPLATE_AUTHORITATIVE,
    DETERMINISTIC_SECTIONS,
    _is_file_map_heading,
    _merge_preserved_sections,
    _split_h2_sections,
    _template_path_for_kind,
)

# ---------------------------------------------------------------------------
# Vocabulary constants
# ---------------------------------------------------------------------------


def test_deterministic_sections_members() -> None:
    assert DETERMINISTIC_SECTIONS == frozenset(
        {
            "## Referenced in wiki",
            "## Commands",
            "## Agents",
            "## Skills",
            "## Scripts",
            "## Hooks",
            "## MCP servers",
        }
    )


def test_template_authoritative_is_deterministic_minus_referenced() -> None:
    assert _TEMPLATE_AUTHORITATIVE == DETERMINISTIC_SECTIONS - {"## Referenced in wiki"}


def test_template_authoritative_headings_in_agent_plugin_template() -> None:
    """Every template-authoritative heading exists as an H2 in the real
    agent_plugin template on disk (they are rendered from it every scan)."""
    template_body = frontmatter.load(_template_path_for_kind("agent_plugin")).content
    template_h2s = {line.strip() for line in template_body.splitlines() if line.startswith("## ")}
    for heading in _TEMPLATE_AUTHORITATIVE:
        assert heading in template_h2s, f"{heading!r} not an H2 in the agent_plugin template"


def test_is_file_map_heading() -> None:
    assert _is_file_map_heading("## File map")
    assert _is_file_map_heading("## File map - graph-io")
    assert not _is_file_map_heading("## Narrative")
    assert not _is_file_map_heading("## Purpose")


# ---------------------------------------------------------------------------
# _split_h2_sections (general helper, survives the epic)
# ---------------------------------------------------------------------------


def test_split_h2_sections_round_trips() -> None:
    body = "# Title\n\nintro\n\n## A\na body\n\n## B\nb body\n"
    preamble, sections = _split_h2_sections(body)
    assert preamble == "# Title\n\nintro\n\n"
    assert [h for h, _ in sections] == ["## A", "## B"]
    assert preamble + "".join(chunk for _, chunk in sections) == body


def test_split_h2_sections_no_headings() -> None:
    body = "# Title\n\njust an intro, no H2\n"
    preamble, sections = _split_h2_sections(body)
    assert preamble == body
    assert sections == []


# ---------------------------------------------------------------------------
# Prose sections (exact-heading matched, disk-verbatim)
# ---------------------------------------------------------------------------


def test_merge_identity_is_stable() -> None:
    """merge(t, t) == t — guarantees a no-edit re-scan is byte-identical."""
    body = "# T\n\n## Narrative\n_(placeholder)_\n\n## Purpose\n> TODO\n"
    assert _merge_preserved_sections(body, body) == body


def test_prose_sections_pass_through_byte_identical() -> None:
    """Epic regression property (a) at merge level: prose chunks — including
    `## Narrative`, now plain prose — come from the existing page verbatim."""
    template = "# T\n\n## Narrative\n_(scanner will populate on next scan)_\n\n## Purpose\n> TODO: fill me\n"
    narrative_chunk = "## Narrative\nModel-written prose, exact bytes.\n\n"
    purpose_chunk = "## Purpose\nHuman-written purpose, exact bytes.\n"
    existing = "# T\n\n" + narrative_chunk + purpose_chunk
    out = _merge_preserved_sections(template, existing)
    assert narrative_chunk in out
    assert purpose_chunk in out
    assert "_(scanner will populate on next scan)_" not in out
    assert "> TODO: fill me" not in out


def test_merge_with_empty_existing_returns_template() -> None:
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    assert _merge_preserved_sections(template, "") == template


def test_new_prose_section_in_template_gets_placeholder() -> None:
    """A template H2 the page lacks falls back to the template chunk."""
    existing = "# T\n\n## Narrative\nprose\n\n## Purpose\nkept\n"
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n\n## Public API\n> TODO\n"
    out = _merge_preserved_sections(template, existing)
    assert "## Public API" in out
    assert "kept" in out


def test_merge_order_follows_template() -> None:
    existing = "# T\n\n## Purpose\np\n\n## Narrative\nprose\n"
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    out = _merge_preserved_sections(template, existing)
    assert out.index("## Narrative") < out.index("## Purpose")


def test_user_added_section_trails_template_sections() -> None:
    existing = "# T\n\n## Narrative\nprose\n\n## Purpose\np\n\n## My Notes\ncustom stuff\n"
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    out = _merge_preserved_sections(template, existing)
    assert "## My Notes" in out
    assert "custom stuff" in out
    assert out.index("## Purpose") < out.index("## My Notes")


def test_template_drops_prose_h2_is_preserved() -> None:
    """A prose H2 the template no longer defines is appended — prose is never
    silently dropped."""
    existing = "# T\n\n## Narrative\nprose\n\n## Purpose\nkept human content\n"
    template = "# T\n\n## Narrative\n_p_\n"
    out = _merge_preserved_sections(template, existing)
    assert "## Purpose" in out
    assert "kept human content" in out


# ---------------------------------------------------------------------------
# `## Referenced in wiki` — deterministic, inject-refreshed, disk-carried
# ---------------------------------------------------------------------------


def test_referenced_in_wiki_carried_from_disk() -> None:
    template = "# T\n\n## Referenced in wiki\n_(scanner will populate on next scan)_\n\n## Purpose\n> TODO\n"
    existing = "# T\n\n## Referenced in wiki\n- [[concepts/foo]]\n\n## Purpose\nkept\n"
    out = _merge_preserved_sections(template, existing)
    assert "- [[concepts/foo]]" in out
    assert "_(scanner will populate on next scan)_" not in out


def test_template_drops_referenced_in_wiki_removes_it() -> None:
    """Deterministic sections are template-driven — they never linger when the
    template drops them."""
    existing = "# T\n\n## Referenced in wiki\n- [[x]]\n\n## Purpose\nkept\n"
    template = "# T\n\n## Purpose\n> TODO\n"
    out = _merge_preserved_sections(template, existing)
    assert "## Referenced in wiki" not in out
    assert "kept" in out


# ---------------------------------------------------------------------------
# `## File map` — deterministic, inject-refreshed, prefix-matched, disk-carried
# ---------------------------------------------------------------------------


def test_file_map_carried_from_disk() -> None:
    template = "# T\n\n## File map - foo\n> TODO\n\n## Purpose\n> TODO\n"
    existing = "# T\n\n## File map - foo\n| a | b | c |\n\n## Purpose\nKeep me.\n"
    out = _merge_preserved_sections(template, existing)
    assert "Keep me." in out
    assert "| a | b | c |" in out


def test_file_map_matched_by_prefix_despite_heading_suffix() -> None:
    """The template renders `## File map - <slug>` while the on-disk page
    carries `## File map - <basename>` (the injector's last-writer form). The
    prefix match must preserve the existing filled section and discard the
    slug-suffixed template slot."""
    template = (
        "# T\n\n## Narrative\n_(placeholder)_\n\n"
        "## File map - pkg_pkg-a\n> TODO: <Overview>\n\n"
        "### pkg_pkg-a/\n| `<file>` | file | — TODO |\n"
    )
    existing = (
        "# T\n\n## Narrative\nreal prose\n\n## File map - pkg-a\n### pkg-a/\n| `mod.py` | file | does a thing |\n"
    )
    out = _merge_preserved_sections(template, existing)
    assert "## File map - pkg-a" in out
    assert "## File map - pkg_pkg-a" not in out
    assert "does a thing" in out
    assert "— TODO" not in out


def test_file_map_template_fallback_on_new_page() -> None:
    """A page with no File map yet gets the template's File map chunk."""
    template = "# T\n\n## File map - foo\n> TODO overview\n\n## Purpose\n> TODO\n"
    existing = "# T\n\n## Purpose\nkept\n"
    out = _merge_preserved_sections(template, existing)
    assert "## File map - foo" in out
    assert "> TODO overview" in out
    assert "kept" in out


def test_template_drops_file_map_removes_it() -> None:
    existing = "# T\n\n## Narrative\nprose\n\n## File map - foo\n| a | b | c |\n\n## Purpose\nkept\n"
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    out = _merge_preserved_sections(template, existing)
    assert "## File map" not in out
    assert "kept" in out


# ---------------------------------------------------------------------------
# Template-authoritative data tables (the six agent_plugin headings)
# ---------------------------------------------------------------------------

_AGENT_PLUGIN_TEMPLATE = (
    "# TestPlugin\n\n"
    "## Narrative\n_(scanner will populate on next scan)_\n\n"
    "## Referenced in wiki\n_(scanner will populate on next scan)_\n\n"
    "## Purpose\n> TODO: fill me\n\n"
    "## Commands\n| Command | Description |\n| --- | --- |\n| cmd-A | desc-A |\n| cmd-B | desc-B |\n\n"
    "## Agents\n| Agent | Model | Tools | Description |\n| --- | --- | --- | --- |\n"
    "| agent-1 | sonnet | t1 | Agent one |\n\n"
    "## Skills\n| Skill | Description |\n| --- | --- |\n| skill-X | Skill X desc |\n\n"
    "## Scripts\n| Script | Language |\n| --- | --- |\n| run.sh | bash |\n\n"
    "## Hooks\n| Event | Matchers |\n| --- | --- |\n| PostToolUse | foo |\n\n"
    "## MCP servers\n| Server | Command |\n| --- | --- |\n| srv | npx srv |\n\n"
    "## How it fits together\n> TODO: relationships\n"
)

_AGENT_PLUGIN_EXISTING_STALE = (
    "# TestPlugin\n\n"
    "## Narrative\nold prose\n\n"
    "## Referenced in wiki\n- [[some-page]]\n\n"
    "## Purpose\nHuman-written purpose.\n\n"
    "## Commands\n| Command | Description |\n| --- | --- |\n| cmd-X | desc-X |\n| cmd-Y | desc-Y |\n\n"
    "## Agents\n| Agent | Model | Tools | Description |\n| --- | --- | --- | --- |\n"
    "| agent-old | haiku | t0 | Old agent |\n\n"
    "## Skills\n| Skill | Description |\n| --- | --- |\n| skill-OLD | stale |\n\n"
    "## Scripts\n| Script | Language |\n| --- | --- |\n| old.sh | bash |\n\n"
    "## Hooks\n| Event | Matchers |\n| --- | --- |\n| OldEvent | bar |\n\n"
    "## MCP servers\n| Server | Command |\n| --- | --- |\n| old-srv | npx old |\n\n"
    "## How it fits together\n> TODO: relationships\n"
)


def test_stale_data_table_never_wins() -> None:
    """Epic regression property (b) at merge level: template-authoritative
    sections take the fresh template render; stale on-disk rows are discarded."""
    out = _merge_preserved_sections(_AGENT_PLUGIN_TEMPLATE, _AGENT_PLUGIN_EXISTING_STALE)
    assert "cmd-A" in out
    assert "cmd-B" in out
    assert "cmd-X" not in out
    assert "cmd-Y" not in out
    assert "agent-old" not in out
    assert "skill-OLD" not in out


def test_data_tables_dont_disturb_prose_or_disk_carried_sections() -> None:
    out = _merge_preserved_sections(_AGENT_PLUGIN_TEMPLATE, _AGENT_PLUGIN_EXISTING_STALE)
    assert "Human-written purpose." in out  # prose preserved
    assert "> TODO: fill me" not in out
    assert "old prose" in out  # Narrative (prose) disk-carried
    assert "- [[some-page]]" in out  # Referenced in wiki disk-carried


def test_data_tables_user_added_h2_still_trails() -> None:
    existing_with_extra = _AGENT_PLUGIN_EXISTING_STALE + "## Notes\nmy notes here\n"
    out = _merge_preserved_sections(_AGENT_PLUGIN_TEMPLATE, existing_with_extra)
    assert "## Notes" in out
    assert "my notes here" in out
    assert out.index("## How it fits together") < out.index("## Notes")


def test_agent_plugin_merge_idempotent() -> None:
    assert _merge_preserved_sections(_AGENT_PLUGIN_TEMPLATE, _AGENT_PLUGIN_TEMPLATE) == _AGENT_PLUGIN_TEMPLATE


def test_disk_only_data_table_never_lingers() -> None:
    """A data-table heading on a page whose template does not define it (e.g. a
    hand-added `## Commands` on a package page) is dropped, matching the
    template-authoritative contract: these sections are never sourced from disk."""
    existing = "# T\n\n## Purpose\np\n\n## Commands\n| Command | Description |\n| --- | --- |\n| old | x |\n"
    template = "# T\n\n## Purpose\n> TODO\n"
    out = _merge_preserved_sections(template, existing)
    assert "## Commands" not in out
