from __future__ import annotations

"""Unit tests for DivergenceMetric (EVAL-11, EVAL-12) — programmatic path only.

Judge path (run_judge / run) is tested separately under the eval gate in 06-11
because it requires live Bedrock access. All tests here are deterministic and
require no AWS credentials.
"""

from pathlib import Path

import pytest

from eval_harness.divergence import ROLE_CHECKS, ROLE_RUBRICS
from eval_harness.divergence.check import AgentOutputProxy


# ---------------------------------------------------------------------------
# DivergenceMetric construction
# ---------------------------------------------------------------------------


def test_metric_constructs_and_reads_rubric(fixture_wiki_path: Path) -> None:
    """DivergenceMetric can be constructed and reads the rubric at init time."""
    from eval_harness.divergence.metric import DivergenceMetric

    m = DivergenceMetric(
        role="librarian",
        checks=ROLE_CHECKS["librarian"],
        rubric_path=ROLE_RUBRICS["librarian"],
        wiki=fixture_wiki_path,
    )
    # rubric text was read at construction time
    assert isinstance(m._rubric_text, str)
    assert len(m._rubric_text) > 0


def test_metric_raises_on_missing_rubric(fixture_wiki_path: Path, tmp_path: Path) -> None:
    """DivergenceMetric raises FileNotFoundError immediately when rubric is missing."""
    from eval_harness.divergence.metric import DivergenceMetric

    missing = tmp_path / "nonexistent-rubric.md"
    with pytest.raises(FileNotFoundError):
        DivergenceMetric(
            role="librarian",
            checks=ROLE_CHECKS["librarian"],
            rubric_path=missing,
            wiki=fixture_wiki_path,
        )


