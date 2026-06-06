"""Tests for wiki_io.scan_monorepo.compute_state_gate — config-driven gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

from wiki_io.scan_monorepo import compute_state_gate


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo_on_branch(repo: Path, branch: str) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "f.txt").write_text("hi\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init")
    _git(repo, "branch", "-M", branch)


def _write_manifest(workspace: Path, body: str) -> None:
    (workspace / ".graph-wiki.yaml").write_text(
        "version: 2\ninitialized_at: 2026-06-06\nplugins: []\n" + body,
        encoding="utf-8",
    )


def test_disabled_gate_allows_regardless_of_branch(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "feature-x")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _write_manifest(workspace, "state_gate:\n  enabled: false\n")
    gate = compute_state_gate(repo, workspace=workspace)
    assert gate["allowed"] is True
    assert gate["reason"] == "state gate disabled in .graph-wiki.yaml"
    assert gate["head_commit"] is not None


def test_disabled_gate_allows_when_dirty(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "main")
    (repo / "dirty.txt").write_text("x\n", encoding="utf-8")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _write_manifest(workspace, "state_gate:\n  enabled: false\n")
    assert compute_state_gate(repo, workspace=workspace)["allowed"] is True


def test_enabled_gate_honors_configured_branches(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "develop")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _write_manifest(workspace, "state_gate:\n  enabled: true\n  branches:\n    - develop\n")
    assert compute_state_gate(repo, workspace=workspace)["allowed"] is True


def test_enabled_gate_blocks_branch_not_in_list(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "main")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _write_manifest(workspace, "state_gate:\n  enabled: true\n  branches:\n    - develop\n")
    gate = compute_state_gate(repo, workspace=workspace)
    assert gate["allowed"] is False
    assert "not in" in gate["reason"]


def test_workspace_none_defaults_to_main(tmp_path):
    """No workspace → (enabled, ['main']) default (backward compat)."""
    repo_main = tmp_path / "repo_main"
    _init_repo_on_branch(repo_main, "main")
    assert compute_state_gate(repo_main)["allowed"] is True

    repo_dev = tmp_path / "repo_dev"
    _init_repo_on_branch(repo_dev, "develop")
    gate = compute_state_gate(repo_dev)
    assert gate["allowed"] is False
    assert "not in" in gate["reason"]
