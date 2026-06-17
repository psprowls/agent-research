"""Parity tests for `gw graph describe-dependency` and `gw graph describe-agent-plugin` (Phase 43-03 Task 6).

Also covers `gw graph describe-builtin` (Phase 49 BUILTIN-06).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from graph_io import exit_codes
from graph_wiki_cli.graph_cli import (
    q_describe_agent_plugin,
    q_describe_app,
    q_describe_builtin,
    q_describe_dependency,
    q_describe_package,
)
from graph_wiki_cli.graph_cli.main import graph_app
from typer.testing import CliRunner


@pytest.fixture
def workspace_with_deps_and_plugin(tmp_path: Path) -> Path:
    """Build a fixture workspace with a dep + a plugin, run gw graph update --full,
    return the resolved workspace path.
    """
    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # Single python package with one dep.
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.1"\ndependencies = ["boto3>=1.38"]\n'
    )
    (repo_root / "src" / "demo").mkdir(parents=True)
    (repo_root / "src" / "demo" / "__init__.py").write_text("")
    # v2 plugin manifest at <repo>/graph-wiki/.graph-wiki.yaml (default workspace location)
    workspace_dir = repo_root / "graph-wiki"
    workspace_dir.mkdir()
    (workspace_dir / ".graph-wiki.yaml").write_text(
        "version: 2\n"
        'initialized_at: "2026-05-27"\n'
        "plugins:\n"
        "  - name: graph-wiki\n"
        '    installed_version: "0.1.1"\n'
        '    applied_version: "0.1.1"\n'
    )

    # agent_plugin entity: build walks repo_root rglob(".claude-plugin/plugin.json")
    import json as _json

    pdir = repo_root / "plugins" / "graph-wiki" / ".claude-plugin"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "plugin.json").write_text(_json.dumps({"name": "graph-wiki", "version": "0.1.1"}))

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo_root, check=True)

    update.run(repo_root, full=True)
    return resolve_workspace(repo_root, require_manifest=False).workspace


def _ns(workspace: Path, *, name: str, ecosystem: str = "pypi", fmt: str = "human"):
    return SimpleNamespace(
        workspace=workspace,
        repo=None,
        fmt=fmt,
        mode="workspace",
        name=name,
        ecosystem=ecosystem,
    )


def _ns_plugin(workspace: Path, *, name: str, fmt: str = "human"):
    return SimpleNamespace(
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
    assert "versions_in_use:" in captured.out


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
    assert parsed["attributes"]["ecosystem"] == "pypi"
    assert parsed["uri"] == "dependency:pypi/boto3"


def test_cg_describe_agent_plugin_smoke(workspace_with_deps_and_plugin, capsys):
    args = _ns_plugin(workspace_with_deps_and_plugin, name="graph-wiki")
    exit_code = q_describe_agent_plugin.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    assert "graph-wiki" in captured.out
    assert "claude-code" in captured.out
    assert "version:" in captured.out
    assert "0.1.1" in captured.out


def test_cg_describe_agent_plugin_json(workspace_with_deps_and_plugin, capsys):
    args = _ns_plugin(workspace_with_deps_and_plugin, name="graph-wiki", fmt="json")
    exit_code = q_describe_agent_plugin.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    parsed = json.loads(captured.out)
    assert parsed["name"] == "graph-wiki"
    assert parsed["attributes"]["ecosystem"] == "claude-code"
    assert parsed["attributes"]["version"] == "0.1.1"
    for key in ("commands", "agents", "skills", "scripts", "hooks", "mcp_servers"):
        assert isinstance(parsed["attributes"][key], int)


def test_cg_describe_agent_plugin_not_found(workspace_with_deps_and_plugin, capsys):
    args = _ns_plugin(workspace_with_deps_and_plugin, name="nonexistent-plugin")
    exit_code = q_describe_agent_plugin.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.GENERIC
    assert "error: agent_plugin not found:" in captured.err


# ---------------------------------------------------------------------------
# Phase 55 CLASS-02 / D-08 / SC#3: gw graph describe-package internal deps/dependents
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace_with_internal_dep(tmp_path: Path) -> Path:
    """Build a fixture workspace where package `beta` declares workspace package
    `alpha` as a dependency, run gw graph update --full, return the workspace path.
    """
    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # Internal target package.
    (repo_root / "alpha").mkdir()
    (repo_root / "alpha" / "pyproject.toml").write_text('[project]\nname = "alpha"\nversion = "0.1.1"\n')
    # Consumer declares alpha (separator mismatch exercises normalization too).
    (repo_root / "beta").mkdir()
    (repo_root / "beta" / "pyproject.toml").write_text(
        '[project]\nname = "beta"\nversion = "0.1.1"\ndependencies = ["alpha>=0.1"]\n'
    )

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo_root, check=True)

    update.run(repo_root, full=True)
    return resolve_workspace(repo_root, require_manifest=False).workspace


def _ns_package(workspace: Path, *, name: str, fmt: str = "human"):
    return SimpleNamespace(
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
    assert parsed["relationships"].get("internal_dependencies", []) == ["alpha"]
    assert parsed["relationships"].get("internal_dependents", []) == []


def test_cg_describe_package_internal_dependents_json(workspace_with_internal_dep, capsys):
    """JSON output exposes internal_dependents (incoming) on the target — SC#3."""
    args = _ns_package(workspace_with_internal_dep, name="alpha", fmt="json")
    exit_code = q_describe_package.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    parsed = json.loads(captured.out)
    assert parsed["name"] == "alpha"
    assert parsed["relationships"].get("internal_dependents", []) == ["beta"]
    assert parsed["relationships"].get("internal_dependencies", []) == []


