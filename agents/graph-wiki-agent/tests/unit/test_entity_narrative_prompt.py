"""Phase 45 D-05: unit tests for build_entity_narrative_prompt."""

from __future__ import annotations

from types import SimpleNamespace

from graph_wiki_agent.commands.scan import build_entity_narrative_prompt


def _node(uri: str = "pkg:agent-research/foo", name: str = "foo"):
    return SimpleNamespace(name=name, attrs={"uri": uri})


class TestSystemMessage:
    def test_system_bans_frontmatter(self):
        sys, _ = build_entity_narrative_prompt(_node(), "package", "", {})
        assert "no YAML frontmatter" in sys

    def test_system_bans_h1(self):
        sys, _ = build_entity_narrative_prompt(_node(), "package", "", {})
        assert "no H1" in sys

    def test_system_references_narrative_anchor(self):
        sys, _ = build_entity_narrative_prompt(_node(), "package", "", {})
        assert "## Narrative" in sys

    def test_system_mentions_length_guidance(self):
        sys, _ = build_entity_narrative_prompt(_node(), "package", "", {})
        assert "2-4" in sys or "two to four" in sys.lower()


class TestHumanMessage:
    def test_includes_uri_kind_name(self):
        _, human = build_entity_narrative_prompt(_node("pkg:x/y", "y"), "package", "", {})
        assert "Entity URI: pkg:x/y" in human
        assert "Kind: package" in human
        assert "Name: y" in human

    def test_renders_list_relations_as_csv(self):
        _, human = build_entity_narrative_prompt(
            _node(),
            "package",
            "",
            {"depends_on": ["pkg:a", "pkg:b"], "test_suites": ["t1"]},
        )
        assert "Depends on: pkg:a, pkg:b" in human
        assert "Test suites: t1" in human

    def test_skips_empty_relations(self):
        _, human = build_entity_narrative_prompt(
            _node(),
            "package",
            "",
            {"depends_on": [], "test_suites": None, "language": ""},
        )
        assert "Depends on" not in human
        assert "Test suites" not in human
        assert "Language" not in human

    def test_includes_file_map_for_package(self):
        _, human = build_entity_narrative_prompt(
            _node(), "package", "src/\n  foo.py\n  bar.py\n", {},
        )
        assert "File listing" in human
        assert "src/" in human
        assert "do NOT include this in your output" in human

    def test_omits_file_map_for_non_package(self):
        _, human = build_entity_narrative_prompt(
            _node(uri="domain:x", name="x"),
            "domain",
            "src/\n  irrelevant.py\n",
            {},
        )
        assert "File listing" not in human

    def test_closing_instruction(self):
        _, human = build_entity_narrative_prompt(_node(), "package", "", {})
        assert "Write the narrative body" in human
        assert "prose only" in human

    def test_relations_render_scalar(self):
        _, human = build_entity_narrative_prompt(
            _node(uri="domain:foo", name="foo"),
            "domain",
            "",
            {"parent_domain": "root"},
        )
        assert "Parent domain: root" in human


def test_returns_tuple_of_two_strings():
    result = build_entity_narrative_prompt(_node(), "package", "", {})
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], str)
