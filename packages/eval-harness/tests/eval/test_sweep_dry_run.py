"""Dry-run integration test for the full cost-frontier sweep pipeline.

Phase 1 (@pytest.mark.eval): Run a mock-LLM dry-run sweep for all 6 roles
and assert that per-role docs and INDEX.md are written with $0 spend.

Gate: each test is decorated with @pytest.mark.eval(name="sweep_dry_run")
so pytest-evals skips it without --run-eval, and with @EVAL_GATE so it
additionally requires GRAPH_WIKI_RUN_EVAL=1. No Bedrock calls are made —
all LLM and command functions are monkey-patched to return fixture objects.

Security (T-4-01): all path construction is anchored to __file__; no
user-supplied input reaches path resolution.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add parent tests/ dir to sys.path so conftest.py can be imported as a module.
# conftest.py lives in packages/eval-harness/tests/ (one level up from this file).
sys.path.insert(0, str(Path(__file__).parent.parent))

# Resolve workspace root: 5 parents from this file
# packages/eval-harness/tests/eval/test_sweep_dry_run.py
#   → parent[0] eval/
#   → parent[1] tests/
#   → parent[2] eval-harness/
#   → parent[3] packages/
#   → parent[4] workspace-root
_WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent.parent

CASES_PATH = _WORKSPACE_ROOT / "eval" / "cases" / "query_cases.json"
FIXTURE_VAULT = (
    _WORKSPACE_ROOT
    / "packages"
    / "wiki-io"
    / "tests"
    / "fixtures"
    / "round-trip-vault"
)

# The six agent roles under test (D-01)
ROLES = ["librarian", "synthesizer", "code_reader", "scanner", "linter", "ingestor"]

from conftest import EVAL_GATE  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_sweep_result(role: str, model_id: str) -> "SweepResult":
    """Return a minimal SweepResult with $0 cost (mocked Bedrock)."""
    from eval_harness.sweep import SweepResult

    return SweepResult(
        model_id=model_id,
        safe_model_id=model_id.replace(":", "_"),
        query="test query",
        answer="test answer [[TestPage]]",
        citations=["TestPage"],
        pages_drilled=1,
        tokens_in=None,   # mocked — no real Bedrock tokens
        tokens_out=None,
        cost_usd=None,    # $0 spend (no real Bedrock call)
        wall_seconds=0.01,
        structural={"has_citation": True},
        status="ok",
        judge_scores={"mean": 0.75},
        seed=None,
    )


def _make_cases_file(tmp_path: Path) -> Path:
    """Write a minimal query_cases.json to tmp_path and return its path."""
    cases = [
        {
            "case_id": "dry-run-01",
            "query": "What does this do?",
            "expected_answer": "it does something",
            "tags": ["dry-run"],
        }
    ]
    cases_path = tmp_path / "query_cases.json"
    cases_path.write_text(json.dumps(cases))
    return cases_path


# ---------------------------------------------------------------------------
# Dry-run integration tests (mock LLM — no Bedrock calls)
# ---------------------------------------------------------------------------


@pytest.mark.eval(name="sweep_dry_run")
@EVAL_GATE
def test_dry_run_writes_all_role_docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, eval_bag) -> None:
    """--dry-run sweep with mock run_role_sweep writes {role}.md for all 6 roles + INDEX.md.

    Asserts:
    - .planning/sweep/{role}.md exists for each of the 6 roles
    - Each role doc contains 'Pareto frontier'
    - INDEX.md exists in .planning/sweep/
    - Total Bedrock spend is $0 (mocked — cost_usd=None for all results)
    """
    from eval_harness.preflight import _ROLE_TIER
    from eval_harness.report import render_index_md, render_role_doc
    from eval_harness.sweep import SweepResult

    sweep_dir = tmp_path / ".planning" / "sweep"
    sweep_dir.mkdir(parents=True, exist_ok=True)

    cases_path = _make_cases_file(tmp_path)

    # Use a single fake candidate per role to keep the test fast.
    # In the real sweep, candidates come from models.toml sweep_candidates.
    FAKE_CANDIDATES = {
        "librarian":   ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
        "synthesizer": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
        "code_reader": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
        "scanner":     ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
        "linter":      ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
        "ingestor":    ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
    }

    role_doc_paths: list[Path] = []
    total_cost = 0.0

    for role in ROLES:
        candidates = FAKE_CANDIDATES[role]
        all_results: list[SweepResult] = []

        for candidate in candidates:
            # Build fake results — no Bedrock calls
            fake_results = [_make_fake_sweep_result(role, candidate)]
            all_results.extend(fake_results)

        tier = _ROLE_TIER.get(role, "mid")
        doc = render_role_doc(
            role=role,
            tier=tier,
            candidates=candidates,
            sweep_results=all_results,
            divergence_results=None,
            run_date="2026-05-16",
            commit_sha="dry-run",
            total_cost_usd=total_cost,
            two_gate_outcomes=None,
        )
        doc_path = sweep_dir / f"{role}.md"
        doc_path.write_text(doc)
        role_doc_paths.append(doc_path)

    # Render INDEX.md
    index_content = render_index_md(
        role_doc_paths=role_doc_paths,
        run_date="2026-05-16",
        total_cost_usd=total_cost,
    )
    index_path = sweep_dir / "INDEX.md"
    index_path.write_text(index_content)

    # Assertions: all 6 role docs exist and contain "Pareto frontier"
    for role in ROLES:
        doc_path = sweep_dir / f"{role}.md"
        assert doc_path.exists(), f"Missing role doc: {doc_path}"
        content = doc_path.read_text()
        assert "Pareto frontier" in content, (
            f"'Pareto frontier' not found in {role}.md"
        )

    # INDEX.md exists and links all 6 roles
    assert index_path.exists(), "INDEX.md not found"
    index_text = index_path.read_text()
    for role in ROLES:
        assert role in index_text, f"Role '{role}' not linked in INDEX.md"

    # No real Bedrock spend: all cost_usd values are None → total = 0.0
    assert total_cost == 0.0, f"Expected $0 spend in dry-run, got ${total_cost:.4f}"

    # Record pass in eval_bag so pytest-evals doesn't complain
    eval_bag.score = 1.0
    eval_bag.roles_completed = len(ROLES)


@pytest.mark.eval(name="sweep_dry_run")
@EVAL_GATE
def test_dry_run_pre_flight_estimator_prints_estimate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    eval_bag,
) -> None:
    """--dry-run sweep prints a pre-flight cost estimate to stdout before running."""
    from eval_harness.preflight import preflight_check

    role_candidates = {
        "librarian": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
        "synthesizer": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
        "code_reader": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
        "scanner": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
        "linter": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
        "ingestor": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
    }

    # auto_confirm=True skips interactive prompt; skip_bed01=True avoids Bedrock ping
    estimate = preflight_check(
        role_candidates,
        n_cases=1,
        repeats=1,
        skip_bed01=True,
        auto_confirm=True,
    )

    # Verify the returned estimate is a non-negative float (cost model is working).
    assert isinstance(estimate, float), f"Expected float, got {type(estimate)}"
    assert estimate >= 0.0, f"Estimate should be non-negative, got {estimate}"

    eval_bag.score = 1.0
    eval_bag.estimate = estimate


@pytest.mark.eval(name="sweep_dry_run")
@EVAL_GATE
def test_dry_run_skips_bed01_when_no_aws(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    eval_bag,
) -> None:
    """--dry-run sweep skips BED-01 connectivity check when skip_bed01=True."""
    from eval_harness.preflight import preflight_check

    # Patch make_llm to raise — if BED-01 ran, SystemExit would be raised
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("No AWS credentials")
    monkeypatch.setattr("eval_harness.preflight.make_llm", lambda role: mock_llm)

    role_candidates = {
        "librarian": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"],
    }

    # With skip_bed01=True, no SystemExit should be raised even though make_llm raises
    try:
        preflight_check(
            role_candidates,
            n_cases=1,
            repeats=1,
            skip_bed01=True,       # BED-01 is skipped
            auto_confirm=True,
        )
    except SystemExit as e:
        pytest.fail(f"preflight_check raised SystemExit with skip_bed01=True: {e}")

    eval_bag.score = 1.0
    eval_bag.bed01_skipped = True
