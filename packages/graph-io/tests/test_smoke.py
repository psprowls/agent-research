"""Smoke tests: package imports, CLI dispatch lists subcommands."""

from __future__ import annotations

import subprocess
import sys


def test_package_imports() -> None:
    import graph_io
    assert graph_io.__version__ == "0.1.0"


def test_cli_help_lists_all_subcommands() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "graph_io.cli.main", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    out = result.stdout
    for sub in (
        "update", "status", "dump",
        "find", "callers", "callees", "imports",
        "imported-by", "exports", "exported-by",
        "describe-package", "describe-path",
    ):
        assert sub in out, f"missing subcommand in --help: {sub}"
