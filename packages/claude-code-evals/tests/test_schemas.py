"""Tests for claude_code_evals.schemas data models."""

from __future__ import annotations

from pathlib import Path

import pytest
from claude_code_evals.schemas import (
    AutoUser,
    Config,
    Runset,
    Scenario,
    ToolAssertion,
    Trigger,
    TriggerMatch,
    VerifyEntry,
)
from pydantic import ValidationError

FIXTURES = Path(__file__).parent / "fixtures"


def test_scenario_worktree_from_path():
    s = Scenario.from_path(FIXTURES / "scenario_worktree.yaml")
    assert s.name == "smoke-readme"
    assert s.isolation_mode == "worktree"
    assert s.target_repo == "~/Personal/my-repo"
    assert s.baseline_sha == "abc1234"
    assert len(s.verify) == 1
    assert s.verify[0].kind == "script"
    assert s.budgets.max_turns == 10


def test_scenario_fixture_from_path():
    s = Scenario.from_path(FIXTURES / "scenario_fixture.yaml")
    assert s.isolation_mode == "fixture"
    assert s.fixture_dir == "fixtures/"
    assert s.verify[0].kind == "golden"


def test_config_from_path():
    c = Config.from_path(FIXTURES / "config_base.yaml")
    assert c.name == "base"
    assert c.model == "claude-sonnet-4-6"
    assert c.temperature == 0.0
    assert c.plugin_dirs == []
    assert c.extra_env == {}


def test_runset_from_path():
    r = Runset.from_path(FIXTURES / "runset.yaml")
    assert r.name == "smoke"
    assert r.scenarios == ["smoke-readme"]
    assert r.default_configs == ["base"]


def test_auto_user_from_path():
    a = AutoUser.from_path(FIXTURES / "auto_user.yaml")
    assert a.model == "claude-haiku-4-5-20251001"
    assert a.max_replies == 3
    assert a.stop_on == "<DONE>"
    assert a.triggers == []
    assert a.default_reply == "proceed"
    assert a.abort_on_default_after == 2


def test_auto_user_from_path_with_triggers():
    a = AutoUser.from_path(FIXTURES / "auto_user_triggers.yaml")
    assert len(a.triggers) == 2
    assert a.triggers[0].match.contains == "clarify"
    assert a.triggers[1].match.regex == r"question\?"
    assert a.default_reply == "continue"
    assert a.abort_on_default_after == 3


def test_worktree_mode_requires_target_repo():
    with pytest.raises(ValidationError, match="target_repo"):
        Scenario.model_validate(
            {
                "name": "x",
                "isolation_mode": "worktree",
                "baseline_sha": "abc1234",
            }
        )


def test_worktree_mode_requires_baseline_sha():
    with pytest.raises(ValidationError, match="baseline_sha"):
        Scenario.model_validate(
            {
                "name": "x",
                "isolation_mode": "worktree",
                "target_repo": "~/repo",
            }
        )


def test_fixture_mode_requires_fixture_dir():
    with pytest.raises(ValidationError, match="fixture_dir"):
        Scenario.model_validate(
            {
                "name": "x",
                "isolation_mode": "fixture",
            }
        )


def test_interactive_mode_forbids_auto_user():
    with pytest.raises(ValidationError, match="interactive"):
        Scenario.model_validate(
            {
                "name": "x",
                "isolation_mode": "fixture",
                "fixture_dir": "fixtures/",
                "mode": "interactive",
                "auto_user": "auto_user.yaml",
            }
        )


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        Config.model_validate({"name": "x", "unknown_field": True})


def test_verify_entry_rubric_fields():
    v = VerifyEntry.model_validate(
        {
            "kind": "rubric",
            "path": "rubric.md",
            "judge": "claude-haiku-4-5-20251001",
            "pass_threshold": 4,
        }
    )
    assert v.pass_threshold == 4
    assert v.judge == "claude-haiku-4-5-20251001"


def test_scenario_discriminator_correctness_gated():
    """Test scenario with correctness-gated discriminator (no metric/min_improvement_pct)."""
    s = Scenario.model_validate(
        {
            "name": "correctness-test",
            "isolation_mode": "worktree",
            "target_repo": "~/repo",
            "baseline_sha": "abc1234",
            "discriminator": {
                "type": "correctness-gated",
            },
        }
    )
    assert s.discriminator is not None
    assert s.discriminator.type == "correctness-gated"
    assert s.discriminator.metric is None
    assert s.discriminator.min_improvement_pct is None


def test_scenario_discriminator_efficiency_gated():
    """Test scenario with efficiency-gated discriminator (includes metric and min_improvement_pct)."""
    s = Scenario.model_validate(
        {
            "name": "efficiency-test",
            "isolation_mode": "worktree",
            "target_repo": "~/repo",
            "baseline_sha": "abc1234",
            "discriminator": {
                "type": "efficiency-gated",
                "metric": "tokens_used",
                "min_improvement_pct": 5.0,
            },
        }
    )
    assert s.discriminator is not None
    assert s.discriminator.type == "efficiency-gated"
    assert s.discriminator.metric == "tokens_used"
    assert s.discriminator.min_improvement_pct == 5.0


def test_scenario_with_inject():
    """Test scenario with inject list."""
    s = Scenario.model_validate(
        {
            "name": "inject-test",
            "isolation_mode": "worktree",
            "target_repo": "~/repo",
            "baseline_sha": "abc1234",
            "inject": ["file1.txt", "file2.txt"],
        }
    )
    assert s.inject == ["file1.txt", "file2.txt"]


