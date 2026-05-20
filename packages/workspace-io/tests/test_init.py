"""Tests for workspace_io.init — idempotent workspace bootstrapping."""
import importlib
import subprocess
from pathlib import Path

from workspace_io.init import init

_init_mod = importlib.import_module("workspace_io.init")
from workspace_io.manifest import read
from workspace_io.paths import manifest_path, work_dir


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def test_default_creates_graph_wiki_under_repo(tmp_path):
    init(tmp_path, plugin="graph-wiki-agent", version="1.0.0")
    assert (tmp_path / "graph-wiki").is_dir()


def test_default_creates_manifest(tmp_path):
    init(tmp_path, plugin="graph-wiki-agent", version="1.0.0")
    assert manifest_path(tmp_path / "graph-wiki").exists()


def test_manifest_contains_plugin(tmp_path):
    init(tmp_path, plugin="graph-wiki-agent", version="1.0.0")
    plugins = read(manifest_path(tmp_path / "graph-wiki"))["plugins"]
    assert any(p["name"] == "graph-wiki-agent" for p in plugins)


def test_two_plugins_both_recorded(tmp_path):
    init(tmp_path, plugin="graph-wiki-agent", version="1.0.0")
    init(tmp_path, plugin="code-wiki-second", version="1.0.0")
    names = [p["name"] for p in read(manifest_path(tmp_path / "graph-wiki"))["plugins"]]
    assert "graph-wiki-agent" in names
    assert "code-wiki-second" in names


def test_idempotent_same_plugin(tmp_path):
    init(tmp_path, plugin="graph-wiki-agent", version="1.0.0")
    init(tmp_path, plugin="graph-wiki-agent", version="1.0.0")
    names = [p["name"] for p in read(manifest_path(tmp_path / "graph-wiki"))["plugins"]]
    assert names.count("graph-wiki-agent") == 1


def test_external_workspace_creates_dir(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)
    workspace = tmp_path / "external"
    init(repo, plugin="graph-wiki-agent", version="1.0.0", workspace=workspace)
    assert workspace.is_dir()
    assert manifest_path(workspace).exists()


def test_external_workspace_outside_git_runs_git_init(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)
    workspace = tmp_path / "external"
    # Patch _is_inside_git_repo so the test doesn't depend on whether TMPDIR
    # happens to be inside a git repo on the host machine.
    monkeypatch.setattr(_init_mod, "_is_inside_git_repo", lambda _: False)
    init(repo, plugin="graph-wiki-agent", version="1.0.0", workspace=workspace)
    assert (workspace / ".git").exists()


def test_external_workspace_inside_existing_git_skips_git_init(tmp_path):
    outer = tmp_path / "outer"
    outer.mkdir()
    _git_init(outer)
    repo = outer / "repo"
    repo.mkdir()
    _git_init(repo)
    workspace = outer / "shared-graph-wiki"
    init(repo, plugin="graph-wiki-agent", version="1.0.0", workspace=workspace)
    # workspace is inside outer's git repo, so no nested .git should be created
    assert not (workspace / ".git").exists()


def test_appends_local_yaml_to_gitignore(tmp_path):
    repo = tmp_path
    init(repo, plugin="graph-wiki-agent", version="1.0.0")
    text = (repo / ".gitignore").read_text()
    assert ".graph-wiki.local.yaml" in text


def test_gitignore_append_is_idempotent(tmp_path):
    repo = tmp_path
    (repo / ".gitignore").write_text(".graph-wiki.local.yaml\n")
    init(repo, plugin="graph-wiki-agent", version="1.0.0")
    text = (repo / ".gitignore").read_text()
    assert text.count(".graph-wiki.local.yaml") == 1


def test_gitignore_created_if_absent(tmp_path):
    repo = tmp_path
    init(repo, plugin="graph-wiki-agent", version="1.0.0")
    assert (repo / ".gitignore").exists()


def test_init_writes_workspace_claude_md(tmp_path):
    init(tmp_path, plugin="graph-wiki-agent", version="1.0.0")
    workspace_claude = tmp_path / "graph-wiki" / "CLAUDE.md"
    assert workspace_claude.exists()
    text = workspace_claude.read_text()
    assert "graph-wiki-agent" in text
    assert "<!-- workspace-io:auto:plugins:start -->" in text


def test_second_plugin_refreshes_claude_md(tmp_path):
    init(tmp_path, plugin="graph-wiki-agent", version="1.0.0")
    init(tmp_path, plugin="code-wiki-second", version="1.0.0")
    text = (tmp_path / "graph-wiki" / "CLAUDE.md").read_text()
    assert "graph-wiki-agent" in text
    assert "code-wiki-second" in text


def test_user_prose_in_claude_md_preserved_across_init(tmp_path):
    init(tmp_path, plugin="graph-wiki-agent", version="1.0.0")
    claude = tmp_path / "graph-wiki" / "CLAUDE.md"
    text = claude.read_text()
    claude.write_text("USER NOTE TOP\n" + text + "\nUSER NOTE BOTTOM\n")
    init(tmp_path, plugin="code-wiki-second", version="1.0.0")
    after = claude.read_text()
    assert "USER NOTE TOP" in after
    assert "USER NOTE BOTTOM" in after
    assert "code-wiki-second" in after
