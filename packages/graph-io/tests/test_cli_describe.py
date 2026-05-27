"""Parity tests for `cg describe-dependency` and `cg describe-plugin` (Phase 43-03 Task 6)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

import pytest

from graph_io import exit_codes
from graph_io.cli import q_describe_dependency, q_describe_plugin


@pytest.fixture
def workspace_with_deps_and_plugin(tmp_path: Path) -> Path:
    """Build a fixture workspace with a dep + a plugin, run cg update --full,
    return the resolved workspace path.
    """
    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # Single python package with one dep.
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
        'dependencies = ["boto3>=1.38"]\n'
    )
    (repo_root / "src" / "demo").mkdir(parents=True)
    (repo_root / "src" / "demo" / "__init__.py").write_text("")
    # v2 plugin manifest at <repo>/graph-wiki/.graph-wiki.yaml (default workspace location)
    workspace_dir = repo_root / "graph-wiki"
    workspace_dir.mkdir()
    (workspace_dir / ".graph-wiki.yaml").write_text(
        'version: 2\n'
        'initialized_at: "2026-05-27"\n'
        'plugins:\n'
        '  - name: graph-wiki\n'
        '    installed_version: "0.1.0"\n'
        '    applied_version: "0.1.0"\n'
    )

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed"], cwd=repo_root, check=True
    )

    update.run(repo_root, full=True)
    return resolve_workspace(repo_root, require_manifest=False).workspace


def _ns(workspace: Path, *, name: str, ecosystem: str = "pypi", fmt: str = "human"):
    return argparse.Namespace(
        workspace=workspace,
        repo=None,
        fmt=fmt,
        mode="workspace",
        name=name,
        ecosystem=ecosystem,
    )


def _ns_plugin(workspace: Path, *, name: str, fmt: str = "human"):
    return argparse.Namespace(
        workspace=workspace,
        repo=None,
        fmt=fmt,
        mode="workspace",
        name=name,
    )


def test_cg_describe_dependency_smoke(workspace_with_deps_and_plugin, capsys):
    args = _ns(workspace_with_deps_and_plugin, name="boto3")
    exit_code = q_describe_dependency.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    assert "boto3" in captured.out
    assert "versions_in_use" in captured.out


def test_cg_describe_dependency_not_found(workspace_with_deps_and_plugin, capsys):
    args = _ns(workspace_with_deps_and_plugin, name="nonexistent-dep")
    exit_code = q_describe_dependency.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.GENERIC
    assert "error: dependency not found:" in captured.err


def test_cg_describe_dependency_json(workspace_with_deps_and_plugin, capsys):
    args = _ns(workspace_with_deps_and_plugin, name="boto3", fmt="json")
    exit_code = q_describe_dependency.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    import json
    parsed = json.loads(captured.out)
    assert parsed["name"] == "boto3"
    assert parsed["ecosystem"] == "pypi"
    assert parsed["uri"] == "dependency:pypi/boto3"


def test_cg_describe_plugin_smoke(workspace_with_deps_and_plugin, capsys):
    args = _ns_plugin(workspace_with_deps_and_plugin, name="graph-wiki")
    exit_code = q_describe_plugin.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    assert "graph-wiki" in captured.out
    assert "claude-code" in captured.out


def test_cg_describe_plugin_not_found(workspace_with_deps_and_plugin, capsys):
    args = _ns_plugin(workspace_with_deps_and_plugin, name="nonexistent-plugin")
    exit_code = q_describe_plugin.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.GENERIC
    assert "error: plugin not found:" in captured.err
