from __future__ import annotations

"""Shared pytest fixtures for graph-wiki-agent tests.

Provides:
- fixture_vault_path: resolves the cross-package round-trip-vault fixture so
  unit and integration tests can read real vault pages without committing
  duplicate data.
"""

import os
from pathlib import Path

import pytest

# Integration gate: decorate real-Bedrock tests so they are skipped in CI
# unless CODE_WIKI_RUN_INTEGRATION=1 is set. Tests may import this from conftest
# or redefine it locally — either is fine.
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)


@pytest.fixture
def fixture_vault_path() -> Path:
    """Return the Path to packages/vault-io/tests/fixtures/round-trip-vault.

    The path is computed relative to this conftest file so it works regardless
    of the cwd from which pytest is invoked. The fixture asserts the path
    exists so a misconfigured repo fails fast with a clear message rather than
    confusing FileNotFoundError in downstream tests.

    Threat mitigation T-03-02: path is anchored to this file's location;
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
