"""format_wiki_lint rendering, incl. the Obsidian render section."""

from __future__ import annotations

from types import SimpleNamespace

from graph_wiki_cli.lint_format import format_wiki_lint


def _blank_result(**over):
    base = dict(
        wiki="/ws/wiki",
        total_pages=1,
        open_proposals=0,
        orphans=[],
        broken_links=[],
        stale=[],
        missing_frontmatter=[],
        unparseable_frontmatter=[],
        source_path_drift=[],
        duplicate_titles={},
        log_gap=None,
        file_map_drift=[],
        package_sync_drift=[],
        domain_placement=[],
        workflow_hints=[],
        concept_kind=[],
        scanner_heading_drift=[],
        semantic_findings={},
        guidance_lint_findings=[],
        obsidian_render_findings=[],
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_obsidian_render_section_clean():
    out = "\n".join(format_wiki_lint(_blank_result()))
    assert "[OK] Obsidian render: 0" in out


def test_unparseable_frontmatter_section_clean():
    out = "\n".join(format_wiki_lint(_blank_result()))
    assert "[OK] Unparseable frontmatter: 0" in out


def test_unparseable_frontmatter_section_with_findings():
    entries = [("concepts/broken", "while parsing a flow sequence: did not find expected ',' or ']'")]
    out = "\n".join(format_wiki_lint(_blank_result(unparseable_frontmatter=entries)))
    assert "[WARN] Unparseable frontmatter: 1" in out
    assert "concepts/broken: while parsing a flow sequence" in out


def test_obsidian_render_section_with_findings():
    findings = [
        {
            "rule_id": "obsidian-render-angle-bracket",
            "severity": "warn",
            "slug": "index",
            "message": "index:250: bare <slug> renders as raw HTML",
        },
        {
            "rule_id": "obsidian-render-wikilink",
            "severity": "error",
            "slug": "foo",
            "message": "foo:3: unbalanced wikilink",
        },
    ]
    out = "\n".join(format_wiki_lint(_blank_result(obsidian_render_findings=findings)))
    assert "[WARN] Obsidian render: 2" in out
    assert "bare <slug>" in out and "unbalanced wikilink" in out
