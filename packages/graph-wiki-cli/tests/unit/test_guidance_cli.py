from __future__ import annotations

from unittest.mock import patch

from graph_wiki_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_guidance_listed_in_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "guidance" in result.output


def test_guidance_scan_help() -> None:
    result = runner.invoke(app, ["guidance", "scan", "--help"])
    assert result.exit_code == 0, result.output


def test_guidance_scan_invokes_core() -> None:
    from graph_wiki_core.commands.guidance_scan import GuidanceScanResult

    with patch(
        "graph_wiki_cli.guidance_cli.main.run_guidance_scan",
        return_value=GuidanceScanResult(scanned=["a.py"], total=1, vocab_hash="h"),
    ) as scan:
        result = runner.invoke(app, ["guidance", "--repo", ".", "--mode", "test", "scan", "--limit", "5"])
    assert result.exit_code == 0, result.output
    assert scan.call_args.kwargs["limit"] == 5


def test_guidance_suggest_invokes_core_and_renders() -> None:
    from graph_wiki_core.commands.guidance_suggest import GuidanceSuggestResult, RankedGuidance

    fake = GuidanceSuggestResult(
        ranked=[RankedGuidance("python/retry", "high", ["index", "entity"], "matches")],
        index_present=True,
    )
    with patch("graph_wiki_cli.guidance_cli.main.run_guidance_suggest", return_value=fake) as suggest:
        result = runner.invoke(
            app,
            ["guidance", "--repo", ".", "--mode", "test", "suggest", "add retry", "--path", "x.py"],
        )
    assert result.exit_code == 0, result.output
    assert "python/retry" in result.output
    assert suggest.call_args.kwargs["paths"] == ["x.py"]


def test_guidance_suggest_json() -> None:
    from graph_wiki_core.commands.guidance_suggest import GuidanceSuggestResult, RankedGuidance

    fake = GuidanceSuggestResult(
        ranked=[RankedGuidance("python/retry", "high", ["index"], "matches")], index_present=True
    )
    with patch("graph_wiki_cli.guidance_cli.main.run_guidance_suggest", return_value=fake):
        result = runner.invoke(app, ["guidance", "--mode", "test", "suggest", "add retry", "--fmt", "json"])
    assert result.exit_code == 0, result.output
    assert '"slug": "python/retry"' in result.output
