"""Tests for work_io.auto_drive — pure model resolution + enum validation."""

from __future__ import annotations

from work_io.auto_drive import ModelResolution, resolve_model, validate_auto_drive

BLOCK = {
    "max_parallel": 2,
    "models": {"design": "claude-fable-5", "execute": "claude-sonnet-5"},
    "overrides": [
        {
            "match": {"phase": "execute", "kind": ["bug", "tech-debt"], "effort": ["xtra-small", "small"]},
            "model": "claude-haiku-4-5",
        },
        {"match": {"phase": "plan", "kind": "epic"}, "model": "claude-fable-5", "reasoning_effort": "high"},
        {"match": {"phase": "plan"}, "model": "claude-sonnet-5"},
    ],
}


def test_override_first_match_wins():
    # Rules 2 and 3 both match (plan, epic); rule 2 is first and wins outright.
    got = resolve_model(BLOCK, phase="plan", kind="epic", effort="large")
    assert got == ModelResolution("claude-fable-5", "high")


def test_later_rule_matches_when_earlier_rules_miss():
    got = resolve_model(BLOCK, phase="plan", kind="feature", effort=None)
    assert got == ModelResolution("claude-sonnet-5", None)


def test_list_membership_and_scalar_equality():
    got = resolve_model(BLOCK, phase="execute", kind="bug", effort="small")
    assert got == ModelResolution("claude-haiku-4-5", None)


def test_effort_constraint_never_matches_unsized_item():
    # Rule 1 requires an effort; an unsized item falls through to models.execute.
    got = resolve_model(BLOCK, phase="execute", kind="bug", effort=None)
    assert got == ModelResolution("claude-sonnet-5", None)


def test_absent_match_key_is_wildcard():
    block = {"overrides": [{"match": {"phase": "design"}, "model": "m"}]}
    assert resolve_model(block, phase="design", kind="spike", effort=None) == ModelResolution("m", None)


def test_phase_default_fallback():
    got = resolve_model(BLOCK, phase="design", kind="feature", effort="medium")
    assert got == ModelResolution("claude-fable-5", None)


def test_no_match_and_no_phase_default_returns_none():
    assert resolve_model(BLOCK, phase="finish", kind="feature", effort="medium") is None


def test_empty_block_returns_none():
    assert resolve_model({}, phase="design", kind="feature", effort=None) is None


def test_validate_clean_block():
    assert validate_auto_drive(BLOCK) == []


def test_validate_empty_block():
    assert validate_auto_drive({}) == []


def test_validate_rejects_bad_enums():
    block = {"overrides": [{"match": {"phase": "done", "kind": "bugg", "effort": "xs"}, "model": "m"}]}
    errors = validate_auto_drive(block)
    assert len(errors) == 3
    assert any("phase" in e and "'done'" in e for e in errors)
    assert any("kind" in e and "'bugg'" in e for e in errors)
    assert any("effort" in e and "'xs'" in e for e in errors)


def test_validate_checks_values_inside_lists():
    block = {"overrides": [{"match": {"effort": ["small", "s"]}, "model": "m"}]}
    errors = validate_auto_drive(block)
    assert len(errors) == 1
    assert "'s'" in errors[0]
