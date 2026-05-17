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


def test_resolve_wiki_and_repo_raises_on_no_config(monkeypatch):
    """When neither arg nor env var is set, the helper must raise an actionable RuntimeError."""
    from vault_io._workspace import resolve_wiki_and_repo

    monkeypatch.delenv("CODE_WIKI_REAL_VAULT_PATH", raising=False)

    try:
        resolve_wiki_and_repo()
    except RuntimeError as exc:
        assert "CODE_WIKI_REAL_VAULT_PATH" in str(exc)
        return
    raise AssertionError("resolve_wiki_and_repo did not raise RuntimeError on missing config")


def test_resolve_wiki_and_repo_honors_env_var(monkeypatch, tmp_path: Path):
    """Env var alone is sufficient to resolve the vault path."""
    from vault_io._workspace import resolve_wiki_and_repo

    fake_vault = tmp_path / "vault"
    fake_vault.mkdir()
    monkeypatch.setenv("CODE_WIKI_REAL_VAULT_PATH", str(fake_vault))

    wiki, repo = resolve_wiki_and_repo()
    assert wiki == fake_vault.resolve()
    assert repo is None
