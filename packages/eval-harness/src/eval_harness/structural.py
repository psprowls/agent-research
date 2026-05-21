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
from graph_wiki_agent.commands.query import QueryResult
from workspace_io.paths import wiki_dir

# Pattern for code path detection in answer text.
_CODE_PATH_RE = re.compile(
    r"(src/|tests/|packages/|agents/|[a-zA-Z0-9_/.-]+\.py|[a-zA-Z0-9_/.-]+\.ts)"
)


def _resolve_citation(slug: str, workspace_path: Path) -> Path | None:
    """Return the .md file for a citation slug, or None if not found.

    Resolution order:
    1. Exact: wiki / f"{slug}.md"
    2. Glob fallback: wiki.glob(f"**/{basename}.md") — first match wins
    """
    wiki = wiki_dir(workspace_path)
    exact = wiki / f"{slug}.md"
    if exact.exists():
        return exact
    base = Path(slug).name
    matches = list(wiki.glob(f"**/{base}.md"))
    if matches:
        return matches[0]
    return None


# Public alias — other modules should import this name, not the private `_resolve_citation`.
resolve_citation = _resolve_citation


def check_structural(result: Any, workspace_path: Path) -> dict[str, Any]:
    """Run deterministic EVAL-06 structural checks on a QueryResult.

    Security (T-4-01): Validates that result is a QueryResult instance before
    accessing any fields. Does not call eval() on any field.

    Args:
        result:         The QueryResult to check.
        workspace_path: path to the workspace root; the wiki is derived
                        internally via workspace_io.paths.wiki_dir(workspace_path).

    Returns:
        dict with keys: has_citation, citations_resolve, unresolved_citations,
        pages_drilled_positive, has_code_path, frontmatter_valid, json_schema_valid.

    Raises:
        TypeError: if result is not a QueryResult instance.
        FileNotFoundError: if workspace_path / "wiki" does not exist.
    """
    if not isinstance(result, QueryResult):
        raise TypeError(
            f"check_structural expects QueryResult, got {type(result).__name__!r}"
        )

    # Fail-fast guard (D-01 / D-09): the wiki dir must exist before any
    # citation lookup runs. Without this guard, a caller that mistakenly
    # passes the wiki path itself (instead of the workspace root) silently
    # records every citation as unresolved against a non-existent nested
    # path — masking real call-site bugs. Raising here surfaces the misuse
    # immediately. _resolve_citation re-derives wiki from its own argument
    # via the same helper to preserve the D-01 "param=workspace, internals
    # derive wiki" convention uniform across sweep / baseline / structural.
    wiki = wiki_dir(workspace_path)
    if not wiki.is_dir():
        raise FileNotFoundError(
            f"wiki dir not found: {wiki} "
            f"(workspace_path={workspace_path!r}; "
            "expected workspace_path/'wiki' to exist)"
        )

    # --- has_citation ---
    has_citation: bool = bool(result.citations)

    # --- citation resolution ---
    unresolved: list[str] = []
    for slug in result.citations:
        if _resolve_citation(slug, workspace_path) is None:
            unresolved.append(slug)

    citations_resolve: bool = len(unresolved) == 0  # vacuously True if citations is empty

    # --- pages_drilled_positive ---
    pages_drilled_positive: bool = result.pages_drilled > 0

    # --- has_code_path ---
    has_code_path: bool = _CODE_PATH_RE.search(result.answer) is not None

    # --- frontmatter_valid ---
    frontmatter_valid: bool = True
    for slug in result.citations:
        md_file = _resolve_citation(slug, workspace_path)
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
