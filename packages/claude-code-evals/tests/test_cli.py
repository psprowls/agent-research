from __future__ import annotations

from pathlib import Path

from claude_code_evals.cli import app
from click.testing import CliRunner


def test_list_no_evals_root(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(app, ["list", "--evals-root", str(tmp_path)])
    assert result.exit_code == 0


def test_report_no_runs(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(app, ["report", str(runs_dir)])
    assert result.exit_code == 0
