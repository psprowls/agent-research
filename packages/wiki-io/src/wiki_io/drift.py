"""Living Wiki M2e: pure (LLM-free) human-section drift primitives.

A human-owned page section can silently drift — the code it describes changed
while the curated prose stayed frozen. These helpers enumerate the human-owned
H2 sections of a page body, hash a section's body (to detect later edits), pull
the scanner-regenerated `## Narrative` / `## File map` that serve as the judge's
ground truth, and recompute which open `drift_review` flags survive after edits.

LLM judging and frontmatter I/O live in the scan pipeline; this module is the
side-effect-free core, mirroring the entity_writer section helpers it reuses.
"""

from __future__ import annotations

import hashlib

from wiki_io.entity_writer import (
    _is_scanner_owned_heading,
    _scanner_section_token,
    _split_h2_sections,
    extract_narrative,
)

__all__ = [
    "iter_human_sections",
    "section_hash",
    "extract_narrative",
    "extract_file_map",
    "clear_resolved_flags",
]


def iter_human_sections(body: str) -> list[tuple[str, str]]:
    """Return ``[(heading, chunk), ...]`` for every human-owned H2 section.

    A section is human-owned iff ``not _is_scanner_owned_heading(heading)`` — so
    `## Narrative`, `## File map[ - <name>]`, and `## Referenced in wiki` are
    excluded. Each ``chunk`` includes its heading line (same shape as
    ``_split_h2_sections``).
    """
    _preamble, sections = _split_h2_sections(body)
    return [(heading, chunk) for heading, chunk in sections if not _is_scanner_owned_heading(heading)]


def section_hash(chunk: str) -> str:
    """SHA-256 hex digest of a section ``chunk`` (heading + body), whitespace
    stripped so trailing-newline churn never looks like an edit."""
    return hashlib.sha256(chunk.strip().encode("utf-8")).hexdigest()


def extract_file_map(body: str) -> str | None:
    """Return the stripped `## File map[ - <name>]` chunk, or None when absent.

    Passed to the judge as additional ground truth only for kinds that have a
    file map (package/app/test_suite); agent_plugin pages have none -> None.
    """
    _preamble, sections = _split_h2_sections(body)
    for heading, chunk in sections:
        if _is_scanner_owned_heading(heading) and _scanner_section_token(heading) == _scanner_section_token(
            "## File map"
        ):
            return chunk.strip()
    return None


def clear_resolved_flags(entries: list[dict], body: str) -> list[dict]:
    """Return the subset of `drift_review` ``entries`` that still hold.

    An entry survives iff its section still exists in ``body`` AND that section's
    current ``section_hash`` equals the stored ``hash``. A hash mismatch means the
    prose was edited (the human addressed the flag); a missing section means it
    was removed — both drop the entry. Pure: no I/O, no side effects.
    """
    current: dict[str, str] = {
        heading.removeprefix("## ").strip(): section_hash(chunk) for heading, chunk in iter_human_sections(body)
    }
    survivors: list[dict] = []
    for entry in entries:
        section = entry.get("section")
        stored = entry.get("hash")
        if section in current and current[section] == stored:
            survivors.append(entry)
    return survivors
