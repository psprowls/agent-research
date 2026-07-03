"""Obsidian render-correctness lint: catches markdown that breaks Obsidian's
renderer. Four rules over one markdown-it-py parse per page — bare angle-bracket
placeholders (html_inline/html_block tags that aren't real HTML Obsidian renders),
malformed callouts, malformed wikilinks/embeds, and unescaped table pipes.

First module under wiki_io/lint/ to return structured LintFinding (rule_id,
severity, slug, message) rather than list[str] — four rule types with two
severities don't fit the "everything is WARN" plain-string convention. Mirrors
the LintFinding shape defined in guidance_io/lint.py and work_io/lifecycle_lint.py
(defined locally to avoid a cross-package dependency).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from markdown_it import MarkdownIt

GROUP = "obsidian_render"


@dataclass
class LintFinding:
    rule_id: str
    severity: Literal["error", "warn", "info"]
    slug: str
    message: str


# Hand-maintained allowlist of HTML tag names Obsidian actually renders inline
# or as blocks. Any other syntactically-valid tag name (e.g. <slug>) is almost
# always an un-backticked placeholder and breaks rendering. Kept deliberately
# generous — false negatives (a rare real tag we forgot) are cheaper than
# false positives on prose.
_HTML_ALLOWLIST = frozenset(
    {
        "a",
        "abbr",
        "audio",
        "b",
        "blockquote",
        "br",
        "center",
        "cite",
        "code",
        "del",
        "details",
        "div",
        "em",
        "font",
        "hr",
        "i",
        "iframe",
        "img",
        "ins",
        "kbd",
        "li",
        "mark",
        "ol",
        "p",
        "pre",
        "s",
        "small",
        "source",
        "span",
        "strong",
        "sub",
        "summary",
        "sup",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "u",
        "ul",
        "video",
    }
)

# ``<`` + optional ``/`` + tag name (letter then alnum/hyphen). Matches the
# CommonMark raw-HTML tag-name grammar that produces the html_inline/html_block
# tokens in the first place.
_TAG_RE = re.compile(r"^</?([a-zA-Z][a-zA-Z0-9-]*)")


def _make_parser() -> MarkdownIt:
    # commonmark preset + the core `table` block rule. NOT "gfm-like" (enables
    # linkify → ModuleNotFoundError) and NOT mdit-py-plugins (not installed).
    return MarkdownIt("commonmark").enable("table")


def _is_excluded(slug: str) -> bool:
    # Mirror mechanical_scan's dotdir filter so .templates/ (and .obsidian/,
    # .graph/, …) never trip render rules even if a caller passes them in.
    return any(part.startswith(".") for part in slug.split("/"))


def check(pages: dict) -> list[LintFinding]:
    """Lint every page for Obsidian render-breakage. Empty list == clean."""
    findings: list[LintFinding] = []
    parser = _make_parser()
    for slug, page in pages.items():
        if _is_excluded(slug):
            continue
        text = page.get("text", "")
        if not text:
            continue
        tokens = parser.parse(text)
        findings.extend(_check_angle_brackets(slug, tokens))
        # rules 2-4 appended in later tasks
    return findings


def _tag_name(html: str) -> str | None:
    """Extract a tag name from an html_inline/html_block chunk, or None for
    comments / non-tag fragments."""
    stripped = html.lstrip()
    if stripped.startswith("<!--"):
        return None
    m = _TAG_RE.match(stripped)
    return m.group(1).lower() if m else None


def _check_angle_brackets(slug: str, tokens) -> list[LintFinding]:
    out: list[LintFinding] = []
    for tok in _walk(tokens):
        if tok.type == "html_block":
            line = (tok.map[0] + 1) if tok.map else 1
            _flag_html(out, slug, tok.content, line)
        elif tok.type == "inline":
            line = (tok.map[0] + 1) if tok.map else 1
            for child in tok.children or []:
                if child.type == "html_inline":
                    _flag_html(out, slug, child.content, line)
    return out


def _flag_html(out: list[LintFinding], slug: str, html: str, line: int) -> None:
    name = _tag_name(html)
    if name is None or name in _HTML_ALLOWLIST:
        return
    frag = html.strip().splitlines()[0][:40]
    out.append(
        LintFinding(
            "obsidian-render-angle-bracket",
            "warn",
            slug,
            f"{slug}:{line}: bare <{name}> renders as raw HTML — wrap in backticks: `{frag}`",
        )
    )


def _walk(tokens):
    """Yield every token depth-first (block tokens carry inline children in
    `.children`, which _check_* helpers descend explicitly, so this only needs
    the top-level stream)."""
    yield from tokens