def test_cg_describe_package_internal_deps_human(workspace_with_internal_dep, capsys):
    """Human output renders the internal dependency on the consumer."""
    args = _ns_package(workspace_with_internal_dep, name="beta")
    exit_code = q_describe_package.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    assert "internal deps:" in captured.out
    assert "alpha" in captured.out


# ---------------------------------------------------------------------------
# Phase 49 BUILTIN-06 / D-12 / D-13: gw graph describe-builtin tests
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace_with_builtins(tmp_path: Path) -> Path:
    """Build a fixture workspace with a Python pkg importing pathlib + os.

    Returns the resolved workspace path after `gw graph update --full`.
    """
    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.1.1"\ndependencies = []\n')
    (repo_root / "src" / "demo").mkdir(parents=True)
    (repo_root / "src" / "demo" / "__init__.py").write_text("from pathlib import Path\nimport os\n")

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo_root, check=True)

    update.run(repo_root, full=True)
    return resolve_workspace(repo_root, require_manifest=False).workspace


def _ns_builtin(workspace: Path, *, uri: str, fmt: str = "human"):
    return SimpleNamespace(
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
    assert parsed["attributes"]["language"] == "python"
    assert parsed["attributes"]["module_name"] == "pathlib"
    assert parsed["uri"] == "builtin:python/pathlib"
    assert isinstance(parsed["relationships"].get("used_by", []), list)


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
# Phase 50 APP-05 / D-10 / D-11: gw graph describe-app tests
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace_with_app(tmp_path: Path) -> Path:
    """Build a fixture workspace with a Python CLI app (pyproject has [project.scripts]).

    Returns the resolved workspace path after `gw graph update --full`.
    """
    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "my-cli"\nversion = "0.1.1"\n[project.scripts]\nmy-cli = "my_cli.cli:main"\n'
    )
    (repo_root / "src" / "my_cli").mkdir(parents=True)
    (repo_root / "src" / "my_cli" / "__init__.py").write_text("")
    (repo_root / "src" / "my_cli" / "cli.py").write_text("def main():\n    return 0\n")

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo_root, check=True)

    update.run(repo_root, full=True)
    return resolve_workspace(repo_root, require_manifest=False).workspace


