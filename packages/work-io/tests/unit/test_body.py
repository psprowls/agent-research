from __future__ import annotations

from work_io.body import render_default_work_body
from work_io.plan_table import parse_plan


def test_bug_body_has_summary_plan_header_and_notes() -> None:
    body = render_default_work_body("X", "bug")
    assert "## Summary" in body
    assert "| Action | Done when | Rationale |" in body
    assert "## Notes / log" in body


def test_bug_body_omits_options_considered() -> None:
    body = render_default_work_body("X", "bug")
    assert "## Options considered" not in body


def test_bug_body_plan_parses_as_empty() -> None:
    body = render_default_work_body("X", "bug")
    assert parse_plan(body).state == "empty"


def test_feature_body_includes_options_considered() -> None:
    body = render_default_work_body("X", "feature")
    assert "## Options considered" in body


def test_summary_text_is_rendered() -> None:
    body = render_default_work_body("the symptom", "bug")
    assert "the symptom" in body
