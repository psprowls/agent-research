"""Cost-frontier report and regression check for wiki query eval sweeps.

Provides:
    cost_frontier_table: build a per-model quality/cost dict sorted by quality descending
    regression_check:    raise AssertionError if quality score is below threshold
    print_frontier:      format the frontier table as a plain-text string for display

These functions are deterministic (no Bedrock calls) and safe to call in any context.
"""

from __future__ import annotations

from eval_harness.sweep import SweepResult


def cost_frontier_table(results: list[SweepResult]) -> dict[str, dict]:
    """Build a per-model cost/quality table from sweep results.

    Only includes results with status="ok". Results with status="error" are excluded.

    Quality score is extracted from result.judge_scores["mean"] when judge scoring
    has been run. Falls back to structural has_citation (1.0 if True, 0.0 if False)
    when judge_scores is None.

    Args:
        results: List of SweepResult from run_sweep().

    Returns:
        dict[str, dict] preserving insertion order (Python 3.7+ guarantee),
        sorted by quality_score descending. Each value has keys:
            quality_score (float), cost_usd (float | None),
            pages_drilled (int), wall_seconds (float), structural_pass (bool).
    """
    rows: list[tuple[str, dict]] = []

    for result in results:
        if result.status != "ok":
            continue

        # Quality score: judge mean if available, else structural fallback
        if result.judge_scores is not None:
            quality_score = float(result.judge_scores["mean"])
        else:
            # Structural fallback: has_citation indicator
            quality_score = 1.0 if result.structural.get("has_citation") else 0.0

        # structural_pass: True if all bool values in structural dict are True
        structural_pass = all(
            v for v in result.structural.values() if isinstance(v, bool)
        )

        row = {
            "quality_score": quality_score,
            "cost_usd": result.cost_usd,
            "pages_drilled": result.pages_drilled,
            "wall_seconds": result.wall_seconds,
            "structural_pass": structural_pass,
        }
        rows.append((result.model_id, row))

    # Sort by quality_score descending (highest quality first)
    rows.sort(key=lambda pair: pair[1]["quality_score"], reverse=True)
    return dict(rows)


def regression_check(score: float, threshold: float = 0.5) -> None:
    """Assert that a quality score meets the minimum threshold.

    Intended for use in pytest-evals analysis functions as the CI quality gate
    (EVAL-09). Raises AssertionError with a structured message so pytest captures
    it as a test failure rather than an error.

    Args:
        score:     Quality score (0.0–1.0).
        threshold: Minimum acceptable quality (default 0.5).

    Raises:
        AssertionError: if score < threshold, with message containing
                        "below threshold" for test matching.
    """
    if score < threshold:
        raise AssertionError(
            f"Quality score {score:.3f} below threshold {threshold:.3f}"
        )


def print_frontier(table: dict[str, dict]) -> str:
    """Format the cost frontier table as a plain-text string.

    Columns: model_id, quality_score, cost_usd, pages_drilled.
    Returns the string — caller is responsible for printing.

    Args:
        table: Output of cost_frontier_table().

    Returns:
        Formatted multi-line string with header and one row per model.
    """
    if not table:
        return "(no results)\n"

    header = f"{'model_id':<45} {'quality':>8} {'cost_usd':>10} {'pages':>6}"
    divider = "-" * len(header)
    lines = [header, divider]

    for model_id, row in table.items():
        quality = f"{row['quality_score']:.3f}"
        cost = f"${row['cost_usd']:.5f}" if row["cost_usd"] is not None else "   N/A"
        pages = str(row["pages_drilled"])
        lines.append(f"{model_id:<45} {quality:>8} {cost:>10} {pages:>6}")

    return "\n".join(lines) + "\n"