def _ns_app(workspace: Path, *, name: str, fmt: str = "human"):
    return SimpleNamespace(
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
    assert "app my-cli" in captured.out
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
    assert parsed["uri"] == "app:my-cli"
    assert parsed["attributes"]["language"] == "python"
    assert parsed["attributes"]["app_kind"] == "cli"
    assert isinstance(parsed["attributes"]["signals"], list)
    assert "cli" in parsed["attributes"]["signals"]
    # Spine shape: core keys present (children/children_depth optional when tree non-empty).
    assert {"kind", "name", "uri", "attributes", "relationships", "nav"} <= set(parsed)


# ---------------------------------------------------------------------------
# Task 3: --depth + children section wiring (e2e)
# ---------------------------------------------------------------------------


def _ns_depth(workspace, *, name, fmt="human", depth=None):
    """SimpleNamespace for per-kind describe modules that read depth."""
    return SimpleNamespace(
        workspace=workspace,
        repo=None,
        fmt=fmt,
        mode="workspace",
        name=name,
        depth=depth,
    )


def _ns_path_depth(workspace, *, path, fmt="human", depth=None):
    """SimpleNamespace for q_describe_path.run()."""
    return SimpleNamespace(
        workspace=workspace,
        repo=None,
        fmt=fmt,
        mode="workspace",
        path=path,
        depth=depth,
    )


def test_describe_package_default_depth_1(workspace_with_internal_dep, capsys):
    """Package describe: default depth is 1 → 'children (depth 1)' in output."""
    args = _ns_depth(workspace_with_internal_dep, name="alpha")
    exit_code = q_describe_package.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    assert "children (depth 1)" in captured.out


def test_describe_file_default_depth_2(workspace_with_app, capsys):
    """File describe: default depth is 2 → 'children (depth 2)' in output when file has symbols."""
    from graph_wiki_cli.graph_cli import q_describe_path

    # src/my_cli/cli.py contains function:main
    args = _ns_path_depth(workspace_with_app, path="src/my_cli/cli.py")
    exit_code = q_describe_path.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    assert "children (depth 2)" in captured.out


def test_describe_explicit_depth(workspace_with_internal_dep, capsys):
    """Passing --depth 2 on a package deepens the tree and adds a go-deeper nav hint."""
    args = _ns_depth(workspace_with_internal_dep, name="alpha", depth=2)
    exit_code = q_describe_package.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    assert "children (depth 2)" in captured.out
    assert "→ gw graph describe" in captured.out
    assert "--depth 3" in captured.out


def test_describe_depth_zero_rejected(workspace_with_internal_dep):
    """depth=0 must be rejected by the CLI with BadParameter before reaching the module."""
    runner = CliRunner()
    # --depth 0 is rejected by describe_cmd's validation in the command body before any graph
    # I/O, so it fails regardless of workspace state.
    result = runner.invoke(
        graph_app,
        ["--repo", str(workspace_with_internal_dep), "--mode", "test", "describe", "alpha", "--depth", "0"],
    )
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
    assert "depth must be >= 1" in combined


def test_describe_leaf_kind_no_children_section(workspace_with_deps_and_plugin, capsys):
    """Dependency (leaf kind) describe must NOT emit a 'children (' section."""
    args = _ns(workspace_with_deps_and_plugin, name="boto3", ecosystem="pypi")
    exit_code = q_describe_dependency.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    assert "children (" not in captured.out


def test_describe_package_go_deeper_nav_hint(workspace_with_internal_dep, capsys):
    """Children present → go-deeper nav hint appears in human output."""
    args = _ns_depth(workspace_with_internal_dep, name="alpha")
    exit_code = q_describe_package.run(args)
    captured = capsys.readouterr()
    assert exit_code == exit_codes.SUCCESS, captured.err
    assert "→ gw graph describe alpha --depth 2" in captured.out
