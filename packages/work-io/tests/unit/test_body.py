from __future__ import annotations

import pytest
from work_io.body import render_default_work_body
from work_io.lifecycle_lint import VALID_KINDS
from work_io.plan_table import parse_plan
from work_io.templates import templates_dir


@pytest.mark.parametrize("kind", sorted(VALID_KINDS))
def test_every_kind_renders_well_formed_body(kind: str) -> None:
    body = render_default_work_body("the symptom", kind)
    assert body.startswith("## Summary")
    assert "the symptom" in body
    assert parse_plan(body).state == "empty"
    assert body.rstrip().endswith("## Notes / log")


@pytest.mark.parametrize("kind", sorted(VALID_KINDS))
def test_every_kind_has_a_template_file(kind: str) -> None:
    assert (templates_dir() / "bodies" / f"{kind}.md").exists()


def test_default_template_exists() -> None:
    assert (templates_dir() / "bodies" / "default.md").exists()


def test_unknown_kind_falls_back_to_default() -> None:
    body = render_default_work_body("x", "made-up")
    assert body.startswith("## Summary")
    assert parse_plan(body).state == "empty"
    assert "## Options considered" not in body


def test_summary_text_is_substituted() -> None:
    body = render_default_work_body("the precise symptom", "bug")
    assert "the precise symptom" in body
    assert "{summary}" not in body
    assert "{plan_table}" not in body


def test_bug_body_has_repro_sections() -> None:
    body = render_default_work_body("x", "bug")
    assert "## Steps to reproduce" in body
    assert "## Expected vs actual" in body
    assert "## Options considered" not in body


def test_feature_body_has_options_considered() -> None:
    body = render_default_work_body("x", "feature")
    assert "## Options considered" in body


def test_spike_body_has_findings() -> None:
    body = render_default_work_body("x", "spike")
    assert "## Question" in body
    assert "## Findings" in body


def test_security_body_has_threat() -> None:
    body = render_default_work_body("x", "security")
    assert "## Threat" in body
    assert "## Impact" in body


def test_epic_body_has_no_sub_items() -> None:
    out = render_default_work_body("decompose the thing", "epic")
    assert "Sub-items" not in out
    assert "## Goal" in out
    assert "## Plan" in out
    assert "## Notes / log" in out
