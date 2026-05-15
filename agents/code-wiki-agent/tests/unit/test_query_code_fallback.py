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


# ---------------------------------------------------------------------------
# Task 2: run_query code-fallback fan-out wiring
# ---------------------------------------------------------------------------


def _setup_run_query_mocks(
    vault: Path,
    fan_result,
    synth_responses: list,
    code_fan_result=None,
):
    """Patch stack + mock wiring for run_query code-fallback tests.

    Returns (patches, mock_synth_llm, mock_librarian_llm, mock_code_llm).
    code_fan_result, if provided, is what the SECOND `pool.run_all` call
    (the code-reader fan-out) will return. Otherwise both calls return
    `fan_result`. This lets tests distinguish "fallback fired" from
    "fallback did not fire".
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_synth_llm = MagicMock()
    mock_synth_llm.ainvoke = AsyncMock(side_effect=synth_responses)
    mock_librarian_llm = MagicMock()
    mock_code_llm = MagicMock()
    # bind_tools returns a new runnable in real langchain; we just return self
    mock_code_llm.bind_tools = MagicMock(return_value=mock_code_llm)

    patches = [
        patch(
            "code_wiki_agent.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch(
            "code_wiki_agent.commands.query.bm25_query",
            return_value=(["page1.md", "page2.md", "page3.md"], [2.0, 1.5, 1.0]),
        ),
        patch(
            "code_wiki_agent.commands.query._cosine_search_sqlite",
            return_value=[("page1.md", 0.9), ("page2.md", 0.8), ("page3.md", 0.7)],
        ),
        patch("code_wiki_agent.commands.query.BedrockEmbeddings"),
        patch("code_wiki_agent.commands.query.make_llm"),
        patch("code_wiki_agent.commands.query.SubagentPool"),
    ]
    return patches, mock_synth_llm, mock_librarian_llm, mock_code_llm


@pytest.mark.asyncio
async def test_code_fallback_triggered_when_all_excerpts_empty(tmp_path: Path) -> None:
    """When every librarian result is NO_RELEVANT_CONTENT, the code-reader fan-out fires."""
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, MagicMock

    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from code_wiki_agent.commands.query import run_query

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".code-wiki" / "bm25").mkdir(parents=True)
    (vault / ".code-wiki" / "search.db").touch()

    librarian_fan = FanOutResult(
        successes=[
            ("page1.md", "NO_RELEVANT_CONTENT"),
            ("page2.md", "   "),  # whitespace-only
            ("page3.md", "NO_RELEVANT_CONTENT"),
        ],
        errors=[],
    )
    code_fan = FanOutResult(
        successes=[
            ("page1.md", "`pool.py:115` — async semaphore creation"),
        ],
        errors=[],
    )
    synth_resp = AIMessage(content="The pool creates the semaphore at `pool.py:115`.")

    patches, mock_synth, mock_lib, mock_code = _setup_run_query_mocks(
        vault, librarian_fan, [synth_resp]
    )

    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in patches]
        _r, _b, _c, mock_embed_cls, mock_make_llm, mock_pool_cls = mocks

        mock_embed_inst = MagicMock()
        mock_embed_inst.embed_query.return_value = [0.1] * 1024
        mock_embed_cls.return_value = mock_embed_inst

        def _llm_for(role: str):
            if role == "librarian":
                return mock_lib
            if role == "code_reader":
                return mock_code
            return mock_synth

        mock_make_llm.side_effect = _llm_for

        mock_pool_inst = MagicMock()
        # First run_all → librarian; second → code_reader
        mock_pool_inst.run_all = AsyncMock(side_effect=[librarian_fan, code_fan])
        mock_pool_cls.return_value = mock_pool_inst

        result = await run_query("how does pool work?", vault_path=vault, top_k=3)

    # Two fan-out calls = code-fallback fired
    assert mock_pool_inst.run_all.await_count == 2, (
        "code-reader fan-out must be invoked when all librarian excerpts are empty"
    )
    # Verify the second call was role=code_reader
    second_call_kwargs = mock_pool_inst.run_all.await_args_list[1].kwargs
    assert second_call_kwargs.get("role") == "code_reader"
    # Marker prefix is present on the final answer
    assert result.answer.startswith("[vault-thin: answer derived from source code]")


@pytest.mark.asyncio
async def test_code_fallback_not_triggered_when_excerpts_present(tmp_path: Path) -> None:
    """At least one non-empty, non-sentinel excerpt -> no code-fallback."""
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, MagicMock

    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from code_wiki_agent.commands.query import run_query

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".code-wiki" / "bm25").mkdir(parents=True)
    (vault / ".code-wiki" / "search.db").touch()

    librarian_fan = FanOutResult(
        successes=[
            ("page1.md", "NO_RELEVANT_CONTENT"),
            ("page2.md", "real useful excerpt with content"),
        ],
        errors=[],
    )
    synth_resp = AIMessage(content="Synth output without any unresolved links.")

    patches, mock_synth, mock_lib, mock_code = _setup_run_query_mocks(
        vault, librarian_fan, [synth_resp]
    )

    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in patches]
        _r, _b, _c, mock_embed_cls, mock_make_llm, mock_pool_cls = mocks

        mock_embed_inst = MagicMock()
        mock_embed_inst.embed_query.return_value = [0.1] * 1024
        mock_embed_cls.return_value = mock_embed_inst

        def _llm_for(role: str):
            if role == "librarian":
                return mock_lib
            if role == "code_reader":
                return mock_code
            return mock_synth

        mock_make_llm.side_effect = _llm_for

        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock(return_value=librarian_fan)
        mock_pool_cls.return_value = mock_pool_inst

        result = await run_query("test query", vault_path=vault, top_k=3)

    # Only one fan-out call: librarian. No code-fallback.
    assert mock_pool_inst.run_all.await_count == 1
    # No marker prefix on the answer (regular path)
    assert not result.answer.startswith("[vault-thin:")


@pytest.mark.asyncio
async def test_code_fallback_marker_prefix_on_answer(tmp_path: Path) -> None:
    """When code-fallback succeeds, final QueryResult.answer starts with the exact marker."""
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, MagicMock

    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from code_wiki_agent.commands.query import run_query

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".code-wiki" / "bm25").mkdir(parents=True)
    (vault / ".code-wiki" / "search.db").touch()

    librarian_fan = FanOutResult(
        successes=[("page1.md", "NO_RELEVANT_CONTENT")],
        errors=[],
    )
    code_fan = FanOutResult(
        successes=[("page1.md", "Quoted code at `foo.py:10`")],
        errors=[],
    )
    synth_resp = AIMessage(content="Source-derived answer about `foo.py:10`.")

    patches, mock_synth, mock_lib, mock_code = _setup_run_query_mocks(
        vault, librarian_fan, [synth_resp]
    )

    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in patches]
        _r, _b, _c, mock_embed_cls, mock_make_llm, mock_pool_cls = mocks

        mock_embed_inst = MagicMock()
        mock_embed_inst.embed_query.return_value = [0.1] * 1024
        mock_embed_cls.return_value = mock_embed_inst

        def _llm_for(role: str):
            if role == "librarian":
                return mock_lib
            if role == "code_reader":
                return mock_code
            return mock_synth

        mock_make_llm.side_effect = _llm_for

        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock(side_effect=[librarian_fan, code_fan])
        mock_pool_cls.return_value = mock_pool_inst

        result = await run_query("test query", vault_path=vault, top_k=3)

    assert result.answer.startswith(
        "[vault-thin: answer derived from source code]"
    )
    # The synthesizer output should still appear after the marker
    assert "Source-derived answer about `foo.py:10`." in result.answer


@pytest.mark.asyncio
async def test_code_fallback_double_empty_returns_disclaimer(tmp_path: Path) -> None:
    """Both librarian and code-reader return nothing useful -> no-fabrication disclaimer."""
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, MagicMock

    from subagent_runtime.pool import FanOutResult

    from code_wiki_agent.commands.query import run_query

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".code-wiki" / "bm25").mkdir(parents=True)
    (vault / ".code-wiki" / "search.db").touch()

    librarian_fan = FanOutResult(
        successes=[("page1.md", "NO_RELEVANT_CONTENT")],
        errors=[],
    )
    code_fan = FanOutResult(
        successes=[("page1.md", "NO_RELEVANT_CONTENT")],
        errors=[],
    )
    # No synth response expected on the double-empty path — the disclaimer is
    # returned directly without calling the synthesizer. If a synth call is
    # made, side_effect=[] will raise StopAsyncIteration loudly.
    patches, mock_synth, mock_lib, mock_code = _setup_run_query_mocks(
        vault, librarian_fan, []
    )

    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in patches]
        _r, _b, _c, mock_embed_cls, mock_make_llm, mock_pool_cls = mocks

        mock_embed_inst = MagicMock()
        mock_embed_inst.embed_query.return_value = [0.1] * 1024
        mock_embed_cls.return_value = mock_embed_inst

        def _llm_for(role: str):
            if role == "librarian":
                return mock_lib
            if role == "code_reader":
                return mock_code
            return mock_synth

        mock_make_llm.side_effect = _llm_for

        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock(side_effect=[librarian_fan, code_fan])
        mock_pool_cls.return_value = mock_pool_inst

        result = await run_query("test query", vault_path=vault, top_k=3)

    # Disclaimer line, no fabrication
    assert "vault does not document this" in result.answer
    assert "source code did not yield" in result.answer
    # Synth was NOT called on the double-empty path
    assert mock_synth.ainvoke.await_count == 0
