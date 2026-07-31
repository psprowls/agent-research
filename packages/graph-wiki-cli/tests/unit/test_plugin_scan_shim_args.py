"""Claude-branch flag wiring for the scan plugin shim.

The shim is the plugin path's only entry point, so its argv contract is the
contract the scanner agent's markdown is written against.
"""

from __future__ import annotations

import json
import runpy
import sys
import types
from pathlib import Path

import pytest

_SCRIPT_DIR = Path(__file__).resolve().parents[4] / "plugins" / "graph-wiki" / "skills" / "graph-wiki" / "scripts"
_SCRIPT = _SCRIPT_DIR / "scan_monorepo.py"


@pytest.fixture
def claude_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    config_module = types.ModuleType("_config")
    config_module.backend_for = lambda command, repo=None: "claude"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "_config", config_module)
    monkeypatch.syspath_prepend(str(_SCRIPT_DIR))


def _patch_apply(monkeypatch: pytest.MonkeyPatch) -> dict:
    from graph_wiki_core.commands import scan as scan_mod
    from graph_wiki_core.commands.scan_contract import ApplyResult

    captured: dict = {}

    async def fake_apply(**kwargs):
        captured.update(kwargs)
        return ApplyResult()

    monkeypatch.setattr(scan_mod, "apply_scan_worklist", fake_apply)
    return captured


def test_results_dir_alone_drives_apply(claude_backend, monkeypatch, capsys, tmp_path):
    captured = _patch_apply(monkeypatch)
    results_dir = tmp_path / ".graph-wiki" / "results"
    results_dir.mkdir(parents=True)

    monkeypatch.setattr(sys, "argv", ["scan_monorepo.py", "--results-dir", str(results_dir)])
    runpy.run_path(str(_SCRIPT), run_name="__main__")

    assert captured["results_path"] is None
    assert captured["results_dir"] == results_dir
    assert captured["worklist_path"] == tmp_path / ".graph-wiki" / "worklist.json"


def test_both_sources_are_passed_in_one_call(claude_backend, monkeypatch, tmp_path):
    captured = _patch_apply(monkeypatch)
    gw_dir = tmp_path / ".graph-wiki"
    gw_dir.mkdir(parents=True)
    results_json = gw_dir / "results.json"
    results_json.write_text("{}", encoding="utf-8")
    results_dir = gw_dir / "results"
    results_dir.mkdir()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scan_monorepo.py",
            "--apply-worklist",
            str(results_json),
            "--results-dir",
            str(results_dir),
            "--short-head",
            "abc1234",
        ],
    )
    runpy.run_path(str(_SCRIPT), run_name="__main__")

    assert captured["results_path"] == results_json
    assert captured["results_dir"] == results_dir
    assert captured["short_head"] == "abc1234"
    assert captured["worklist_path"] == gw_dir / "worklist.json"


def test_emit_payload_advertises_brief_and_result_dirs(claude_backend, monkeypatch, capsys, tmp_path):
    from graph_wiki_core.commands import scan as scan_mod

    async def fake_emit(**kwargs):
        return scan_mod.ScanResult(state_gate={})

    monkeypatch.setattr(scan_mod, "emit_scan_worklist", fake_emit)
    out = tmp_path / ".graph-wiki" / "worklist.json"

    monkeypatch.setattr(sys, "argv", ["scan_monorepo.py", "--emit-worklist", str(out)])
    runpy.run_path(str(_SCRIPT), run_name="__main__")

    payload = json.loads(capsys.readouterr().out)
    assert payload["worklist_path"] == str(out)
    assert payload["briefs_dir"] == str(out.parent / "briefs")
    assert payload["results_dir"] == str(out.parent / "results")
    assert "scan_result" in payload
