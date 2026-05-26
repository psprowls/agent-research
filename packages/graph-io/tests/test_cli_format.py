"""CLI format adapter: human + json output."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass

import pytest
from graph_io.cli import _format
from graph_io.queries import ExporterRecord, ExportRecord, ImporterRecord


@dataclass(frozen=True)
class Row:
    kind: str
    name: str
    path: str
    line: int


def test_render_json() -> None:
    rows = [Row("function", "foo", "a.py", 10)]
    out = _format.render(rows, fmt="json")
    parsed = json.loads(out)
    assert parsed == [{"kind": "function", "name": "foo", "path": "a.py", "line": 10}]


def test_render_json_empty() -> None:
    out = _format.render([], fmt="json")
    assert json.loads(out) == []


def test_render_human_aligned_columns() -> None:
    rows = [
        Row("function", "foo", "a.py", 10),
        Row("class", "Bar", "b.py", 5),
    ]
    out = _format.render(rows, fmt="human")
    lines = out.splitlines()
    assert "function" in lines[0]
    assert "class" in lines[1]
    assert "foo" in lines[0]


def test_render_human_empty_returns_empty_string() -> None:
    assert _format.render([], fmt="human") == ""


def test_render_invalid_format() -> None:
    with pytest.raises(ValueError):
        _format.render([], fmt="xml")


def test_cli_rejects_invalid_fmt() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "graph_io.cli.main", "--fmt", "xml", "status"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_render_importer_human_collapses_symbols() -> None:
    rows = [
        ImporterRecord(path="a.py", symbols=("bar", "foo"), depth=1),
        ImporterRecord(path="b.py", symbols=("foo",), depth=2),
    ]
    out = _format.render(rows, fmt="human")
    lines = out.splitlines()
    assert lines[0].startswith("a.py")
    assert "(bar, foo)" in lines[0]
    assert "1" in lines[0]
    assert lines[1].startswith("b.py")
    assert "(foo)" in lines[1]
    assert "2" in lines[1]


def test_render_importer_human_no_symbols() -> None:
    rows = [ImporterRecord(path="a.py", symbols=(), depth=2)]
    out = _format.render(rows, fmt="human")
    assert "a.py" in out
    assert "2" in out
    assert "(" not in out


def test_render_importer_json_one_object_per_edge() -> None:
    rows = [
        ImporterRecord(path="a.py", symbols=("x", "y"), depth=1),
        ImporterRecord(path="b.py", symbols=("x",), depth=1),
    ]
    parsed = json.loads(_format.render(rows, fmt="json"))
    assert parsed == [
        {"path": "a.py", "symbol": "x", "depth": 1},
        {"path": "a.py", "symbol": "y", "depth": 1},
        {"path": "b.py", "symbol": "x", "depth": 1},
    ]


def test_render_importer_json_empty_symbols_emits_null() -> None:
    rows = [ImporterRecord(path="a.py", symbols=(), depth=2)]
    parsed = json.loads(_format.render(rows, fmt="json"))
    assert parsed == [{"path": "a.py", "symbol": None, "depth": 2}]


def test_render_export_record_falls_through() -> None:
    rows = [ExportRecord(name="foo", kind="function", line=10)]
    parsed = json.loads(_format.render(rows, fmt="json"))
    assert parsed == [{"name": "foo", "kind": "function", "line": 10}]


def test_render_exporter_record_falls_through() -> None:
    rows = [ExporterRecord(path="a.py", name="foo")]
    parsed = json.loads(_format.render(rows, fmt="json"))
    assert parsed == [{"path": "a.py", "name": "foo"}]


# ── Phase 36: cap + on_truncate (D-09) ───────────────────────────────────────


def _make_rows(n: int) -> list[Row]:
    return [Row("function", f"f{i}", f"f{i}.py", i) for i in range(n)]


def test_render_caps_human_at_50() -> None:
    rows = _make_rows(75)
    out = _format.render(rows, fmt="human", cap=50)
    lines = out.splitlines()
    # 50 data rows + 1 trailer line
    assert len(lines) == 51
    assert "showing 50 of 75" in lines[-1]
    assert "truncated" in lines[-1]


def test_render_caps_json_at_50() -> None:
    rows = _make_rows(75)
    out = _format.render(rows, fmt="json", cap=50)
    parsed = json.loads(out)
    # Flat array, no envelope wrap (RESEARCH §3.2 option 1)
    assert isinstance(parsed, list)
    assert len(parsed) == 50


def test_render_invokes_on_truncate_callback() -> None:
    calls: list[tuple[int, int]] = []

    def _cb(shown: int, total: int) -> None:
        calls.append((shown, total))

    # Truncation fires
    _format.render(_make_rows(75), fmt="human", cap=50, on_truncate=_cb)
    assert calls == [(50, 75)]

    # No truncation when total <= cap
    calls.clear()
    _format.render(_make_rows(10), fmt="human", cap=50, on_truncate=_cb)
    assert calls == []


def test_render_no_cap_passes_through() -> None:
    rows = _make_rows(75)
    out = _format.render(rows, fmt="human")
    lines = out.splitlines()
    assert len(lines) == 75
    # No truncation trailer present
    assert not any("truncated" in line for line in lines)
