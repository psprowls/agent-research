"""Derived-children refresh: rewrite parents' `children` frontmatter from child `parent` keys.

The child's `parent` key is the single source of truth; `children` is a
tool-refreshed projection. Hand-edits to `children` are overwritten. Invoked
from graph-wiki-core's run_work_regen_index — the single choke point already
called by file/advance/archive — so the list self-heals on every mutation.

The rewrite is a surgical in-place splice on the frontmatter block — modeled on
work_io.doc_pointers, which faces the same problem (mutating a page as a side
effect of some other action). It never reserializes the whole frontmatter
through yaml.safe_dump, so key order, formatting (flow vs. block lists, quote
style), and comments on every OTHER key are preserved byte-for-byte; only the
`children` key's own line(s) change.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from work_io.hierarchy import children_map
from work_io.lifecycle_lint import load_items

# `children` sits adjacent to the other hierarchy keys per wiki-schema.md's
# work-page key order (affects, parent, depends_on): insert after whichever of
# these occurs LAST in the file's actual key order (not a fixed priority).
_ANCHOR_KEYS = frozenset({"depends_on", "parent", "affects"})

# Frontmatter-level keys sit at column 0 (block-sequence items emitted by
# yaml.safe_dump also sit at column 0, as `- item`, so they never match this
# key-line pattern and are correctly treated as part of the preceding key's
# block). Matching is further restricted to the frontmatter span, so nothing
# in the body can be mistaken for a key line.
_KEY_LINE = re.compile(r"^([A-Za-z_][\w.-]*):", re.MULTILINE)


def _frontmatter_span(text: str) -> tuple[int, int] | None:
    """Return (start, end) char offsets of the frontmatter block body, or None.

    Mirrors work_io.doc_pointers._frontmatter_span: the block is the region
    between the opening ``---\\n`` fence and the closing ``\\n---`` fence.
    """
    if not text.startswith("---\n"):
        return None
    close = text.find("\n---", 4)
    if close == -1:
        return None
    return 4, close + 1


def _key_blocks(fm_text: str) -> list[tuple[str, int, int]]:
    """Return (key, start, end) offsets of each top-level key's block within fm_text.

    A key's block spans from its own line through the line before the next
    top-level key line (or the end of fm_text), so it includes any nested
    block-sequence lines (`- item`) or wrapped scalar continuation lines that
    belong to it.
    """
    matches = list(_KEY_LINE.finditer(fm_text))
    blocks: list[tuple[str, int, int]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(fm_text)
        blocks.append((m.group(1), start, end))
    return blocks


def _splice_children(fm_text: str, children: list[str]) -> str:
    """Remove any existing `children` block and insert the derived one.

    Insertion point is immediately after whichever of `depends_on`/`parent`/
    `affects` occurs last (by file position) among those present, or at the
    end of the frontmatter block when none are present. When `children` is
    empty, the key is simply removed (omitted) rather than reinserted. Every
    other byte of fm_text is left untouched.
    """
    blocks = _key_blocks(fm_text)
    existing = next(((s, e) for k, s, e in blocks if k == "children"), None)
    if existing is not None:
        s, e = existing
        fm_text = fm_text[:s] + fm_text[e:]
        blocks = _key_blocks(fm_text)

    if not children:
        return fm_text

    insertion = yaml.safe_dump({"children": children}, default_flow_style=False, sort_keys=False)
    anchor_ends = [e for k, _s, e in blocks if k in _ANCHOR_KEYS]
    insert_at = max(anchor_ends) if anchor_ends else len(fm_text)
    return fm_text[:insert_at] + insertion + fm_text[insert_at:]


def refresh_children(work_dir: Path) -> list[str]:
    """Rewrite active parent pages whose derived `children` list changed.

    Children are derived across active AND archived items (the relationship is
    permanent); only active parent pages are rewritten — archived pages are
    frozen. The rewrite is a text-level splice (see _splice_children): only the
    `children` key's own line(s) change, everything else on the page — body,
    other frontmatter keys, their formatting and order — is byte-preserved.
    Returns the slugs rewritten. IO errors propagate (regen-index is not
    best-effort).
    """
    active = load_items(work_dir)
    archived = load_items(work_dir / "_archive")
    view = [
        {"slug": it["slug"], "parent": it["fm"].get("parent"), "opened": str(it["fm"].get("opened", ""))}
        for it in active + archived
    ]
    derived = children_map(view)
    rewritten: list[str] = []
    for it in active:
        slug = it["slug"]
        expected = derived.get(slug, [])
        current = [str(c) for c in (it["fm"].get("children") or [])]
        if current == expected:
            continue
        path = work_dir / f"{slug}.md"
        text = path.read_text(encoding="utf-8")
        span = _frontmatter_span(text)
        if span is None:
            continue
        fm_start, fm_end = span
        new_fm_text = _splice_children(text[fm_start:fm_end], expected)
        path.write_text(text[:fm_start] + new_fm_text + text[fm_end:], encoding="utf-8")
        rewritten.append(slug)
    return rewritten
