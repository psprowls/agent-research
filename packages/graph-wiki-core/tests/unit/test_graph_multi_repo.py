"""Tests for run_build multi-repo member resolution (Task 4).

Verifies that run_build:
  1. Calls update.run_workspace when members exist (all members).
  2. Scopes to a single member when repo matches one of the members.
  3. Falls back to update.run (single-repo path) when members is empty.
"""

from pathlib import Path

from graph_wiki_core.commands import graph as graph_cmd


class _Cfg:
    """Minimal GraphWikiConfig stand-in."""

    def __init__(self, members, workspace):
        self.members = tuple(members)
        self.workspace = workspace
        self.repo_root = members[0] if members else Path()


def test_run_build_uses_run_workspace_when_members(monkeypatch, tmp_path):
    """When members exist and repo doesn't match any member, run_workspace gets all members."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    members = [tmp_path / "alpha", tmp_path / "beta"]
    captured = {}

    monkeypatch.setattr(graph_cmd, "resolve", lambda *a, **k: _Cfg(members, ws))

    def _fake_run_workspace(mem, *, workspace, full, lock_timeout_ms=None):
        captured["members"] = list(mem)
        captured["full"] = full

    monkeypatch.setattr(graph_cmd.update, "run_workspace", _fake_run_workspace)
    # Pass a repo that matches no member — expect all members forwarded
    graph_cmd.run_build(tmp_path / "other", ws, full=True)

    assert captured["members"] == members
    assert captured["full"] is True


def test_run_build_scopes_to_single_member_when_repo_named(monkeypatch, tmp_path):
    """When repo names one member, only that member is passed to run_workspace."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    members = [tmp_path / "alpha", tmp_path / "beta"]
    captured = {}

    monkeypatch.setattr(graph_cmd, "resolve", lambda *a, **k: _Cfg(members, ws))

    def _fake_run_workspace(mem, *, workspace, full, lock_timeout_ms=None):
        captured["members"] = list(mem)

    monkeypatch.setattr(graph_cmd.update, "run_workspace", _fake_run_workspace)
    # Pass beta — should scope to only beta
    graph_cmd.run_build(members[1], ws, full=False)

    assert captured["members"] == [members[1]]


def test_run_build_scope_to_repo_false_builds_all_members(monkeypatch, tmp_path):
    """scope_to_repo=False (scan/whole-monorepo) builds ALL members even when repo names one."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    members = [tmp_path / "alpha", tmp_path / "beta"]
    captured = {}

    monkeypatch.setattr(graph_cmd, "resolve", lambda *a, **k: _Cfg(members, ws))

    def _fake_run_workspace(mem, *, workspace, full, lock_timeout_ms=None):
        captured["members"] = list(mem)

    monkeypatch.setattr(graph_cmd.update, "run_workspace", _fake_run_workspace)
    # repo == members[0]; with scope_to_repo=False, expect ALL members, not just members[0]
    graph_cmd.run_build(members[0], ws, full=True, scope_to_repo=False)

    assert captured["members"] == members


def test_run_build_uses_run_for_single_repo(monkeypatch, tmp_path):
    """When no members exist, run_build calls update.run (single-repo path)."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    repo = tmp_path / "repo"
    captured = {}

    monkeypatch.setattr(graph_cmd, "resolve", lambda *a, **k: _Cfg([], ws))

    def _fake_run(r, *, workspace, full, lock_timeout_ms=None):
        captured["run"] = True
        captured["repo"] = r

    def _fake_run_workspace(mem, *, workspace, full, lock_timeout_ms=None):
        captured["run_workspace"] = True

    monkeypatch.setattr(graph_cmd.update, "run", _fake_run)
    monkeypatch.setattr(graph_cmd.update, "run_workspace", _fake_run_workspace)
    graph_cmd.run_build(repo, ws, full=False)

    assert captured.get("run") is True
    assert "run_workspace" not in captured
