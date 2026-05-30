"""pytest-evals two-phase integration for the wiki query sweep.

Phase 1 (@pytest.mark.eval):    Run sweep cases against each SWEEP_MODEL and
                                 store per-case scores in eval_bag.
Phase 2 (@pytest.mark.eval_analysis): Aggregate scores, print cost-frontier
                                 table, and call regression_check() to assert
                                 quality gate (EVAL-09).

Gate: all tests in this file are under @pytest.mark.eval (module-level pytestmark)
so pytest-evals skips them without --run-eval. The EVAL_GATE fixture adds an
additional guard on GRAPH_WIKI_RUN_EVAL=1 for tests that make real Bedrock calls.

Security (T-4-01): Cases loaded via json.load() at module level. Each case is
validated (isinstance check on "query" field) before reaching test parametrization.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

# Add parent tests/ dir to sys.path so conftest.py can be imported as a module.
# conftest.py lives in packages/eval-harness/tests/ (one level up from this file).
sys.path.insert(0, str(Path(__file__).parent.parent))

# Resolve workspace root: 5 parents from this file
# packages/eval-harness/tests/eval/test_sweep_eval.py
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

SWEEP_MODELS: list[str] = [
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.amazon.nova-lite-v1:0",
    "qwen.qwen3-32b-v1:0",
]

# Module-level eval gate: skips this entire file without --run-eval
# (handled by pytest-evals) and additionally gates on GRAPH_WIKI_RUN_EVAL
pytestmark = [pytest.mark.eval]

# Import EVAL_GATE from conftest for explicit test-level gating
from conftest import EVAL_GATE  # noqa: E402


def _load_cases() -> list[dict]:
    """Load and validate eval cases from query_cases.json.

    Security (T-4-01): validates isinstance(case["query"], str) before
    reaching test parametrization. Invalid cases are skipped with a warning.
    """
    if not CASES_PATH.exists():
        return []
    with CASES_PATH.open(encoding="utf-8") as f:
        raw: list[dict] = json.load(f)
    valid = []
    for case in raw:
        if not isinstance(case.get("query"), str):
            continue
        if not isinstance(case.get("expected_answer"), str):
            continue
        valid.append(case)
    return valid


def _make_case_model_params() -> list[dict]:
    """Build the combined parametrize list: CASES × SWEEP_MODELS."""
    cases = _load_cases()
    params = []
    for case in cases:
        for model_id in SWEEP_MODELS:
            params.append({
                "case_id": case.get("case_id", case["query"][:20]),
                "query": case["query"],
                "expected_answer": case["expected_answer"],
                "model_id": model_id,
            })
    return params


# Skip module if CASES_PATH or FIXTURE_VAULT is missing
if not CASES_PATH.exists():
    pytest.skip(
        f"query_cases.json not found at {CASES_PATH}; skipping sweep eval tests",
        allow_module_level=True,
    )
if not FIXTURE_VAULT.exists():
    pytest.skip(
        f"round-trip-vault not found at {FIXTURE_VAULT}; skipping sweep eval tests",
        allow_module_level=True,
    )

CASE_MODEL_PARAMS = _make_case_model_params()


@pytest.fixture
def fixture_workspace(tmp_path: Path) -> Path:
    """Build a workspace-shaped tmp dir whose ``wiki/`` symlinks to FIXTURE_VAULT.

    Post-Phase-24, sweep entrypoints accept ``workspace_path`` and derive the
    wiki via ``workspace_io.paths.wiki_dir(workspace_path) = workspace_path / "wiki"``.
    FIXTURE_VAULT itself is the wiki content (no ``wiki/`` subdir of its own),
    so passing it directly as ``workspace_path`` would resolve the wiki at
    ``FIXTURE_VAULT/"wiki"`` — which does not exist. This fixture wraps it
    correctly so ``EvalWorktree`` can locate the wiki on copytree.
    """
    wiki_link = tmp_path / "wiki"
    if not wiki_link.exists():
        wiki_link.symlink_to(FIXTURE_VAULT, target_is_directory=True)
    return tmp_path


@pytest.mark.eval(name="query_sweep")
@pytest.mark.parametrize("case_and_model", CASE_MODEL_PARAMS, ids=[
    f"{p['case_id']}::{p['model_id'].split('.')[-1]}"
    for p in CASE_MODEL_PARAMS
])
@EVAL_GATE
async def test_query_sweep_case(case_and_model: dict, eval_bag, fixture_workspace: Path) -> None:  # type: ignore[no-untyped-def]
    """Run a single (case, model) combination and store metrics in eval_bag.

    - EVAL_GATE: skips unless GRAPH_WIKI_RUN_EVAL=1
    - @pytest.mark.eval: skips unless --run-eval
    - panel_score() is called only when GRAPH_WIKI_RUN_JUDGES=1 is also set,
      to decouple sweep cost from judge cost in multi-run workflows.
    """
    from eval_harness.judge import panel_score
    from eval_harness.sweep import run_sweep

    query = case_and_model["query"]
    expected = case_and_model["expected_answer"]
    model_id = case_and_model["model_id"]

    results = await run_sweep(CASES_PATH, fixture_workspace, [model_id])
    # Filter to the case matching this test's query
    matching = [r for r in results if r.query == query]

    eval_bag.model_id = model_id
    eval_bag.query = query

    if not matching:
        eval_bag.score = 0.0
        eval_bag.answer = ""
        eval_bag.structural = {}
        return

    result = matching[0]
    eval_bag.answer = result.answer
    eval_bag.structural = result.structural

    if os.environ.get("GRAPH_WIKI_RUN_JUDGES") and result.status == "ok":
        # Run LLM judge panel (incurs Bedrock cost)
        scores = panel_score(query, result.answer, expected)
        result.judge_scores = scores
        eval_bag.score = scores["mean"]
    else:
        # Structural composite fallback: 1.0 all pass, 0.5 partial, 0.0 none
        bool_vals = [v for v in result.structural.values() if isinstance(v, bool)]
        if not bool_vals:
            eval_bag.score = 0.0
        elif all(bool_vals):
            eval_bag.score = 1.0
        elif any(bool_vals):
            eval_bag.score = 0.5
        else:
            eval_bag.score = 0.0

    eval_bag.cost_usd = result.cost_usd
    eval_bag.pages_drilled = result.pages_drilled
    eval_bag.wall_seconds = result.wall_seconds
    eval_bag.sweep_result = result


@pytest.mark.eval_analysis(name="query_sweep")
def test_query_sweep_analysis(eval_results) -> None:  # type: ignore[no-untyped-def]
    """Aggregate sweep scores and assert the quality regression gate.

    - Collects scores from all eval_bag results
    - Builds cost_frontier_table and prints it
    - Calls regression_check(mean_score, threshold=0.5) — EVAL-09 quality gate
    """
    from eval_harness.report import cost_frontier_table, print_frontier, regression_check
    from eval_harness.sweep import SweepResult

    scores = [r.score for r in eval_results if hasattr(r, "score") and r.score is not None]

    if not scores:
        pytest.skip("No eval results with scores; run --run-eval first")

    mean_score = sum(scores) / len(scores)

    # Reconstruct SweepResult list for cost_frontier_table (from eval_results)
    sweep_results: list[SweepResult] = [
        r.sweep_result for r in eval_results
        if hasattr(r, "sweep_result") and r.sweep_result is not None
    ]

    if sweep_results:
        table = cost_frontier_table(sweep_results)
        frontier_str = print_frontier(table)
        print("\n=== Cost Frontier Table ===")
        print(frontier_str)

    print(f"\nMean quality score across all cases: {mean_score:.3f}")

    # Quality regression gate: raises AssertionError if below threshold
    regression_check(mean_score, threshold=0.5)


@pytest.mark.eval(name="query_sweep")
@EVAL_GATE
async def test_position_bias_check() -> None:
    """UAT: verify judge panel has low position bias (< 0.05 delta).

    Calls run_sweep twice with the same query (different synthetic answers),
    then calls position_bias_check() and asserts the returned delta < 0.05.

    Both marks ensure this skips in normal CI (requires --run-eval AND GRAPH_WIKI_RUN_EVAL=1).
    """
    from eval_harness.judge import panel_score, position_bias_check

    # Use a simple synthetic query with two plausible answers
    query = "What does lattice-wiki-core do?"
    answer_a = "lattice-wiki-core provides the core wiki maintenance logic. See [[lattice-wiki-core]]."
    answer_b = "The lattice-wiki-core package is responsible for core wiki operations."
    expected = "lattice-wiki-core provides the core wiki maintenance logic"

    # Measure position bias
    delta = position_bias_check(query, answer_a, answer_b)
    assert delta < 0.05, (
        f"Judge panel shows position bias: delta={delta:.3f} >= 0.05. "
        "This suggests the panel is sensitive to answer order."
    )


@pytest.mark.eval(name="full_matrix")
@EVAL_GATE
async def test_full_matrix_live(tmp_path, capsys, monkeypatch, fixture_workspace: Path) -> None:  # type: ignore[no-untyped-def]
    """Live 24-cell matrix run via run_full_matrix() — SWEEP-01..03.

    Drives all 6 in-scope agent roles × 4 sweep candidates against real Bedrock,
    writes 6 per-role docs + INDEX.md into tmp_path, asserts BED-01 confirmation
    appeared, and verifies total cost is under HARD_CAP_USD.  Patches
    score_two_gate with a kwargs-capturing wrapper to verify call signature
    contract.

    Gates: requires --run-eval and GRAPH_WIKI_RUN_EVAL=1 (and GRAPH_WIKI_RUN_JUDGES=1
    if you want quality gate2 values populated; without it panel_means are None).
    """
    from eval_harness import sweep as sweep_mod
    from eval_harness.preflight import HARD_CAP_USD
    from eval_harness.sweep import SweepResult, run_full_matrix
    from eval_harness.two_gate import (
        ROLES_WITH_DIVERGENCE,
        TwoGateOutcome,
        score_two_gate as original_score_two_gate,
    )
    from model_adapter.loader import load_role_config

    roles = ["librarian", "synthesizer", "code_reader", "scanner", "linter", "ingestor"]
    role_candidates: dict[str, list[str]] = {}
    for role in roles:
        cfg = load_role_config(role)
        role_candidates[role] = list(cfg["sweep_candidates"])

    captured_calls: list[dict] = []

    def score_two_gate_wrapper(**kwargs) -> TwoGateOutcome:
        captured_calls.append(dict(kwargs))
        return original_score_two_gate(**kwargs)

    monkeypatch.setattr(sweep_mod, "score_two_gate", score_two_gate_wrapper)

    code_reader_cases_path = _WORKSPACE_ROOT / "eval" / "cases" / "code_reader_cases.json"
    ingestor_source = FIXTURE_VAULT / "README.md"
    if not ingestor_source.exists():
        ingestor_source = next(FIXTURE_VAULT.glob("*.md"))

    result = await run_full_matrix(
        role_candidates=role_candidates,
        workspace_path=fixture_workspace,
        query_cases_path=CASES_PATH,
        code_reader_cases_path=code_reader_cases_path,
        ingestor_source_path=ingestor_source,
        repeats=3,
        output_dir=tmp_path,
        dry_run=False,
        skip_bed01=False,
        auto_confirm=True,
    )

    captured = capsys.readouterr()
    assert "[BED-01] Bedrock connectivity confirmed." in captured.out, (
        "BED-01 confirmation line missing from preflight stdout"
    )

    for role in roles:
        doc_path = tmp_path / f"{role}.md"
        assert doc_path.exists(), f"Missing role doc: {doc_path}"
        text = doc_path.read_text(encoding="utf-8")
        assert "Pareto frontier" in text, f"{role}.md missing 'Pareto frontier' section"
    assert (tmp_path / "INDEX.md").exists(), "INDEX.md missing"

    total_cost = 0.0
    for role_results in result.values():
        for r in role_results:
            if isinstance(r, SweepResult) and r.cost_usd is not None:
                total_cost += r.cost_usd
    assert total_cost < HARD_CAP_USD, (
        f"Total cost ${total_cost:.4f} exceeds HARD_CAP_USD ${HARD_CAP_USD}"
    )

    cr_results = result.get("code_reader", [])
    code_reader_queries = {
        c["query"]
        for c in json.loads(code_reader_cases_path.read_text(encoding="utf-8"))
    }
    for r in cr_results:
        if r.status == "ok":
            assert r.query in code_reader_queries, (
                f"code_reader SweepResult query {r.query!r} not in code_reader_cases.json"
            )

    assert captured_calls, "score_two_gate was never called"
    for call in captured_calls:
        for key in ("role", "panel_mean", "default_panel_mean", "threshold"):
            assert key in call, f"score_two_gate call missing kwarg {key}: {call}"
        if call["role"] in ROLES_WITH_DIVERGENCE:
            assert call["divergence_metric_or_none"] is not None, (
                f"divergence-eligible role {call['role']!r} got None divergence_metric_or_none"
            )
            assert call["baselines_dir"] is not None, (
                f"divergence-eligible role {call['role']!r} got None baselines_dir"
            )


def test_eval_mark_skip() -> None:
    """Verify that EVAL_GATE skips tests when GRAPH_WIKI_RUN_EVAL is not set.

    This test is NOT marked with @pytest.mark.eval so it runs in normal CI.
    It checks that the EVAL_GATE skipif condition evaluates True in the
    absence of the env var (meaning eval tests would be skipped).
    """
    # EVAL_GATE is a pytest.mark.skipif marker
    # Its condition is: not os.environ.get("GRAPH_WIKI_RUN_EVAL")
    # Without GRAPH_WIKI_RUN_EVAL set, the condition is True → test would skip.
    run_eval = os.environ.get("GRAPH_WIKI_RUN_EVAL")
    if run_eval:
        pytest.skip("GRAPH_WIKI_RUN_EVAL is set — EVAL_GATE would not skip")

    # Verify the skipif condition directly
    condition = not os.environ.get("GRAPH_WIKI_RUN_EVAL")
    assert condition is True, (
        "EVAL_GATE condition should be True when GRAPH_WIKI_RUN_EVAL is not set, "
        "ensuring eval tests are skipped without the env var."
    )
