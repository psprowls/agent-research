"""Living Wiki M2e: drift_judge prompt + verdict parser, and role config."""

from __future__ import annotations

from graph_wiki_core.prompts.drift_judge import (
    build_drift_judge_prompt,
    parse_drift_verdict,
)


def test_build_prompt_includes_section_and_narrative():
    system, human = build_drift_judge_prompt(
        heading="## Purpose",
        section_body="## Purpose\nProcesses items synchronously.\n",
        narrative="The package does async fan-out.",
        file_map="| `x.py` | file | core |",
    )
    assert "stale" in system.lower()
    assert "Purpose" in human
    assert "synchronously" in human
    assert "async fan-out" in human
    assert "x.py" in human  # file map included when provided


def test_build_prompt_omits_file_map_when_none():
    _system, human = build_drift_judge_prompt(
        heading="## Commands", section_body="## Commands\n/foo\n",
        narrative="An agent plugin.", file_map=None,
    )
    assert "File map" not in human


def test_parse_verdict_happy_path():
    v = parse_drift_verdict('{"stale": true, "reason": "narrative now async"}')
    assert v == {"stale": True, "reason": "narrative now async"}


def test_parse_verdict_strips_code_fence():
    v = parse_drift_verdict('```json\n{"stale": false, "reason": "ok"}\n```')
    assert v["stale"] is False


def test_parse_verdict_fails_safe_on_garbage():
    v = parse_drift_verdict("the model rambled with no json")
    assert v["stale"] is False
    assert isinstance(v["reason"], str)


def test_drift_judge_role_in_models_toml():
    from model_adapter.loader import load_role_config

    cfg = load_role_config("drift_judge")
    assert cfg["model_id"]
    assert cfg["max_concurrency"] >= 1
