"""Unit tests for eval_harness.report — deterministic paths only, no Bedrock calls.

Tests:
- regression_check raises AssertionError with "below threshold" when score < threshold
- regression_check does not raise when score >= threshold
- cost_frontier_table returns dict keyed by model_id
- cost_frontier_table extracts quality_score from judge_scores["mean"] and cost_usd from result
- cost_frontier_table sorts by quality_score descending
"""

from __future__ import annotations

from eval_harness.report import cost_frontier_table, print_frontier, regression_check
from eval_harness.sweep import SweepResult


def _make_result(
    model_id: str,
    cost_usd: float | None = None,
    judge_scores: dict | None = None,
    structural: dict | None = None,
    status: str = "ok",
) -> SweepResult:
    """Create a minimal SweepResult for unit testing."""
    return SweepResult(
        model_id=model_id,
        safe_model_id=model_id.replace(":", "_"),
        query="test query",
        answer="test answer [[SomePage]]",
        citations=["SomePage"],
        pages_drilled=2,
        tokens_in=100,
        tokens_out=50,
        cost_usd=cost_usd,
        wall_seconds=1.0,
        structural=structural or {"has_citation": True},
        status=status,
        judge_scores=judge_scores,
        seed=None,
    )


class TestRegressionCheck:
    def test_regression_check_fails(self) -> None:
        """regression_check raises AssertionError with 'below threshold' when score < threshold."""
        try:
            regression_check(score=0.3, threshold=0.5)
            raise AssertionError("Expected AssertionError was not raised")
        except AssertionError as exc:
            assert "below threshold" in str(exc), (
                f"AssertionError message should contain 'below threshold', got: {exc!r}"
            )

    def test_regression_check_passes(self) -> None:
        """regression_check does not raise when score >= threshold."""
        regression_check(score=0.7, threshold=0.5)
        # No exception = pass

    def test_regression_check_at_threshold(self) -> None:
        """regression_check does not raise when score == threshold."""
        regression_check(score=0.5, threshold=0.5)
        # No exception = pass


class TestCostFrontierTable:
    def test_cost_frontier_table_keys(self) -> None:
        """cost_frontier_table returns dict with keys matching model_ids."""
        result_a = _make_result("model-a", judge_scores={"mean": 0.8, "judge_a": 0.8, "judge_b": 0.8})
        result_b = _make_result("model-b", judge_scores={"mean": 0.6, "judge_a": 0.6, "judge_b": 0.6})
        table = cost_frontier_table([result_a, result_b])
        assert "model-a" in table
        assert "model-b" in table

    def test_cost_frontier_table_values(self) -> None:
        """Table values include quality_score and cost_usd."""
        result = _make_result(
            "model-x",
            cost_usd=0.001,
            judge_scores={"mean": 0.8, "judge_a": 0.8, "judge_b": 0.8},
        )
        table = cost_frontier_table([result])
        row = table["model-x"]
        assert row["quality_score"] == 0.8
        assert row["cost_usd"] == 0.001

    def test_cost_frontier_sorted(self) -> None:
        """Table is ordered by quality_score descending (highest quality first)."""
        result_low = _make_result("model-low", judge_scores={"mean": 0.4, "judge_a": 0.4, "judge_b": 0.4})
        result_high = _make_result("model-high", judge_scores={"mean": 0.9, "judge_a": 0.9, "judge_b": 0.9})
        result_mid = _make_result("model-mid", judge_scores={"mean": 0.7, "judge_a": 0.7, "judge_b": 0.7})

        table = cost_frontier_table([result_low, result_high, result_mid])
        keys = list(table.keys())
        assert keys == ["model-high", "model-mid", "model-low"], (
            f"Expected descending quality order, got: {keys}"
        )

    def test_cost_frontier_structural_fallback(self) -> None:
        """When judge_scores is None, quality_score falls back to structural has_citation."""
        result = _make_result(
            "model-fallback",
            cost_usd=0.002,
            judge_scores=None,
            structural={"has_citation": True},
        )
        table = cost_frontier_table([result])
        row = table["model-fallback"]
        assert row["quality_score"] == 1.0

    def test_cost_frontier_skips_error_results(self) -> None:
        """Results with status='error' are excluded from the table."""
        ok_result = _make_result("model-ok", judge_scores={"mean": 0.7, "judge_a": 0.7, "judge_b": 0.7})
        err_result = _make_result("model-err", status="error")
        table = cost_frontier_table([ok_result, err_result])
        assert "model-ok" in table
        assert "model-err" not in table


class TestPrintFrontier:
    def test_print_frontier_returns_string(self) -> None:
        """print_frontier returns a string (does not print)."""
        result = _make_result("my-model", cost_usd=0.01, judge_scores={"mean": 0.75})
        table = cost_frontier_table([result])
        output = print_frontier(table)
        assert isinstance(output, str)
        assert "my-model" in output
