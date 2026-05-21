"""Programmatic divergence checks for the ingestor role (ING-001..ING-004).

Security (T-06-15): All check callables use frontmatter.loads() and string
operations only. No eval/exec of LLM-generated text.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter

from eval_harness.divergence.check import AgentOutputProxy, DivergenceCheck, Verdict

# Required frontmatter fields per RESEARCH §Divergence Check Inventory ING-002.
_REQUIRED_FIELDS = ["title", "category", "page_type", "target_slug", "summary"]

# Valid page_type values per SKILL.md #page-categories and ingestor workflow.
_VALID_PAGE_TYPES = {"package", "concept", "adr", "source"}


def _check_frontmatter_present(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """ING-001: LLM output contains --- delimited YAML frontmatter."""
    text = output.answer
    if not text.startswith("---"):
        return Verdict(passed=False, excerpt="Missing YAML frontmatter delimiters")
    # Need a second --- delimiter after the first line.
    rest = text[3:]
    if "---" not in rest:
        return Verdict(passed=False, excerpt="Missing closing --- frontmatter delimiter")
    return Verdict(passed=True, excerpt="")


def _check_required_fields(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """ING-002: title, category, page_type, target_slug, summary all present."""
    try:
        post = frontmatter.loads(output.answer)
    except Exception as exc:
        return Verdict(passed=False, excerpt=f"Frontmatter parse error: {exc!s}"[:80])
    missing = [f for f in _REQUIRED_FIELDS if not post.metadata.get(f)]
    if missing:
        return Verdict(passed=False, excerpt=f"Missing fields: {', '.join(missing)}")
    return Verdict(passed=True, excerpt="")


def _check_page_type_routing(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """ING-003: page_type is one of: package, concept, adr, source."""
    try:
        post = frontmatter.loads(output.answer)
    except Exception:
        return Verdict(passed=True, excerpt="")  # ING-002 will catch this
    page_type = post.metadata.get("page_type", "")
    if not page_type:
        return Verdict(passed=True, excerpt="")  # ING-002 handles missing field
    if page_type not in _VALID_PAGE_TYPES:
        return Verdict(
            passed=False,
            excerpt=f"Invalid page_type: {str(page_type)[:60]}",
        )
    return Verdict(passed=True, excerpt="")


def _check_page_type_valid_category(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """ING-004: category matches page_type (e.g. page_type:source -> category:source)."""
    try:
        post = frontmatter.loads(output.answer)
    except Exception:
        return Verdict(passed=True, excerpt="")  # ING-001/ING-002 will catch this
    page_type = post.metadata.get("page_type", "")
    category = post.metadata.get("category", "")
    if not page_type or not category:
        return Verdict(passed=True, excerpt="")  # ING-002 handles missing fields
    if page_type not in _VALID_PAGE_TYPES:
        return Verdict(passed=True, excerpt="")  # ING-003 will catch invalid type
    # source page_type must have category=source; others must match page_type.
    if page_type == "source":
        if category != "source":
            return Verdict(
                passed=False,
                excerpt=f"page_type:source requires category:source, got category:{category}",
            )
    else:
        if category != page_type:
            return Verdict(
                passed=False,
                excerpt=f"category:{category} does not match page_type:{page_type}",
            )
    return Verdict(passed=True, excerpt="")


INGESTOR_CHECKS: list[DivergenceCheck] = [
    DivergenceCheck(
        id="ING-001-frontmatter-present",
        source_anchor="packages/prompt-sources/agents/ingestor.md#workflow-step-4",
        severity="hard",
        check=_check_frontmatter_present,
    ),
    DivergenceCheck(
        id="ING-002-required-fields",
        source_anchor="packages/prompt-sources/agents/ingestor.md#workflow-step-4",
        severity="hard",
        check=_check_required_fields,
    ),
    DivergenceCheck(
        id="ING-003-page-type-routing",
        source_anchor="packages/prompt-sources/SKILL.md#page-categories",
        severity="hard",
        check=_check_page_type_routing,
    ),
    DivergenceCheck(
        id="ING-004-page-type-valid-category",
        source_anchor="packages/prompt-sources/agents/ingestor.md#rules",
        severity="hard",
        check=_check_page_type_valid_category,
    ),
]
