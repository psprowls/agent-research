"""Escaping helpers for splicing raw (non-markdown) text into rendered wiki pages.

Frontmatter values (`summary`, file-map `Description` cells, directory
overviews) are plain prose, not markdown -- a bare literal `<name>` or `<w1>`
token in that text is indistinguishable from an unclosed HTML tag to
Obsidian's renderer (see `wiki_io/lint/obsidian_render.py`'s
`obsidian-render-angle-bracket` check, which flags exactly this). Escape
before splicing so placeholder-shaped prose renders literally instead of
vanishing as unrecognized HTML.
"""

from __future__ import annotations


def escape_angle_brackets(text: str) -> str:
    """Backslash-escape literal ``<``/``>`` so CommonMark renders them
    literally instead of attempting to parse an HTML tag.

    Safe to apply to plain prose (frontmatter values, docstring-derived
    descriptions) that carries no intentional markdown of its own.
    """
    return text.replace("<", "\\<").replace(">", "\\>")
