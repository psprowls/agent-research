"""VAULT-07 surface check: every ported module imports cleanly.

These smoke imports also catch lazy-import breakage and missing-symbol bugs
introduced during port surgery.
"""

from __future__ import annotations

from pathlib import Path


def test_all_ports_importable():
    from wiki_io import _workspace  # noqa: F401
    from wiki_io.append_log import VALID_OPS, append_log
    from wiki_io.graph_analyzer import analyze, build_graph
    from wiki_io.init_vault import FIXED_VAULT_DIRS, init_wiki
    from wiki_io.lint.common import WIKILINK_RE, _is_placeholder_target
    from wiki_io.scan_monorepo import unscope
    from wiki_io.update_index import render_index, scan_vault
    from wiki_io.update_tokens import update_page, update_vault

    # Callables / values are present and reasonably typed.
    assert callable(update_page)
    assert callable(update_vault)
    assert callable(append_log)
    assert isinstance(VALID_OPS, set) and "scan" in VALID_OPS
    assert callable(scan_vault)
    assert callable(render_index)
    assert callable(build_graph)
    assert callable(analyze)
    assert callable(unscope)
    assert callable(init_wiki)
    assert isinstance(FIXED_VAULT_DIRS, list) and "concepts" in FIXED_VAULT_DIRS
    assert callable(_is_placeholder_target)
    assert WIKILINK_RE.search("[[foo]]") is not None


def test_resolve_wiki_and_repo_raises_on_no_config(monkeypatch, tmp_path: Path):
    """When neither arg nor env var is set and no manifest is found, raise an actionable RuntimeError."""
    from wiki_io._workspace import resolve_wiki_and_repo

    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    monkeypatch.chdir(tmp_path)
    # Force workspace_io.config.resolve() to treat this cwd as outside any
    # git repo so it cannot accidentally pick up the real agent-research repo.
    monkeypatch.setattr("workspace_io.config._find_repo_root", lambda _: None)

    try:
        resolve_wiki_and_repo()
    except RuntimeError as exc:
        assert "gw bootstrap" in str(exc)
        return
    raise AssertionError("resolve_wiki_and_repo did not raise RuntimeError on missing config")


def test_resolve_wiki_and_repo_honors_env_var(monkeypatch, tmp_path: Path):
    """GRAPH_WIKI_WORKSPACE env var alone is sufficient to resolve the wiki path."""
    from wiki_io._workspace import resolve_wiki_and_repo

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
    """Without env var and without .graph-wiki.yaml, raises RuntimeError naming bootstrap command."""
    from wiki_io._workspace import resolve_wiki_and_repo

    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    monkeypatch.chdir(tmp_path)
    # Ensure no .git ancestor so we don't hit a real workspace.
    monkeypatch.setattr("workspace_io.config._find_repo_root", lambda _: None)

    try:
        resolve_wiki_and_repo()
    except RuntimeError as exc:
        assert "gw bootstrap" in str(exc)
        return
    raise AssertionError("did not raise RuntimeError")
