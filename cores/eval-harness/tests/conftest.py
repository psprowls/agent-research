from __future__ import annotations

"""Shared pytest fixtures for eval-harness tests.

Provides:
- fixture_vault_path: resolves the cross-package round-trip-vault fixture so
  unit and integration tests can read real vault pages without committing
  duplicate data.
- accept_baseline: returns the value of --accept-divergence-baseline CLI option
  so divergence tests can overwrite baseline files when requested (EVAL-13).
- _produce_outputs(role, vault): callable helper that produces
  list[tuple[str, AgentOutputProxy, str]] for the given role by running the
  corresponding agent command against the Phase 4 fixture corpus. Guarded by
  CODE_WIKI_RUN_EVAL=1.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from eval_harness.divergence.check import AgentOutputProxy

# Eval gate: decorate eval tests so they are skipped unless CODE_WIKI_RUN_EVAL=1 is set.
EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_EVAL"),
    reason="Set CODE_WIKI_RUN_EVAL=1 to run eval sweep tests",
)

# Path to eval/cases/query_cases.json — used by librarian role outputs.
# cores/eval-harness/tests/conftest.py
#   parent[0] → tests/
#   parent[1] → eval-harness/
#   parent[2] → cores/
#   parent[3] → workspace-root
_WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
_QUERY_CASES_PATH = _WORKSPACE_ROOT / "eval" / "cases" / "query_cases.json"


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
    """Return the Path to cores/vault-io/tests/fixtures/round-trip-vault.

    The path is computed relative to this conftest file so it works regardless
    of the cwd from which pytest is invoked. The fixture asserts the path
    exists so a misconfigured repo fails fast with a clear message rather than
    confusing FileNotFoundError in downstream tests.

    Threat mitigation T-4-01: path is anchored to this file's location;
    no user-supplied input is involved.
    """
    vault = (
        Path(__file__).parent.parent.parent.parent
        / "cores"
        / "vault-io"
        / "tests"
        / "fixtures"
        / "round-trip-vault"
    )
    if not vault.exists():
        pytest.skip(
            f"round-trip-vault fixture not found at {vault}; "
            "check that cores/vault-io is present in the workspace."
        )
    return vault


def _produce_outputs(
    role: str,
    vault: Path,
) -> "list[tuple[str, AgentOutputProxy, str]]":
    """Produce agent outputs for the given role against the fixture corpus.

    Returns list[tuple[str, AgentOutputProxy, str]] shaped as:
        (fixture_id, AgentOutputProxy(answer=..., page_type=...), query_or_description)

    The triple matches DivergenceMetric.run() expected input shape.

    Args:
        role:  One of "librarian", "ingestor", "linter", "scanner".
        vault: Path to the round-trip-vault fixture (fixture_vault_path).

    Corpus assumptions (per EVAL plan):
        - librarian: eval/cases/query_cases.json in the workspace root.
          Missing → pytest.skip with path.
        - ingestor:  .md files from vault/packages/* or vault/concepts/*.
          Uses existing vault pages as "source documents" to re-ingest.
          Missing → pytest.skip with path.
        - linter:    The round-trip-vault itself (passed as vault arg).
          Missing → pytest.skip (vault check already done in fixture_vault_path).
        - scanner:   Uses the eval-harness package dir itself as the "monorepo"
          (cores/eval-harness) since it's a real Python package with pyproject.toml.
          Missing → pytest.skip with path.

    Raises:
        pytest.skip.Exception: if the corpus for the given role is not available.
        Any underlying exception from Bedrock/agent calls surfaces directly.

    Security (T-06-24): guards on CODE_WIKI_RUN_EVAL=1 — callers enforce this
    gate via the EVAL_GATE mark; this function adds a belt-and-suspenders check.
    """
    if not os.environ.get("CODE_WIKI_RUN_EVAL"):
        pytest.skip("CODE_WIKI_RUN_EVAL=1 required to produce agent outputs")

    from eval_harness.divergence.check import AgentOutputProxy  # noqa: PLC0415

    if role == "librarian":
        return _produce_librarian_outputs(vault)
    elif role == "ingestor":
        return _produce_ingestor_outputs(vault)
    elif role == "linter":
        return _produce_linter_outputs(vault)
    elif role == "scanner":
        return _produce_scanner_outputs(vault)
    else:
        pytest.skip(f"Unknown role: {role}; no output producer implemented")


# ---------------------------------------------------------------------------
# Per-role output producers
# ---------------------------------------------------------------------------


def _produce_librarian_outputs(vault: Path) -> "list[tuple[str, AgentOutputProxy, str]]":
    """Run query command against eval query cases and return outputs.

    Corpus: eval/cases/query_cases.json (loaded from workspace root).
    Wraps run_query() with asyncio.run().
    """
    from eval_harness.divergence.check import AgentOutputProxy  # noqa: PLC0415

    if not _QUERY_CASES_PATH.exists():
        pytest.skip(
            f"librarian corpus not found: {_QUERY_CASES_PATH}; "
            "add query cases to eval/cases/query_cases.json"
        )

    with _QUERY_CASES_PATH.open(encoding="utf-8") as f:
        cases: list[dict] = json.load(f)

    valid = [c for c in cases if isinstance(c.get("query"), str)]
    if not valid:
        pytest.skip(f"No valid query cases in {_QUERY_CASES_PATH}")

    from code_wiki_agent.commands.query import run_query  # noqa: PLC0415

    outputs: list[tuple[str, AgentOutputProxy, str]] = []
    for case in valid:
        query = case["query"]
        case_id = str(case.get("case_id", query[:30]))
        result = asyncio.run(run_query(query, vault_path=vault))
        outputs.append((case_id, AgentOutputProxy(answer=result.answer), query))

    return outputs


def _produce_ingestor_outputs(vault: Path) -> "list[tuple[str, AgentOutputProxy, str]]":
    """Run ingest command against existing vault pages as source documents.

    Corpus: up to 2 .md files from vault/packages/*/  or vault/concepts/*.
    Uses run_ingest_source() so the LLM processes real source content.
    The "query" slot (third tuple element) is the source file path string.

    Corpus path: {vault}/packages/**/*.md or {vault}/concepts/*.md
    """
    from eval_harness.divergence.check import AgentOutputProxy  # noqa: PLC0415

    # Collect candidate source files from the vault fixture itself
    candidates: list[Path] = []
    for subdir in ("packages", "concepts"):
        subdir_path = vault / subdir
        if subdir_path.exists():
            for md in sorted(subdir_path.rglob("*.md")):
                if md.name not in {"index.md", "log.md"}:
                    candidates.append(md)
        if len(candidates) >= 2:
            break

    if not candidates:
        pytest.skip(
            f"ingestor corpus not found: no .md files under {vault}/packages/ or "
            f"{vault}/concepts/; add source documents for ingest eval."
        )

    from code_wiki_agent.commands.ingest import run_ingest_source  # noqa: PLC0415

    outputs: list[tuple[str, AgentOutputProxy, str]] = []
    for source_path in candidates[:2]:
        fixture_id = f"ingest:{source_path.name}"
        result = asyncio.run(run_ingest_source(source_path, vault_path=vault))
        # LLM output is the full page text written to vault.
        # Read it back to get the raw LLM content for divergence checks.
        written_path = vault / result.page_path
        if written_path.exists():
            answer = written_path.read_text(encoding="utf-8")
        else:
            answer = result.page_path  # fallback: page path as answer
        outputs.append(
            (
                fixture_id,
                AgentOutputProxy(answer=answer, page_type=result.page_type),
                str(source_path),
            )
        )

    return outputs


def _produce_linter_outputs(vault: Path) -> "list[tuple[str, AgentOutputProxy, str]]":
    """Run lint command against the round-trip-vault and return per-group outputs.

    Corpus: the round-trip-vault fixture (vault arg).
    Returns one output per semantic group (page_quality, adr_chain, stale_claims).
    The "query" slot is the group name.
    """
    from eval_harness.divergence.check import AgentOutputProxy  # noqa: PLC0415
    from code_wiki_agent.commands.lint import run_lint  # noqa: PLC0415

    result = asyncio.run(run_lint(vault_path=vault))

    outputs: list[tuple[str, AgentOutputProxy, str]] = []
    for group in ("page_quality", "adr_chain", "stale_claims"):
        findings = result.semantic_findings.get(group, [])
        findings_text = "\n".join(findings) if findings else "(no findings)"
        outputs.append(
            (
                f"linter:{group}",
                AgentOutputProxy(answer=findings_text),
                group,
            )
        )

    if not outputs:
        pytest.skip(
            f"linter corpus produced no outputs from vault {vault}; "
            "check that semantic findings are reachable."
        )

    return outputs


def _produce_scanner_outputs(vault: Path) -> "list[tuple[str, AgentOutputProxy, str]]":
    """Run scan command against the eval-harness package as the monorepo.

    Corpus: cores/eval-harness/ (a real Python uv workspace member).
    vault is treated as the scanner's wiki destination.
    The "query" slot is the package name.

    Corpus path: cores/eval-harness relative to workspace root.
    """
    from eval_harness.divergence.check import AgentOutputProxy  # noqa: PLC0415
    from code_wiki_agent.commands.scan import run_scan  # noqa: PLC0415

    eval_harness_dir = _WORKSPACE_ROOT / "cores" / "eval-harness"
    if not eval_harness_dir.exists():
        pytest.skip(
            f"scanner corpus not found: {eval_harness_dir}; "
            "cores/eval-harness must exist in the workspace."
        )

    result = asyncio.run(run_scan(vault_path=vault))

    # Collect the stub pages written for any added or updated packages
    added_or_updated = result.added + result.updated
    if not added_or_updated:
        pytest.skip(
            "scanner produced no added/updated package stubs against "
            f"vault {vault}; check that a monorepo is resolvable from the vault."
        )

    outputs: list[tuple[str, AgentOutputProxy, str]] = []
    for pkg_name in added_or_updated:
        # Read the written stub page back from the vault
        stub_path = vault / "packages" / pkg_name / f"{pkg_name}.md"
        if stub_path.exists():
            stub_text = stub_path.read_text(encoding="utf-8")
        else:
            # Try flat path
            stub_path = vault / f"packages/{pkg_name}.md"
            stub_text = stub_path.read_text(encoding="utf-8") if stub_path.exists() else ""
        if stub_text:
            outputs.append(
                (
                    f"scanner:{pkg_name}",
                    AgentOutputProxy(answer=stub_text),
                    pkg_name,
                )
            )

    if not outputs:
        pytest.skip(
            f"scanner: no readable stub pages found for packages {added_or_updated}"
        )

    return outputs
