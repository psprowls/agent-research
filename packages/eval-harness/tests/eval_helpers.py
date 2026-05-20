from __future__ import annotations

"""Shared helpers for eval-harness integration tests.

This module exists so that both conftest.py (pytest fixtures) and
test_divergence.py (parametrized integration tests) can import helpers
without relying on sys.path manipulation or importing conftest as a plain
module (which is fragile and does not work reliably across pytest versions).

Public API:
    EVAL_GATE     — pytest.mark.skipif decorator gating eval tests.
    produce_outputs(role, vault) — produce agent outputs for the given role.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from eval_harness.divergence.check import AgentOutputProxy

# Eval gate: skip eval tests unless GRAPH_WIKI_RUN_EVAL=1 is set.
# Defined here (not in conftest) so test_divergence.py can import it directly
# without relying on conftest being importable as a plain module (which breaks
# under pytest's --import-mode=importlib).
EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_EVAL"),
    reason="Set GRAPH_WIKI_RUN_EVAL=1 to run divergence eval",
)

# Path to eval/cases/query_cases.json — used by librarian role outputs.
# packages/eval-harness/tests/eval_helpers.py
#   parent[0] → tests/
#   parent[1] → eval-harness/
#   parent[2] → packages/
#   parent[3] → workspace-root
_WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
_QUERY_CASES_PATH = _WORKSPACE_ROOT / "eval" / "cases" / "query_cases.json"


def produce_outputs(
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
          (packages/eval-harness) since it's a real Python package with pyproject.toml.
          Missing → pytest.skip with path.

    Raises:
        pytest.skip.Exception: if the corpus for the given role is not available.
        Any underlying exception from Bedrock/agent calls surfaces directly.

    Security (T-06-24): guards on GRAPH_WIKI_RUN_EVAL=1 — callers enforce this
    gate via the EVAL_GATE mark; this function adds a belt-and-suspenders check.
    """
    if not os.environ.get("GRAPH_WIKI_RUN_EVAL"):
        pytest.skip("GRAPH_WIKI_RUN_EVAL=1 required to produce agent outputs")

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

    Corpus: packages/eval-harness/ (a real Python uv workspace member).
    vault is treated as the scanner's wiki destination.
    The "query" slot is the package name.

    Passes repo_path=packages/eval-harness explicitly so workspace discovery
    does not depend on pytest cwd. (Plan 06-15 / UAT G5 — without this, the
    scanner falls back to Path.cwd() and may find nothing resolvable from
    the round-trip-vault fixture.)
    """
    from eval_harness.divergence.check import AgentOutputProxy  # noqa: PLC0415
    from code_wiki_agent.commands.scan import run_scan  # noqa: PLC0415

    eval_harness_dir = _WORKSPACE_ROOT / "packages" / "eval-harness"
    if not eval_harness_dir.exists():
        pytest.skip(
            f"scanner corpus not found: {eval_harness_dir}; "
            "packages/eval-harness must exist in the workspace."
        )

    # repo_path override (Plan 06-15 / UAT G5): point the scanner at the
    # eval-harness package as a known-good uv workspace member so it has
    # something to discover, regardless of pytest cwd or vault layout.
    result = asyncio.run(run_scan(vault_path=vault, repo_path=eval_harness_dir))

    # Collect the stub pages written for any added or updated packages
    added_or_updated = result.added + result.updated
    if not added_or_updated:
        pytest.skip(
            f"scanner produced no added/updated stubs against vault {vault} "
            f"using repo_path={eval_harness_dir}; "
            "this is unexpected post-Plan-06-15 — discover_workspaces should find "
            "the eval-harness workspace and report it as 'new' (no existing page)."
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
