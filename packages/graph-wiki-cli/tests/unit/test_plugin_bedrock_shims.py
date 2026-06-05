from __future__ import annotations

import runpy
import subprocess
import sys
import types
from pathlib import Path

import pytest


_SCRIPT_DIR = (
    Path(__file__).resolve().parents[4]
    / "plugins"
    / "graph-wiki"
    / "skills"
    / "graph-wiki"
    / "scripts"
)


@pytest.mark.parametrize(
    ("script_name", "argv_tail", "expected_argv"),
    [
        (
            "scan_monorepo.py",
            ["--workspace", "/tmp/wiki", "--json"],
            ["gw", "scan", "--workspace", "/tmp/wiki", "--json"],
        ),
        (
            "init_vault.py",
            ["--topic", "Demo", "--tool", "claude-code", "--force"],
            ["gw", "bootstrap", "--topic", "Demo", "--tool", "claude-code", "--force"],
        ),
        (
            "ingest_source.py",
            ["docs/example.md", "--workspace", "/tmp/wiki"],
            ["gw", "wiki", "ingest", "source", "docs/example.md", "--workspace", "/tmp/wiki"],
        ),
        (
            "lint_wiki.py",
            ["--workspace", "/tmp/wiki", "--stale-days", "30"],
            ["gw", "wiki", "lint", "--workspace", "/tmp/wiki", "--stale-days", "30"],
        ),
        (
            "wiki_search.py",
            ["Where is auth documented?", "--top-k", "5"],
            ["gw", "wiki", "query", "Where is auth documented?", "--top-k", "5"],
        ),
    ],
)
def test_bedrock_plugin_shims_dispatch_to_gw_with_expected_argv(
    monkeypatch: pytest.MonkeyPatch,
    script_name: str,
    argv_tail: list[str],
    expected_argv: list[str],
) -> None:
    """Bedrock backend shims preserve args while mapping plugin commands to gw commands."""
    captured: dict[str, object] = {}

    def fake_run(argv: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured["check"] = check
        return subprocess.CompletedProcess(argv, 0)

    config_module = types.ModuleType("_config")
    config_module.backend_for = lambda command, repo=None: "bedrock"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "_config", config_module)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", [script_name, *argv_tail])
    monkeypatch.syspath_prepend(str(_SCRIPT_DIR))
    _install_fake_wiki_io(monkeypatch)

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(_SCRIPT_DIR / script_name), run_name="__main__")

    assert excinfo.value.code == 0
    assert captured == {"argv": expected_argv, "check": True}


def _install_fake_wiki_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide import-only wiki_io modules; Bedrock tests must never call them."""
    package = types.ModuleType("wiki_io")
    package.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wiki_io", package)

    for name in ("scan_monorepo", "init_vault", "ingest_source", "lint_wiki", "wiki_search", "graph_analyzer"):
        module = types.ModuleType(f"wiki_io.{name}")
        monkeypatch.setitem(sys.modules, f"wiki_io.{name}", module)
