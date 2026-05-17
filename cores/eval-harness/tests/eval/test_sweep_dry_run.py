"""Dry-run integration test for the full cost-frontier sweep pipeline.

Phase 1 (@pytest.mark.eval): Run a mock-LLM dry-run sweep for all 6 roles
and assert that per-role docs and INDEX.md are written with $0 spend.

Gate: module-level pytestmark includes both `pytest.mark.eval` (skips
without --run-eval) and `pytest.mark.skip` (pending Plan 07-06). Once
Plan 07-06 lands the sweep runner, the skip reason is removed.

Security (T-4-01): all path construction is anchored to __file__; no
user-supplied input reaches path resolution.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add parent tests/ dir to sys.path so conftest.py can be imported as a module.
# conftest.py lives in cores/eval-harness/tests/ (one level up from this file).
sys.path.insert(0, str(Path(__file__).parent.parent))

# Resolve workspace root: 5 parents from this file
# cores/eval-harness/tests/eval/test_sweep_dry_run.py
#   → parent[0] eval/
#   → parent[1] tests/
#   → parent[2] eval-harness/
#   → parent[3] cores/
#   → parent[4] workspace-root
_WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent.parent

CASES_PATH = _WORKSPACE_ROOT / "eval" / "cases" / "query_cases.json"
FIXTURE_VAULT = (
    _WORKSPACE_ROOT
    / "cores"
    / "vault-io"
    / "tests"
    / "fixtures"
    / "round-trip-vault"
)

# Module-level marks:
# - pytest.mark.eval: skips without --run-eval (same as test_sweep_eval.py)
# - pytest.mark.skip: pending Plan 07-06 implementation
pytestmark = [
    pytest.mark.eval,
    pytest.mark.skip(reason="Pending Plan 07-06"),
]

from conftest import EVAL_GATE  # noqa: E402


# ---------------------------------------------------------------------------
# Dry-run integration tests (mock LLM — no Bedrock calls)
# ---------------------------------------------------------------------------


def test_dry_run_writes_all_role_docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--dry-run sweep with mock LLM writes {role}.md for all 6 roles + INDEX.md.

    Asserts:
    - .planning/sweep/{role}.md exists for each of the 6 roles
    - Each role doc contains 'Pareto frontier'
    - INDEX.md exists in .planning/sweep/
    - Total spend is $0 (dry-run, mock LLM)
    """
    raise NotImplementedError("TODO Plan 07-06")


def test_dry_run_pre_flight_estimator_prints_estimate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """--dry-run sweep prints a pre-flight cost estimate to stdout before running."""
    raise NotImplementedError("TODO Plan 07-06")


def test_dry_run_skips_bed01_when_no_aws(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--dry-run sweep skips BED-01 connectivity check when AWS credentials are absent."""
    raise NotImplementedError("TODO Plan 07-06")
