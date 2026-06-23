from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from graph_wiki_cli.cli import app
from graph_wiki_core.commands.guidance_recall import RankedGuidance
from graph_wiki_core.commands.next_guidance import NextGuidanceResult
from graph_wiki_core.commands.work import WorkAdvanceResult, WorkNextResult
from typer.testing import CliRunner

runner = CliRunner()


def test_next_json_merges_guidance():
    wn = WorkNextResult(
        slug="wi",
        status="open",
        kind="feature",
        phase="plan",
        action={"skill": "writing-plans", "reason": "r"},
    )
    ng = NextGuidanceResult(
        ranked=[RankedGuidance("python/retry", "high", ["message"], "matches")],
        warnings=["no guidance index yet — run `gw guidance scan` to improve recall"],
    )
    with (
        patch("graph_wiki_cli.cli.run_work_next", new=AsyncMock(return_value=wn)),
        patch("graph_wiki_cli.cli.run_next_guidance", new=AsyncMock(return_value=ng)),
    ):
        res = runner.invoke(app, ["next", "wi", "--json"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["slug"] == "wi"
    assert payload["guidance"] == [
        {"slug": "python/retry", "relevance": "high", "signals_fired": ["message"], "reason": "matches"}
    ]
    assert any("scan" in w for w in payload["guidance_warnings"])


def test_next_skips_guidance_on_blockers_and_exits_1():
    wn = WorkNextResult(slug="wi", blockers=["effort required"])
    with (
        patch("graph_wiki_cli.cli.run_work_next", new=AsyncMock(return_value=wn)),
        patch("graph_wiki_cli.cli.run_next_guidance", new=AsyncMock()) as guidance,
    ):
        res = runner.invoke(app, ["next", "wi", "--json"])
    assert res.exit_code == 1
    guidance.assert_not_called()
    payload = json.loads(res.stdout)
    assert payload["guidance"] == []
    assert payload["guidance_warnings"] == []


def test_next_file_writes_bundle(tmp_path: Path):
    wn = WorkNextResult(slug="wi", status="open", kind="feature", phase="plan")
    out = tmp_path / "raw" / "guidance" / "wi.md"
    ng = NextGuidanceResult(
        ranked=[RankedGuidance("python/retry", "high", ["message"], "matches")],
        assembled="<!-- python/retry -->\nRetry it.",
    )
    with (
        patch("graph_wiki_cli.cli.run_work_next", new=AsyncMock(return_value=wn)),
        patch("graph_wiki_cli.cli.run_next_guidance", new=AsyncMock(return_value=ng)),
    ):
        res = runner.invoke(app, ["next", "wi", "--json", "--file", str(out)])
    assert res.exit_code == 0
    assert out.read_text(encoding="utf-8") == "<!-- python/retry -->\nRetry it."
    payload = json.loads(res.stdout)
    assert payload["guidance_file"] == str(out)


def test_next_human_is_not_dead():
    wn = WorkNextResult(slug="wi", status="open", kind="feature", phase="plan")
    ng = NextGuidanceResult(ranked=[RankedGuidance("python/retry", "high", ["message"], "matches")])
    with (
        patch("graph_wiki_cli.cli.run_work_next", new=AsyncMock(return_value=wn)),
        patch("graph_wiki_cli.cli.run_next_guidance", new=AsyncMock(return_value=ng)),
    ):
        human_res = runner.invoke(app, ["next", "wi", "--human"])
        json_res = runner.invoke(app, ["next", "wi", "--json"])
    # --human (no --json): human render contains the guidance slug and is not JSON.
    assert human_res.exit_code == 0
    assert "python/retry" in human_res.stdout
    with pytest.raises(json.JSONDecodeError):
        json.loads(human_res.stdout)
    # --json alone: pure JSON, no human lines leaked into stdout.
    assert json_res.exit_code == 0
    assert json.loads(json_res.stdout)["slug"] == "wi"


def test_advance_passthrough():
    wa = WorkAdvanceResult(
        slug="wi",
        phase="execute",
        status="accepted",
        applied={"phase": ["plan", "execute"]},
    )
    with patch("graph_wiki_cli.cli.run_work_advance", new=AsyncMock(return_value=wa)):
        res = runner.invoke(app, ["advance", "wi", "--json"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["phase"] == "execute"
    assert payload["status"] == "accepted"
