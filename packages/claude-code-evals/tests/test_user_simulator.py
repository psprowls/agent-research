"""Tests for AutoUserSimulator priority chain."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from claude_code_evals.schemas import AutoUser, Trigger, TriggerMatch
from claude_code_evals.user_simulator import AutoUserSimulator


def _make_auto_user(**kwargs) -> AutoUser:
    defaults = {
        "model": "claude-haiku-4-5-20251001",
        "max_replies": 10,
        "stop_on": "<DONE>",
        "system_prompt": "Drive task.",
        "default_reply": "proceed",
        "abort_on_default_after": 2,
        "triggers": [],
    }
    defaults.update(kwargs)
    return AutoUser.model_validate(defaults)


def _make_judge_result(text: str) -> MagicMock:
    r = MagicMock()
    r.stdout = text
    r.input_tokens = 5
    r.output_tokens = 3
    return r


def test_stop_on_returns_none():
    sim = AutoUserSimulator(_make_auto_user())
    assert sim.reply("task complete <DONE>") is None


def test_max_replies_exhausted_returns_none():
    sim = AutoUserSimulator(_make_auto_user(max_replies=1))
    with patch("claude_code_evals.user_simulator._run_claude_judge", return_value=_make_judge_result("ok")):
        sim.reply("first")
    # Second call exceeds max_replies
    assert sim.reply("second") is None


def test_trigger_contains_matches_and_returns_reply():
    triggers = [Trigger(match=TriggerMatch(contains="clarify"), reply="No clarification needed.")]
    sim = AutoUserSimulator(_make_auto_user(triggers=triggers))
    result = sim.reply("Can you clarify this for me?")
    assert result == "No clarification needed."


def test_trigger_regex_matches_and_returns_reply():
    triggers = [Trigger(match=TriggerMatch(regex=r"question\?"), reply="Yes.")]
    sim = AutoUserSimulator(_make_auto_user(triggers=triggers))
    assert sim.reply("Is this a question?") == "Yes."


def test_trigger_no_match_falls_through_to_llm():
    triggers = [Trigger(match=TriggerMatch(contains="never_matches"), reply="nope")]
    sim = AutoUserSimulator(_make_auto_user(triggers=triggers))
    judge_result = _make_judge_result("LLM reply")
    with patch("claude_code_evals.user_simulator._run_claude_judge", return_value=judge_result) as mock_judge:
        result = sim.reply("some text")
    assert result == "LLM reply"
    mock_judge.assert_called_once()


def test_trigger_match_resets_consecutive_defaults():
    triggers = [Trigger(match=TriggerMatch(contains="trigger"), reply="matched")]
    sim = AutoUserSimulator(_make_auto_user(triggers=triggers, abort_on_default_after=1))
    # Exhaust consecutive defaults (LLM fails)
    with patch("claude_code_evals.user_simulator._run_claude_judge", side_effect=RuntimeError("fail")):
        sim.reply("no match here")  # → default_reply, consecutive_defaults=1
    # Now trigger fires → resets consecutive_defaults
    result = sim.reply("trigger word here")
    assert result == "matched"
    # Next LLM failure should not abort yet (consecutive_defaults was reset to 0)
    with patch("claude_code_evals.user_simulator._run_claude_judge", side_effect=RuntimeError("fail")):
        result = sim.reply("no match")
    assert result == "proceed"  # default_reply, not None


def test_llm_failure_falls_back_to_default_reply():
    sim = AutoUserSimulator(_make_auto_user(default_reply="fallback", abort_on_default_after=3))
    with patch("claude_code_evals.user_simulator._run_claude_judge", side_effect=RuntimeError("LLM error")):
        result = sim.reply("something")
    assert result == "fallback"


def test_abort_on_default_after_consecutive_failures():
    sim = AutoUserSimulator(_make_auto_user(abort_on_default_after=2))
    with patch("claude_code_evals.user_simulator._run_claude_judge", side_effect=RuntimeError("fail")):
        r1 = sim.reply("turn 1")  # consecutive_defaults=1
        r2 = sim.reply("turn 2")  # consecutive_defaults=2, abort
    assert r1 == "proceed"
    assert r2 is None


def test_token_accumulation_across_turns():
    sim = AutoUserSimulator(_make_auto_user())
    with patch("claude_code_evals.user_simulator._run_claude_judge", return_value=_make_judge_result("ok")):
        sim.reply("turn 1")
        sim.reply("turn 2")
    assert sim.input_tokens == 10
    assert sim.output_tokens == 6


def test_stop_on_checked_before_triggers():
    triggers = [Trigger(match=TriggerMatch(contains="<DONE>"), reply="matched")]
    sim = AutoUserSimulator(_make_auto_user(triggers=triggers))
    # stop_on should fire before the trigger check
    assert sim.reply("all done <DONE>") is None
