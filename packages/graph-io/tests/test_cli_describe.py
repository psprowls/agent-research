"""Parity tests for `cg describe-dependency` and `cg describe-plugin` (Phase 43-03 Task 6).

Also covers `cg describe-builtin` (Phase 49 BUILTIN-06).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from graph_io import exit_codes
from graph_io.cli import (
    q_describe_app,
    q_describe_builtin,
    q_describe_dependency,
    q_describe_package,
    q_describe_plugin,
)


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


# ---------------------------------------------------------------------------
# Phase 55 CLASS-02 / D-08 / SC#3: cg describe-package internal deps/dependents
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace_with_internal_dep(tmp_path: Path) -> Path:
    """Build a fixture workspace where package `beta` declares workspace package
    `alpha` as a dependency, run cg update --full, return the workspace path.
    """
    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # Internal target package.
    (repo_root / "alpha").mkdir()
    (repo_root / "alpha" / "pyproject.toml").write_text(
        '[project]\nname = "alpha"\nversion = "0.1.0"\n'
    )
    # Consumer declares alpha (separator mismatch exercises normalization too).
    (repo_root / "beta").mkdir()
    (repo_root / "beta" / "pyproject.toml").write_text(
        '[project]\nname = "beta"\nversion = "0.1.0"\n'
        'dependencies = ["alpha>=0.1"]\n'
    )

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo_root, check=True)

    update.run(repo_root, full=True)
    return resolve_workspace(repo_root, require_manifest=False).workspace


def _ns_package(workspace: Path, *, name: str, fmt: str = "human"):
    return argparse.Namespace(
        workspace=workspace,
        repo=None,
        fmt=fmt,
        mode="workspace",
        name=name,
    )


def test_cg_describe_package_internal_deps_json(workspace_with_internal_dep, capsys):
    """JSON output exposes internal_dependencies (outgoing) on the consumer."""
    args = _ns_package(workspace_with_internal_dep, name="beta", fmt="json")
    exit_code = q_describe_package.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    parsed = json.loads(captured.out)
    assert parsed["name"] == "beta"
    assert "internal_dependencies" in parsed
    assert "internal_dependents" in parsed
    assert parsed["internal_dependencies"] == ["alpha"]
    assert parsed["internal_dependents"] == []


def test_cg_describe_package_internal_dependents_json(
    workspace_with_internal_dep, capsys
):
    """JSON output exposes internal_dependents (incoming) on the target — SC#3."""
    args = _ns_package(workspace_with_internal_dep, name="alpha", fmt="json")
    exit_code = q_describe_package.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    parsed = json.loads(captured.out)
    assert parsed["name"] == "alpha"
    assert parsed["internal_dependents"] == ["beta"]
    assert parsed["internal_dependencies"] == []


def test_cg_describe_package_internal_deps_human(workspace_with_internal_dep, capsys):
    """Human output renders the internal dependency on the consumer."""
    args = _ns_package(workspace_with_internal_dep, name="beta")
    exit_code = q_describe_package.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    assert "internal deps:" in captured.out
    assert "alpha" in captured.out


# ---------------------------------------------------------------------------
# Phase 49 BUILTIN-06 / D-12 / D-13: cg describe-builtin tests
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace_with_builtins(tmp_path: Path) -> Path:
    """Build a fixture workspace with a Python pkg importing pathlib + os.

    Returns the resolved workspace path after `cg update --full`.
    """
    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\ndependencies = []\n'
    )
    (repo_root / "src" / "demo").mkdir(parents=True)
    (repo_root / "src" / "demo" / "__init__.py").write_text(
        "from pathlib import Path\nimport os\n"
    )

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo_root, check=True)

    update.run(repo_root, full=True)
    return resolve_workspace(repo_root, require_manifest=False).workspace


def _ns_builtin(workspace: Path, *, uri: str, fmt: str = "human"):
    return argparse.Namespace(
        workspace=workspace,
        repo=None,
        fmt=fmt,
        mode="workspace",
        uri=uri,
    )


def test_cg_describe_builtin_smoke(workspace_with_builtins, capsys):
    """Happy path: describe builtin:python/pathlib; verifies human output fields."""
    args = _ns_builtin(workspace_with_builtins, uri="builtin:python/pathlib")
    exit_code = q_describe_builtin.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    assert "language:" in captured.out
    assert "python" in captured.out
    assert "module_name:" in captured.out
    assert "pathlib" in captured.out
    assert "used_by:" in captured.out
    assert "demo" in captured.out


