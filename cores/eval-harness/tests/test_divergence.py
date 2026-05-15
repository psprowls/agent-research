from __future__ import annotations

"""Integration test for the full DivergenceMetric pipeline (EVAL-12, EVAL-13).

Gated behind CODE_WIKI_RUN_EVAL=1 so it does not run in quick CI. Parametrized
over all four roles: librarian, ingestor, linter, scanner.

This test exercises the full programmatic + LLM-judge divergence check against
the round-trip-vault fixture and either:
  - Writes the per-role baseline JSON when --accept-divergence-baseline is passed.
  - Compares current results against the stored baseline otherwise, asserting that
    no hard-severity rule regresses (EVAL-13 regression gate).

Per-rule failure counts and the first 3 accepted_failures excerpts are printed
under `pytest -s` (EVAL-12 "concrete examples in the report" requirement).

Security:
  T-06-24: EVAL_GATE + CODE_WIKI_RUN_EVAL guard — no Bedrock calls without the env var.
  T-06-25: Underlying Bedrock errors surface directly; no exception swallowing.
  T-06-26: _current_agent_commit() writes git SHA into every accepted baseline.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Add tests/ directory to sys.path so conftest can be imported as a module.
# conftest.py lives in cores/eval-harness/tests/ (same dir as this file).
sys.path.insert(0, str(Path(__file__).parent))

from eval_harness.divergence import ROLE_CHECKS, ROLE_RUBRICS
from eval_harness.divergence.metric import (
    DivergenceMetric,
    check_regression,
    load_baseline,
    write_baseline,
)

# ---------------------------------------------------------------------------
# Eval gate — matches the EVAL_GATE constant in conftest.py
# ---------------------------------------------------------------------------

EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_EVAL"),
    reason="Set CODE_WIKI_RUN_EVAL=1 to run divergence eval",
)

# Baselines directory: cores/eval-harness/baselines/
# cores/eval-harness/tests/test_divergence.py
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
# Import the per-role output-producer helper from conftest.py
# ---------------------------------------------------------------------------

# _produce_outputs is defined in conftest.py (same directory) and is available
# as a plain callable — not a pytest fixture — so we can import it directly.
from conftest import _produce_outputs  # noqa: E402


# ---------------------------------------------------------------------------
# Main integration test — EVAL_GATE + parametrized over 4 roles
# ---------------------------------------------------------------------------


@EVAL_GATE
@pytest.mark.parametrize("role", ["librarian", "ingestor", "linter", "scanner"])
def test_divergence_regression(
    role: str,
    fixture_vault_path: Path,
    accept_baseline: bool,
    capsys: pytest.CaptureFixture,
) -> None:
    """Full divergence eval pipeline passes without hard-severity regressions.

    Requires CODE_WIKI_RUN_EVAL=1 and a live Bedrock connection. Uses
    fixture_vault_path from conftest.py and accept_baseline from the
    --accept-divergence-baseline CLI option.

    When accept_baseline=True: writes current results to
    cores/eval-harness/baselines/divergence-{role}.json and returns.

    When accept_baseline=False (default): loads the stored baseline and calls
    check_regression(), which raises AssertionError if any hard-severity rule
    has more failures than the baseline. The test passes silently (report
    visible under `pytest -s`) when there is no regression.
    """
    # Produce real agent outputs for this role via the fixture corpus
    outputs = _produce_outputs(role, fixture_vault_path)

    # Build and run the DivergenceMetric (programmatic + judge passes)
    metric = DivergenceMetric(
        role=role,
        checks=ROLE_CHECKS[role],
        rubric_path=ROLE_RUBRICS[role],
        vault=fixture_vault_path,
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
