"""Mechanical guidance lint runner tests."""

from __future__ import annotations

from pathlib import Path

from guidance_io.lint import LintFinding, run_lint
from guidance_io.paths import list_all_pages

_CLEAN = """---
title: Always Pin The Model Role
category: guidance
summary: Use make_llm(role) for every model call.
topic: model-adapter
applies_when: writing code that calls Bedrock
impact: high
updated: 2026-06-15
tokens: 40
---

## Guidance
Use make_llm.

## Applies to
All model calls.
"""


def _write(ws: Path, topic: str, slug: str, text: str) -> None:
    p = ws / "wiki" / "guidance" / topic / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_list_all_pages_spans_topics_excludes_index(tmp_path: Path) -> None:
    _write(tmp_path, "model-adapter", "pin-role", _CLEAN)
    _write(tmp_path, "wiki-io", "docstring-first", _CLEAN)
    (tmp_path / "wiki" / "guidance" / "model-adapter" / "index.md").write_text("x", encoding="utf-8")

    pages = list_all_pages(tmp_path)

    names = sorted(p.name for p in pages)
    assert names == ["docstring-first.md", "pin-role.md"]


def test_list_all_pages_absent_dir(tmp_path: Path) -> None:
    assert list_all_pages(tmp_path) == []


def test_clean_page_no_findings(tmp_path: Path) -> None:
    _write(tmp_path, "model-adapter", "pin-role", _CLEAN)
    assert run_lint(tmp_path) == []


def test_parse_error_finding(tmp_path: Path) -> None:
    _write(tmp_path, "model-adapter", "broken", "no frontmatter here\n")
    findings = run_lint(tmp_path)
    assert [f.rule_id for f in findings] == ["guidance-parse-error"]
    assert findings[0].severity == "error"
    assert findings[0].slug == "model-adapter/broken"


def test_invalid_frontmatter_findings(tmp_path: Path) -> None:
    bad = "---\ntitle: X\ncategory: concept\n---\n\nbody\n"
    _write(tmp_path, "model-adapter", "bad", bad)
    findings = run_lint(tmp_path)
    assert all(f.rule_id == "guidance-invalid-frontmatter" for f in findings)
    assert all(f.severity == "error" for f in findings)
    assert all(f.slug == "model-adapter/bad" for f in findings)
    assert any("category" in f.message for f in findings)


def test_topic_placement_finding(tmp_path: Path) -> None:
    moved = _CLEAN.replace("topic: model-adapter", "topic: Model Adapter")
    _write(tmp_path, "misc", "pin-role", moved)
    findings = run_lint(tmp_path)
    assert [f.rule_id for f in findings] == ["guidance-topic-placement"]
    assert findings[0].severity == "warn"
    assert isinstance(findings[0], LintFinding)


def test_run_lint_flags_off_vocab_tag(tmp_path: Path) -> None:
    import yaml
    from guidance_io.lint import run_lint

    gdir = tmp_path / "wiki" / "guidance" / "python"
    gdir.mkdir(parents=True)
    (tmp_path / "wiki" / "guidance" / "tags.yaml").write_text(yaml.safe_dump(["retry"]), encoding="utf-8")
    fm = {
        "title": "T",
        "category": "guidance",
        "summary": "s",
        "topic": "python",
        "applies_when": "w",
        "impact": "high",
        "updated": "2026-06-22",
        "tokens": 0,
        "tags": ["retry", "bogus"],
    }
    (gdir / "a.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n## Guidance\nx\n",
        encoding="utf-8",
    )
    findings = run_lint(tmp_path)
    assert any(f.rule_id == "guidance-tag-not-allowlisted" and "bogus" in f.message for f in findings)


def test_run_lint_warns_on_prose_keyword(tmp_path: Path) -> None:
    import yaml
    from guidance_io.lint import run_lint

    gdir = tmp_path / "wiki" / "guidance" / "python"
    gdir.mkdir(parents=True)
    fm = {
        "title": "T",
        "category": "guidance",
        "summary": "s",
        "topic": "python",
        "applies_when": "w",
        "impact": "high",
        "updated": "2026-06-22",
        "tokens": 0,
        "triggers": {"keywords": ["this is clearly prose not an identifier"]},
    }
    (gdir / "b.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n## Guidance\nx\n",
        encoding="utf-8",
    )
    findings = run_lint(tmp_path)
    assert any(f.rule_id == "guidance-keyword-shape" and f.severity == "warn" for f in findings)
