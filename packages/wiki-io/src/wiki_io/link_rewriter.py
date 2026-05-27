"""Markdown-aware wikilink rewriter for the v1.8 vault migration (Phase 46).

Pure-function core. Plan 02 adds ``build_rewrite_table`` and ``rewrite_vault``.
Plan 03 wires this into the ``cg migrate-vault`` CLI subcommand.

CONTEXT.md decisions (see .planning/phases/46-inbound-link-migration-cutover/46-CONTEXT.md):
    D-01 regex with position-aware code-region masking (no markdown-it-py)
    D-02 explicit fixture suite for edge cases
    D-13 5 curated lanes (concepts, adrs, architecture, sources, work) — applied by rewrite_vault
    D-14 wiki/ root files NOT rewritten — enforced by rewrite_vault's lane scope
"""

from __future__ import annotations

from wiki_io.lint.common import (
    FENCED_CODE_RE,
    INLINE_CODE_RE,
    WIKILINK_RE,
    indented_code_spans,
)


# ----------------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------------


def _code_region_spans(text: str) -> list[tuple[int, int]]:
    """Return sorted, merged spans covering fenced + inline + indented code regions.

    The union covers every position whose surrounding context is code.
    Wikilinks whose start position falls inside any returned span are SKIPPED
    by :func:`rewrite_text`.
    """
    spans: list[tuple[int, int]] = []
    # Fenced
    for m in FENCED_CODE_RE.finditer(text):
        spans.append((m.start(), m.end()))
    # Inline — find on whole text; if an inline match falls inside a fenced
    # span, it's harmless (already covered by the merge below).
    for m in INLINE_CODE_RE.finditer(text):
        spans.append((m.start(), m.end()))
    # Indented
    spans.extend(indented_code_spans(text))
    if not spans:
        return []
    spans.sort()
    # Merge overlapping/adjacent.
    merged: list[tuple[int, int]] = [spans[0]]
    for s, e in spans[1:]:
        ms, me = merged[-1]
        if s <= me:
            merged[-1] = (ms, max(me, e))
        else:
            merged.append((s, e))
    return merged


def _is_inside_any_span(pos: int, spans: list[tuple[int, int]]) -> bool:
    """O(N) scan — N is tiny for typical markdown docs.

    Spans are sorted ascending, so we can short-circuit once we pass the
    candidate position.
    """
    for s, e in spans:
        if s <= pos < e:
            return True
        if pos < s:
            return False
    return False


def _rebuild_wikilink(original: str, old_target: str, new_slug: str) -> str:
    """Replace ``old_target`` with ``new_slug`` in the wikilink, preserving anchor + alias.

    ``WIKILINK_RE`` guarantees the captured target appears at the start of the
    bracketed content. ``original.replace(old_target, new_slug, 1)`` is
    sufficient because:

    - the target appears exactly once at the lead position
    - the ``, 1`` limits replacement to the first occurrence (defensive
      against an alias whose text happens to equal the target).
    """
    return original.replace(old_target, new_slug, 1)


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------


def rewrite_text(text: str, table: dict[str, str | None]) -> tuple[str, int]:
    """Rewrite old-layout wikilinks to new-layout slugs in ``text``.

    Args:
        text: The markdown content of one file.
        table: Mapping from old-layout target string to new-layout slug.
            A ``None`` value means "discovered as inbound but unresolvable" —
            the wikilink is SKIPPED. A missing key also means SKIP.

    Returns:
        ``(new_text, rewrite_count)``. ``rewrite_count`` is the number of
        wikilinks actually rewritten (NOT the number of wikilink matches).

    Behavior:
        - Wikilinks inside fenced code blocks, inline code spans, or indented
          code blocks are SKIPPED (their bytes are preserved byte-identical).
        - Alias (``|alias``) and anchor (``#anchor``) suffixes are preserved.
        - Idempotent: a second call on already-rewritten text yields count == 0.

    See CONTEXT.md D-01 / D-02 for the decisions backing this design.
    """
    code_spans = _code_region_spans(text)
    parts: list[str] = []
    cursor = 0
    count = 0
    for m in WIKILINK_RE.finditer(text):
        if _is_inside_any_span(m.start(), code_spans):
            continue
        target = m.group(1).strip()
        new_slug = table.get(target)
        if new_slug is None:
            # Missing key OR explicit None — skip silently.
            continue
        # Splice text up to match start, then the rebuilt link.
        parts.append(text[cursor:m.start()])
        parts.append(_rebuild_wikilink(m.group(0), target, new_slug))
        cursor = m.end()
        count += 1
    parts.append(text[cursor:])
    return ("".join(parts), count)
