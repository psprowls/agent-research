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
    _split_h2_sections,
    extract_narrative,
)

__all__ = [
    "iter_human_sections",
    "section_hash",
    "extract_narrative",
    "extract_file_map",
    "clear_resolved_flags",
    "page_body_hash",
    "CONTENT_HASH_KEY",
]

# Living Wiki M4 extension: frontmatter key for the content-hash detection
# baseline on curated (concept/ADR) pages. NOT in SCANNER_OWNED_KEYS (that
# frozenset only governs entity-page re-render) — stamped by
# propagate_drift._stamp_curated_page_if_changed, preserved otherwise.
CONTENT_HASH_KEY = "content_hash"

# ---------------------------------------------------------------------------
# Legacy three-class helpers (relocated from entity_writer.py; M2e-scoped).
# OLD semantics preserved verbatim: `## Narrative` still counts as
# scanner-owned here, so M2e drift-judging and TODO-fill enumeration are
# unchanged. This whole module (and human_sections.py) is deleted wholesale
# by Child 3 of epic 2026-07-29-epic-simplify-ownership-commit-refresh.
# ---------------------------------------------------------------------------

# Scanner-DATA sections — deterministic graph projections rendered into the
# template every scan. These headings appear only on the agent_plugin template.
SCANNER_DATA_HEADINGS: frozenset[str] = frozenset(
    {
        "## Commands",
        "## Agents",
        "## Skills",
        "## Scripts",
        "## Hooks",
        "## MCP servers",
    }
)


def _is_scanner_owned_heading(heading: str) -> bool:
    """True for the three H2 sections the scanner regenerates each scan:
    `## Narrative`, `## File map[ - <name>]`, `## Referenced in wiki`.

    Everything else (e.g. `## Purpose`, `## Public API`, any hand-added H2)
    is human-owned and preserved across re-scan.
    """
    h = heading.strip()
    return h == "## Narrative" or h.startswith("## File map") or h == "## Referenced in wiki"


def _scanner_section_token(heading: str) -> str:
    """Collapse a scanner-owned H2 heading to a constant per-type token.

    The `## File map - <name>` heading carries a name suffix that differs
    between the template render and the injected deterministic block, so the
    suffix must be normalized away. The token distinguishes the three scanner
    sections so an added/removed section still registers as a difference.
    """
    h = heading.strip()
    if h == "## Narrative":
        return "\x00scanner:narrative\x00"
    if h.startswith("## File map"):
        return "\x00scanner:filemap\x00"
    # `_is_scanner_owned_heading` guarantees the only remaining case.
    return "\x00scanner:referenced\x00"


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


def page_body_hash(body: str) -> str:
    """SHA-256 hex digest of a curated (concept/ADR) page body, frontmatter
    already stripped by the caller. Mirrors ``section_hash``'s approach but
    over the whole body rather than one H2 section — the M4 content-hash
    detection pass (``propagate_drift.py``) uses it to notice hand-edits."""
    return section_hash(body)


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
