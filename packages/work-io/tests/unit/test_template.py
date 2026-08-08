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
    assert "## Summary" in body


def test_work_template_documents_worktree_branch_keys() -> None:
    from importlib.resources import files

    text = (files("work_io.assets") / "work.md").read_text(encoding="utf-8")
    assert "worktree:" in text
    assert "branch:" in text
    assert "auto_drive:" not in text  # scoped out with the backed-out dispatcher
