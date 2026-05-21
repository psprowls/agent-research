from __future__ import annotations

"""Integration test for the full DivergenceMetric pipeline (EVAL-12, EVAL-13).

Gated behind GRAPH_WIKI_RUN_EVAL=1 so it does not run in quick CI. Parametrized
over all four roles: librarian, ingestor, linter, scanner.

This test exercises the full programmatic + LLM-judge divergence check against
the round-trip-vault fixture and either:
  - Writes the per-role baseline JSON when --accept-divergence-baseline is passed.
  - Compares current results against the stored baseline otherwise, asserting that
    no hard-severity rule regresses (EVAL-13 regression gate).

Per-rule failure counts and the first 3 accepted_failures excerpts are printed
under `pytest -s` (EVAL-12 "concrete examples in the report" requirement).

Security:
  T-06-24: EVAL_GATE + GRAPH_WIKI_RUN_EVAL guard — no Bedrock calls without the env var.
  T-06-25: Underlying Bedrock errors surface directly; no exception swallowing.
  T-06-26: _current_agent_commit() writes git SHA into every accepted baseline.
"""

import subprocess
from pathlib import Path

import pytest

from eval_harness.divergence import ROLE_CHECKS, ROLE_RUBRICS
from eval_harness.divergence.metric import (
    DivergenceMetric,
    check_regression,
    load_baseline,
    write_baseline,
)

# Eval gate and helpers — imported from eval_helpers (WR-05, WR-06)
from eval_helpers import EVAL_GATE, produce_outputs as _produce_outputs

# Baselines directory: packages/eval-harness/baselines/
# packages/eval-harness/tests/test_divergence.py
#   parent[0] → tests/
#   parent[1] → eval-harness/
BASELINES_DIR = Path(__file__).parent.parent / "baselines"


# ---------------------------------------------------------------------------
# Helper: capture current agent git SHA for baseline provenance (T-06-26)
# ---------------------------------------------------------------------------


def _current_agent_commit() -> str:
    """Return the short git SHA of HEAD, or 'unknown' if git is unavailable."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"




# ---------------------------------------------------------------------------
# Main integration test — EVAL_GATE + parametrized over 4 roles
# ---------------------------------------------------------------------------


@EVAL_GATE
@pytest.mark.parametrize("role", ["librarian", "ingestor", "linter", "scanner"])
def test_divergence_regression(
    role: str,
    fixture_wiki_path: Path,
    fixture_workspace_path: Path,
    accept_baseline: bool,
    capsys: pytest.CaptureFixture,
) -> None:
    """Full divergence eval pipeline passes without hard-severity regressions.

    Requires GRAPH_WIKI_RUN_EVAL=1 and a live Bedrock connection. Uses
    fixture_workspace_path (for produce_outputs, which feeds agent commands
    that expect a workspace_path post-Phase-24 D-01) and fixture_wiki_path
    (for DivergenceMetric, whose check functions take a bare wiki: Path per D-03).
    accept_baseline comes from the --accept-divergence-baseline CLI option.

    When accept_baseline=True: writes current results to
    packages/eval-harness/baselines/divergence-{role}.json and returns.

    When accept_baseline=False (default): loads the stored baseline and calls
    check_regression(), which raises AssertionError if any hard-severity rule
    has more failures than the baseline. The test passes silently (report
    visible under `pytest -s`) when there is no regression.
    """
    # Produce real agent outputs for this role via the fixture corpus.
    # produce_outputs takes a workspace path (post-Phase-24 D-01); the agent
    # commands inside derive the wiki via wiki_dir(workspace_path).
    outputs = _produce_outputs(role, fixture_workspace_path)

    # Build and run the DivergenceMetric (programmatic + judge passes)
    metric = DivergenceMetric(
        role=role,
        checks=ROLE_CHECKS[role],
        rubric_path=ROLE_RUBRICS[role],
        wiki=fixture_wiki_path,
    )
    results = metric.run(outputs)

    # EVAL-12: print per-rule failure counts + first 3 accepted_failures excerpts
    # (visible under `pytest -s`)
    print(f"\n=== Divergence report: {role} ===")
    for rule_id, data in results.items():
        print(f"  {rule_id}: runs={data['runs']} failures={data['failures']}")
        for failure in data["accepted_failures"][:3]:
            print(f"    - [{failure['fixture']}] {failure['excerpt']}")

    if accept_baseline:
        # Write current results as the new baseline (EVAL-13 baseline acceptance)
        path = write_baseline(role, BASELINES_DIR, results, _current_agent_commit())
        print(f"\n  Baseline written to: {path}")
        return

    # EVAL-13 regression gate: raises AssertionError on hard-severity regression
    baseline = load_baseline(role, BASELINES_DIR)
    check_regression(role, results, baseline)
