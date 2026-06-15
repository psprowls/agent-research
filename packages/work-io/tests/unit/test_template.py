from __future__ import annotations

from work_io.frontmatter import parse
from work_io.templates import templates_dir


def _template_text() -> str:
    return (templates_dir() / "work.md").read_text(encoding="utf-8")


def test_templates_dir_contains_work_md() -> None:
    assert (templates_dir() / "work.md").is_file()


def test_shipped_template_parses() -> None:
    fm, body = parse(_template_text())
    assert fm["category"] == "work"
    assert "## Plan" in body
