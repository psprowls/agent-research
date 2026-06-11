"""Unit tests for fill_dir_section_descriptions, fill_file_map_overview, extract_file_map_descriptions."""

from __future__ import annotations

from pathlib import Path

from wiki_io.entity_writer import (
    extract_file_map_descriptions,
    fill_dir_section_descriptions,
    fill_file_map_overview,
)

_PLACEHOLDER_SEC = "TODO — describe what this directory contains."
_PLACEHOLDER_OV = "TODO — overview of this package's tree."

_MIXED = """\
## File map - test-pkg
TODO — overview of this package's tree.

### test-pkg/
TODO — describe what this directory contains.

| Path | Kind | Description |
|---|---|---|
| `foo.py` | file | module foo |

### test-pkg/src/
Already filled.

| Path | Kind | Description |
|---|---|---|
| `bar.py` | file | module bar |
"""

_ALL_FILLED = """\
## File map - test-pkg
Package overview description.

### test-pkg/
Root section description.

| Path | Kind | Description |
|---|---|---|
| `foo.py` | file | module foo |
"""

_WITH_FILE_TODOS = """\
## File map - test-pkg
TODO — overview of this package's tree.

### test-pkg/
TODO — describe what this directory contains.

| Path | Kind | Description |
|---|---|---|
| `foo.py` | file | module foo |
| `bar.py` | file | module bar |
| `todo.py` | file | — TODO |
"""


def _page(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "page.md"
    p.write_text(content, encoding="utf-8")
    return p


def test_fill_dir_section_descriptions_replaces_placeholder(tmp_path):
    p = _page(tmp_path, _MIXED)
    n = fill_dir_section_descriptions(p, {"": "root files and config"})
    assert n == 1
    text = p.read_text(encoding="utf-8")
    assert "root files and config" in text
    assert _PLACEHOLDER_SEC not in text.split("### test-pkg/src/")[0]


def test_fill_dir_section_descriptions_preserves_filled_section(tmp_path):
    p = _page(tmp_path, _MIXED)
    n = fill_dir_section_descriptions(p, {"src": "should not overwrite"})
    assert n == 0
    text = p.read_text(encoding="utf-8")
    assert "Already filled." in text
    assert "should not overwrite" not in text


def test_fill_dir_section_descriptions_returns_zero_for_empty_descs(tmp_path):
    p = _page(tmp_path, _MIXED)
    assert fill_dir_section_descriptions(p, {}) == 0


def test_fill_dir_section_descriptions_atomic_no_tmp_left(tmp_path):
    p = _page(tmp_path, _MIXED)
    fill_dir_section_descriptions(p, {"": "description"})
    assert not (tmp_path / "page.md.tmp").exists()


def test_fill_file_map_overview_replaces_placeholder(tmp_path):
    p = _page(tmp_path, _MIXED)
    result = fill_file_map_overview(p, "manages config and src modules")
    assert result is True
    text = p.read_text(encoding="utf-8")
    assert "manages config and src modules" in text
    assert _PLACEHOLDER_OV not in text


def test_fill_file_map_overview_preserves_non_placeholder(tmp_path):
    p = _page(tmp_path, _ALL_FILLED)
    result = fill_file_map_overview(p, "new overview")
    assert result is False
    assert "Package overview description." in p.read_text(encoding="utf-8")


def test_fill_file_map_overview_atomic_no_tmp_left(tmp_path):
    p = _page(tmp_path, _MIXED)
    fill_file_map_overview(p, "overview text")
    assert not (tmp_path / "page.md.tmp").exists()


def test_extract_file_map_descriptions_returns_filled_rows_only(tmp_path):
    p = _page(tmp_path, _WITH_FILE_TODOS)
    result = extract_file_map_descriptions(p)
    assert result == {"foo.py": "module foo", "bar.py": "module bar"}
    assert "todo.py" not in result


def test_extract_file_map_descriptions_no_file_map_returns_empty(tmp_path):
    p = _page(tmp_path, "## Narrative\nSome text.\n")
    assert extract_file_map_descriptions(p) == {}


def test_fill_dir_section_descriptions_no_file_map_returns_zero(tmp_path):
    p = _page(tmp_path, "## Narrative\nSome text.\n")
    assert fill_dir_section_descriptions(p, {"": "desc"}) == 0
