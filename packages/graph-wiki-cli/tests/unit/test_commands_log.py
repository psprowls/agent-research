from __future__ import annotations

"""Unit tests for the log command (Plan 05-01).

Requirements covered: CMD-06, CLI-06.
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: build a minimal wiki fixture under tmp_path
# ---------------------------------------------------------------------------


def _make_wiki(tmp_path: Path) -> Path:
    """Create a minimal wiki directory with log.md so append_log doesn't raise."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("# Log\n", encoding="utf-8")
    return wiki


def _make_log_result():
    from graph_wiki_core.commands.log import LogResult

    return LogResult(
        status="ok",
        log_path="/wiki/log.md",
        date="2026-05-14",
        op="note",
        title="test entry",
        header="## [2026-05-14] note | test entry",
        detail=None,
    )


# ---------------------------------------------------------------------------
# run_log() functional test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_log_appends_to_log_md(tmp_path: Path) -> None:
    """run_log() calls append_log and returns a LogResult with correct fields."""
    wiki = _make_wiki(tmp_path)

    # Patch resolve_wiki_and_repo so it returns our tmp wiki
    with patch(
        "graph_wiki_core.commands.log.resolve_wiki_and_repo",
        return_value=(wiki, wiki.parent),
    ):
        from graph_wiki_core.commands.log import run_log

        result = await run_log(op="note", title="hello", detail=None, workspace_path=None)

    assert result.status == "ok"
    assert result.op == "note"
    assert result.title == "hello"
    assert "note | hello" in result.header
    log_text = (wiki / "log.md").read_text(encoding="utf-8")
    assert "note | hello" in log_text


# ---------------------------------------------------------------------------
# LogResult field mapping
# ---------------------------------------------------------------------------


def test_log_result_fields_match_append_log_keys() -> None:
    """LogResult has exactly the fields returned by append_log()."""
    from graph_wiki_core.commands.log import LogResult

    fields = {f.name for f in dataclasses.fields(LogResult)}
    expected = {"status", "log_path", "date", "op", "title", "header", "detail"}
    assert fields == expected


# ---------------------------------------------------------------------------
# CLI --json output
# ---------------------------------------------------------------------------


def test_cli_log_json_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI log --json emits valid JSON with required keys."""
    from typer.testing import CliRunner

    from graph_wiki_cli.cli import app

    mock_result = _make_log_result()
    monkeypatch.setattr(
        "graph_wiki_cli.cli.run_log",
        AsyncMock(return_value=mock_result),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["log", "--op", "note", "--title", "test", "--json"])
    assert result.exit_code == 0, f"Unexpected exit: {result.output}"
    parsed = json.loads(result.output)
    assert parsed["status"] == "ok"
    assert parsed["op"] == "note"
    assert parsed["title"] == "test entry"
