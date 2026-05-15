from __future__ import annotations

"""Unit tests for per-role DivergenceCheck callables (EVAL-11).

All tests are deterministic and require no Bedrock access. They exercise
the DivergenceCheck.check callables against synthetic in-memory
AgentOutputProxy and tiny vault fixtures.

Tests skip at module level when the divergence subpackage has not landed yet
(before 06-08); they are stub-stubbed per rule-id so `pytest --collect-only`
shows the expected test IDs even before the implementation exists.
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import guard — skip entire module if divergence package not yet implemented
# ---------------------------------------------------------------------------

_DIVERGENCE_AVAILABLE = True
try:
    from eval_harness.divergence.check import AgentOutputProxy, DivergenceCheck
    from eval_harness.divergence.librarian import LIBRARIAN_CHECKS
    from eval_harness.divergence.ingestor import INGESTOR_CHECKS
    from eval_harness.divergence.linter import LINTER_CHECKS
    from eval_harness.divergence.scanner import SCANNER_CHECKS
except ImportError:
    _DIVERGENCE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _DIVERGENCE_AVAILABLE,
    reason="divergence module not yet implemented (lands in 06-08)",
)


# ---------------------------------------------------------------------------
# Librarian checks
# ---------------------------------------------------------------------------


def test_lib001_passes_on_resolved_wikilink(fixture_vault_path: Path) -> None:
    """LIB-001 passes when all wikilinks in the answer resolve to existing vault pages."""
    pytest.skip("filled in by 06-08")


def test_lib001_fails_on_unresolved_wikilink(fixture_vault_path: Path) -> None:
    """LIB-001 fails when a wikilink does not resolve; excerpt names the unresolved link."""
    pytest.skip("filled in by 06-08")


# ---------------------------------------------------------------------------
# Ingestor checks
# ---------------------------------------------------------------------------


def test_ing001_frontmatter_present(fixture_vault_path: Path) -> None:
    """ING-001 passes when ingestor output contains YAML frontmatter delimiters."""
    pytest.skip("filled in by 06-08")


# ---------------------------------------------------------------------------
# Linter checks
# ---------------------------------------------------------------------------


def test_lnt002_findings_nonempty(fixture_vault_path: Path) -> None:
    """LNT-002 check validates that linter output is non-empty when issues exist."""
    pytest.skip("filled in by 06-08")


# ---------------------------------------------------------------------------
# Scanner checks
# ---------------------------------------------------------------------------


def test_scn001_frontmatter_present(fixture_vault_path: Path) -> None:
    """SCN-001 passes when scanner output contains YAML frontmatter delimiters."""
    pytest.skip("filled in by 06-08")
