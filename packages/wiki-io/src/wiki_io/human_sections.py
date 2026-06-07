"""Human-owned H2 section primitives for TODO-style wiki placeholders.

These helpers identify human-owned sections that still carry placeholder prose
and safely replace only those bodies when a narrated scan later fills them in.
Scanner-owned H2 sections remain outside this surface so real scanner prose and
data tables are never rewritten by accident.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from wiki_io.entity_writer import SCANNER_DATA_HEADINGS, _is_scanner_owned_heading, _split_h2_sections

_TODO_HEAD_RE = re.compile(r"^(?:>\s*)?(?:[-*]\s*)?(?:TODO\b|[-\u2014]\s*TODO\b)", re.IGNORECASE)
_FRONTMATTER_KIND_RE = re.compile(r"^kind:\s*(.+?)\s*$")


@dataclass(frozen=True)
class HumanTodoSection:
    heading: str
    full_heading: str
    body: str


def is_todo_like_body(body: str) -> bool:
    """Return True when ``body`` still looks like a placeholder."""
    cleaned = body.strip()
    if not cleaned:
        return True
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not _TODO_HEAD_RE.match(stripped):
            return False
    return True


def find_todo_human_sections(text: str, *, entity_kind: str) -> list[HumanTodoSection]:
    """Return human-owned H2 sections whose bodies still look like TODOs."""
    _preamble, sections = _split_h2_sections(text)
    out: list[HumanTodoSection] = []
    for full_heading, chunk in sections:
        if _is_scanner_owned_heading(full_heading):
            continue
        if entity_kind == "agent_plugin" and full_heading in SCANNER_DATA_HEADINGS:
            continue
        heading = full_heading.removeprefix("## ").strip()
        body = _section_body(chunk).strip()
        if is_todo_like_body(body):
            out.append(HumanTodoSection(heading=heading, full_heading=full_heading, body=body))
    return out


def replace_todo_human_sections(page_path: Path, replacements: dict[str, str]) -> list[str]:
    """Replace TODO-like human section bodies on ``page_path``.

    Only sections currently shaped like placeholders are replaced. Unknown
    headings, empty replacements, real prose, and replacement bodies that are
    still TODO-like are ignored. Returns the headings that changed, in page
    order. Writes atomically via temp file + ``os.replace``.
    """
    text = page_path.read_text(encoding="utf-8")
    entity_kind = _parse_frontmatter_kind(text) or ""
    preamble, sections = _split_h2_sections(text)

    wanted = {heading: replacement for heading, replacement in replacements.items() if replacement.strip()}
    if not wanted:
        return []

    changed: list[str] = []
    rebuilt: list[str] = [preamble]

    seen: set[str] = set()
    for full_heading, chunk in sections:
        heading = full_heading.removeprefix("## ").strip()
        body = _section_body(chunk).strip()
        replacement = wanted.get(heading)
        if (
            replacement is not None
            and heading not in seen
            and not _is_scanner_owned_heading(full_heading)
            and not (entity_kind == "agent_plugin" and full_heading in SCANNER_DATA_HEADINGS)
            and is_todo_like_body(body)
            and not is_todo_like_body(replacement)
        ):
            rebuilt.append(_replace_chunk_body(chunk, replacement.strip()))
            changed.append(heading)
            seen.add(heading)
        else:
            rebuilt.append(chunk)

    new_text = "".join(rebuilt)
    if new_text != text:
        tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
        tmp_path.write_text(new_text, encoding="utf-8")
        os.replace(tmp_path, page_path)
    return changed


def _parse_frontmatter_kind(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None

    kind: str | None = None
    for line in lines[1:]:
        if line == "---":
            return kind
        match = _FRONTMATTER_KIND_RE.match(line)
        if match is not None:
            kind = match.group(1).strip().strip('"').strip("'")
    return kind


def _section_body(chunk: str) -> str:
    heading_end = chunk.find("\n")
    if heading_end == -1:
        return ""
    return chunk[heading_end + 1 :].rstrip("\n")


def _replace_chunk_body(chunk: str, new_body: str) -> str:
    heading_end = chunk.find("\n")
    if heading_end == -1:
        return chunk
    suffix_len = len(chunk) - len(chunk.rstrip("\n"))
    suffix = chunk[-suffix_len:] if suffix_len else ""
    heading = chunk[:heading_end]
    return f"{heading}\n{new_body.strip()}{suffix}"
