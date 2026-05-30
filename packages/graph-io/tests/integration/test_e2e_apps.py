"""End-to-end integration tests for Phase 50 App reclassification.

Each test exercises the full pipeline (manifest → classify → emit → SQL →
query → CLI) against a real-shaped repo and asserts a ROADMAP success
criterion. The five tests below cover SC #1..#5 plus the APP-06 round-trip
flip behaviour.
"""

# integration-gate-allow — subprocess + local, no LLM

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

from graph_io import exit_codes, update
from graph_io.cli import q_describe_app, q_list_apps, q_list_packages
from workspace_io.config import resolve as resolve_workspace


def _ns_list(workspace: Path, fmt: str = "human") -> argparse.Namespace:
    return argparse.Namespace(
        workspace=workspace, repo=None, fmt=fmt, mode="workspace"
    )


def _ns_describe(workspace: Path, name: str, fmt: str = "human") -> argparse.Namespace:
    return argparse.Namespace(
        workspace=workspace, repo=None, fmt=fmt, mode="workspace", name=name
    )


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)


def _git_commit_all(repo: Path, msg: str) -> None:
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo, check=True)


def test_e2e_python_cli_app_reclassified(tmp_path: Path, capsys) -> None:
    """ROADMAP SC #1: pyproject with [project.scripts] → kind='app', app_kind='cli'."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "my-cli"\nversion = "0.1.0"\n'
        '[project.scripts]\nmy-cli = "my_cli.cli:main"\n'
    )
    (repo / "src" / "my_cli").mkdir(parents=True)
    (repo / "src" / "my_cli" / "__init__.py").write_text("")
    (repo / "src" / "my_cli" / "cli.py").write_text("def main():\n    return 0\n")
    _git_init(repo)
    _git_commit_all(repo, "seed")

    update.run(repo, full=True)
    workspace = resolve_workspace(repo, require_manifest=False).workspace

    # list-apps shows my-cli
    rc = q_list_apps.run(_ns_list(workspace))
    assert rc == exit_codes.SUCCESS, capsys.readouterr().err
    out = capsys.readouterr().out.splitlines()
    assert "my-cli" in out

    # describe-app shows app_kind=cli
    rc2 = q_describe_app.run(_ns_describe(workspace, name="my-cli"))
    assert rc2 == exit_codes.SUCCESS
    out2 = capsys.readouterr().out
    assert "app_kind:" in out2
    assert "cli" in out2


def test_e2e_pure_library_stays_package(tmp_path: Path, capsys) -> None:
    """ROADMAP SC #5: pyproject WITHOUT scripts → stays kind='package'; not in list-apps."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "purelib"\nversion = "0.1.0"\n'
    )
    (repo / "src" / "purelib").mkdir(parents=True)
    (repo / "src" / "purelib" / "__init__.py").write_text("")
    _git_init(repo)
    _git_commit_all(repo, "seed")

    update.run(repo, full=True)
    workspace = resolve_workspace(repo, require_manifest=False).workspace

    # list-apps does NOT include purelib (empty graph or other apps only).
    rc = q_list_apps.run(_ns_list(workspace))
    assert rc == exit_codes.SUCCESS
    captured = capsys.readouterr()
    # human mode: empty result emits "No apps in graph." on stderr; no stdout.
    if captured.out.strip():
        assert "purelib" not in captured.out.splitlines()
    else:
        assert "No apps in graph." in captured.err

    # list-packages DOES include purelib.
    rc2 = q_list_packages.run(_ns_list(workspace))
    assert rc2 == exit_codes.SUCCESS, capsys.readouterr().err
    out2 = capsys.readouterr().out.splitlines()
    assert "purelib" in out2


