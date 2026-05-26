from __future__ import annotations

"""Unit tests for the bootstrap CLI's --interactive flag (HYGIENE-11).

Covers:
- `bootstrap --help` lists the `--interactive` flag alongside all existing flags.
- `run_init(interactive=...)` forwards the inverted boolean to `init_wiki` as
  `non_interactive=not interactive` (default behaviour preserved when absent).
"""

import asyncio
import os
import subprocess
from pathlib import Path

import pytest


_PLAIN_HELP_ENV = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"}


def test_bootstrap_help_lists_interactive_flag() -> None:
    result = subprocess.run(
        ["uv", "run", "--package", "graph-wiki-agent", "graph-wiki-agent", "bootstrap", "--help"],
        capture_output=True,
        text=True,
        env=_PLAIN_HELP_ENV,
    )
    assert result.returncode == 0, f"bootstrap --help exited {result.returncode}\n{result.stderr}"
    assert "--interactive" in result.stdout, (
        f"`--interactive` must appear in `bootstrap --help` after HYGIENE-11.\n"
        f"stdout:\n{result.stdout}"
    )
    # Regression guard: all existing options still present.
    for flag in ("--topic", "--tool", "--force", "--workspace", "--repo", "--json"):
        assert flag in result.stdout, (
            f"`{flag}` missing from `bootstrap --help` — HYGIENE-11 must be purely additive.\n"
            f"stdout:\n{result.stdout}"
        )


@pytest.mark.parametrize(
    "interactive,expected_non_interactive",
    [(False, True), (True, False)],
)
def test_run_init_forwards_interactive_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    interactive: bool,
    expected_non_interactive: bool,
) -> None:
    """`run_init(interactive=X)` calls `init_wiki(non_interactive=not X)`."""
    from graph_wiki_agent.commands import init as init_mod

    captured: dict = {}

    def fake_init_wiki(**kwargs):
        captured.update(kwargs)
        return {
            "status": "ok",
            "wiki_path": str(tmp_path / "wiki"),
            "repo_path": str(tmp_path),
            "topic": "t",
            "tool": "claude-code",
            "date": "2026-05-26",
            "installed_files": [],
            "page_templates_copied": 0,
            "layers": {},
            "raw_path": str(tmp_path / "raw"),
            "work_path": str(tmp_path / "work"),
        }

    monkeypatch.setattr(init_mod, "init_wiki", fake_init_wiki)
    monkeypatch.setattr(init_mod, "_ws_init", lambda *a, **kw: None)
    monkeypatch.setattr(
        init_mod, "resolve_wiki_and_repo", lambda ws, repo: (tmp_path / "wiki", tmp_path)
    )

    asyncio.run(
        init_mod.run_init(
            topic="t",
            tool="claude-code",
            force=False,
            interactive=interactive,
            workspace_path=None,
            repo_path=tmp_path,
        )
    )
    assert captured.get("non_interactive") is expected_non_interactive
