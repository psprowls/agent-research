from __future__ import annotations

"""Integration test for the full DivergenceMetric pipeline (EVAL-12).

Gated behind CODE_WIKI_RUN_EVAL=1 (same pattern as conftest.py EVAL_GATE) so
it does not run in quick CI. Parametrized over all four roles that have
canonical source content: librarian, ingestor, linter, scanner.

This test exercises the full programmatic + LLM-judge divergence check against
the round-trip-vault fixture and writes (or compares against) per-role baseline
files in cores/eval-harness/baselines/.

Tests skip until the divergence.metric module lands in 06-09/06-11.
"""

import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Eval gate — matches the EVAL_GATE constant in conftest.py
# ---------------------------------------------------------------------------

EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_EVAL"),
    reason="Set CODE_WIKI_RUN_EVAL=1 to run divergence eval",
)

# ---------------------------------------------------------------------------
# Import guard — skip entire module if divergence package not yet implemented
# ---------------------------------------------------------------------------

_DIVERGENCE_AVAILABLE = True
try:
    from eval_harness.divergence.metric import check_regression, load_baseline
except ImportError:
    _DIVERGENCE_AVAILABLE = False

# Baselines directory: cores/eval-harness/baselines/
# cores/eval-harness/tests/test_divergence.py
#   parent[0] → tests/
#   parent[1] → eval-harness/
#   parent[2] → cores/
BASELINES_DIR = Path(__file__).parent.parent / "baselines"


# ---------------------------------------------------------------------------
# Integration test — EVAL_GATE + parametrized over roles
# ---------------------------------------------------------------------------


@EVAL_GATE
@pytest.mark.parametrize("role", ["librarian", "ingestor", "linter", "scanner"])
def test_divergence_regression(
    role: str,
    fixture_vault_path: Path,
    accept_baseline: bool,
) -> None:
    """Full divergence eval pipeline passes without hard-severity regressions.

    Requires CODE_WIKI_RUN_EVAL=1 and a live Bedrock connection. Uses
    fixture_vault_path from conftest.py and accept_baseline from the
    --accept-divergence-baseline CLI option.
    """
    if not _DIVERGENCE_AVAILABLE:
        pytest.skip("divergence.metric module not yet implemented (lands in 06-11)")
    pytest.skip("filled in by 06-11")
