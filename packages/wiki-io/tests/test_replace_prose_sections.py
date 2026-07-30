"""replace_prose_sections / prose_section_bodies — two-class prose write surface."""

from __future__ import annotations

from pathlib import Path

from wiki_io.entity_writer import prose_section_bodies, replace_prose_sections

PAGE = """---
uri: pkg:demo
kind: package
---
# demo

## Narrative
Old narrative prose.

## Purpose
TODO

## File map - demo
| Path | Kind | Description |
| --- | --- | --- |
| `a.py` | file | — TODO |

## Referenced in wiki
- [[concepts/x]]
"""


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "pkg_demo.md"
    p.write_text(PAGE, encoding="utf-8")
    return p


def test_prose_section_bodies_excludes_deterministic_and_file_map():
    bodies = prose_section_bodies(PAGE)
    assert set(bodies) == {"## Narrative", "## Purpose"}
    assert bodies["## Narrative"] == "Old narrative prose."
    assert bodies["## Purpose"] == "TODO"


def test_replace_prose_sections_replaces_existing_bodies(tmp_path):
    page = _write(tmp_path)
    changed = replace_prose_sections(page, {"## Narrative": "New prose.", "## Purpose": "Real purpose."})
    assert changed == ["## Narrative", "## Purpose"]
    text = page.read_text(encoding="utf-8")
    assert "New prose." in text and "Real purpose." in text
    assert "Old narrative prose." not in text
    assert text.count("## Narrative") == 1


def test_replace_prose_sections_refuses_deterministic_and_unknown(tmp_path):
    page = _write(tmp_path)
    before = page.read_text(encoding="utf-8")
    changed = replace_prose_sections(
        page,
        {"## Referenced in wiki": "hax", "## File map - demo": "hax", "## Nope": "x", "## Narrative": "   "},
    )
    assert changed == []
    assert page.read_text(encoding="utf-8") == before  # byte-identical no-op


def test_replace_prose_sections_never_creates_headings(tmp_path):
    page = _write(tmp_path)
    replace_prose_sections(page, {"## Brand new": "body"})
    assert "## Brand new" not in page.read_text(encoding="utf-8")


def test_replace_prose_sections_identical_replacement_not_reported(tmp_path):
    page = _write(tmp_path)
    changed = replace_prose_sections(page, {"## Narrative": "New prose.", "## Purpose": "TODO"})
    assert changed == ["## Narrative"]
