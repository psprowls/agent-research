"""obsidian_render lint checks: angle brackets, callouts, wikilinks, table pipes."""

from __future__ import annotations

from wiki_io.lint.obsidian_render import check


def _pages(**text_by_slug):
    """Build a pages dict shaped like mechanical_scan's output."""
    return {slug: {"path": f"{slug}.md", "fm": {}, "text": text} for slug, text in text_by_slug.items()}


def _rule_ids(findings):
    return sorted(f.rule_id for f in findings)


# ---- angle brackets -------------------------------------------------------


def test_bare_angle_bracket_flagged():
    findings = check(_pages(index="see the `wiki/work/` dir written as <slug> here\n"))
    assert [f.rule_id for f in findings] == ["obsidian-render-angle-bracket"]
    assert findings[0].severity == "warn"
    assert findings[0].message.startswith("index:1:")
    assert "<slug>" in findings[0].message


def test_real_html_and_autolinks_and_code_pass():
    pages = _pages(
        a="line <br> and <br/> and <div>x</div> and </span>\n",
        b="an autolink <https://example.com> is fine\n",
        c="inline code `<slug>` is fine\n",
        d="```\n<slug> inside a fence\n```\n",
        e="<!-- a comment <slug> --> is fine\n",
    )
    assert check(pages) == []


def test_templates_dir_excluded():
    pages = _pages(**{".templates/entity": "placeholder <slug> token\n"})
    assert check(pages) == []
