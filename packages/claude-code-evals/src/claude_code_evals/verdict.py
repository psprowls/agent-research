"""Verdict computation for three-arm wiki eval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class Verdict:
    """Result of comparing metrics across three arms."""

    verdict: Literal["WIKI_HELPED", "NO_WIKI_VALUE", "PLUGIN_MISS", "INCOMPLETE"]
    reason: str
    injected_ceiling_score: Optional[float] = None
    discovery_cost: Optional[float] = None


def compute_verdict(
    discriminator_type: str,
    base_score: Optional[float] = None,
    base_metric: Optional[float] = None,
    injected_score: Optional[float] = None,
    injected_metric: Optional[float] = None,
    plugin_score: Optional[float] = None,
    plugin_metric: Optional[float] = None,
    metric: Optional[str] = None,
    min_improvement_pct: Optional[float] = None,
) -> Verdict:
    """Compute verdict by comparing arms.

    Args:
        discriminator_type: One of 'correctness-gated', 'efficiency-gated', 'impossible-without-wiki'
        base_score: Score (0.0–1.0) for base arm
        injected_score: Score for injected arm
        plugin_score: Score for plugin arm
        base_metric: Numeric metric for base arm
        injected_metric: Numeric metric for injected arm
        plugin_metric: Numeric metric for plugin arm
        metric: Name of metric (for efficiency-gated)
        min_improvement_pct: Threshold for improvement (for efficiency-gated)

    Returns:
        Verdict object with verdict and reason
    """

    if discriminator_type == "correctness-gated":
        return _verdict_correctness_gated(base_score, injected_score, plugin_score)
    elif discriminator_type == "efficiency-gated":
        return _verdict_efficiency_gated(base_metric, plugin_metric, injected_metric, metric, min_improvement_pct)
    elif discriminator_type == "impossible-without-wiki":
        return _verdict_impossible_without_wiki(base_score, injected_score, plugin_score)
    else:
        return Verdict("INCOMPLETE", f"Unknown discriminator type: {discriminator_type}")


def _verdict_correctness_gated(
    base_score: float,
    injected_score: float,
    plugin_score: float,
) -> Verdict:
    """Judge correctness-gated scenario.

    Wiki helps if:
    - Base fails (< 0.5)
    - Injected passes (>= 0.5)
    """
    base_passes = base_score >= 0.5
    injected_passes = injected_score >= 0.5

    if not base_passes and injected_passes:
        discovery_cost = injected_score - plugin_score
        return Verdict(
            "WIKI_HELPED",
            f"correctness: base failed ({base_score:.1%}), injected passed ({injected_score:.1%})",
            injected_ceiling_score=injected_score,
            discovery_cost=discovery_cost,
        )
    elif injected_passes:
        return Verdict(
            "NO_WIKI_VALUE",
            "correctness: both base and injected passed; base was sufficient",
        )
    else:
        return Verdict(
            "NO_WIKI_VALUE",
            f"correctness: scenario is broken; even injected failed ({injected_score:.1%})",
        )


def _verdict_efficiency_gated(
    base_metric: float,
    plugin_metric: float,
    injected_metric: Optional[float],
    metric: str,
    min_improvement_pct: float,
) -> Verdict:
    """Judge efficiency-gated scenario.

    Wiki helps if plugin beats base by min_improvement_pct.
    """
    if plugin_metric is None:
        return Verdict("INCOMPLETE", "plugin metric not recorded")

    improvement_pct = (1.0 - plugin_metric / base_metric) * 100

    if improvement_pct >= min_improvement_pct:
        return Verdict(
            "WIKI_HELPED",
            f"efficiency: {metric} improved {improvement_pct:.0f}% (threshold {min_improvement_pct:.0f}%)",
            discovery_cost=injected_metric - plugin_metric if injected_metric else 0,
        )
    else:
        return Verdict(
            "NO_WIKI_VALUE",
            f"efficiency: {metric} improved {improvement_pct:.0f}%, below threshold {min_improvement_pct:.0f}%",
        )


def _verdict_impossible_without_wiki(
    base_score: float,
    injected_score: float,
    plugin_score: float,
) -> Verdict:
    """Judge impossible-without-wiki scenario.

    Wiki helps if:
    - Base fails (< 0.5)
    - Plugin passes (>= 0.5)

    Plugin miss if:
    - Base passes (>= 0.5)
    - Plugin fails (< 0.5)
    """
    base_passes = base_score >= 0.5
    plugin_passes = plugin_score >= 0.5

    if base_passes and not plugin_passes:
        return Verdict(
            "PLUGIN_MISS",
            f"impossible-without-wiki: base passed ({base_score:.1%}), "
            f"but plugin failed ({plugin_score:.1%}); agent didn't query wiki",
        )
    elif not base_passes and plugin_passes:
        return Verdict(
            "WIKI_HELPED",
            f"impossible-without-wiki: base failed ({base_score:.1%}), plugin passed ({plugin_score:.1%})",
            injected_ceiling_score=injected_score,
        )
    elif not base_passes and not plugin_passes:
        return Verdict(
            "NO_WIKI_VALUE",
            "impossible-without-wiki: both base and plugin failed; wiki page may not be discoverable or not help",
        )
    else:
        return Verdict(
            "NO_WIKI_VALUE",
            f"impossible-without-wiki: base passed ({base_score:.1%}); not actually impossible without wiki",
        )
