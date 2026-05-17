"""Unit tests for estimate_sweep_cost() pre-flight cost estimator.

Covers: 24-cell sweep under $25 hard cap (D-13), empty candidate handling,
graceful skip of unknown model IDs, repeat scaling, cap enforcement,
confirmation prompt, and BED-01 ping happy/sad paths.

Requirements: D-13, SWEEP-02.

All tests are deterministic (no live Bedrock calls).
"""

from __future__ import annotations

import pytest

from eval_harness.preflight import HARD_CAP_USD, estimate_sweep_cost, preflight_bed01, preflight_check
from model_adapter.exceptions import BedrockAccessDenied

# ---------------------------------------------------------------------------
# Full 6-role × 4-candidate role_candidates fixture (matches D-03 tier map)
# ---------------------------------------------------------------------------

_FULL_ROLE_CANDIDATES: dict[str, list[str]] = {
    # quality tier
    "librarian": [
        "us.anthropic.claude-sonnet-4-6",
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "us.amazon.nova-pro-v1:0",
        "qwen.qwen3-32b-v1:0",
    ],
    "synthesizer": [
        "us.anthropic.claude-sonnet-4-6",
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "us.amazon.nova-pro-v1:0",
        "qwen.qwen3-32b-v1:0",
    ],
    # mid tier
    "linter": [
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "us.amazon.nova-pro-v1:0",
        "us.amazon.nova-lite-v1:0",
        "qwen.qwen3-32b-v1:0",
    ],
    "ingestor": [
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "us.amazon.nova-pro-v1:0",
        "us.amazon.nova-lite-v1:0",
        "qwen.qwen3-32b-v1:0",
    ],
    # cheap-fast tier
    "scanner": [
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "us.amazon.nova-micro-v1:0",
        "us.amazon.nova-lite-v1:0",
        "qwen.qwen3-32b-v1:0",
    ],
    "code_reader": [
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "us.amazon.nova-micro-v1:0",
        "us.amazon.nova-lite-v1:0",
        "qwen.qwen3-32b-v1:0",
    ],
}


# ---------------------------------------------------------------------------
# estimate_sweep_cost tests (D-13)
# ---------------------------------------------------------------------------


def test_estimate_24_cell_sweep_within_cap() -> None:
    """estimate_sweep_cost for 6-role × 4-candidate matrix is below the $25 hard cap."""
    estimate = estimate_sweep_cost(_FULL_ROLE_CANDIDATES, n_cases=4, repeats=3)
    assert estimate > 0.0, "Estimate must be positive for known models"
    assert estimate < HARD_CAP_USD, f"Estimate ${estimate:.4f} must be below cap ${HARD_CAP_USD}"


def test_estimate_returns_zero_for_empty_candidates() -> None:
    """estimate_sweep_cost returns 0.0 when all roles have empty candidate lists."""
    result = estimate_sweep_cost({}, n_cases=4, repeats=3)
    assert result == 0.0


def test_estimator_skips_unknown_model_ids() -> None:
    """estimate_sweep_cost silently skips unknown model IDs (UnknownModelError swallowed)."""
    role_candidates = {
        "librarian": ["bogus-model-xyz-unknown"],
    }
    # No exception raised, total contribution from bogus model is 0
    result = estimate_sweep_cost(role_candidates, n_cases=2, repeats=1)
    assert result == 0.0


def test_estimator_scales_with_repeats() -> None:
    """estimate(repeats=3) is approximately 3× estimate(repeats=1)."""
    candidates = {"librarian": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"]}
    est1 = estimate_sweep_cost(candidates, n_cases=4, repeats=1)
    est3 = estimate_sweep_cost(candidates, n_cases=4, repeats=3)
    assert est1 > 0.0
    assert est3 == pytest.approx(est1 * 3, rel=0.05)


# ---------------------------------------------------------------------------
# preflight_check tests
# ---------------------------------------------------------------------------


def test_preflight_check_aborts_above_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """preflight_check raises SystemExit with 'exceeds hard cap' when estimate > HARD_CAP_USD."""
    # Patch cost_for_usage to return a large number per model/case
    # Use a role_candidates that will produce a very high estimate
    import eval_harness.preflight as pf

    def _expensive_cost(model: str, usage: dict) -> float:
        return 100.0

    monkeypatch.setattr("eval_harness.preflight.cost_for_usage", _expensive_cost)

    # Also patch preflight_bed01 so it doesn't run
    bed01_called = []

    def _mock_bed01() -> None:
        bed01_called.append(True)

    monkeypatch.setattr(pf, "preflight_bed01", _mock_bed01)

    candidates = {"librarian": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"]}

    with pytest.raises(SystemExit) as exc_info:
        pf.preflight_check(candidates, n_cases=1, repeats=1, auto_confirm=True)

    assert "exceeds hard cap" in str(exc_info.value)
    assert not bed01_called, "preflight_bed01 must NOT be called when estimate exceeds cap"


def test_preflight_check_prompts_for_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    """preflight_check prompts for confirmation; SystemExit on 'n', returns estimate on 'y'."""
    import eval_harness.preflight as pf

    # Patch bed01 to skip live call
    monkeypatch.setattr(pf, "preflight_bed01", lambda: None)

    candidates = {"librarian": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"]}

    # User declines
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    with pytest.raises(SystemExit):
        pf.preflight_check(candidates, n_cases=1, repeats=1, skip_bed01=True)

    # User confirms
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    result = pf.preflight_check(candidates, n_cases=1, repeats=1, skip_bed01=True)
    assert isinstance(result, float)
    assert result >= 0.0


# ---------------------------------------------------------------------------
# preflight_bed01 tests
# ---------------------------------------------------------------------------


def test_preflight_bed01_systemexit_on_access_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """preflight_bed01 raises SystemExit with prefix 'BED-01 FAILED:' on BedrockAccessDenied."""
    import eval_harness.preflight as pf

    class _FakeLLM:
        def invoke(self, *args, **kwargs):
            raise BedrockAccessDenied("arn:aws:bedrock:us-east-1::foundation-model/haiku")

    monkeypatch.setattr(pf, "make_llm", lambda role: _FakeLLM())

    with pytest.raises(SystemExit) as exc_info:
        pf.preflight_bed01()

    assert str(exc_info.value).startswith("BED-01 FAILED:")


def test_preflight_bed01_prints_confirmation_on_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """preflight_bed01 prints '[BED-01] Bedrock connectivity confirmed.' on success."""
    import eval_harness.preflight as pf

    class _FakeLLM:
        def invoke(self, *args, **kwargs):
            return "pong"

    monkeypatch.setattr(pf, "make_llm", lambda role: _FakeLLM())

    pf.preflight_bed01()

    captured = capsys.readouterr()
    assert "[BED-01] Bedrock connectivity confirmed." in captured.out
