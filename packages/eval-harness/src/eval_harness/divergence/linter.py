"""Programmatic divergence checks for the linter role (LNT-001..LNT-003).

Security (T-06-15): All check callables use regex and string operations only.
No eval/exec of LLM-generated text.
"""

from __future__ import annotations

import re
from pathlib import Path

from eval_harness.divergence.check import AgentOutputProxy, DivergenceCheck, Verdict

# Patterns for code-drift first ordering check (LNT-001).
_CODE_DRIFT_RE = re.compile(r"code.?drift|outdated.?claim|outdated claim", re.IGNORECASE)
_ORPHAN_STALE_RE = re.compile(r"\borphan\b|\bstale\b", re.IGNORECASE)

# Patterns for silent-fix detection (LNT-003).
# Matches write-operation words paired with .md file references.
_WRITE_OP_RE = re.compile(
    r"\b(?:wrote|created|updated|edited|fixed|modified)\b[^.\n]*\.md",
    re.IGNORECASE,
)


def _check_code_drift_first(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """LNT-001 (soft): Code-drift finding appears before orphan/stale findings."""
    lines = output.answer.splitlines()
    first_code_drift = None
    first_orphan_stale = None
    for i, line in enumerate(lines):
        if first_code_drift is None and _CODE_DRIFT_RE.search(line):
            first_code_drift = i
        if first_orphan_stale is None and _ORPHAN_STALE_RE.search(line):
            first_orphan_stale = i
    # Only flag if both appear and orphan/stale comes first.
    if (
        first_code_drift is not None
        and first_orphan_stale is not None
        and first_orphan_stale < first_code_drift
    ):
        return Verdict(
            passed=False,
            excerpt="Code-drift finding should appear before orphan/stale finding",
        )
    return Verdict(passed=True, excerpt="")


def _check_findings_nonempty(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """LNT-002: Findings list is not empty (non-empty output required when issues exist)."""
    if not output.answer.strip():
        return Verdict(passed=False, excerpt="Linter output is empty")
    return Verdict(passed=True, excerpt="")


def _check_no_silent_fix(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """LNT-003: LLM does not include write operations in output (report only)."""
    match = _WRITE_OP_RE.search(output.answer)
    if match:
        excerpt = match.group()[:80]
        return Verdict(passed=False, excerpt=f"Write operation detected: {excerpt}")
    return Verdict(passed=True, excerpt="")


LINTER_CHECKS: list[DivergenceCheck] = [
    DivergenceCheck(
        id="LNT-001-code-drift-first",
        source_anchor="packages/prompt-sources/agents/linter.md#rules",
        severity="soft",
        check=_check_code_drift_first,
    ),
    DivergenceCheck(
        id="LNT-002-findings-nonempty-when-issues",
        source_anchor="packages/prompt-sources/agents/linter.md#workflow-pass-3",
        severity="hard",
        check=_check_findings_nonempty,
    ),
    DivergenceCheck(
        id="LNT-003-no-silent-fix",
        source_anchor="packages/prompt-sources/agents/linter.md#rules",
        severity="hard",
        check=_check_no_silent_fix,
    ),
]
