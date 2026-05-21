from __future__ import annotations

"""Shared pytest fixtures for eval-harness tests.

Provides:
- fixture_wiki_path: resolves the cross-package round-trip-vault fixture so
  unit and integration tests can read real wiki pages without committing
  duplicate data. (The on-disk directory is still ``round-trip-vault`` per
  Phase 22 D-10 / Phase 24 D-10 — only the eval-harness nomenclature changed.)
- fixture_workspace_path: a tmp_path-rooted workspace that contains a
  ``wiki`` symlink to fixture_wiki_path. Tests that call public functions
  taking ``workspace_path`` (Phase 24 D-01) pass this fixture; the wiki dir
  is then resolved via ``workspace_io.paths.wiki_dir(workspace_path)``.
- accept_baseline: returns the value of --accept-divergence-baseline CLI option
  so divergence tests can overwrite baseline files when requested (EVAL-13).
- EVAL_GATE: pytest.mark.skipif decorator gating eval tests on GRAPH_WIKI_RUN_EVAL=1.

Output-producer helpers have been moved to eval_helpers.py (WR-05).
Import produce_outputs from there directly in test files.
"""

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
    """Return the Path to packages/vault-io/tests/fixtures/round-trip-vault.

    The path is computed relative to this conftest file so it works regardless
    of the cwd from which pytest is invoked. The fixture asserts the path
    exists so a misconfigured repo fails fast with a clear message rather than
    confusing FileNotFoundError in downstream tests.

    Note: the on-disk fixture directory is named ``round-trip-vault`` and
    lives under ``packages/vault-io/`` — those paths are milestone-locked
    (Phase 22 D-10 / Phase 24 D-10). Only the eval-harness fixture name
    changed (vault → wiki) per Phase 24's nomenclature rename.

    Threat mitigation T-4-01: path is anchored to this file's location;
    no user-supplied input is involved.
    """
    wiki = (
        Path(__file__).parent.parent.parent.parent
        / "packages"
        / "vault-io"
        / "tests"
        / "fixtures"
        / "round-trip-vault"
    )
    if not wiki.exists():
        pytest.skip(
            f"round-trip-vault fixture not found at {wiki}; "
            "check that packages/vault-io is present in the workspace."
        )
    return wiki


@pytest.fixture
def fixture_workspace_path(tmp_path: Path, fixture_wiki_path: Path) -> Path:
    """Build a workspace-shaped tmp dir that points to the round-trip wiki.

    Returns ``tmp_path`` after symlinking ``tmp_path / "wiki"`` to
    ``fixture_wiki_path``. Tests that exercise public functions taking
    ``workspace_path`` (post-Phase-24 D-01) pass this fixture; the wiki dir
    is derived internally via ``workspace_io.paths.wiki_dir(workspace_path)``,
    which lands back on the round-trip-vault fixture.

    Threat mitigation T-4-01: both ends of the symlink are anchored to
    test-machine-local Paths; no user-supplied input is involved.
    """
    wiki_link = tmp_path / "wiki"
    if not wiki_link.exists():
        wiki_link.symlink_to(fixture_wiki_path, target_is_directory=True)
    return tmp_path


