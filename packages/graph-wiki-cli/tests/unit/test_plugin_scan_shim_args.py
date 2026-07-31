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


def test_both_sources_in_different_parents_file_wins_for_worklist(claude_backend, monkeypatch, tmp_path):
    """When --apply-worklist and --results-dir sit in different directories, the derived
    worklist.json location must come from the FILE's parent, not the directory's — pinning
    the "file wins" precedence that the un-annotated default previously left unverified.
    """
    captured = _patch_apply(monkeypatch)
    file_parent = tmp_path / "from-file"
    file_parent.mkdir(parents=True)
    results_json = file_parent / "results.json"
    results_json.write_text("{}", encoding="utf-8")

    dir_parent = tmp_path / "from-dir"
    dir_parent.mkdir(parents=True)
    results_dir = dir_parent / "results"
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
    assert captured["worklist_path"] == file_parent / "worklist.json"
    assert captured["worklist_path"] != dir_parent / "worklist.json"


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


def test_emit_payload_normalizes_relative_worklist_path(claude_backend, monkeypatch, capsys, tmp_path):
    """All three emit-payload path strings must share the same (pathlib-normalized) shape.

    Regression for a bug where worklist_path echoed the raw --emit-worklist string while
    briefs_dir/results_dir were normalized Path strings, so a relative input like
    "./out/worklist.json" produced inconsistent sibling paths in the JSON.
    """
    from graph_wiki_core.commands import scan as scan_mod

    async def fake_emit(**kwargs):
        return scan_mod.ScanResult(state_gate={})

    monkeypatch.setattr(scan_mod, "emit_scan_worklist", fake_emit)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(sys, "argv", ["scan_monorepo.py", "--emit-worklist", "./out/worklist.json"])
    runpy.run_path(str(_SCRIPT), run_name="__main__")

    payload = json.loads(capsys.readouterr().out)
    out_path = Path("./out/worklist.json")
    assert payload["worklist_path"] == str(out_path)
    assert payload["briefs_dir"] == str(out_path.parent / "briefs")
    assert payload["results_dir"] == str(out_path.parent / "results")
    # Genuinely siblings: same parent directory for all three.
    assert Path(payload["worklist_path"]).parent == Path(payload["briefs_dir"]).parent
    assert Path(payload["worklist_path"]).parent == Path(payload["results_dir"]).parent


def test_apply_worklist_alone_drives_apply(claude_backend, monkeypatch, tmp_path):
    """The pre-existing single-source path, now flowing through the rewritten
    `if args.apply_worklist or args.results_dir:` guard.
    """
    captured = _patch_apply(monkeypatch)
    gw_dir = tmp_path / ".graph-wiki"
    gw_dir.mkdir(parents=True)
    results_json = gw_dir / "results.json"
    results_json.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["scan_monorepo.py", "--apply-worklist", str(results_json), "--short-head", "abc1234"],
    )
    runpy.run_path(str(_SCRIPT), run_name="__main__")

    assert captured["results_path"] == results_json
    assert captured["results_dir"] is None
    assert captured["short_head"] == "abc1234"
    assert captured["worklist_path"] == gw_dir / "worklist.json"


def test_explicit_worklist_path_overrides_derived_default(claude_backend, monkeypatch, tmp_path):
    captured = _patch_apply(monkeypatch)
    gw_dir = tmp_path / ".graph-wiki"
    gw_dir.mkdir(parents=True)
    results_json = gw_dir / "results.json"
    results_json.write_text("{}", encoding="utf-8")
    explicit_worklist = tmp_path / "elsewhere" / "custom-worklist.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scan_monorepo.py",
            "--apply-worklist",
            str(results_json),
            "--worklist-path",
            str(explicit_worklist),
        ],
    )
    runpy.run_path(str(_SCRIPT), run_name="__main__")

    assert captured["results_path"] == results_json
    assert captured["worklist_path"] == explicit_worklist
    assert captured["worklist_path"] != gw_dir / "worklist.json"


def test_apply_exits_3_on_entity_errors(claude_backend, monkeypatch, tmp_path):
    from graph_wiki_core.commands import scan as scan_mod
    from graph_wiki_core.commands.scan_contract import ApplyResult

    async def fake_apply(**kwargs):
        return ApplyResult(entity_errors=["entities/foo.md: boom"])

    monkeypatch.setattr(scan_mod, "apply_scan_worklist", fake_apply)
    gw_dir = tmp_path / ".graph-wiki"
    gw_dir.mkdir(parents=True)
    results_json = gw_dir / "results.json"
    results_json.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["scan_monorepo.py", "--apply-worklist", str(results_json)])

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(_SCRIPT), run_name="__main__")

    assert excinfo.value.code == 3
