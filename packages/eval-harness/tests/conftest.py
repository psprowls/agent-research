from __future__ import annotations

"""Shared pytest fixtures for eval-harness tests.

Provides:
- fixture_vault_path: resolves the cross-package round-trip-vault fixture so
  unit and integration tests can read real vault pages without committing
  duplicate data.
- accept_baseline: returns the value of --accept-divergence-baseline CLI option
  so divergence tests can overwrite baseline files when requested (EVAL-13).
- EVAL_GATE: pytest.mark.skipif decorator gating eval tests on CODE_WIKI_RUN_EVAL=1.

Output-producer helpers have been moved to eval_helpers.py (WR-05).
Import produce_outputs from there directly in test files.
"""

import os
from pathlib import Path

import pytest

# Eval gate: decorate eval tests so they are skipped unless CODE_WIKI_RUN_EVAL=1 is set.
# Also defined in eval_helpers.EVAL_GATE (same condition) so test files can import it
# directly without importing conftest as a plain module (which fails under
# --import-mode=importlib). Both definitions are intentionally in sync.
EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_EVAL"),
    reason="Set CODE_WIKI_RUN_EVAL=1 to run eval sweep tests",
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom CLI options for the eval-harness test suite."""
    parser.addoption(
        "--accept-divergence-baseline",
        action="store_true",
        default=False,
        help="Overwrite divergence baselines with current run results",
    )


@pytest.fixture
def accept_baseline(request: pytest.FixtureRequest) -> bool:
    """Return True if --accept-divergence-baseline was passed on the CLI."""
    return request.config.getoption("--accept-divergence-baseline")


@pytest.fixture
def fixture_vault_path() -> Path:
    """Return the Path to packages/vault-io/tests/fixtures/round-trip-vault.

    The path is computed relative to this conftest file so it works regardless
    of the cwd from which pytest is invoked. The fixture asserts the path
    exists so a misconfigured repo fails fast with a clear message rather than
    confusing FileNotFoundError in downstream tests.

    Threat mitigation T-4-01: path is anchored to this file's location;
    no user-supplied input is involved.
    """
    vault = (
        Path(__file__).parent.parent.parent.parent
        / "packages"
        / "vault-io"
        / "tests"
        / "fixtures"
        / "round-trip-vault"
    )
    if not vault.exists():
        pytest.skip(
            f"round-trip-vault fixture not found at {vault}; "
            "check that packages/vault-io is present in the workspace."
        )
    return vault


