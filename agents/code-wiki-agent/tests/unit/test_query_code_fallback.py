from __future__ import annotations

"""Unit tests for Plan 03-09 code-fallback layer.

Covers the bounded read_file tool, repo-root resolution, CODE_READER_SYSTEM
prompt, the new code_reader role in models.toml, and the run_query code-fallback
fan-out branch.

These tests pin behavior described in `03-09-PLAN.md` <task>1 and 2.
"""

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Task 1: role config + prompt + read_file helpers
# ---------------------------------------------------------------------------


def test_code_reader_role_in_models_toml() -> None:
    """load_role_config('code_reader') returns a dict with the expected keys."""
    from model_adapter.loader import load_role_config

    cfg = load_role_config("code_reader")
    assert isinstance(cfg, dict)
    assert "model_id" in cfg
    assert "region" in cfg
    assert "max_tokens" in cfg
    assert "max_concurrency" in cfg
    # Conservative defaults per plan:
    assert cfg["region"] == "us-east-1"
    assert cfg["max_tokens"] == 2048
    assert cfg["max_concurrency"] == 3


def test_code_reader_system_constant_defined() -> None:
    """CODE_READER_SYSTEM is a non-empty string with the no-invention contract."""
    from code_wiki_agent.commands.query import CODE_READER_SYSTEM

    assert isinstance(CODE_READER_SYSTEM, str)
    assert len(CODE_READER_SYSTEM) > 100  # not a stub
    # Same sentinel as the librarian — the synthesizer's existing filter
    # at query.py expects this exact literal.
    assert "NO_RELEVANT_CONTENT" in CODE_READER_SYSTEM
    # No-invention rule (substring assertion — exact wording flexible)
    lower = CODE_READER_SYSTEM.lower()
    assert "invent" in lower or "fabricat" in lower, (
        "CODE_READER_SYSTEM must encode the no-invention contract"
    )
    # Tool name reference — model must know it can call read_file
    assert "read_file" in CODE_READER_SYSTEM


def test_read_file_bounded_rejects_path_outside_repo(tmp_path: Path) -> None:
    """Path traversal via '..' is rejected with PermissionError."""
    from code_wiki_agent.commands.query import _read_file_bounded

    repo_a = tmp_path / "repoA"
    repo_a.mkdir()
    repo_b = tmp_path / "repoB"
    repo_b.mkdir()
    (repo_b / "secret").write_text("classified")

    with pytest.raises(PermissionError):
        _read_file_bounded(repo_a, "../repoB/secret")


def test_read_file_bounded_rejects_symlink_escape(tmp_path: Path) -> None:
    """Symlinks that point outside the repo root are rejected.

    This pins the requirement that _read_file_bounded calls Path.resolve()
    on BOTH the repo_root and the candidate path before performing the
    is_relative_to check. Without resolve(), the symlink's literal path
    would appear to live under repo_root and the check would falsely pass.
    """
    from code_wiki_agent.commands.query import _read_file_bounded

    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("classified")

    escape_link = repo / "escape_link"
    escape_link.symlink_to(secret)

    with pytest.raises(PermissionError):
        _read_file_bounded(repo, "escape_link")


def test_read_file_bounded_rejects_code_wiki(tmp_path: Path) -> None:
    """Paths whose parts include '.code-wiki' are rejected."""
    from code_wiki_agent.commands.query import _read_file_bounded

    repo = tmp_path / "repo"
    (repo / ".code-wiki" / "search.db").parent.mkdir(parents=True)
    (repo / ".code-wiki" / "search.db").write_text("vault metadata")

    with pytest.raises(PermissionError):
        _read_file_bounded(repo, ".code-wiki/search.db")


def test_read_file_bounded_truncates_large_file(tmp_path: Path) -> None:
    """A file larger than max_bytes is read up to max_bytes and suffixed with [TRUNCATED]."""
    from code_wiki_agent.commands.query import _read_file_bounded

    repo = tmp_path / "repo"
    repo.mkdir()
    big = repo / "big.py"
    big.write_text("x" * 1000)

    content = _read_file_bounded(repo, "big.py", max_bytes=100)
    assert len(content) >= 100
    assert content.endswith("[TRUNCATED]")
    assert content[:100] == "x" * 100


def test_read_file_bounded_reads_inside_repo(tmp_path: Path) -> None:
    """A regular file inside the repo is read normally."""
    from code_wiki_agent.commands.query import _read_file_bounded

    repo = tmp_path / "repo"
    repo.mkdir()
    src = repo / "src" / "foo.py"
    src.parent.mkdir()
    src.write_text("def foo():\n    return 1\n")

    content = _read_file_bounded(repo, "src/foo.py")
    assert "def foo()" in content
    assert "[TRUNCATED]" not in content


def test_resolve_repo_root_finds_git_parent(tmp_path: Path) -> None:
    """Vault at repo/wiki with a sibling repo/.git/ dir resolves to repo."""
    from code_wiki_agent.commands.query import _resolve_repo_root

    repo = tmp_path / "repo"
    wiki = repo / "wiki"
    wiki.mkdir(parents=True)
    (repo / ".git").mkdir()

    assert _resolve_repo_root(wiki) == repo


def test_resolve_repo_root_finds_pyproject_parent(tmp_path: Path) -> None:
    """Vault at repo/wiki with a sibling repo/pyproject.toml resolves to repo."""
    from code_wiki_agent.commands.query import _resolve_repo_root

    repo = tmp_path / "repo"
    wiki = repo / "wiki"
    wiki.mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    assert _resolve_repo_root(wiki) == repo


def test_resolve_repo_root_falls_back_to_vault(tmp_path: Path) -> None:
    """No .git or pyproject.toml sibling -> repo root falls back to vault_path."""
    from code_wiki_agent.commands.query import _resolve_repo_root

    wiki = tmp_path / "lonely-vault"
    wiki.mkdir()

    assert _resolve_repo_root(wiki) == wiki
