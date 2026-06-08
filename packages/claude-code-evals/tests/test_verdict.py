"""Tests for verdict computation logic."""

from __future__ import annotations

from claude_code_evals.verdict import compute_verdict


def test_correctness_gated_verdict_base_fails_injected_passes():
    """Correctness-gated: if base fails and injected passes, verdict is WIKI_HELPED."""
    base_score = 0.0
    injected_score = 1.0
    plugin_score = 0.8

    verdict = compute_verdict(
        discriminator_type="correctness-gated",
        base_score=base_score,
        injected_score=injected_score,
        plugin_score=plugin_score,
    )

    assert verdict.verdict == "WIKI_HELPED"
    assert "base failed" in verdict.reason
    assert "injected passed" in verdict.reason


def test_correctness_gated_verdict_both_pass():
    """Correctness-gated: if both base and injected pass, verdict is NO_WIKI_VALUE."""
    base_score = 0.8
    injected_score = 1.0
    plugin_score = 0.7

    verdict = compute_verdict(
        discriminator_type="correctness-gated",
        base_score=base_score,
        injected_score=injected_score,
        plugin_score=plugin_score,
    )

    assert verdict.verdict == "NO_WIKI_VALUE"
    assert "base was sufficient" in verdict.reason


def test_correctness_gated_verdict_both_fail():
    """Correctness-gated: if both base and injected fail, verdict is NO_WIKI_VALUE."""
    base_score = 0.2
    injected_score = 0.3
    plugin_score = 0.2

    verdict = compute_verdict(
        discriminator_type="correctness-gated",
        base_score=base_score,
        injected_score=injected_score,
        plugin_score=plugin_score,
    )

    assert verdict.verdict == "NO_WIKI_VALUE"
    assert "scenario is broken" in verdict.reason


def test_efficiency_gated_verdict_wiki_helps():
    """Efficiency-gated: if plugin beats base by threshold, verdict is WIKI_HELPED."""
    base_files = 29
    injected_files = 8
    plugin_files = 11

    verdict = compute_verdict(
        discriminator_type="efficiency-gated",
        base_metric=base_files,
        injected_metric=injected_files,
        plugin_metric=plugin_files,
        metric="files_read_count",
        min_improvement_pct=40,  # plugin must be 40% better than base
    )

    # 11 files vs 29 = 62% improvement > 40% threshold
    assert verdict.verdict == "WIKI_HELPED"
    assert "62%" in verdict.reason


def test_efficiency_gated_verdict_wiki_doesnt_help():
    """Efficiency-gated: if plugin doesn't beat threshold, verdict is NO_WIKI_VALUE."""
    base_files = 29
    plugin_files = 25

    verdict = compute_verdict(
        discriminator_type="efficiency-gated",
        base_metric=base_files,
        plugin_metric=plugin_files,
        metric="files_read_count",
        min_improvement_pct=40,
    )

    # 25 files vs 29 = 14% improvement < 40% threshold
    assert verdict.verdict == "NO_WIKI_VALUE"
    assert "14%" in verdict.reason
    assert "below threshold" in verdict.reason


def test_impossible_without_wiki_base_fails_plugin_passes():
    """Impossible-without-wiki: if base fails and plugin passes, verdict is WIKI_HELPED."""
    base_score = 0.0
    injected_score = 1.0
    plugin_score = 0.9

    verdict = compute_verdict(
        discriminator_type="impossible-without-wiki",
        base_score=base_score,
        injected_score=injected_score,
        plugin_score=plugin_score,
    )

    assert verdict.verdict == "WIKI_HELPED"
    assert "base failed" in verdict.reason
    assert "plugin passed" in verdict.reason


def test_impossible_without_wiki_base_passes_plugin_fails():
    """Impossible-without-wiki: if base passes but plugin fails, verdict is PLUGIN_MISS."""
    base_score = 0.9
    injected_score = 1.0
    plugin_score = 0.2

    verdict = compute_verdict(
        discriminator_type="impossible-without-wiki",
        base_score=base_score,
        injected_score=injected_score,
        plugin_score=plugin_score,
    )

    assert verdict.verdict == "PLUGIN_MISS"
    assert "agent didn't query wiki" in verdict.reason


def test_impossible_without_wiki_both_fail():
    """Impossible-without-wiki: if both base and plugin fail, verdict is NO_WIKI_VALUE."""
    base_score = 0.2
    injected_score = 0.9
    plugin_score = 0.1

    verdict = compute_verdict(
        discriminator_type="impossible-without-wiki",
        base_score=base_score,
        injected_score=injected_score,
        plugin_score=plugin_score,
    )

    assert verdict.verdict == "NO_WIKI_VALUE"
    assert "both base and plugin failed" in verdict.reason


def test_impossible_without_wiki_both_pass():
    """Impossible-without-wiki: if both base and plugin pass, verdict is NO_WIKI_VALUE."""
    base_score = 0.8
    injected_score = 1.0
    plugin_score = 0.9

    verdict = compute_verdict(
        discriminator_type="impossible-without-wiki",
        base_score=base_score,
        injected_score=injected_score,
        plugin_score=plugin_score,
    )

    assert verdict.verdict == "NO_WIKI_VALUE"
    assert "not actually impossible" in verdict.reason
