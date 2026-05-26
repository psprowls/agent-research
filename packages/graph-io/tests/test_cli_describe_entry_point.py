"""Parity tests for cg describe-entry-point CLI module (Phase 38-01 Task 2)."""

from __future__ import annotations

import argparse

import pytest

from graph_io import exit_codes
from graph_io.cli import q_describe_entry_point


def _build_namespace(workspace, name, fmt="human"):
    # seeded_db yields a sqlite3.Connection directly; we need to derive the
    # workspace path. Call sites pass the workspace path determined by walking
    # the same fixture path the conftest uses.
    return argparse.Namespace(
        workspace=workspace,
        repo=None,  # cg modules read DB via workspace, not repo
        fmt=fmt,
        mode="workspace",
        name=name,
        _module=q_describe_entry_point,
        _parser=None,
    )


@pytest.fixture
def workspace_path(tmp_path_factory):
    """Re-create the seeded_db workspace path so we can call CLI modules.

    The session-scoped `seeded_db` fixture yields a read-only sqlite3 connection
    but not the workspace path; rebuild it here function-scoped so each test gets
    a clean workspace whose DB the CLI module can open via store.read_only_connect.
    """
    import shutil
    import subprocess
    from pathlib import Path

    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace

    fixture_src = Path(__file__).parent / "fixtures" / "sample_monorepo"
    repo_root = tmp_path_factory.mktemp("cli_describe_ep") / "repo"
    shutil.copytree(fixture_src, repo_root)

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


def test_describe_entry_point_with_known_name(workspace_path, capsys):
    args = _build_namespace(workspace_path, name="mypkg-run")
    exit_code = q_describe_entry_point.run(args)
    assert exit_code == exit_codes.SUCCESS, capsys.readouterr()
    captured = capsys.readouterr()
    assert "mypkg-run" in captured.out


def test_describe_entry_point_unknown_name_returns_generic(workspace_path, capsys):
    args = _build_namespace(
        workspace_path, name="definitely-not-a-real-entry-point-9999"
    )
    exit_code = q_describe_entry_point.run(args)
    assert exit_code == exit_codes.GENERIC
    captured = capsys.readouterr()
    assert "error: entry point not found:" in captured.err
