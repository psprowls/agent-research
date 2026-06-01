"""Unit tests for wiki_io.entity_writer.inject_file_map."""

from __future__ import annotations

import logging
from pathlib import Path

import frontmatter
import pytest

from wiki_io.entity_writer import (
    _extract_file_map_descriptions,
    fill_file_map_descriptions,
    file_map_todo_paths,
    inject_file_map,
)

# A multi-section deterministic block as emitted by build_file_map().
_BLOCK_MULTI = (
    "## File map - foo\n"
    "TODO — overview of this package's tree.\n"
    "\n"
    "### foo/\n"
    "TODO — describe what this directory contains.\n"
    "\n"
    "| Path | Kind | Description |\n"
    "|---|---|---|\n"
    "| `pyproject.toml` | file | — TODO |\n"
    "\n"
    "### foo/src/\n"
    "TODO — describe what this directory contains.\n"
    "\n"
    "| Path | Kind | Description |\n"
    "|---|---|---|\n"
    "| `__init__.py` | file | — TODO |\n"
    "| `core.py` | file | — TODO |\n"
)

# A realistic deterministic block as emitted by build_file_map() — its own
# `## File map - <name>` heading plus a per-folder H3 table.
_BLOCK = (
    "## File map - foo\n"
    "TODO — overview of this package's tree.\n"
    "\n"
    "### foo/\n"
    "TODO — describe what this directory contains.\n"
    "\n"
    "| Path | Kind | Description |\n"
    "|---|---|---|\n"
    "| `__init__.py` | file | — TODO |\n"
)


def _template_page() -> str:
    """Mirrors entity-package.md: a `## File map - foo` section between
    `## Purpose` and `## Public API`, with the empty template placeholder rows."""
    return (
        "---\n"
        "uri: pkg:agent-research/foo\n"
        "kind: package\n"
        "---\n"
        "\n"
        "# foo\n"
        "\n"
        "## Purpose\n"
        "> TODO: purpose\n"
        "\n"
        "## File map - foo\n"
        "> TODO — <Overview of this package's source tree.>\n"
        "\n"
        "### foo/\n"
        "> TODO — <describe what this directory contains.>\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `<file>` | file | — > TODO — <Short description of file contents.> |\n"
        "\n"
        "## Public API\n"
        "> TODO: api\n"
    )


