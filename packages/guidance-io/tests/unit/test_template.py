from __future__ import annotations

from guidance_io.frontmatter import parse, validate
from guidance_io.templates import templates_dir


def _template_text() -> str:
    return (templates_dir() / "guidance.md").read_text(encoding="utf-8")


def test_shipped_template_parses() -> None:
    fm, body = parse(_template_text())
    assert fm["category"] == "guidance"
    assert "## Guidance" in body
    assert "## Applies to" in body


def test_shipped_template_validates_clean() -> None:
    fm, _ = parse(_template_text())
    assert validate(fm) == []


def test_shipped_template_has_triggers_block() -> None:
    fm, _ = parse(_template_text())
    assert isinstance(fm["triggers"], dict)
    assert isinstance(fm["triggers"]["globs"], list)
    assert isinstance(fm["triggers"]["keywords"], list)
    assert isinstance(fm["triggers"]["entities"], list)
