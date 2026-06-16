"""run_lint_all — run the wiki lint and the work-lifecycle lint, aggregated.

Thin orchestrator over run_lint (wiki: mechanical + semantic + guidance) and
run_work_lint (work lifecycle). run_lint is decoupled from work lint, so this
runs each pass exactly once. Continue-on-error: a failure in one pass is
captured and does not block the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from graph_wiki_core.commands.lint import LintResult, run_lint
from graph_wiki_core.commands.work import WorkLintResult, run_work_lint


@dataclass
class LintAllResult:
    """Aggregate of a wiki lint + work-lifecycle lint pass."""

    wiki: LintResult | None = None
    work: WorkLintResult | None = None
    errors: list[dict] = field(default_factory=list)


async def run_lint_all(
    workspace_path: Path | None = None,
    stale_days: int = 90,
    log_gap_days: int = 14,
) -> LintAllResult:
    """Run wiki lint then work lint; capture per-pass failures."""
    errors: list[dict] = []
    wiki: LintResult | None = None
    work: WorkLintResult | None = None

    try:
        wiki = await run_lint(workspace_path=workspace_path, stale_days=stale_days, log_gap_days=log_gap_days)
    except RuntimeError as e:
        errors.append({"command": "wiki", "error": str(e)})

    try:
        work = await run_work_lint(workspace_path=workspace_path)
    except RuntimeError as e:
        errors.append({"command": "work", "error": str(e)})

    return LintAllResult(wiki=wiki, work=work, errors=errors)
