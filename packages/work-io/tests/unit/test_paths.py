"""Tests for work_io.paths — pure path arithmetic over a workspace path."""

from __future__ import annotations

import pytest
from work_io.paths import ARTIFACT_KINDS, PHASE_ORDINALS, artifact_path, work_item_dir


def test_work_item_dir(tmp_path):
    assert work_item_dir(tmp_path, "2026-06-30-fix-bug") == tmp_path / "wiki" / "work" / "2026-06-30-fix-bug"


def test_phase_ordinals_keys():
    assert set(PHASE_ORDINALS) == {"open", "design", "plan", "execute", "finish"}
    assert PHASE_ORDINALS["open"] == "00"
    assert PHASE_ORDINALS["design"] == "01"
    assert PHASE_ORDINALS["plan"] == "02"
    assert PHASE_ORDINALS["execute"] == "03"
    assert PHASE_ORDINALS["finish"] == "04"


def test_artifact_kinds():
    assert ARTIFACT_KINDS == frozenset({"spec", "plan", "guidance", "results"})


def test_artifact_path_design_spec(tmp_path):
    p = artifact_path(tmp_path, "slug", "design", "spec", ext="md")
    assert p == work_item_dir(tmp_path, "slug") / "01-design-spec.md"


def test_artifact_path_design_guidance(tmp_path):
    p = artifact_path(tmp_path, "slug", "design", "guidance", ext="md")
    assert p == work_item_dir(tmp_path, "slug") / "01-design-guidance.md"


def test_artifact_path_execute_guidance_with_role(tmp_path):
    p = artifact_path(tmp_path, "slug", "execute", "guidance", role="review", ext="md")
    assert p == work_item_dir(tmp_path, "slug") / "03-execute-guidance-review.md"


def test_artifact_path_execute_results(tmp_path):
    p = artifact_path(tmp_path, "slug", "execute", "results", ext="md")
    assert p == work_item_dir(tmp_path, "slug") / "03-execute-results.md"


def test_artifact_path_bare_transcript(tmp_path):
    p = artifact_path(tmp_path, "slug", "design", ext="jsonl")
    assert p == work_item_dir(tmp_path, "slug") / "01-design.jsonl"


def test_artifact_path_subagent_transcript(tmp_path):
    p = artifact_path(tmp_path, "slug", "design", agent="subagent-explore", ext="jsonl")
    assert p == work_item_dir(tmp_path, "slug") / "01-design-subagent-explore.jsonl"


def test_artifact_path_agent_and_role_combine(tmp_path):
    p = artifact_path(tmp_path, "slug", "execute", agent="subagent-1", role="review", ext="jsonl")
    assert p == work_item_dir(tmp_path, "slug") / "03-execute-subagent-1-review.jsonl"


def test_artifact_path_unknown_phase_raises(tmp_path):
    with pytest.raises(ValueError):
        artifact_path(tmp_path, "slug", "bogus-phase", "spec", ext="md")


def test_artifact_path_unknown_kind_raises(tmp_path):
    with pytest.raises(ValueError):
        artifact_path(tmp_path, "slug", "design", "bogus-kind", ext="md")


def test_artifact_path_returns_absolute_path(tmp_path):
    p = artifact_path(tmp_path, "slug", "design", "spec", ext="md")
    assert p.parent == work_item_dir(tmp_path, "slug")


def test_sidechain_dir_derives_from_transcript_stem(tmp_path):
    from work_io.paths import sidechain_dir

    transcript = tmp_path / "abc123.jsonl"
    assert sidechain_dir(transcript) == tmp_path / "abc123" / "subagents"
