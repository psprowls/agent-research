"""Programmatic divergence checks for the scanner role (SCN-001..SCN-004).

Security (T-06-15): All check callables use frontmatter.loads() and string
operations only. No eval/exec of LLM-generated text.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter

from eval_harness.divergence.check import AgentOutputProxy, DivergenceCheck, Verdict

# Required frontmatter fields per RESEARCH §Divergence Check Inventory SCN-002.
_REQUIRED_FIELDS = ["title", "category", "summary", "package_path", "language"]

# Section markers the scanner must/must not include.
_FILE_MAP_SECTION = "## File map"
_OVERVIEW_SECTION = "## Overview"


def _check_frontmatter_present(output: AgentOutputProxy, vault: Path) -> Verdict:
    """SCN-001: Scanner stub output contains --- delimited YAML frontmatter."""
    text = output.answer
    if not text.startswith("---"):
        return Verdict(passed=False, excerpt="Missing YAML frontmatter delimiters")
    rest = text[3:]
    if "---" not in rest:
        return Verdict(passed=False, excerpt="Missing closing --- frontmatter delimiter")
    return Verdict(passed=True, excerpt="")


def _check_required_fields(output: AgentOutputProxy, vault: Path) -> Verdict:
    """SCN-002: title, category, summary, package_path, language all present."""
    try:
        post = frontmatter.loads(output.answer)
    except Exception as exc:
        return Verdict(passed=False, excerpt=f"Frontmatter parse error: {exc!s}"[:80])
    missing = [f for f in _REQUIRED_FIELDS if not post.metadata.get(f)]
    if missing:
        return Verdict(passed=False, excerpt=f"Missing fields: {', '.join(missing)}")
    return Verdict(passed=True, excerpt="")


def _check_no_file_map_section(output: AgentOutputProxy, vault: Path) -> Verdict:
    """SCN-003: Output does not contain ## File map section (added by pipeline)."""
    if _FILE_MAP_SECTION in output.answer:
        return Verdict(
            passed=False,
            excerpt="Output contains '## File map' section (pipeline adds this)",
        )
    return Verdict(passed=True, excerpt="")


def _check_overview_present(output: AgentOutputProxy, vault: Path) -> Verdict:
    """SCN-004: Output contains ## Overview section."""
    if _OVERVIEW_SECTION not in output.answer:
        return Verdict(passed=False, excerpt="Missing '## Overview' section")
    return Verdict(passed=True, excerpt="")


SCANNER_CHECKS: list[DivergenceCheck] = [
    DivergenceCheck(
        id="SCN-001-frontmatter-present",
        source_anchor="cores/prompt-sources/agents/scanner.md#workflow-step-3",
        severity="hard",
        check=_check_frontmatter_present,
    ),
    DivergenceCheck(
        id="SCN-002-required-fields",
        source_anchor="cores/prompt-sources/agents/scanner.md#workflow-step-3",
        severity="hard",
        check=_check_required_fields,
    ),
    DivergenceCheck(
        id="SCN-003-no-file-map-section",
        source_anchor="cores/prompt-sources/agents/scanner.md",
        severity="hard",
        check=_check_no_file_map_section,
    ),
    DivergenceCheck(
        id="SCN-004-overview-present",
        source_anchor="cores/prompt-sources/agents/scanner.md#workflow-step-3",
        severity="hard",
        check=_check_overview_present,
    ),
]
