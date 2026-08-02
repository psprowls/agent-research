"""Shared real-YAML frontmatter parsing for wiki pages.

Single replacement for the naive line-based parsers that previously lived in
``lint/common.py``, ``update_index.py``, ``index_generator.py``, and the
block-list workaround in ``graph_analyzer.py``. Values come back as real YAML
types (``str``, ``int``, ``bool``, ``datetime.date``, ``list``, ``None``) —
consumers must not assume strings.
"""

from __future__ import annotations

import re

import frontmatter as _frontmatter
import yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse(text: str) -> tuple[dict, str | None]:
    """Parse YAML frontmatter. Returns ``(metadata, error)``.

    ``error`` is ``None`` on success; on malformed YAML returns
    ``({}, "<message>")``. A page with no frontmatter block returns
    ``({}, None)`` — absence is not an error. Never raises.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, None
    try:
        post = _frontmatter.loads(text)
    except Exception as exc:  # noqa: BLE001 — yaml scanner/parser errors and friends
        return {}, str(exc)
    metadata = post.metadata
    if not isinstance(metadata, dict):
        return {}, f"frontmatter is not a YAML mapping: {type(metadata).__name__}"
    # Verify that the raw YAML is actually a mapping (not a list or scalar)
    # because python-frontmatter silently returns {} for non-mapping YAML
    fm_text = match.group(1)
    try:
        raw_parsed = yaml.safe_load(fm_text)
        if raw_parsed is not None and not isinstance(raw_parsed, dict):
            return {}, f"frontmatter is not a YAML mapping: {type(raw_parsed).__name__}"
    except Exception as exc:  # noqa: BLE001
        return {}, str(exc)
    return metadata, None
