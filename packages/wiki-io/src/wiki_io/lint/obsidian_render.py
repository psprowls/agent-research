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

from wiki_io.lint.common import WIKILINK_RE, _split_pipes

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

# Obsidian's built-in callout types (lowercased). Unknown types render with a
# default icon in Obsidian but are usually typos, so they warn.
_CALLOUT_TYPES = frozenset(
    {
        "note",
        "abstract",
        "summary",
        "tldr",
        "info",
        "todo",
        "tip",
        "hint",
        "important",
        "success",
        "check",
        "done",
        "question",
        "help",
        "faq",
        "warning",
        "caution",
        "attention",
        "failure",
        "fail",
        "missing",
        "danger",
        "error",
        "bug",
        "example",
        "quote",
        "cite",
    }
)

# A well-formed callout header: ``[!type]`` optional fold marker (+/-) then an
# optional space-separated title. Anchored to the start of the (already
# ``> ``-stripped) first blockquote line.
_CALLOUT_OK_RE = re.compile(r"^\[!([a-zA-Z][a-zA-Z0-9-]*)\][+-]?(?:\s.*)?$")
# The "attempted callout" trigger — first line opens with [! or [![.
_CALLOUT_ATTEMPT_RE = re.compile(r"^\[!?\[?!")


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
        src_lines = text.splitlines()
        tokens = parser.parse(text)
        findings.extend(_check_angle_brackets(slug, tokens))
        findings.extend(_check_callouts(slug, tokens, src_lines))
        findings.extend(_check_wikilinks(slug, tokens))
        findings.extend(_check_table_pipes(slug, tokens, src_lines))
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


def _check_callouts(slug: str, tokens, src_lines) -> list[LintFinding]:
    out: list[LintFinding] = []
    for tok in tokens:
        if tok.type != "blockquote_open" or not tok.map:
            continue
        line0 = tok.map[0]  # 0-indexed line of the ``>`` line
        raw = src_lines[line0] if line0 < len(src_lines) else ""
        first = raw.lstrip()
        if first.startswith(">"):
            first = first[1:].lstrip()
        if not _CALLOUT_ATTEMPT_RE.match(first):
            continue  # ordinary blockquote — not a callout attempt
        m = _CALLOUT_OK_RE.match(first)
        if m is None:
            out.append(
                LintFinding(
                    "obsidian-render-callout",
                    "warn",
                    slug,
                    f"{slug}:{line0 + 1}: malformed callout header `{first[:40]}` — expected `> [!type] title`",
                )
            )
        elif m.group(1).lower() not in _CALLOUT_TYPES:
            out.append(
                LintFinding(
                    "obsidian-render-callout",
                    "warn",
                    slug,
                    f"{slug}:{line0 + 1}: unknown callout type `{m.group(1)}`",
                )
            )
    return out


# An opening ``[[`` or ``![[`` — used to find candidate spans to validate.
_WIKILINK_OPEN_RE = re.compile(r"!?\[\[")


def _check_wikilinks(slug: str, tokens) -> list[LintFinding]:
    out: list[LintFinding] = []
    for tok in tokens:
        if tok.type != "inline" or not tok.map:
            continue
        line = tok.map[0] + 1
        # Join only text children — code_inline / autolink children are dropped,
        # so `[[foo` inside backticks never reaches the scan.
        text = "".join(c.content for c in (tok.children or []) if c.type == "text")
        for m in _WIKILINK_OPEN_RE.finditer(text):
            # Anchor the candidate span at the ``[[`` (the last two chars of the
            # match), so an ``![[…]]`` embed is validated from its brackets, not
            # from the leading ``!`` — otherwise WIKILINK_RE.match would fail on
            # the ``!`` and false-flag a valid embed.
            rest = text[m.end() - 2 :]
            valid = WIKILINK_RE.match(rest)
            if valid is None:
                out.append(
                    LintFinding(
                        "obsidian-render-wikilink",
                        "error",
                        slug,
                        f"{slug}:{line}: unbalanced wikilink `{rest[:30]}` — missing closing ]]",
                    )
                )
            elif not valid.group(1).strip():
                out.append(
                    LintFinding(
                        "obsidian-render-wikilink",
                        "error",
                        slug,
                        f"{slug}:{line}: empty wikilink target `{valid.group(0)}`",
                    )
                )
    return out


def _check_table_pipes(slug: str, tokens, src_lines) -> list[LintFinding]:
    out: list[LintFinding] = []
    for tok in tokens:
        if tok.type != "table_open" or not tok.map:
            continue
        start, end = tok.map  # half-open line range for the whole table
        rows = [i for i in range(start, min(end, len(src_lines))) if src_lines[i].lstrip().startswith("|")]
        if len(rows) < 2:
            continue
        header_cols = len(_split_pipes(src_lines[rows[0]].strip()))
        # rows[1] is the |---|---| delimiter; body rows start at rows[2]
        for i in rows[2:]:
            if len(_split_pipes(src_lines[i].strip())) > header_cols:
                out.append(
                    LintFinding(
                        "obsidian-render-table-pipe",
                        "warn",
                        slug,
                        f"{slug}:{i + 1}: unescaped `|` in a table cell "
                        "(escape as `\\|`) — row splits into too many columns",
                    )
                )
    return out


def _walk(tokens):
    """Yield every token depth-first (block tokens carry inline children in
    `.children`, which _check_* helpers descend explicitly, so this only needs
    the top-level stream)."""
    yield from tokens
