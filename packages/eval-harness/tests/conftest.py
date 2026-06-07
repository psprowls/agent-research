"""Shared pytest fixtures for eval-harness tests.

Provides:
- fixture_workspace_path: resolves the workspace-shaped post-rebrand fixture.
  Tests that call public functions taking ``workspace_path`` pass this fixture;
  the wiki dir is then resolved via ``workspace_io.paths.wiki_dir(workspace_path)``.
- fixture_wiki_path: resolves the fixture wiki at ``fixture_workspace_path / "wiki"``.
- accept_baseline: returns the value of --accept-divergence-baseline CLI option
  so divergence tests can overwrite baseline files when requested (EVAL-13).
- EVAL_GATE: pytest.mark.skipif decorator gating eval tests on GRAPH_WIKI_RUN_EVAL=1.

Output-producer helpers have been moved to eval_helpers.py (WR-05).
Import produce_outputs from there directly in test files.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Eval gate: decorate eval tests so they are skipped unless GRAPH_WIKI_RUN_EVAL=1 is set.
# Also defined in eval_helpers.EVAL_GATE (same condition) so test files can import it
# directly without importing conftest as a plain module (which fails under
# --import-mode=importlib). Both definitions are intentionally in sync.
EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_EVAL"),
    reason="Set GRAPH_WIKI_RUN_EVAL=1 to run eval sweep tests",
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
def fixture_wiki_path() -> Path:
    """Return the Path to the post-rebrand fixture wiki.

    Threat mitigation T-4-01: path is anchored to this file's location; no
    user-supplied input is involved.
    """
    wiki = Path(__file__).parent / "fixtures" / "post-rebrand-workspace" / "wiki"
    if not wiki.exists():
        pytest.skip(f"post-rebrand fixture wiki not found at {wiki}; check that eval-harness fixtures are present.")
    return wiki


@pytest.fixture
def fixture_workspace_path(fixture_wiki_path: Path) -> Path:
    """Return the post-rebrand workspace fixture root.

    Tests that exercise public functions taking ``workspace_path`` pass this
    fixture; the wiki dir is derived internally via
    ``workspace_io.paths.wiki_dir(workspace_path)``.

    Threat mitigation T-4-01: both ends of the symlink are anchored to
    test-machine-local Paths; no user-supplied input is involved.
    """
    return fixture_wiki_path.parent