def test_inject_file_map_replaces_whole_section(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")

    inject_file_map(p, _BLOCK)

    text = p.read_text(encoding="utf-8")
    # Deterministic rows landed; template placeholder rows are gone.
    assert "| `__init__.py` | file | — TODO |" in text
    assert "<Overview of this package's source tree.>" not in text
    assert "<Short description of file contents.>" not in text
    # Neighboring sections untouched.
    assert "## Purpose\n> TODO: purpose\n" in text
    assert "## Public API\n> TODO: api\n" in text
    # Exactly one File map heading remains.
    assert text.count("## File map - foo") == 1


def test_inject_file_map_idempotent(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")

    inject_file_map(p, _BLOCK)
    after_first = p.read_bytes()
    inject_file_map(p, _BLOCK)
    after_second = p.read_bytes()

    assert after_first == after_second


def test_inject_file_map_atomic_no_tmp_remains(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")

    inject_file_map(p, _BLOCK)

    assert list(tmp_path.glob("*.tmp")) == []


def test_inject_file_map_preserves_frontmatter(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")
    before = dict(frontmatter.load(p).metadata)

    inject_file_map(p, _BLOCK)

    assert dict(frontmatter.load(p).metadata) == before


def test_inject_file_map_replaces_through_eof_when_last_section(tmp_path: Path):
    page = (
        "---\nuri: pkg:x\nkind: package\n---\n"
        "\n## Purpose\n\nfoo\n"
        "\n## File map - foo\n> TODO — old\n\n### foo/\n\n| Path | Kind | Description |\n"
    )
    p = tmp_path / "page.md"
    p.write_text(page, encoding="utf-8")

    inject_file_map(p, _BLOCK)

    text = p.read_text(encoding="utf-8")
    assert "## Purpose\n\nfoo\n" in text
    assert text.rstrip().endswith("| `__init__.py` | file | — TODO |")


def test_inject_file_map_missing_heading_logs_warning_no_write(
    tmp_path: Path, caplog
):
    page = (
        "---\nuri: pkg:x\nkind: package\n---\n"
        "\n## Purpose\n\nfoo\n"
        "\n## Public API\n\napi\n"
    )
    p = tmp_path / "page.md"
    p.write_text(page, encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="wiki_io.entity_writer"):
        inject_file_map(p, _BLOCK)

    assert p.read_text(encoding="utf-8") == page  # untouched
    assert any(
        "File map" in record.getMessage() and record.levelno == logging.WARNING
        for record in caplog.records
    ), f"No WARNING about File map; saw: {[r.getMessage() for r in caplog.records]}"


def test_inject_file_map_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        inject_file_map(tmp_path / "nope.md", _BLOCK)


# ---------------------------------------------------------------------------
# Merge-preserving behavior (durability across rescans)
# ---------------------------------------------------------------------------


def test_extract_file_map_descriptions_keys_filled_rows_by_path():
    section_body = (
        "\n### foo/\nRoot.\n\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | package manifest |\n"
        "\n### foo/src/\nSources.\n\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `__init__.py` | file | — TODO |\n"
        "| `core.py` | file | the core engine |\n"
    )
    descs = _extract_file_map_descriptions(section_body, "foo")
    # Only filled rows are captured, keyed by package-root path.
    assert descs == {
        "pyproject.toml": "package manifest",
        "src/core.py": "the core engine",
    }


def test_inject_file_map_restores_preserved_descriptions(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")

    preserved = {
        "pyproject.toml": "package manifest",
        "src/core.py": "the core engine",
    }
    inject_file_map(p, _BLOCK_MULTI, preserved=preserved)

    text = p.read_text(encoding="utf-8")
    # Preserved descriptions restored for paths still present.
    assert "| `pyproject.toml` | file | package manifest |" in text
    assert "| `core.py` | file | the core engine |" in text
    # A path with no preserved description keeps its — TODO.
    assert "| `__init__.py` | file | — TODO |" in text


def test_inject_file_map_preserved_ignores_unknown_paths(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")

    # `gone.py` is not in the new block → has no effect; rows stay — TODO.
    inject_file_map(p, _BLOCK_MULTI, preserved={"src/gone.py": "removed file"})

    text = p.read_text(encoding="utf-8")
    assert "removed file" not in text
    assert "| `core.py` | file | — TODO |" in text


def test_inject_file_map_merge_roundtrips_through_extractor(tmp_path: Path):
    """A block injected with preserved descriptions, then re-extracted, yields
    the same description map (path keys survive a write/read cycle)."""
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")

    preserved = {"pyproject.toml": "package manifest", "src/core.py": "core engine"}
    inject_file_map(p, _BLOCK_MULTI, preserved=preserved)

    from wiki_io.entity_writer import _FILE_MAP_HEADING_RE, _NEXT_H2_RE

    text = p.read_text(encoding="utf-8")
    start = _FILE_MAP_HEADING_RE.search(text)
    body_start = start.end()
    nxt = _NEXT_H2_RE.search(text, body_start)
    body = text[body_start : nxt.start() if nxt else len(text)]
    again = _extract_file_map_descriptions(body, "foo")
    assert again == preserved


def test_inject_file_map_preserved_handles_pipe_in_description(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")

    inject_file_map(
        p, _BLOCK_MULTI, preserved={"src/core.py": "handles a | b routing"}
    )

    text = p.read_text(encoding="utf-8")
    # Pipe is escaped in the cell so the table stays well-formed, and a
    # re-extract decodes it back to the original.
    assert "handles a \\| b routing" in text
    from wiki_io.entity_writer import _FILE_MAP_HEADING_RE, _NEXT_H2_RE

    start = _FILE_MAP_HEADING_RE.search(text)
    nxt = _NEXT_H2_RE.search(text, start.end())
    body = text[start.end() : nxt.start() if nxt else len(text)]
    descs = _extract_file_map_descriptions(body, "foo")
    assert descs["src/core.py"] == "handles a | b routing"


# ---------------------------------------------------------------------------
# file_map_todo_paths + fill_file_map_descriptions (code-reader fill target)
# ---------------------------------------------------------------------------


def test_file_map_todo_paths_lists_unfilled_file_rows(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")
    inject_file_map(p, _BLOCK_MULTI)  # all rows — TODO

    assert file_map_todo_paths(p) == [
        "pyproject.toml",
        "src/__init__.py",
        "src/core.py",
    ]


def test_file_map_todo_paths_excludes_filled_rows(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")
    inject_file_map(
        p, _BLOCK_MULTI, preserved={"src/core.py": "the core engine"}
    )

    # src/core.py now filled → only the other two remain TODO.
    assert file_map_todo_paths(p) == ["pyproject.toml", "src/__init__.py"]


def test_file_map_todo_paths_no_section_returns_empty(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(
        "---\nuri: pkg:x\n---\n\n## Purpose\n\nx\n", encoding="utf-8"
    )
    assert file_map_todo_paths(p) == []


def test_fill_file_map_descriptions_fills_todo_cells(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")
    inject_file_map(p, _BLOCK_MULTI)

    n = fill_file_map_descriptions(
        p,
        {
            "pyproject.toml": "package manifest",
            "src/core.py": "the core engine",
            "src/nope.py": "not in the table",  # ignored
        },
    )
    assert n == 2

    text = p.read_text(encoding="utf-8")
    assert "| `pyproject.toml` | file | package manifest |" in text
    assert "| `core.py` | file | the core engine |" in text
    assert "| `__init__.py` | file | — TODO |" in text
    assert "not in the table" not in text


def test_fill_file_map_descriptions_never_overwrites_filled(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")
    inject_file_map(p, _BLOCK_MULTI, preserved={"src/core.py": "human-written"})

    # Try to overwrite the already-filled cell + fill a real TODO.
    n = fill_file_map_descriptions(
        p, {"src/core.py": "llm guess", "pyproject.toml": "package manifest"}
    )
    assert n == 1  # only the TODO row counted

    text = p.read_text(encoding="utf-8")
    assert "| `core.py` | file | human-written |" in text  # untouched
    assert "llm guess" not in text
    assert "| `pyproject.toml` | file | package manifest |" in text


def test_fill_file_map_descriptions_empty_is_noop(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_template_page(), encoding="utf-8")
    inject_file_map(p, _BLOCK_MULTI)
    before = p.read_bytes()

    assert fill_file_map_descriptions(p, {}) == 0
    assert p.read_bytes() == before


def test_fill_file_map_descriptions_no_section_returns_zero(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text("---\nuri: pkg:x\n---\n\n## Purpose\n\nx\n", encoding="utf-8")
    assert fill_file_map_descriptions(p, {"a.py": "desc"}) == 0
