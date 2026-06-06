"""End-to-end: tiny multi-language repo → all CLI subcommands work."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ._git_repo import init_repo, write_and_commit


def _cg(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "graph_wiki_cli.graph_cli.main", "--repo", str(cwd), "--mode", "test", *args],
        capture_output=True,
        text=True,
    )


def test_e2e_pipeline(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "demo-py"\nversion = "0.1.1"\n',
            "package.json": '{"name": "demo-js", "version": "0.1.1"}',
            "src/a.py": "def alpha():\n    return beta()\n\ndef beta():\n    return 1\n",
            "src/b.js": "function gamma() { return 1; }\n",
        },
        "",
    )

    assert _cg(["update", "--full"], tmp_path).returncode == 0

    res = _cg(["--fmt", "json", "find", "--name", "alpha"], tmp_path)
    assert res.returncode == 0
    assert any(r["name"] == "alpha" for r in json.loads(res.stdout))

    res = _cg(["callers", "beta"], tmp_path)
    assert res.returncode == 0
    assert "alpha" in res.stdout

    res = _cg(["callees", "alpha"], tmp_path)
    assert res.returncode == 0
    assert "beta" in res.stdout

    res = _cg(["--fmt", "json", "describe", "demo-py", "--kind", "package"], tmp_path)
    assert res.returncode == 0
    assert json.loads(res.stdout)["language"] == "python"

    res = _cg(["--fmt", "json", "describe", "demo-js", "--kind", "package"], tmp_path)
    assert res.returncode == 0
    assert json.loads(res.stdout)["language"] == "javascript"

    res = _cg(["--fmt", "json", "describe", "src/a.py", "--kind", "path"], tmp_path)
    assert res.returncode == 0
    assert json.loads(res.stdout)["path"] == "src/a.py"

    res = _cg(["status"], tmp_path)
    assert res.returncode == 0
    assert "stale:" in res.stdout.lower() or "False" in res.stdout
