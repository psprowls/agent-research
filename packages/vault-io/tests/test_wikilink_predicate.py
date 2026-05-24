"""VAULT-06: _is_placeholder_target predicate.

Ported from lattice_wiki_core/tests/test_lint_wikilink_placeholders.py.
The predicate lives at vault_io.lint.common._is_placeholder_target in the port.
"""

from __future__ import annotations

import unittest

from vault_io.lint.common import WIKILINK_RE, _is_placeholder_target


class IsPlaceholderTargetTest(unittest.TestCase):
    """Tests for placeholder/template wikilink detection."""

    def test_detects_ellipsis_as_placeholder(self):
        """Target containing ... is recognized as placeholder template."""
        self.assertTrue(_is_placeholder_target("wiki/packages/..."))
        self.assertTrue(_is_placeholder_target("..."))
        self.assertTrue(_is_placeholder_target("wiki/..."))

    def test_detects_angle_brackets_as_placeholder(self):
        """Target containing < or > is recognized as placeholder template."""
        self.assertTrue(_is_placeholder_target("wiki/<package>"))
        self.assertTrue(_is_placeholder_target("<package>"))
        self.assertTrue(_is_placeholder_target("work/<slug>"))
        self.assertTrue(_is_placeholder_target("wiki/adrs/<adr_id>"))

    def test_rejects_normal_wiki_links(self):
        """Normal wikilinks are not placeholders."""
        self.assertFalse(_is_placeholder_target("wiki/adrs/index"))
        self.assertFalse(_is_placeholder_target("wiki/packages/foo"))
        self.assertFalse(_is_placeholder_target("work/2026-05-10-slug"))
        self.assertFalse(_is_placeholder_target("wiki/domains/bar"))

    def test_rejects_empty_and_simple_targets(self):
        """Empty and simple targets are not placeholders."""
        self.assertFalse(_is_placeholder_target(""))
        self.assertFalse(_is_placeholder_target("index"))
        self.assertFalse(_is_placeholder_target("page"))


class WikilinkRegexTest(unittest.TestCase):
    """WIKILINK_RE must capture the target only, dropping anchor and alias —
    including the ``\\|`` table-cell-escaped alias separator."""

    def _target(self, text: str) -> str:
        m = WIKILINK_RE.search(text)
        assert m is not None, f"no wikilink matched in {text!r}"
        return m.group(1).strip()

    def test_bare_link(self) -> None:
        self.assertEqual(self._target("[[foo]]"), "foo")

    def test_aliased_link(self) -> None:
        self.assertEqual(self._target("[[foo|bar]]"), "foo")

    def test_anchored_link(self) -> None:
        self.assertEqual(self._target("[[foo#section]]"), "foo")

    def test_table_cell_escaped_alias(self) -> None:
        """``[[target\\|alias]]`` inside a markdown table cell must capture
        ``target`` — not ``target\\``. Regression for the 6 false-positive
        broken links reported by /graph-wiki:lint on 2026-05-23."""
        self.assertEqual(
            self._target(r"[[wiki/concepts/orchestrator-agent-anatomy\|orchestrator]]"),
            "wiki/concepts/orchestrator-agent-anatomy",
        )

    def test_table_cell_escaped_alias_with_anchor(self) -> None:
        self.assertEqual(
            self._target(r"[[foo#bar\|alias]]"),
            "foo",
        )


if __name__ == "__main__":
    unittest.main()
