"""Scanner regression check against the synthetic post-rebrand fixture vault.

CI-runnable forward-regression check (no Bedrock — uses deterministic
SCANNER_CHECKS programmatic rules against pinned fixture pages). SWEEP-FU-04 (a)
per D-11.

NOTE — two-baseline split: This is the FORWARD-regression half. The first
Phase-16 run seeds the snapshot baseline; subsequent runs compare. Because the
synthetic fixture is brand-new in Phase 16, it has no v1.1 baseline to compare
against. The v1.1-equivalent regression check (live-vault re-sweep against
`~/Personal/graph-wiki/agent-research`) lives in Task 9 / 16-VERIFICATION.md SC#2 and
provides the v1.1 → v1.2 regression evidence on the same vault that v1.1 ran
against.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from eval_harness.divergence.check import AgentOutputProxy
from eval_harness.divergence.scanner import SCANNER_CHECKS


# Cross-package fixture vault path, precomputed at import time (mirrors
# the FIXTURE_VAULT pattern from test_query_e2e.py:27-34).
FIXTURE_VAULT: Path = Path(__file__).parent / "fixtures" / "post-rebrand-vault"

# Pinned baseline: every package page must pass every hard SCANNER_CHECKS rule.
# The first Phase-16 run seeded this baseline; future drift trips the assertion.
_EXPECTED_PACKAGE_FILES: tuple[str, ...] = (
    "workspace-io",
    "wiki-io",
    "prompt-sources",
    "subagent-runtime",
    "model-adapter",
    "eval-harness",
)


def _package_page_for(name: str) -> Path:
    return FIXTURE_VAULT / "packages" / name / f"{name}.md"


def test_fixture_vault_contains_every_post_rebrand_package() -> None:
    """Fixture vault has one page per current packages/* member."""
    for pkg in _EXPECTED_PACKAGE_FILES:
        assert _package_page_for(pkg).is_file(), (
            f"missing fixture page for {pkg}: {_package_page_for(pkg)}"
        )


def test_fixture_vault_contains_no_lattice_symbols() -> None:
    """Fixture is post-rebrand by construction — no lattice* names anywhere."""
    for md in FIXTURE_VAULT.rglob("*.md"):
        text = md.read_text()
        lowered = text.lower()
        assert "lattice" not in lowered, (
            f"fixture page {md.relative_to(FIXTURE_VAULT)} still contains 'lattice'"
        )


@pytest.mark.parametrize("package", _EXPECTED_PACKAGE_FILES)
def test_scanner_hard_checks_pass_on_fixture_page(package: str) -> None:
    """Every fixture package page passes every hard SCANNER_CHECKS rule.

    Acts as the pinned baseline. If a future PR breaks the canonical scanner
    output shape (missing frontmatter field, dropped section, etc), this test
    fails — surfacing the regression before it reaches the live sweep.
    """
    page = _package_page_for(package)
    proxy = AgentOutputProxy(answer=page.read_text())
    hard_failures: list[tuple[str, str]] = []
    for check in SCANNER_CHECKS:
        if check.severity != "hard":
            continue
        verdict = check.check(proxy, FIXTURE_VAULT)
        if not verdict.passed:
            hard_failures.append((check.id, verdict.excerpt))
    assert not hard_failures, (
        f"scanner regression on {package}: {hard_failures}"
    )