def test_trigger_match_contains():
    t = TriggerMatch.model_validate({"contains": "hello"})
    assert t.contains == "hello"
    assert t.regex is None


def test_trigger_match_regex():
    t = TriggerMatch.model_validate({"regex": r"\d+"})
    assert t.regex == r"\d+"
    assert t.contains is None


def test_trigger_match_requires_exactly_one():
    with pytest.raises(ValidationError, match="exactly one"):
        TriggerMatch.model_validate({})

    with pytest.raises(ValidationError, match="exactly one"):
        TriggerMatch.model_validate({"contains": "a", "regex": "b"})


def test_trigger_has_match_and_reply():
    t = Trigger.model_validate({"match": {"contains": "proceed"}, "reply": "yes"})
    assert t.match.contains == "proceed"
    assert t.reply == "yes"


def test_auto_user_defaults():
    a = AutoUser.model_validate({})
    assert a.triggers == []
    assert a.default_reply == "proceed"
    assert a.abort_on_default_after == 2


def test_auto_user_with_triggers():
    a = AutoUser.model_validate(
        {
            "triggers": [
                {"match": {"contains": "clarify"}, "reply": "Please go ahead."},
                {"match": {"regex": r"question\?"}, "reply": "Yes."},
            ],
            "default_reply": "continue",
            "abort_on_default_after": 3,
        }
    )
    assert len(a.triggers) == 2
    assert a.triggers[0].match.contains == "clarify"
    assert a.triggers[1].match.regex == r"question\?"
    assert a.default_reply == "continue"
    assert a.abort_on_default_after == 3


def test_auto_user_abort_on_default_after_min_1():
    with pytest.raises(ValidationError):
        AutoUser.model_validate({"abort_on_default_after": 0})


def test_auto_user_backward_compat():
    # Old-style YAML (no new fields) still loads cleanly
    a = AutoUser.model_validate(
        {
            "model": "claude-haiku-4-5-20251001",
            "max_replies": 3,
            "stop_on": "<DONE>",
            "system_prompt": "Drive the task.",
        }
    )
    assert a.triggers == []
    assert a.default_reply == "proceed"
    assert a.abort_on_default_after == 2


# --- tools verifier schema ---


def test_verify_entry_tools_kind_parses():
    ve = VerifyEntry.model_validate(
        {
            "kind": "tools",
            "assertions": [
                {"tool": "Skill", "params": {"skill": "graph-wiki:scan"}},
                {"tool": "Read", "min_count": 3},
                {"tool": "Write", "params": {"file_path": "wiki/entities/.*"}, "absent": True},
                {
                    "order": [
                        {"tool": "Read", "params": {"file_path": ".*StatusBadge.*"}},
                        {"tool": "Edit", "params": {"file_path": ".*StatusBadge.*"}},
                    ]
                },
                {"tool": "Read", "min_count": 5, "include_subagents": True},
            ],
        }
    )
    assert ve.kind == "tools"
    assert ve.assertions is not None and len(ve.assertions) == 5
    assert ve.assertions[4].include_subagents is True


def test_tools_kind_requires_assertions():
    with pytest.raises(ValueError, match="assertions"):
        VerifyEntry.model_validate({"kind": "tools"})


def test_tools_kind_forbids_path():
    with pytest.raises(ValueError, match="path"):
        VerifyEntry.model_validate({"kind": "tools", "path": "x.sh", "assertions": [{"tool": "Read"}]})


def test_other_kinds_still_require_path():
    with pytest.raises(ValueError, match="path"):
        VerifyEntry.model_validate({"kind": "script"})


def test_other_kinds_forbid_assertions():
    with pytest.raises(ValueError, match="assertions"):
        VerifyEntry.model_validate({"kind": "script", "path": "verify.sh", "assertions": [{"tool": "Read"}]})


def test_invalid_regex_rejected_at_load():
    with pytest.raises(ValueError, match="invalid regex"):
        ToolAssertion.model_validate({"tool": "Read", "params": {"file_path": "([unclosed"}})


def test_invalid_regex_in_order_step_rejected():
    with pytest.raises(ValueError, match="invalid regex"):
        ToolAssertion.model_validate({"order": [{"tool": "Read", "params": {"file_path": "([unclosed"}}]})


def test_order_cannot_combine_with_tool_fields():
    with pytest.raises(ValueError, match="order"):
        ToolAssertion.model_validate({"tool": "Read", "order": [{"tool": "Edit"}]})


def test_assertion_requires_tool_or_order():
    with pytest.raises(ValueError, match="tool or order"):
        ToolAssertion.model_validate({"min_count": 2})


def test_absent_forbids_counts():
    with pytest.raises(ValueError, match="absent"):
        ToolAssertion.model_validate({"tool": "Write", "absent": True, "min_count": 1})


def test_min_count_cannot_exceed_max_count():
    with pytest.raises(ValueError, match="min_count"):
        ToolAssertion.model_validate({"tool": "Bash", "min_count": 5, "max_count": 2})


def test_empty_order_rejected():
    with pytest.raises(ValueError, match="order"):
        ToolAssertion.model_validate({"order": []})


def test_scenario_with_tools_verify_round_trips():
    s = Scenario.model_validate(
        {
            "name": "s",
            "isolation_mode": "fixture",
            "fixture_dir": "/tmp/x",
            "verify": [{"kind": "tools", "assertions": [{"tool": "Skill", "params": {"skill": "graph-wiki:scan"}}]}],
        }
    )
    assert s.verify[0].kind == "tools"
