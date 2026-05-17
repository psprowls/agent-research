"""Deterministic structural checks for QueryResult objects.

Implements EVAL-06 checks: citation presence, citation resolution, page drill count,
code path detection, frontmatter validity, and JSON schema validation.

Security (T-4-01): The result parameter is validated as a QueryResult instance
before any field access. No eval() is called on any field.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import frontmatter
from code_wiki_agent.commands.query import QueryResult

# Pattern for code path detection in answer text.
_CODE_PATH_RE = re.compile(
    r"(src/|tests/|packages/|agents/|[a-zA-Z0-9_/.-]+\.py|[a-zA-Z0-9_/.-]+\.ts)"
)


def _resolve_citation(slug: str, vault_path: Path) -> Path | None:
    """Return the .md file for a citation slug, or None if not found.

    Resolution order:
    1. Exact: vault_path / f"{slug}.md"
    2. Glob fallback: vault_path.glob(f"**/{basename}.md") — first match wins
    """
    exact = vault_path / f"{slug}.md"
    if exact.exists():
        return exact
    base = Path(slug).name
    matches = list(vault_path.glob(f"**/{base}.md"))
    if matches:
        return matches[0]
    return None


# Public alias — other modules should import this name, not the private `_resolve_citation`.
resolve_citation = _resolve_citation


def check_structural(result: Any, vault_path: Path) -> dict[str, Any]:
    """Run deterministic EVAL-06 structural checks on a QueryResult.

    Security (T-4-01): Validates that result is a QueryResult instance before
    accessing any fields. Does not call eval() on any field.

    Args:
        result:     The QueryResult to check.
        vault_path: Path to the wiki vault root (used for citation resolution).

    Returns:
        dict with keys: has_citation, citations_resolve, unresolved_citations,
        pages_drilled_positive, has_code_path, frontmatter_valid, json_schema_valid.

    Raises:
        TypeError: if result is not a QueryResult instance.
    """
    if not isinstance(result, QueryResult):
        raise TypeError(
            f"check_structural expects QueryResult, got {type(result).__name__!r}"
        )

    # --- has_citation ---
    has_citation: bool = bool(result.citations)

    # --- citation resolution ---
    unresolved: list[str] = []
    for slug in result.citations:
        if _resolve_citation(slug, vault_path) is None:
            unresolved.append(slug)

    citations_resolve: bool = len(unresolved) == 0  # vacuously True if citations is empty

    # --- pages_drilled_positive ---
    pages_drilled_positive: bool = result.pages_drilled > 0

    # --- has_code_path ---
    has_code_path: bool = _CODE_PATH_RE.search(result.answer) is not None

    # --- frontmatter_valid ---
    frontmatter_valid: bool = True
    for slug in result.citations:
        md_file = _resolve_citation(slug, vault_path)
        if md_file is None:
            continue  # already counted as unresolved; skip frontmatter check
        try:
            post = frontmatter.load(str(md_file))
            title = post.metadata.get("title")
            if not title:
                frontmatter_valid = False
                break
        except Exception:
            frontmatter_valid = False
            break

    # --- json_schema_valid ---
    json_schema_valid: bool = (
        isinstance(result, QueryResult)
        and isinstance(result.answer, str)
        and result.answer is not None
        and isinstance(result.citations, list)
        and isinstance(result.pages_drilled, (int, float))
        and isinstance(result.search_scores, (dict, list))
    )

    return {
        "has_citation": has_citation,
        "citations_resolve": citations_resolve,
        "unresolved_citations": unresolved,
        "pages_drilled_positive": pages_drilled_positive,
        "has_code_path": has_code_path,
        "frontmatter_valid": frontmatter_valid,
        "json_schema_valid": json_schema_valid,
    }
