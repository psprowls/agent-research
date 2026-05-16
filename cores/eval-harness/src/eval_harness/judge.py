"""LLM judge panel for wiki query quality evaluation.

Implements a two-judge GEval panel using deepeval with explicit AmazonBedrockModel
instances. CRITICAL: model= is always passed explicitly to GEval — deepeval defaults
to OpenAI GPT if model is omitted, which would silently route calls outside Bedrock
(threat T-4-04).

Exports:
    JUDGE_PANEL_CONFIG: list of judge configurations (model_id, pricing)
    make_judge: construct an AmazonBedrockModel from a config dict
    panel_score: score a query/answer pair using both judges, return mean
    position_bias_check: measure judge sensitivity to answer order
"""

from __future__ import annotations

from deepeval.metrics import GEval
from deepeval.models import AmazonBedrockModel
from deepeval.test_case import LLMTestCase, SingleTurnParams

# Two-judge panel per D-07 (cost-frontier design): Sonnet for quality ceiling,
# Nova Pro for cost diversity. Both use temperature=0 for deterministic scoring.
JUDGE_PANEL_CONFIG: list[dict] = [
    {
        "model_id": "us.anthropic.claude-sonnet-4-6",
        "input_price_per_m": 3.0,
        "output_price_per_m": 15.0,
    },
    {
        "model_id": "us.amazon.nova-pro-v1:0",
        "input_price_per_m": 0.80,
        "output_price_per_m": 3.20,
    },
]

EVAL_CRITERIA: str = (
    "Determine whether the actual output accurately answers the input query based on "
    "the expected answer. The actual output should cite relevant wiki pages using "
    "[[wikilink]] notation and include code path references when present."
)

EVAL_STEPS: list[str] = [
    "Check whether the response directly addresses the query",
    "Check whether at least one [[wikilink]] citation is present and plausible",
    "Check whether the response avoids hallucinating package or file names",
    "Penalize responses with no citations or vague answers with no specifics",
]


def make_judge(cfg: dict) -> AmazonBedrockModel:
    """Construct an AmazonBedrockModel from a JUDGE_PANEL_CONFIG entry.

    CRITICAL: model= is always explicit — deepeval defaults to OpenAI GPT if
    model is omitted (threat T-4-04). All values come from the hardcoded config,
    never from user input (T-4-02: no sanitization needed for panel configs).

    Args:
        cfg: A dict with keys model_id, input_price_per_m, output_price_per_m.

    Returns:
        AmazonBedrockModel configured for us-east-1 with temperature=0.
    """
    return AmazonBedrockModel(
        model=cfg["model_id"],
        region="us-east-1",
        cost_per_input_token=cfg["input_price_per_m"] / 1_000_000,
        cost_per_output_token=cfg["output_price_per_m"] / 1_000_000,
        generation_kwargs={"temperature": 0},
    )


def panel_score(query: str, actual: str, expected: str) -> dict:
    """Score a query/answer pair using the full two-judge panel.

    Creates fresh AmazonBedrockModel and GEval instances per call — per
    RESEARCH.md anti-pattern, reusing instances across calls leads to state
    accumulation issues.

    Each judge independently scores the response on a 0.0–1.0 scale.
    The mean of both scores is the panel score.

    Args:
        query:    The original query (GEval INPUT).
        actual:   The synthesized answer to evaluate (GEval ACTUAL_OUTPUT).
        expected: Reference answer from eval cases (GEval EXPECTED_OUTPUT).

    Returns:
        dict with keys: judge_a (float), judge_b (float), mean (float),
        reason_a (str), reason_b (str).
    """
    scores: list[float] = []
    reasons: list[str] = []

    for cfg in JUDGE_PANEL_CONFIG:
        # Fresh instances per call — do not reuse across calls
        judge = make_judge(cfg)
        metric = GEval(
            name="wiki_query_quality",
            criteria=EVAL_CRITERIA,
            evaluation_steps=EVAL_STEPS,
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
            ],
            model=judge,  # ALWAYS explicit — never let deepeval default to OpenAI
            threshold=0.5,
        )
        tc = LLMTestCase(
            input=query,
            actual_output=actual,
            expected_output=expected,
        )
        metric.measure(tc)
        scores.append(metric.score)
        reasons.append(metric.reason or "")

    if len(scores) < 2:
        raise RuntimeError(
            f"panel_score requires at least 2 judges, got {len(scores)}"
        )
    mean_score = sum(scores) / len(scores)
    return {
        "judge_a": scores[0],
        "judge_b": scores[1],
        "mean": mean_score,
        "reason_a": reasons[0],
        "reason_b": reasons[1],
    }


def position_bias_check(query: str, answer_a: str, answer_b: str) -> float:
    """Measure judge sensitivity to answer position (order bias).

    Scores with (answer_a, answer_b) then (answer_b, answer_a). A well-calibrated
    judge should produce similar scores regardless of order.

    Args:
        query:    The query used for both scoring passes.
        answer_a: First answer variant.
        answer_b: Second answer variant.

    Returns:
        abs(score1["mean"] - score2["mean"]) — caller asserts this is < 0.05.

    UAT verification: run_sweep twice for the same case with swapped answer
    positions and assert the returned delta < 0.05.
    """
    score1 = panel_score(query, answer_a, answer_b)
    score2 = panel_score(query, answer_b, answer_a)
    return abs(score1["mean"] - score2["mean"])
