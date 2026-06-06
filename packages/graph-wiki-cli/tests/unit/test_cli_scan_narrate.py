from __future__ import annotations

from unittest.mock import patch

from graph_wiki_cli.cli import app
from graph_wiki_core.commands.scan import ScanResult
from typer.testing import CliRunner

runner = CliRunner()


def _ok_result() -> ScanResult:
    return ScanResult(state_gate={"allowed": True, "reason": "x", "head_commit": "y"})


def test_scan_no_narrate_passes_narrate_false():
    with patch("graph_wiki_cli.cli.run_scan") as mock_run:

        async def _fake(**kwargs):
            mock_run.captured = kwargs
            return _ok_result()

        mock_run.side_effect = _fake
        result = runner.invoke(app, ["scan", "--no-narrate"])
    assert result.exit_code == 0, result.output
    assert mock_run.captured["narrate"] is False


def test_scan_default_is_narrated():
    with patch("graph_wiki_cli.cli.run_scan") as mock_run:

        async def _fake(**kwargs):
            mock_run.captured = kwargs
            return _ok_result()

        mock_run.side_effect = _fake
        result = runner.invoke(app, ["scan"])
    assert result.exit_code == 0, result.output
    assert mock_run.captured["narrate"] is True
