"""VAULT-07 surface check: every ported module imports cleanly.

These smoke imports also catch lazy-import breakage and missing-symbol bugs
introduced during port surgery.
"""

from __future__ import annotations

from pathlib import Path


def test_all_ports_importable():
    from vault_io import _workspace, layout_io  # noqa: F401
    from vault_io.append_log import VALID_OPS, append_log
    from vault_io.detect_containers import detect
    from vault_io.graph_analyzer import analyze, build_graph
    from vault_io.init_vault import FIXED_VAULT_DIRS, init_wiki
    from vault_io.lint.common import WIKILINK_RE, _is_placeholder_target
    from vault_io.scan_monorepo import discover_workspaces, scan, unscope
    from vault_io.update_index import render_index, scan_vault
    from vault_io.update_tokens import update_page, update_vault

    # Callables / values are present and reasonably typed.
    assert callable(update_page)
    assert callable(update_vault)
    assert callable(detect)
    assert callable(append_log)
    assert isinstance(VALID_OPS, set) and "scan" in VALID_OPS
    assert callable(scan_vault)
    assert callable(render_index)
    assert callable(build_graph)
    assert callable(analyze)
    assert callable(discover_workspaces)
    assert callable(scan)
    assert callable(unscope)
    assert callable(init_wiki)
    assert isinstance(FIXED_VAULT_DIRS, list) and "concepts" in FIXED_VAULT_DIRS
    assert callable(_is_placeholder_target)
    assert WIKILINK_RE.search("[[foo]]") is not None


def test_detect_containers_smoke(tmp_path: Path):
    """A tmp repo with a package.json plus a pyproject.toml child must be classified."""
    from vault_io.detect_containers import detect

    repo = tmp_path / "repo"
    repo.mkdir()
    # Child directory with a python manifest — looks like a 'packages' container.
    pkgs = repo / "packages"
    pkgs.mkdir()
    (pkgs / "alpha").mkdir()
    (pkgs / "alpha" / "pyproject.toml").write_text(
        '[project]\nname = "alpha"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    records = detect(repo)
    assert isinstance(records, list)
    assert records, "detect() should return at least one container record"
    sources = {r["source"] for r in records}
    assert "packages" in sources
    # The packages dir contains one manifest-bearing child → classification 'package'.
    classes = {r["source"]: r["classification"] for r in records}
    assert classes["packages"] == "package", f"expected 'package', got {classes['packages']!r}"


def test_resolve_wiki_and_repo_raises_on_no_config(monkeypatch, tmp_path: Path):
    """When neither arg nor env var is set and no manifest is found, raise an actionable RuntimeError."""
    from vault_io._workspace import resolve_wiki_and_repo

    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    monkeypatch.chdir(tmp_path)
    # Force workspace_io.config.resolve() to treat this cwd as outside any
    # git repo so it cannot accidentally pick up the real deep-agents repo.
    monkeypatch.setattr("workspace_io.config._find_repo_root", lambda _: None)

    try:
        resolve_wiki_and_repo()
    except RuntimeError as exc:
        assert "graph-wiki-agent init" in str(exc)
        return
    raise AssertionError("resolve_wiki_and_repo did not raise RuntimeError on missing config")


def test_resolve_wiki_and_repo_honors_env_var(monkeypatch, tmp_path: Path):
    """GRAPH_WIKI_WORKSPACE env var alone is sufficient to resolve the wiki path."""
    from vault_io._workspace import resolve_wiki_and_repo

    fake_workspace = tmp_path / "workspace"
    fake_workspace.mkdir()
    # workspace_io.config.resolve() with env set returns the workspace dir,
    # then paths.wiki_dir() returns workspace/"wiki". No manifest needed
    # because the env-override branch skips the strict manifest check.
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(fake_workspace))

    wiki, repo = resolve_wiki_and_repo()
    assert wiki == (fake_workspace / "wiki").resolve()
    # repo_root is discovered via _find_repo_root; may be None or a real path,
    # we only assert the wiki path here (matches the env-override contract).


def test_resolve_wiki_and_repo_strict_raises_without_manifest(monkeypatch, tmp_path: Path):
    """Without env var and without .graph-wiki.yaml, raises RuntimeError naming init command."""
    from vault_io._workspace import resolve_wiki_and_repo

    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    monkeypatch.chdir(tmp_path)
    # Ensure no .git ancestor so we don't hit a real workspace.
    monkeypatch.setattr("workspace_io.config._find_repo_root", lambda _: None)

    try:
        resolve_wiki_and_repo()
    except RuntimeError as exc:
        assert "graph-wiki-agent init" in str(exc)
        return
    raise AssertionError("did not raise RuntimeError")
