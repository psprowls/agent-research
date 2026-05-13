from __future__ import annotations

import subprocess


def test_cli_help_exits_zero() -> None:
    result = subprocess.run(
        ["uv", "run", "--package", "code-wiki-agent", "code-wiki-agent", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"--help exited {result.returncode}\n{result.stderr}"
    assert "code-wiki-agent" in result.stdout.lower()