def test_metric_importable_without_aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Module is importable even when AWS credentials are absent (lazy import gate)."""
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    # Import must succeed — deepeval/boto3 not touched at module level
    from eval_harness.divergence.metric import DivergenceMetric, summarize  # noqa: F401


# ---------------------------------------------------------------------------
# run_programmatic — D-11 result shape
# ---------------------------------------------------------------------------


def test_run_programmatic_returns_d11_shape(fixture_wiki_path: Path) -> None:
    """run_programmatic returns dict keyed by rule_id with runs/failures/accepted_failures."""
    from eval_harness.divergence.metric import DivergenceMetric

    m = DivergenceMetric(
        role="librarian",
        checks=ROLE_CHECKS["librarian"],
        rubric_path=ROLE_RUBRICS["librarian"],
        wiki=fixture_wiki_path,
    )
    outputs = [("fix1", AgentOutputProxy(answer="See [[packages/lattice-wiki-core]]."))]
    results = m.run_programmatic(outputs)

    # Every check id appears as a key
    for check in ROLE_CHECKS["librarian"]:
        assert check.id in results, f"Missing key {check.id}"
        entry = results[check.id]
        assert "runs" in entry
        assert "failures" in entry
        assert "accepted_failures" in entry
        assert isinstance(entry["runs"], int)
        assert isinstance(entry["failures"], int)
        assert isinstance(entry["accepted_failures"], list)


def test_run_programmatic_counts_runs_correctly(fixture_wiki_path: Path) -> None:
    """run_programmatic increments runs for each (fixture, check) pair."""
    from eval_harness.divergence.metric import DivergenceMetric

    m = DivergenceMetric(
        role="librarian",
        checks=ROLE_CHECKS["librarian"],
        rubric_path=ROLE_RUBRICS["librarian"],
        wiki=fixture_wiki_path,
    )
    # 3 fixtures -> each check should have runs == 3
    outputs = [
        ("fix1", AgentOutputProxy(answer="See [[packages/lattice-wiki-core]].")),
        ("fix2", AgentOutputProxy(answer="See [[packages/lattice-wiki-core]].")),
        ("fix3", AgentOutputProxy(answer="See [[packages/lattice-wiki-core]].")),
    ]
    results = m.run_programmatic(outputs)
    for check in ROLE_CHECKS["librarian"]:
        assert results[check.id]["runs"] == 3, f"{check.id}: expected 3 runs"


def test_run_programmatic_records_failure_with_fixture_and_excerpt(
    fixture_wiki_path: Path,
) -> None:
    """Failures include accepted_failures entries with fixture and excerpt keys."""
    from eval_harness.divergence.metric import DivergenceMetric

    m = DivergenceMetric(
        role="librarian",
        checks=ROLE_CHECKS["librarian"],
        rubric_path=ROLE_RUBRICS["librarian"],
        wiki=fixture_wiki_path,
    )
    # LIB-001 fails on an unresolved wikilink
    outputs = [("fixture-bad", AgentOutputProxy(answer="See [[nonexistent/page]]."))]
    results = m.run_programmatic(outputs)

    lib001 = results["LIB-001-wikilink-resolves"]
    assert lib001["failures"] >= 1
    assert len(lib001["accepted_failures"]) >= 1
    entry = lib001["accepted_failures"][0]
    assert entry["fixture"] == "fixture-bad"
    assert isinstance(entry["excerpt"], str)
    assert len(entry["excerpt"]) <= 200  # capped at 200 chars


def test_run_programmatic_zero_failures_on_valid_output(fixture_wiki_path: Path) -> None:
    """Fully valid librarian output produces 0 failures across all hard checks."""
    from eval_harness.divergence.metric import DivergenceMetric

    m = DivergenceMetric(
        role="librarian",
        checks=ROLE_CHECKS["librarian"],
        rubric_path=ROLE_RUBRICS["librarian"],
        wiki=fixture_wiki_path,
    )
    # Well-formed: resolved wikilink, citation present, path-wikilink, code path in backticks
    outputs = [
        (
            "fix-good",
            AgentOutputProxy(
                answer="See [[packages/lattice-wiki-core]] for the entry. Also `src/main.py:10`."
            ),
        )
    ]
    results = m.run_programmatic(outputs)
    for check in ROLE_CHECKS["librarian"]:
        assert results[check.id]["failures"] == 0, (
            f"{check.id}: expected 0 failures on well-formed output"
        )


def test_run_programmatic_all_four_roles(fixture_wiki_path: Path) -> None:
    """run_programmatic works for all four roles without error."""
    from eval_harness.divergence.metric import DivergenceMetric

    for role in ("librarian", "ingestor", "linter", "scanner"):
        m = DivergenceMetric(
            role=role,
            checks=ROLE_CHECKS[role],
            rubric_path=ROLE_RUBRICS[role],
            wiki=fixture_wiki_path,
        )
        # Minimal output — just check no exception is raised
        outputs = [("fix1", AgentOutputProxy(answer="placeholder output"))]
        results = m.run_programmatic(outputs)
        assert isinstance(results, dict), f"role={role}: expected dict result"


# ---------------------------------------------------------------------------
# summarize helper — D-11 envelope shape
# ---------------------------------------------------------------------------


def test_summarize_returns_d11_envelope(fixture_wiki_path: Path) -> None:
    """summarize() wraps results in the D-11 envelope with required keys."""
    from eval_harness.divergence.metric import DivergenceMetric, summarize

    m = DivergenceMetric(
        role="librarian",
        checks=ROLE_CHECKS["librarian"],
        rubric_path=ROLE_RUBRICS["librarian"],
        wiki=fixture_wiki_path,
    )
    outputs = [("fix1", AgentOutputProxy(answer="See [[packages/lattice-wiki-core]]."))]
    results = m.run_programmatic(outputs)
    envelope = summarize("librarian", results, "abc1234")

    required_keys = {"role", "recorded_at", "agent_commit", "checks"}
    assert required_keys <= envelope.keys(), (
        f"Missing keys: {required_keys - envelope.keys()}"
    )
    assert envelope["role"] == "librarian"
    assert envelope["agent_commit"] == "abc1234"
    assert envelope["checks"] is results


def test_summarize_recorded_at_is_iso_timestamp(fixture_wiki_path: Path) -> None:
    """summarize() recorded_at is a non-empty ISO-format timestamp string."""
    from eval_harness.divergence.metric import DivergenceMetric, summarize

    m = DivergenceMetric(
        role="scanner",
        checks=ROLE_CHECKS["scanner"],
        rubric_path=ROLE_RUBRICS["scanner"],
        wiki=fixture_wiki_path,
    )
    results = m.run_programmatic([("f1", AgentOutputProxy(answer="placeholder"))])
    envelope = summarize("scanner", results, "deadbeef")

    ts = envelope["recorded_at"]
    assert isinstance(ts, str) and len(ts) > 0
    # Must contain a 'T' separator (ISO 8601 format)
    assert "T" in ts


# ---------------------------------------------------------------------------
# GEval model= invariant (static grep — no Bedrock needed)
# ---------------------------------------------------------------------------


def test_geval_model_explicit_in_source() -> None:
    """metric.py passes model=judge explicitly to every GEval instantiation (T-06-18)."""
    metric_src = (
        Path(__file__).parent.parent
        / "src"
        / "eval_harness"
        / "divergence"
        / "metric.py"
    ).read_text()
    count = metric_src.count("model=judge")
    assert count >= 1, (
        "GEval in metric.py must pass model=judge explicitly (T-06-18 invariant). "
        f"Found {count} occurrences."
    )


# ---------------------------------------------------------------------------
# make_judge + JUDGE_PANEL_CONFIG reuse (import verification)
# ---------------------------------------------------------------------------


def test_metric_imports_judge_panel_config() -> None:
    """DivergenceMetric uses JUDGE_PANEL_CONFIG from eval_harness.judge (not redefined)."""
    import importlib

    metric_mod = importlib.import_module("eval_harness.divergence.metric")
    judge_mod = importlib.import_module("eval_harness.judge")

    # metric.py must reference the same object, not a copy
    assert metric_mod.JUDGE_PANEL_CONFIG is judge_mod.JUDGE_PANEL_CONFIG, (
        "JUDGE_PANEL_CONFIG in metric.py must be imported from eval_harness.judge, not redefined"
    )
    assert metric_mod.make_judge is judge_mod.make_judge, (
        "make_judge in metric.py must be imported from eval_harness.judge, not redefined"
    )


# ---------------------------------------------------------------------------
# check_regression — rate-based Gate 1 (Fix E, quick-260529-sot)
# ---------------------------------------------------------------------------


def _hard_rule_id() -> str:
    """A real hard-severity rule_id from the librarian rubric."""
    return next(c.id for c in ROLE_CHECKS["librarian"] if c.severity == "hard")


def test_check_regression_equal_rate_at_higher_scale_passes() -> None:
    """runs=12/failures=9 (rate 0.75) vs baseline runs=4/failures=3 (rate 0.75)
    must NOT raise — Gate 1 compares RATES, not absolute counts."""
    from eval_harness.divergence.metric import check_regression

    rule = _hard_rule_id()
    baseline = {"checks": {rule: {"failures": 3, "runs": 4}}}
    current = {rule: {"runs": 12, "failures": 9}}

    # Does not raise.
    check_regression("librarian", current, baseline)


def test_check_regression_higher_rate_raises() -> None:
    """runs=12/failures=12 (rate 1.0) > baseline rate 0.75 DOES raise."""
    from eval_harness.divergence.metric import check_regression

    rule = _hard_rule_id()
    baseline = {"checks": {rule: {"failures": 3, "runs": 4}}}
    current = {rule: {"runs": 12, "failures": 12}}

    with pytest.raises(AssertionError):
        check_regression("librarian", current, baseline)


def test_check_regression_zero_current_runs_skipped() -> None:
    """A rule whose current runs==0 carries no data — must be skipped (no raise)."""
    from eval_harness.divergence.metric import check_regression

    rule = _hard_rule_id()
    baseline = {"checks": {rule: {"failures": 0, "runs": 4}}}
    current = {rule: {"runs": 0, "failures": 0}}

    # Does not raise — no data for this rule.
    check_regression("librarian", current, baseline)


def test_check_regression_missing_baseline_zero_floor() -> None:
    """Missing baseline (no runs field) keeps the 0.0-rate floor: any failure on
    a hard rule still raises."""
    from eval_harness.divergence.metric import check_regression

    rule = _hard_rule_id()
    baseline = {"checks": {}}  # no entry for this rule
    current = {rule: {"runs": 4, "failures": 1}}

    with pytest.raises(AssertionError):
        check_regression("librarian", current, baseline)
