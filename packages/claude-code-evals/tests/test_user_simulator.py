"""Tests for the Bedrock-backed AutoUserSimulator priority chain."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from claude_code_evals.schemas import AutoUser, Trigger, TriggerMatch
from claude_code_evals.user_simulator import AutoUserSimulator
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from model_adapter import BedrockAccessDenied


def _make_auto_user(**kwargs) -> AutoUser:
    defaults = {
        "max_replies": 10,
        "stop_on": "<DONE>",
        "system_prompt": "Drive task.",
        "default_reply": "proceed",
        "abort_on_default_after": 2,
        "triggers": [],
    }
    defaults.update(kwargs)
    return AutoUser.model_validate(defaults)


def _llm_response(text: str, input_tokens: int = 5, output_tokens: int = 3) -> MagicMock:
    r = MagicMock()
    r.content = text
    r.usage_metadata = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return r


def _make_sim(
    config: AutoUser | None = None, task_prompt: str = "Build the thing."
) -> tuple[AutoUserSimulator, MagicMock]:
    """Construct a simulator with make_llm mocked; returns (sim, mock_llm)."""
    llm = MagicMock()
    with patch("claude_code_evals.user_simulator.make_llm", return_value=llm):
        sim = AutoUserSimulator(config or _make_auto_user(), task_prompt=task_prompt)
    return sim, llm


def test_make_llm_called_with_role_and_none_override():
    with patch("claude_code_evals.user_simulator.make_llm", return_value=MagicMock()) as mk:
        AutoUserSimulator(_make_auto_user(), task_prompt="t")
    mk.assert_called_once_with("user_simulator", model_override=None)


def test_make_llm_receives_model_override():
    with patch("claude_code_evals.user_simulator.make_llm", return_value=MagicMock()) as mk:
        AutoUserSimulator(_make_auto_user(model="qwen.qwen3-32b-v1:0"), task_prompt="t")
    mk.assert_called_once_with("user_simulator", model_override="qwen.qwen3-32b-v1:0")


def test_stop_on_scans_full_text_returns_none():
    sim, llm = _make_sim()
    # stop_on appears in full_text but NOT in final_block — must still stop.
    assert sim.reply("task complete <DONE> trailing", "trailing") is None
    llm.invoke.assert_not_called()


def test_max_replies_exhausted_returns_none():
    sim, llm = _make_sim(_make_auto_user(max_replies=1))
    llm.invoke.return_value = _llm_response("ok")
    assert sim.reply("first", "first") == "ok"
    assert sim.reply("second", "second") is None


def test_trigger_contains_scans_full_text():
    triggers = [Trigger(match=TriggerMatch(contains="clarify"), reply="No clarification needed.")]
    sim, llm = _make_sim(_make_auto_user(triggers=triggers))
    # match word only in full_text, not final_block
    assert sim.reply("Can you clarify this? Working on it.", "Working on it.") == "No clarification needed."
    llm.invoke.assert_not_called()


def test_trigger_regex_scans_full_text():
    triggers = [Trigger(match=TriggerMatch(regex=r"question\?"), reply="Yes.")]
    sim, _ = _make_sim(_make_auto_user(triggers=triggers))
    assert sim.reply("Is this a question? More narration.", "More narration.") == "Yes."


def test_llm_called_with_inverted_role_history():
    sim, llm = _make_sim(task_prompt="Create hello.txt.")
    llm.invoke.return_value = _llm_response("keep going")
    assert sim.reply("full turn text", "final block") == "keep going"

    (history,) = llm.invoke.call_args.args
    assert isinstance(history[0], SystemMessage)
    assert "Drive task." in history[0].content
    assert "The agent was given this task:" in history[0].content
    assert "Create hello.txt." in history[0].content
    assert isinstance(history[1], HumanMessage)
    assert history[1].content == "final block"  # final block only, not full text

    # Second turn: prior LLM reply is in history as AIMessage.
    llm.invoke.return_value = _llm_response("again")
    sim.reply("turn 2 full", "turn 2 final")
    (history2,) = llm.invoke.call_args.args
    assert isinstance(history2[2], AIMessage)
    assert history2[2].content == "keep going"
    assert history2[3].content == "turn 2 final"


def test_trigger_and_default_replies_recorded_in_history():
    triggers = [Trigger(match=TriggerMatch(contains="clarify"), reply="Go ahead.")]
    sim, llm = _make_sim(_make_auto_user(triggers=triggers))
    sim.reply("please clarify", "please clarify")  # trigger reply
    llm.invoke.side_effect = RuntimeError("boom")
    sim.reply("no match", "no match")  # default reply
    llm.invoke.side_effect = None
    llm.invoke.return_value = _llm_response("llm reply")
    sim.reply("plain", "plain")  # LLM consulted now
    (history,) = llm.invoke.call_args.args
    contents = [(type(m).__name__, m.content) for m in history]
    assert ("AIMessage", "Go ahead.") in contents
    assert ("AIMessage", "proceed") in contents


def test_token_accumulation_from_usage_metadata():
    sim, llm = _make_sim()
    llm.invoke.return_value = _llm_response("ok", input_tokens=5, output_tokens=3)
    sim.reply("a", "a")
    sim.reply("b", "b")
    assert sim.input_tokens == 10
    assert sim.output_tokens == 6


def test_abort_after_n_defaults_sends_exactly_n():
    sim, llm = _make_sim(_make_auto_user(abort_on_default_after=2))
    llm.invoke.side_effect = RuntimeError("fail")
    assert sim.reply("t1", "t1") == "proceed"  # default #1
    assert sim.reply("t2", "t2") == "proceed"  # default #2
    assert sim.reply("t3", "t3") is None  # abort: N=2 defaults already sent


def test_bedrock_access_denied_falls_to_default_chain():
    sim, llm = _make_sim(_make_auto_user(abort_on_default_after=3))
    llm.invoke.side_effect = BedrockAccessDenied("denied")
    assert sim.reply("x", "x") == "proceed"


def test_trigger_match_resets_consecutive_defaults():
    triggers = [Trigger(match=TriggerMatch(contains="trigger"), reply="matched")]
    sim, llm = _make_sim(_make_auto_user(triggers=triggers, abort_on_default_after=1))
    llm.invoke.side_effect = RuntimeError("fail")
    assert sim.reply("no match", "no match") == "proceed"  # default #1 (N=1 sent)
    assert sim.reply("trigger here", "trigger here") == "matched"  # resets counter
    assert sim.reply("no match", "no match") == "proceed"  # default chain restarts
    assert sim.reply("no match", "no match") is None  # now aborts


def test_llm_success_resets_consecutive_defaults():
    sim, llm = _make_sim(_make_auto_user(abort_on_default_after=1))
    llm.invoke.side_effect = RuntimeError("fail")
    assert sim.reply("a", "a") == "proceed"
    llm.invoke.side_effect = None
    llm.invoke.return_value = _llm_response("ok")
    assert sim.reply("b", "b") == "ok"
    llm.invoke.side_effect = RuntimeError("fail")
    assert sim.reply("c", "c") == "proceed"  # not None — counter was reset


def test_stop_on_checked_before_triggers():
    triggers = [Trigger(match=TriggerMatch(contains="<DONE>"), reply="matched")]
    sim, _ = _make_sim(_make_auto_user(triggers=triggers))
    assert sim.reply("all done <DONE>", "all done <DONE>") is None


# --- real Bedrock role (skipped by default; -m integration to opt in) ---


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)
def test_real_bedrock_user_simulator_reply():
    """Exercises the real user_simulator role end-to-end (needs AWS creds and GRAPH_WIKI_RUN_INTEGRATION=1)."""
    sim = AutoUserSimulator(
        _make_auto_user(max_replies=1),
        task_prompt="Create a file named hello.txt containing the word hi.",
    )
    text = "I created hello.txt with the requested content. Anything else?"
    reply = sim.reply(text, text)
    assert isinstance(reply, str) and reply.strip()
    assert sim.input_tokens > 0
    assert sim.output_tokens > 0
