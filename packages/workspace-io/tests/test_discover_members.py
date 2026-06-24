from pathlib import Path

from workspace_io.config import discover_members, resolve


def _mk_repo(root: Path, name: str) -> Path:
    d = root / name
    (d / ".git").mkdir(parents=True)
    return d


def test_discover_members_finds_git_children(tmp_path):
    _mk_repo(tmp_path, "alpha")
    _mk_repo(tmp_path, "beta")
    (tmp_path / "node_modules").mkdir()
    ws = tmp_path / "workspace"
    (ws / ".git").mkdir(parents=True)
    members = discover_members(tmp_path, workspace=ws, allow=(), exclude=())
    assert [m.name for m in members] == ["alpha", "beta"]


def test_discover_members_allow_and_exclude(tmp_path):
    _mk_repo(tmp_path, "alpha")
    _mk_repo(tmp_path, "beta")
    _mk_repo(tmp_path, "gamma")
    ws = tmp_path / "workspace"
    (ws / ".git").mkdir(parents=True)
    assert [m.name for m in discover_members(tmp_path, workspace=ws, allow=("alpha", "beta"), exclude=())] == [
        "alpha",
        "beta",
    ]
    assert [m.name for m in discover_members(tmp_path, workspace=ws, allow=(), exclude=("beta",))] == [
        "alpha",
        "gamma",
    ]


def test_resolve_multi_repo(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    _mk_repo(tmp_path, "alpha")
    _mk_repo(tmp_path, "beta")
    # Make tmp_path look like a git repo so _find_repo_root finds it.
    (tmp_path / ".git").mkdir()
    # Default workspace name is "graph-wiki" (resolve_workspace default).
    ws = tmp_path / "graph-wiki"
    ws.mkdir()
    (ws / ".graph-wiki.yaml").write_text("multi-repo: true\n")
    cfg = resolve(cwd=tmp_path)
    assert [m.name for m in cfg.members] == ["alpha", "beta"]
    assert cfg.repo_root == cfg.members[0]


def test_resolve_single_repo_has_empty_members(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    (tmp_path / ".git").mkdir()
    ws = tmp_path / "graph-wiki"
    ws.mkdir()
    (ws / ".graph-wiki.yaml").write_text("topic: x\n")
    cfg = resolve(cwd=tmp_path)
    assert cfg.members == ()


def test_discover_members_allow_then_exclude(tmp_path):
    _mk_repo(tmp_path, "alpha")
    _mk_repo(tmp_path, "beta")
    ws = tmp_path / "workspace"
    (ws / ".git").mkdir(parents=True)
    members = discover_members(tmp_path, workspace=ws, allow=("alpha", "beta"), exclude=("beta",))
    assert [m.name for m in members] == ["alpha"]


def test_resolve_multi_repo_false_disables(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    _mk_repo(tmp_path, "alpha")
    _mk_repo(tmp_path, "beta")
    (tmp_path / ".git").mkdir()
    ws = tmp_path / "graph-wiki"
    ws.mkdir()
    (ws / ".graph-wiki.yaml").write_text("multi-repo: false\n")
    cfg = resolve(cwd=tmp_path)
    assert cfg.members == ()


def test_resolve_multi_repo_repos_scalar_restricts_members(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    _mk_repo(tmp_path, "alpha")
    _mk_repo(tmp_path, "beta")
    _mk_repo(tmp_path, "gamma")
    (tmp_path / ".git").mkdir()
    ws = tmp_path / "graph-wiki"
    ws.mkdir()
    (ws / ".graph-wiki.yaml").write_text("multi-repo: true\nrepos: alpha,beta\n")
    cfg = resolve(cwd=tmp_path)
    assert [m.name for m in cfg.members] == ["alpha", "beta"]
