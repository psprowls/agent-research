"""Tests that wiki-context eval scenario files parse correctly via Scenario.from_path()."""

from __future__ import annotations

from pathlib import Path

from claude_code_evals.schemas import Config, Scenario

EVAL_ROOT = Path(__file__).parent.parent.parent.parent / "eval"
SCENARIOS_ROOT = EVAL_ROOT / "scenarios"
CONFIGS_ROOT = EVAL_ROOT / "configs"


def test_base_config_parses():
    c = Config.from_path(CONFIGS_ROOT / "base.yaml")
    assert c.name == "base"
    assert c.model == "claude-sonnet-4-6"
    assert c.temperature == 0.0
    assert c.plugin_dirs == []


def test_wiki_api_client_scenario_parses():
    s = Scenario.from_path(SCENARIOS_ROOT / "wiki-api-client" / "scenario.yaml")
    assert s.name == "wiki-api-client"
    assert s.isolation_mode == "worktree"
    assert s.target_repo == "~/Personal/mono-repo"
    assert s.baseline_sha == "551f7ed8b9c0b4f51a4000302548e24284729652"
    assert s.configs == ["base"]
    assert s.mode == "headless"
    assert s.eval_mode == "implement"
    assert s.preflight == "preflight.sh"
    assert len(s.verify) == 2
    assert s.verify[0].kind == "script"
    assert s.verify[0].path == "verify.sh"
    assert s.verify[1].kind == "rubric"
    assert s.verify[1].path == "rubric.md"
    assert s.verify[1].pass_threshold == 4.0
    assert s.budgets.max_turns == 40
    assert s.budgets.max_input_tokens == 4_000_000
    assert s.budgets.max_wall_seconds == 300
    assert s.metrics.tool_shape is True
    assert s.metrics.judge_qualitative is False


def test_wiki_api_client_prompt_exists():
    prompt = SCENARIOS_ROOT / "wiki-api-client" / "prompt.md"
    assert prompt.exists()
    text = prompt.read_text()
    assert "timeline-summary.ts" in text
    assert "getRecentTimeline" in text


def test_wiki_api_client_rubric_exists():
    rubric = SCENARIOS_ROOT / "wiki-api-client" / "rubric.md"
    assert rubric.exists()
    text = rubric.read_text()
    assert "uses_domain_client" in text
    assert "no_raw_http" in text
    assert "no_hardcoded_url" in text
    assert "no_manual_auth" in text
    assert "correct_types" in text


def test_wiki_api_client_scripts_executable():
    for name in ("preflight.sh", "verify.sh"):
        p = SCENARIOS_ROOT / "wiki-api-client" / name
        assert p.exists(), f"{name} missing"
        assert p.stat().st_mode & 0o111, f"{name} not executable"


def test_wiki_design_tokens_scenario_parses():
    s = Scenario.from_path(SCENARIOS_ROOT / "wiki-design-tokens" / "scenario.yaml")
    assert s.name == "wiki-design-tokens"
    assert s.isolation_mode == "worktree"
    assert s.target_repo == "~/Personal/mono-repo"
    assert s.baseline_sha == "551f7ed8b9c0b4f51a4000302548e24284729652"
    assert s.configs == ["base"]
    assert s.mode == "headless"
    assert s.eval_mode == "implement"
    assert s.preflight == "preflight.sh"
    assert len(s.verify) == 2
    assert s.verify[0].kind == "script"
    assert s.verify[0].path == "verify.sh"
    assert s.verify[1].kind == "rubric"
    assert s.verify[1].path == "rubric.md"
    assert s.verify[1].pass_threshold == 4.0
    assert s.budgets.max_turns == 40
    assert s.budgets.max_input_tokens == 4_000_000
    assert s.budgets.max_wall_seconds == 300
    assert s.metrics.tool_shape is True
    assert s.metrics.judge_qualitative is False


def test_wiki_design_tokens_prompt_exists():
    prompt = SCENARIOS_ROOT / "wiki-design-tokens" / "prompt.md"
    assert prompt.exists()
    text = prompt.read_text()
    assert "StatusBadge" in text
    assert "status" in text


def test_wiki_design_tokens_rubric_exists():
    rubric = SCENARIOS_ROOT / "wiki-design-tokens" / "rubric.md"
    assert rubric.exists()
    text = rubric.read_text()
    assert "uses_semantic_tokens" in text
    assert "no_hex_values" in text
    assert "uses_cva_pattern" in text
    assert "dark_mode_safe" in text
    assert "uses_cn_utility" in text


def test_wiki_design_tokens_scripts_executable():
    for name in ("preflight.sh", "verify.sh"):
        p = SCENARIOS_ROOT / "wiki-design-tokens" / name
        assert p.exists(), f"{name} missing"
        assert p.stat().st_mode & 0o111, f"{name} not executable"
