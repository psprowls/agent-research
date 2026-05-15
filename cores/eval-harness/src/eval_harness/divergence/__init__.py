"""eval_harness.divergence: per-role divergence check infrastructure (EVAL-11).

Re-exports DivergenceCheck, Verdict, AgentOutputProxy, ROLE_CHECKS (per-role
list[DivergenceCheck]), and ROLE_RUBRICS (per-role Path to judge rubric .md).

Consumers (DivergenceMetric in metric.py, test_divergence_checks.py) should
import from this package rather than from individual role modules.

Exports:
    DivergenceCheck  — dataclass pairing rule ID + severity + check callable
    Verdict          — NamedTuple (passed: bool, excerpt: str)
    AgentOutputProxy — dataclass (answer: str, page_type: str = "")
    ROLE_CHECKS      — dict[role_name, list[DivergenceCheck]]
    ROLE_RUBRICS     — dict[role_name, Path] to per-role judge rubric files
"""

from __future__ import annotations

from pathlib import Path

from eval_harness.divergence.check import (  # re-export
    AgentOutputProxy,
    DivergenceCheck,
    Verdict,
)
from eval_harness.divergence.ingestor import INGESTOR_CHECKS
from eval_harness.divergence.librarian import LIBRARIAN_CHECKS
from eval_harness.divergence.linter import LINTER_CHECKS
from eval_harness.divergence.scanner import SCANNER_CHECKS

_RUBRICS_DIR = Path(__file__).parent / "rubrics"

ROLE_CHECKS: dict[str, list[DivergenceCheck]] = {
    "librarian": LIBRARIAN_CHECKS,
    "ingestor": INGESTOR_CHECKS,
    "linter": LINTER_CHECKS,
    "scanner": SCANNER_CHECKS,
}

ROLE_RUBRICS: dict[str, Path] = {
    "librarian": _RUBRICS_DIR / "librarian.md",
    "ingestor": _RUBRICS_DIR / "ingestor.md",
    "linter": _RUBRICS_DIR / "linter.md",
    "scanner": _RUBRICS_DIR / "scanner.md",
}

__all__ = [
    "DivergenceCheck",
    "Verdict",
    "AgentOutputProxy",
    "ROLE_CHECKS",
    "ROLE_RUBRICS",
]