def test_e2e_js_multi_signal_precedence(tmp_path: Path, capsys) -> None:
    """ROADMAP SC #2: JS package with bin + next deps → kind='app', app_kind='nextjs',
    app_signals contains both 'cli' and 'nextjs' sorted."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text(
        json.dumps(
            {
                "name": "site",
                "version": "1.0.0",
                "bin": "cli.js",
                "dependencies": {"next": "14", "react": "18"},
            }
        )
    )
    _git_init(repo)
    _git_commit_all(repo, "seed")

    update.run(repo, full=True)
    workspace = resolve_workspace(repo, require_manifest=False).workspace

    rc = q_describe_app.run(_ns_describe(workspace, name="site", fmt="json"))
    assert rc == exit_codes.SUCCESS, capsys.readouterr().err
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["app_kind"] == "nextjs"
    assert parsed["app_signals"] == sorted(["cli", "nextjs"])


def test_e2e_kind_flip_repeatable(tmp_path: Path, capsys) -> None:
    """ROADMAP SC #4 / APP-06: cg update on the same repo with manifest mutations flips
    kind in place. Verifies the D-06 in-place UPDATE preserves row id end-to-end."""
    import sqlite3
    from workspace_io.paths import graph_dir

    repo = tmp_path / "repo"
    repo.mkdir()
    pyp = repo / "pyproject.toml"
    pyp.write_text('[project]\nname = "myapp"\nversion = "0.1.0"\n')
    _git_init(repo)
    _git_commit_all(repo, "seed")

    # First cg update: no scripts → kind='package'.
    update.run(repo, full=True)
    workspace = resolve_workspace(repo, require_manifest=False).workspace
    db = graph_dir(workspace) / "code.db"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT id, kind, uri FROM nodes WHERE name='myapp'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    pkg_id, kind1, uri1 = row
    assert kind1 == "package"
    assert uri1.startswith("pkg:")

    # Add [project.scripts] → second update should flip to kind='app'.
    pyp.write_text(
        '[project]\nname = "myapp"\nversion = "0.1.0"\n'
        '[project.scripts]\nmyapp = "myapp.cli:main"\n'
    )
    update.run(repo, full=True)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT id, kind, uri FROM nodes WHERE name='myapp'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    app_id, kind2, uri2 = row
    assert app_id == pkg_id, "D-06 in-place UPDATE must preserve row id"
    assert kind2 == "app"
    assert uri2.startswith("app:")

    # Remove [project.scripts] → third update should revert to kind='package'.
    pyp.write_text('[project]\nname = "myapp"\nversion = "0.1.0"\n')
    update.run(repo, full=True)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT id, kind, uri FROM nodes WHERE name='myapp'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    pkg_id_after, kind3, uri3 = row
    assert pkg_id_after == pkg_id, "row id must survive the revert"
    assert kind3 == "package"
    assert uri3.startswith("pkg:")


def test_e2e_list_apps_and_describe_app_shape(tmp_path: Path, capsys) -> None:
    """ROADMAP SC #3: cg list-apps --fmt json + cg describe-app --fmt json carry the
    expected shape (NodeRecord list with kind='app' for list-apps; full AppDescription
    field set for describe-app)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "graph-wiki-agent"\nversion = "0.1.0"\n'
        '[project.scripts]\ngraph-wiki = "graph_wiki_agent.cli:main"\n'
    )
    (repo / "src" / "graph_wiki_agent").mkdir(parents=True)
    (repo / "src" / "graph_wiki_agent" / "__init__.py").write_text("")
    (repo / "src" / "graph_wiki_agent" / "cli.py").write_text(
        "def main():\n    return 0\n"
    )
    _git_init(repo)
    _git_commit_all(repo, "seed")

    update.run(repo, full=True)
    workspace = resolve_workspace(repo, require_manifest=False).workspace

    # list-apps --fmt json
    rc = q_list_apps.run(_ns_list(workspace, fmt="json"))
    assert rc == exit_codes.SUCCESS
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert all(r["kind"] == "app" for r in data)
    names = {r["name"] for r in data}
    assert "graph-wiki-agent" in names

    # describe-app --fmt json: assert full AppDescription field set is present.
    rc2 = q_describe_app.run(
        _ns_describe(workspace, name="graph-wiki-agent", fmt="json")
    )
    assert rc2 == exit_codes.SUCCESS
    parsed = json.loads(capsys.readouterr().out)
    expected_keys = {
        "name", "language", "version", "app_kind", "app_signals",
        "files", "counts", "domains", "entry_points", "test_suites",
    }
    assert expected_keys == set(parsed.keys()), (
        f"AppDescription field set mismatch: expected={expected_keys}, "
        f"got={set(parsed.keys())}"
    )
    assert parsed["name"] == "graph-wiki-agent"
    assert parsed["app_kind"] == "cli"
    assert "cli" in parsed["app_signals"]


def test_e2e_electron_app_from_dev_deps(tmp_path: Path, capsys) -> None:
    """GQP-01: electron+vite under devDependencies + index.html → app_kind='electron'."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text(
        json.dumps({
            "name": "my-electron-app",
            "version": "1.0.0",
            "devDependencies": {"electron": "^30.0.0", "vite": "^5.0.0"},
        })
    )
    (repo / "index.html").write_text("<!doctype html><html></html>")
    _git_init(repo)
    _git_commit_all(repo, "seed")

    update.run(repo, full=True)
    workspace = resolve_workspace(repo, require_manifest=False).workspace

    rc = q_describe_app.run(_ns_describe(workspace, name="my-electron-app", fmt="json"))
    assert rc == exit_codes.SUCCESS, capsys.readouterr().err
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["app_kind"] == "electron"
