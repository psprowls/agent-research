"""Unit tests for dir_section_todo_contexts and is_overview_unfilled."""

from __future__ import annotations

from pathlib import Path

from wiki_io.entity_writer import (
    _DIR_SECTION_PLACEHOLDER,
    _OVERVIEW_PLACEHOLDER,
    dir_section_todo_contexts,
    is_overview_unfilled,
)

_MIXED = (
    "## File map - test-pkg\n" + _OVERVIEW_PLACEHOLDER + "\n"
    "\n"
    "### test-pkg/\n" + _DIR_SECTION_PLACEHOLDER + "\n"
    "\n"
    "| Path | Kind | Description |\n"
    "|---|---|---|\n"
    "| `foo.py` | file | module foo |\n"
    "\n"
    "### test-pkg/src/\n" + _DIR_SECTION_PLACEHOLDER + "\n"
    "\n"
    "| Path | Kind | Description |\n"
    "|---|---|---|\n"
    "| `bar.py` | file | module bar |\n"
    "\n"
    "### test-pkg/tests/\n"
    "Already filled this directory.\n"
    "\n"
    "| Path | Kind | Description |\n"
    "|---|---|---|\n"
    "| `test_foo.py` | file | tests for foo |\n"
)

_ALL_FILLED = """\
## File map - test-pkg
Package overview filled.

### test-pkg/
Root directory description.

| Path | Kind | Description |
|---|---|---|
| `foo.py` | file | module foo |
"""

_NO_FILE_MAP = "## Narrative\nSome narrative content.\n"


def _page(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "page.md"
    p.write_text(content, encoding="utf-8")
    return p


def test_dir_section_todo_contexts_returns_unfilled_contexts(tmp_path):
    p = _page(tmp_path, _MIXED)
    result = dir_section_todo_contexts(p)
    assert set(result) == {"", "src"}


def test_dir_section_todo_contexts_all_filled_returns_empty(tmp_path):
    p = _page(tmp_path, _ALL_FILLED)
    assert dir_section_todo_contexts(p) == []


def test_dir_section_todo_contexts_no_file_map_returns_empty(tmp_path):
    p = _page(tmp_path, _NO_FILE_MAP)
    assert dir_section_todo_contexts(p) == []


def test_is_overview_unfilled_true_for_placeholder(tmp_path):
    p = _page(tmp_path, _MIXED)
    assert is_overview_unfilled(p) is True


def test_is_overview_unfilled_false_when_filled(tmp_path):
    p = _page(tmp_path, _ALL_FILLED)
    assert is_overview_unfilled(p) is False


def test_is_overview_unfilled_false_when_no_file_map(tmp_path):
    p = _page(tmp_path, _NO_FILE_MAP)
    assert is_overview_unfilled(p) is False
