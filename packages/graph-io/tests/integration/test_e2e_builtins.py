"""End-to-end Builtin emission + CLI inspection (Phase 49)."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

from graph_io import exit_codes, update
from graph_io.cli import q_describe_builtin, q_describe_dependency, q_list_builtins
from workspace_io.config import resolve as resolve_workspace


@pytest.fixture
def mixed_workspace(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    # Python pkg importing pathlib + os + boto3
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
        'dependencies = ["boto3>=1.38"]\n'
    )
    (repo / "src" / "demo").mkdir(parents=True)
    (repo / "src" / "demo" / "__init__.py").write_text(
        "from pathlib import Path\nimport os\nimport boto3\n"
    )
    # JS pkg importing fs + node:path + express
    (repo / "js-app").mkdir()
    (repo / "js-app" / "package.json").write_text(
        '{"name": "js-demo", "version": "0.1.0", "dependencies": {"express": "^4.0.0"}}'
    )
    (repo / "js-app" / "index.js").write_text(
        "const fs = require('fs');\nconst path = require('node:path');\n"
        "const express = require('express');\n"
    )
    # git init + commit
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    update.run(repo, full=True)
    return resolve_workspace(repo, require_manifest=False).workspace


def _ns_list(ws, fmt="human"):
    return argparse.Namespace(workspace=ws, repo=None, fmt=fmt, mode="workspace")


def _ns_describe_builtin(ws, uri, fmt="human"):
    return argparse.Namespace(workspace=ws, repo=None, fmt=fmt, mode="workspace", uri=uri)


def _ns_describe_dep(ws, name, ecosystem="pypi", fmt="human"):
    return argparse.Namespace(
        workspace=ws, repo=None, fmt=fmt, mode="workspace",
        name=name, ecosystem=ecosystem,
    )


def test_e2e_python_and_node_builtins_emitted(mixed_workspace, capsys):
    """list-builtins includes pathlib and os (always); fs and path if Node is available."""
    rc = q_list_builtins.run(_ns_list(mixed_workspace))
    assert rc == exit_codes.SUCCESS, capsys.readouterr().err
    out = capsys.readouterr().out.splitlines()
    assert "pathlib" in out
    assert "os" in out
    # If node was available, fs and path also appear
    if "fs" in out:
        assert "path" in out  # node:path → 'path'


def test_e2e_describe_python_builtin_shows_used_by(mixed_workspace, capsys):
    """describe-builtin builtin:python/pathlib shows language, module_name, and demo in used_by."""
    rc = q_describe_builtin.run(_ns_describe_builtin(mixed_workspace, "builtin:python/pathlib"))
    assert rc == exit_codes.SUCCESS, capsys.readouterr().err
    out = capsys.readouterr().out
    assert "language:" in out and "python" in out
    assert "module_name:" in out and "pathlib" in out
    assert "demo" in out  # used_by includes the demo pkg


def test_e2e_npm_dependency_classification_unchanged(mixed_workspace, capsys):
    """boto3 is still classified as a dependency, not a builtin."""
    rc = q_describe_dependency.run(_ns_describe_dep(mixed_workspace, name="boto3"))
    assert rc == exit_codes.SUCCESS, capsys.readouterr().err
    out = capsys.readouterr().out
    assert "boto3" in out


def test_e2e_express_remains_dependency_not_builtin(mixed_workspace, capsys):
    """express is NOT classified as javascript builtin — builtin not found returns GENERIC."""
    rc = q_describe_builtin.run(_ns_describe_builtin(mixed_workspace, "builtin:javascript/express"))
    assert rc == exit_codes.GENERIC
    err = capsys.readouterr().err
    assert "not found" in err


def test_e2e_idempotency(mixed_workspace, capsys):
    """Second cg update (incremental) does not add extra Builtin nodes."""
    # mixed_workspace = tmp_path/repo/graph-wiki; parent = tmp_path/repo (repo root)
    repo = mixed_workspace.parent
    update.run(repo)  # incremental
    rc = q_list_builtins.run(_ns_list(mixed_workspace, fmt="json"))
    assert rc == exit_codes.SUCCESS
    data = json.loads(capsys.readouterr().out)
    first_count = len(data)

    update.run(repo)  # second incremental run
    rc = q_list_builtins.run(_ns_list(mixed_workspace, fmt="json"))
    assert rc == exit_codes.SUCCESS
    data2 = json.loads(capsys.readouterr().out)
    assert len(data2) == first_count