def test_cg_describe_builtin_not_found(workspace_with_builtins, capsys):
    """Not-found path: describe a builtin that does not exist."""
    args = _ns_builtin(workspace_with_builtins, uri="builtin:python/nonexistent")
    exit_code = q_describe_builtin.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.GENERIC
    assert "error: builtin not found:" in captured.err


def test_cg_describe_builtin_json(workspace_with_builtins, capsys):
    """JSON mode: verify output keys and correct types."""
    args = _ns_builtin(workspace_with_builtins, uri="builtin:python/pathlib", fmt="json")
    exit_code = q_describe_builtin.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    parsed = json.loads(captured.out)
    assert parsed["language"] == "python"
    assert parsed["module_name"] == "pathlib"
    assert parsed["uri"] == "builtin:python/pathlib"
    assert isinstance(parsed["used_by"], list)


def test_cg_describe_builtin_malformed_uri(workspace_with_builtins, capsys):
    """Malformed URI: not-a-builtin prefix → GENERIC exit; no slash → GENERIC exit."""
    # Not a builtin URI
    args = _ns_builtin(workspace_with_builtins, uri="not-a-builtin-uri")
    exit_code = q_describe_builtin.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.GENERIC
    assert "not a builtin URI" in captured.err

    # builtin: prefix present but no slash after language
    args2 = _ns_builtin(workspace_with_builtins, uri="builtin:incomplete")
    exit_code2 = q_describe_builtin.run(args2)
    captured2 = capsys.readouterr()
    assert exit_code2 == exit_codes.GENERIC
    assert "malformed builtin URI" in captured2.err


# ---------------------------------------------------------------------------
# Phase 50 APP-05 / D-10 / D-11: cg describe-app tests
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace_with_app(tmp_path: Path) -> Path:
    """Build a fixture workspace with a Python CLI app (pyproject has [project.scripts]).

    Returns the resolved workspace path after `cg update --full`.
    """
    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "my-cli"\nversion = "0.1.0"\n'
        '[project.scripts]\nmy-cli = "my_cli.cli:main"\n'
    )
    (repo_root / "src" / "my_cli").mkdir(parents=True)
    (repo_root / "src" / "my_cli" / "__init__.py").write_text("")
    (repo_root / "src" / "my_cli" / "cli.py").write_text(
        "def main():\n    return 0\n"
    )

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo_root, check=True)

    update.run(repo_root, full=True)
    return resolve_workspace(repo_root, require_manifest=False).workspace


def _ns_app(workspace: Path, *, name: str, fmt: str = "human"):
    return argparse.Namespace(
        workspace=workspace,
        repo=None,
        fmt=fmt,
        mode="workspace",
        name=name,
    )


def test_cg_describe_app_smoke(workspace_with_app, capsys):
    """Happy path: describe my-cli; verifies human output fields including app_kind."""
    args = _ns_app(workspace_with_app, name="my-cli")
    exit_code = q_describe_app.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    assert "app:" in captured.out
    assert "my-cli" in captured.out
    assert "language:" in captured.out
    assert "python" in captured.out
    assert "app_kind:" in captured.out
    assert "cli" in captured.out
    assert "signals:" in captured.out


def test_cg_describe_app_not_found(workspace_with_app, capsys):
    """Not-found: describe an app that does not exist → GENERIC with stderr message."""
    args = _ns_app(workspace_with_app, name="nonexistent-app")
    exit_code = q_describe_app.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.GENERIC
    assert "error: app not found:" in captured.err


def test_cg_describe_app_json(workspace_with_app, capsys):
    """JSON mode: verify all AppDescription fields present and typed correctly."""
    args = _ns_app(workspace_with_app, name="my-cli", fmt="json")
    exit_code = q_describe_app.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    parsed = json.loads(captured.out)
    assert parsed["name"] == "my-cli"
    assert parsed["language"] == "python"
    assert parsed["app_kind"] == "cli"
    assert isinstance(parsed["app_signals"], list)
    assert "cli" in parsed["app_signals"]
    # Ensure full AppDescription field set is present.
    expected_keys = {
        "name", "language", "version", "app_kind", "app_signals",
        "files", "counts", "domains", "entry_points", "test_suites",
    }
    assert expected_keys.issubset(set(parsed.keys()))
