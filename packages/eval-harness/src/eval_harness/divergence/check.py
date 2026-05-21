"""DivergenceCheck dataclass, Verdict NamedTuple, and AgentOutputProxy dataclass.

Implements DivergenceCheck dataclass schema locked in CONTEXT.md D-08. Used by
per-role rule modules (librarian.py, ingestor.py, linter.py, scanner.py) and
DivergenceMetric (metric.py).

Security (T-06-15): Inputs to check callables are LLM-generated text; checks
must not eval/exec the input. All check implementations use string operations,
regex, and frontmatter.loads only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple


class Verdict(NamedTuple):
    """Immutable result from a DivergenceCheck.check callable.

    Attributes:
        passed:  True when the check passes (no divergence detected).
        excerpt: Short evidence string (max ~100 chars) for accepted_failures
                 array when passed=False. Empty string when passed=True.
    """

    passed: bool
    excerpt: str


@dataclass
class AgentOutputProxy:
    """Minimal wrapper mapping any agent command result to a common check interface.

    Attributes:
        answer:    The LLM's text output (answer, stub page, findings list, etc.).
        page_type: Page type string for ingestor checks (ING-003, ING-004).
                   Defaults to "" so non-ingestor callers can omit it.
    """

    answer: str
    page_type: str = ""


@dataclass
class DivergenceCheck:
    """A single divergence rule pairing an ID and severity with a check callable.

    Schema locked per CONTEXT.md D-08. Rule IDs follow the convention:
    ``<ROLE>-<NNN>-<slug>`` (e.g. ``LIB-001-wikilink-resolves``).

    Severity values (documented, not runtime-validated):
    - ``"hard"``: gates the regression check; failures cause AssertionError in CI
    - ``"soft"``: reported in accepted_failures but never fails CI

    Attributes:
        id:            Stable rule identifier (e.g. "LIB-001-wikilink-resolves").
        source_anchor: Path + section anchor tracing back to canonical source
                       (e.g. "plugins/graph-wiki/skills/graph-wiki/SKILL.md#iron-rules").
        severity:      "hard" or "soft".
        check:         Pure function (AgentOutputProxy, Path) -> Verdict.
                       Must not eval/exec the output text (T-06-15).
    """

    id: str
    source_anchor: str
    severity: str
    check: Callable[[AgentOutputProxy, Path], Verdict]
