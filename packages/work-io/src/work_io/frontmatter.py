"""Frontmatter parse/emit for work item pages."""

from __future__ import annotations

import yaml


def parse(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Raises ValueError on malformed input."""
    if not text.startswith("---"):
        raise ValueError("no frontmatter block found: text must start with ---")
    rest = text[3:]
    if "\n---" not in rest:
        raise ValueError("unclosed frontmatter block: no closing ---")
    idx = rest.index("\n---")
    fm_text = rest[:idx].strip()
    body = rest[idx + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    try:
        fm = yaml.safe_load(fm_text) if fm_text else {}
    except yaml.YAMLError as e:
        raise ValueError(f"malformed frontmatter YAML: {e}") from e
    if fm is None:
        fm = {}
    if not isinstance(fm, dict):
        raise ValueError(f"frontmatter must be a YAML mapping, got {type(fm).__name__}")
    return fm, body


def emit(fm: dict) -> str:
    """Serialize frontmatter dict to a fenced YAML block (--- ... ---)."""
    content = yaml.safe_dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return f"---\n{content}---"
