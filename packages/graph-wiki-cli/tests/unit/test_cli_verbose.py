"""Tests for the gw root --verbose/-v/-vv callback."""

from __future__ import annotations

import os
import subprocess

import pytest

_PLAIN_ENV = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"}


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["version"], 0),
        (["-v", "version"], 1),
        (["-vv", "version"], 2),
        (["--verbose", "version"], 1),
    ],
)
def test_callback_passes_verbosity_count(monkeypatch, argv, expected):
    """The root callback calls configure_verbose_logging with the counted -v value."""
    import graph_wiki_cli.cli as cli
    from typer.testing import CliRunner

    calls: list[int] = []
    monkeypatch.setattr(cli, "configure_verbose_logging", lambda v: calls.append(v))

    runner = CliRunner()
    result = runner.invoke(cli.app, argv)
    assert result.exit_code == 0, result.output
    assert calls == [expected]


def test_verbose_keeps_stdout_clean_for_version():
    """`gw -v version` writes only the version banner to stdout (logs go to stderr)."""
    result = subprocess.run(
        ["uv", "run", "--package", "graph-wiki-cli", "gw", "-v", "version"],
        capture_output=True,
        text=True,
        env=_PLAIN_ENV,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.startswith("gw ")
    # Exactly one line on stdout — no verbose noise leaked from stderr.
    assert "\n" not in result.stdout.strip()
