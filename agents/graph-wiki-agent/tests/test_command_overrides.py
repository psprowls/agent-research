from __future__ import annotations

"""Unit tests for per-role model_override surfaces on command functions.

Proves D-06 single-role-swap protocol: when exactly one role is overridden,
all other roles still use their models.toml defaults (make_llm path).

All tests use unittest.mock.patch and AsyncMock — no real Bedrock calls.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_query_result(answer: str = "test answer [[wiki-page]]"):
    from graph_wiki_agent.commands.query import QueryResult

    return QueryResult(
        answer=answer,
        citations=["wiki-page"],
        pages_drilled=2,
        search_scores={"page.md": {"bm25": 0.5, "embed": 0.4, "rrf": 0.9}},
    )


def _make_vault(tmp_path: Path) -> Path:
    """Create a minimal vault directory that resolve_wiki_and_repo can find."""
    vault = tmp_path / "vault"
    vault.mkdir()
    code_wiki = vault / ".graph-wiki"
    code_wiki.mkdir()
    return vault


# ---------------------------------------------------------------------------
# Task 1: run_query overrides (synthesizer, code_reader, librarian back-compat)
# ---------------------------------------------------------------------------


async def test_run_query_synthesizer_override(tmp_path: Path) -> None:
    """role_model_overrides={"synthesizer": "..."} routes synthesizer LLM to ChatBedrockConverse
    with the specified model_id, not to the make_llm("synthesizer") default."""
    candidate = "us.amazon.nova-pro-v1:0"
    vault = _make_vault(tmp_path)

    mock_synth_resp = MagicMock()
    mock_synth_resp.content = "The answer [[page]]"

    mock_lib_resp = MagicMock()
    mock_lib_resp.content = "relevant excerpt"

    mock_fan = MagicMock()
    mock_fan.successes = [("page.md", "relevant excerpt")]
    mock_fan.errors = []

    synth_converse_instance = AsyncMock()
    synth_converse_instance.ainvoke = AsyncMock(return_value=mock_synth_resp)

    lib_converse_instance = AsyncMock()
    lib_converse_instance.ainvoke = AsyncMock(return_value=mock_lib_resp)

    captured_converse_calls: list[dict] = []

    def _fake_converse(**kwargs):
        captured_converse_calls.append(kwargs)
        if kwargs.get("model_id") == candidate:
            return synth_converse_instance
        return lib_converse_instance

    with (
        patch(
            "graph_wiki_agent.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch("graph_wiki_agent.commands.query.build_index"),
        patch(
            "graph_wiki_agent.commands.query.bm25_query",
            return_value=(["page.md"], [1.0]),
        ),
        patch(
            "graph_wiki_agent.commands.query.BedrockEmbeddings",
        ) as mock_embed_cls,
        patch(
            "graph_wiki_agent.commands.query._cosine_search_sqlite",
            return_value=[("page.md", 0.9)],
        ),
        patch(
            "graph_wiki_agent.commands.query.SubagentPool",
        ) as mock_pool_cls,
        patch(
            "graph_wiki_agent.commands.query.make_llm",
        ) as mock_make_llm,
        patch(
            "graph_wiki_agent.commands.query.ChatBedrockConverse",
            side_effect=_fake_converse,
        ),
        patch("graph_wiki_agent.commands.query.apply_guardrails", side_effect=lambda r, *a, **kw: r),
    ):
        mock_embed_cls.return_value.embed_query.return_value = [0.1] * 10
        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = AsyncMock(return_value=mock_fan)
        mock_pool_cls.return_value = mock_pool_instance
        mock_make_llm.return_value = lib_converse_instance

        from graph_wiki_agent.commands.query import run_query

        await run_query(
            "test query",
            workspace_path=vault,
            top_k=3,
            role_model_overrides={"synthesizer": candidate},
        )

    # ChatBedrockConverse was called with the candidate model_id for the synthesizer
    synthesizer_calls = [c for c in captured_converse_calls if c.get("model_id") == candidate]
    assert len(synthesizer_calls) >= 1, (
        f"Expected ChatBedrockConverse called with model_id={candidate!r}; "
        f"got calls: {captured_converse_calls}"
    )


async def test_run_query_code_reader_override(tmp_path: Path) -> None:
    """role_model_overrides={"code_reader": "..."} routes code_reader LLM to ChatBedrockConverse
    with the specified model_id when the vault-thin code fallback fires."""
    candidate = "us.amazon.nova-micro-v1:0"
    vault = _make_vault(tmp_path)

    # Simulate empty librarian fan-out -> triggers code fallback
    mock_fan_empty = MagicMock()
    mock_fan_empty.successes = []
    mock_fan_empty.errors = []

    mock_code_fan = MagicMock()
    mock_code_fan.successes = []
    mock_code_fan.errors = []

    captured_converse_calls: list[dict] = []

    def _fake_converse(**kwargs):
        captured_converse_calls.append(kwargs)
        inst = MagicMock()
        inst.bind_tools = MagicMock(return_value=AsyncMock())
        return inst

    with (
        patch(
            "graph_wiki_agent.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch("graph_wiki_agent.commands.query.build_index"),
        patch(
            "graph_wiki_agent.commands.query.bm25_query",
            return_value=(["page.md"], [1.0]),
        ),
        patch(
            "graph_wiki_agent.commands.query.BedrockEmbeddings",
        ) as mock_embed_cls,
        patch(
            "graph_wiki_agent.commands.query._cosine_search_sqlite",
            return_value=[("page.md", 0.9)],
        ),
        patch(
            "graph_wiki_agent.commands.query.SubagentPool",
        ) as mock_pool_cls,
        patch(
            "graph_wiki_agent.commands.query.make_llm",
        ),
        patch(
            "graph_wiki_agent.commands.query.ChatBedrockConverse",
            side_effect=_fake_converse,
        ),
        patch("graph_wiki_agent.commands.query.apply_guardrails", side_effect=lambda r, *a, **kw: r),
        patch("graph_wiki_agent.commands.query._resolve_repo_root", return_value=tmp_path),
    ):
        mock_embed_cls.return_value.embed_query.return_value = [0.1] * 10
        mock_pool_instance = MagicMock()
        # First call: librarian fan-out (empty), second call: code fan-out (empty -> disclaimer)
        mock_pool_instance.run_all = AsyncMock(side_effect=[mock_fan_empty, mock_code_fan])
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_agent.commands.query import run_query

        await run_query(
            "How is _StdoutGuard implemented?",
            workspace_path=vault,
            top_k=3,
            role_model_overrides={"code_reader": candidate},
        )

    code_reader_calls = [c for c in captured_converse_calls if c.get("model_id") == candidate]
    assert len(code_reader_calls) >= 1, (
        f"Expected ChatBedrockConverse called with model_id={candidate!r}; "
        f"got calls: {captured_converse_calls}"
    )


async def test_run_query_librarian_back_compat(tmp_path: Path) -> None:
    """Legacy librarian_model_override=... still works when role_model_overrides is absent."""
    candidate = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    vault = _make_vault(tmp_path)

    mock_synth_resp = MagicMock()
    mock_synth_resp.content = "The answer [[page]]"

    mock_fan = MagicMock()
    mock_fan.successes = [("page.md", "relevant")]
    mock_fan.errors = []

    captured_converse_calls: list[dict] = []

    def _fake_converse(**kwargs):
        captured_converse_calls.append(kwargs)
        inst = AsyncMock()
        inst.ainvoke = AsyncMock(return_value=mock_synth_resp)
        return inst

    with (
        patch(
            "graph_wiki_agent.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch("graph_wiki_agent.commands.query.build_index"),
        patch(
            "graph_wiki_agent.commands.query.bm25_query",
            return_value=(["page.md"], [1.0]),
        ),
        patch(
            "graph_wiki_agent.commands.query.BedrockEmbeddings",
        ) as mock_embed_cls,
        patch(
            "graph_wiki_agent.commands.query._cosine_search_sqlite",
            return_value=[("page.md", 0.9)],
        ),
        patch(
            "graph_wiki_agent.commands.query.SubagentPool",
        ) as mock_pool_cls,
        patch(
            "graph_wiki_agent.commands.query.make_llm",
        ) as mock_make_llm,
        patch(
            "graph_wiki_agent.commands.query.ChatBedrockConverse",
            side_effect=_fake_converse,
        ),
        patch("graph_wiki_agent.commands.query.apply_guardrails", side_effect=lambda r, *a, **kw: r),
    ):
        mock_embed_cls.return_value.embed_query.return_value = [0.1] * 10
        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = AsyncMock(return_value=mock_fan)
        mock_pool_cls.return_value = mock_pool_instance
        synth_inst = AsyncMock()
        synth_inst.ainvoke = AsyncMock(return_value=mock_synth_resp)
        mock_make_llm.return_value = synth_inst

        from graph_wiki_agent.commands.query import run_query

        await run_query(
            "test query",
            workspace_path=vault,
            top_k=3,
            librarian_model_override=candidate,
        )

    librarian_calls = [c for c in captured_converse_calls if c.get("model_id") == candidate]
    assert len(librarian_calls) >= 1, (
        f"Expected ChatBedrockConverse called with librarian model_id={candidate!r}; "
        f"got calls: {captured_converse_calls}"
    )


async def test_run_query_other_roles_unaffected(tmp_path: Path) -> None:
    """Single-role-swap: role_model_overrides={"librarian": X} must NOT override synthesizer.

    Confirms D-06 protocol: only the named role gets the candidate; all others use make_llm.
    """
    librarian_candidate = "us.amazon.nova-pro-v1:0"
    vault = _make_vault(tmp_path)

    mock_resp = MagicMock()
    mock_resp.content = "The answer [[page]]"

    mock_fan = MagicMock()
    mock_fan.successes = [("page.md", "relevant excerpt")]
    mock_fan.errors = []

    captured_converse_model_ids: list[str] = []

    def _fake_converse(**kwargs):
        captured_converse_model_ids.append(kwargs.get("model_id", ""))
        inst = AsyncMock()
        inst.ainvoke = AsyncMock(return_value=mock_resp)
        return inst

    make_llm_roles: list[str] = []

    def _fake_make_llm(role: str):
        make_llm_roles.append(role)
        inst = AsyncMock()
        inst.ainvoke = AsyncMock(return_value=mock_resp)
        return inst

    with (
        patch(
            "graph_wiki_agent.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch("graph_wiki_agent.commands.query.build_index"),
        patch(
            "graph_wiki_agent.commands.query.bm25_query",
            return_value=(["page.md"], [1.0]),
        ),
        patch(
            "graph_wiki_agent.commands.query.BedrockEmbeddings",
        ) as mock_embed_cls,
        patch(
            "graph_wiki_agent.commands.query._cosine_search_sqlite",
            return_value=[("page.md", 0.9)],
        ),
        patch(
            "graph_wiki_agent.commands.query.SubagentPool",
        ) as mock_pool_cls,
        patch(
            "graph_wiki_agent.commands.query.make_llm",
            side_effect=_fake_make_llm,
        ),
        patch(
            "graph_wiki_agent.commands.query.ChatBedrockConverse",
            side_effect=_fake_converse,
        ),
        patch("graph_wiki_agent.commands.query.apply_guardrails", side_effect=lambda r, *a, **kw: r),
    ):
        mock_embed_cls.return_value.embed_query.return_value = [0.1] * 10
        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = AsyncMock(return_value=mock_fan)
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_agent.commands.query import run_query

        await run_query(
            "test query",
            workspace_path=vault,
            top_k=3,
            role_model_overrides={"librarian": librarian_candidate},
        )

    # The librarian candidate was used via ChatBedrockConverse
    assert librarian_candidate in captured_converse_model_ids, (
        f"Librarian candidate {librarian_candidate!r} not found in ChatBedrockConverse calls: "
        f"{captured_converse_model_ids}"
    )
    # synthesizer must have gone through make_llm, not ChatBedrockConverse with the candidate
    assert "synthesizer" in make_llm_roles, (
        f"Expected synthesizer to use make_llm path; make_llm was called for: {make_llm_roles}"
    )
    # synthesizer must NOT appear in ChatBedrockConverse calls with the librarian candidate
    assert captured_converse_model_ids.count(librarian_candidate) == 1, (
        "Librarian candidate bled into synthesizer ChatBedrockConverse call (D-06 violation); "
        f"all captured model_ids: {captured_converse_model_ids}"
    )


# ---------------------------------------------------------------------------
# Task 2: scan, lint, ingest model_override
# ---------------------------------------------------------------------------


async def test_run_scan_model_override(tmp_path: Path) -> None:
    """run_scan(model_override=...) constructs ChatBedrockConverse with that model_id
    and does NOT call make_llm("scanner")."""
    candidate = "us.amazon.nova-lite-v1:0"
    vault = _make_vault(tmp_path)

    mock_fan = MagicMock()
    mock_fan.successes = []
    mock_fan.errors = []

    mock_scan_resp = MagicMock()
    mock_scan_resp.content = "stub content"

    converse_instance = AsyncMock()
    converse_instance.ainvoke = AsyncMock(return_value=mock_scan_resp)

    captured_converse_calls: list[dict] = []

    def _fake_converse(**kwargs):
        captured_converse_calls.append(kwargs)
        return converse_instance

    with (
        patch(
            "graph_wiki_agent.commands.scan.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch("graph_wiki_agent.commands.scan.read_layout", return_value=None),
        patch("graph_wiki_agent.commands.scan.discover_workspaces", return_value=[]),
        patch("graph_wiki_agent.commands.scan._load_existing_pages", return_value={}),
        patch(
            "graph_wiki_agent.commands.scan.compute_diff",
            return_value={"new": [], "renamed": [], "deleted": [], "unchanged": []},
        ),
        patch(
            "graph_wiki_agent.commands.scan.compute_state_gate",
            return_value={"allowed": True, "reason": "ok", "head_commit": "abc123"},
        ),
        patch("graph_wiki_agent.commands.scan.attach_changed_files"),
        patch(
            "graph_wiki_agent.commands.scan.SubagentPool",
        ) as mock_pool_cls,
        patch("graph_wiki_agent.commands.scan.make_llm") as mock_make_llm,
        patch(
            "graph_wiki_agent.commands.scan.ChatBedrockConverse",
            side_effect=_fake_converse,
        ),
        patch("graph_wiki_agent.commands.scan.regenerate_dependencies_index"),
        patch("graph_wiki_agent.commands.scan.append_log"),
        patch("graph_wiki_agent.commands.scan.update_index"),
    ):
        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = AsyncMock(return_value=mock_fan)
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_agent.commands.scan import run_scan

        await run_scan(workspace_path=vault, model_override=candidate)

    scanner_calls = [c for c in captured_converse_calls if c.get("model_id") == candidate]
    assert len(scanner_calls) >= 1, (
        f"Expected ChatBedrockConverse called with model_id={candidate!r}; "
        f"got: {captured_converse_calls}"
    )
    # make_llm("scanner") must NOT have been called
    scanner_make_llm_calls = [c for c in mock_make_llm.call_args_list if c == call("scanner")]
    assert len(scanner_make_llm_calls) == 0, (
        f"make_llm('scanner') should not be called when model_override is set; "
        f"actual calls: {mock_make_llm.call_args_list}"
    )


async def test_run_lint_model_override(tmp_path: Path) -> None:
    """run_lint(model_override=...) constructs ChatBedrockConverse with that model_id
    inside run_linter_group and does NOT call make_llm("linter").

    The pool.run_all mock invokes the provided task function so that
    run_linter_group actually executes and the ChatBedrockConverse call can be captured.
    """
    candidate = "us.amazon.nova-lite-v1:0"
    vault = _make_vault(tmp_path)

    linter_resp = MagicMock()
    linter_resp.content = ""

    converse_instance = AsyncMock()
    converse_instance.ainvoke = AsyncMock(return_value=linter_resp)

    captured_converse_calls: list[dict] = []

    def _fake_converse(**kwargs):
        captured_converse_calls.append(kwargs)
        return converse_instance

    # One non-empty page so run_linter_group actually runs (pages_sample > 0)
    non_empty_pages = {
        "concepts/hello.md": {
            "fm": {"title": "Hello"},
            "text": "Hello world.",
            "linted": True,
            "is_work": False,
        }
    }

    async def _mock_run_all(items, task, **kwargs):
        """Execute the task function on each item so run_linter_group fires."""
        from subagent_runtime.pool import FanOutResult
        successes = []
        errors = []
        for item in items:
            try:
                result = await task(item)
                successes.append((item, result))
            except Exception as exc:
                errors.append(exc)
        return FanOutResult(successes=successes, errors=errors)

    with (
        patch(
            "graph_wiki_agent.commands.lint.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch(
            "graph_wiki_agent.commands.lint._mechanical_pass",
            return_value={
                "pages": non_empty_pages,
                "total_pages": 1,
                "orphans": [],
                "broken_links": [],
                "stale": [],
                "missing_frontmatter": [],
                "duplicate_titles": [],
                "log_gap": False,
            },
        ),
        patch(
            "graph_wiki_agent.commands.lint._module_pass",
            return_value={
                "code_drift": {},
                "container_drift": {},
                "dependency_drift": {},
                "domain_drift": {},
                "file_map_drift": {},
                "package_sync_drift": {},
                "source_sync_drift": {},
                "workflow_hints": [],
                "domain_placement": {},
                "dependency_layer": {},
            },
        ),
        patch(
            "graph_wiki_agent.commands.lint.SubagentPool",
        ) as mock_pool_cls,
        patch("graph_wiki_agent.commands.lint.make_llm") as mock_make_llm,
        patch(
            "graph_wiki_agent.commands.lint.ChatBedrockConverse",
            side_effect=_fake_converse,
        ),
    ):
        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = _mock_run_all
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_agent.commands.lint import run_lint

        await run_lint(workspace_path=vault, model_override=candidate)

    linter_calls = [c for c in captured_converse_calls if c.get("model_id") == candidate]
    assert len(linter_calls) >= 1, (
        f"Expected ChatBedrockConverse called with model_id={candidate!r}; "
        f"got: {captured_converse_calls}"
    )
    linter_make_llm_calls = [c for c in mock_make_llm.call_args_list if c == call("linter")]
    assert len(linter_make_llm_calls) == 0, (
        f"make_llm('linter') should not be called when model_override is set; "
        f"actual calls: {mock_make_llm.call_args_list}"
    )


async def test_run_ingest_source_model_override(tmp_path: Path) -> None:
    """run_ingest_source(source_path, model_override=...) constructs ChatBedrockConverse
    with that model_id and does NOT call make_llm("ingestor")."""
    candidate = "us.amazon.nova-lite-v1:0"
    vault = _make_vault(tmp_path)
    source = tmp_path / "test_source.py"
    source.write_text("def hello(): pass\n")

    ingestor_resp = MagicMock()
    ingestor_resp.content = (
        "---\npage_type: concept\ntarget_slug: hello-func\n---\n# Hello\n"
    )

    converse_instance = AsyncMock()
    converse_instance.ainvoke = AsyncMock(return_value=ingestor_resp)

    captured_converse_calls: list[dict] = []

    def _fake_converse(**kwargs):
        captured_converse_calls.append(kwargs)
        return converse_instance

    # Phase 40: run_ingest_source opens a read-only graph DB at workspace start.
    # Seed an empty graph so the test exercises the model_override path.
    from graph_io.store import connect as _gio_connect
    from workspace_io.paths import graph_dir as _gio_graph_dir
    _gio_db = _gio_graph_dir(vault) / "code.db"
    _gio_db.parent.mkdir(parents=True, exist_ok=True)
    _gio_conn = _gio_connect(_gio_db, create=True)
    _gio_conn.close()

    with (
        patch(
            "graph_wiki_agent.commands.ingest.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
        patch(
            "graph_wiki_agent.commands.ingest.ChatBedrockConverse",
            side_effect=_fake_converse,
        ),
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log"),
    ):
        from graph_wiki_agent.commands.ingest import run_ingest_source

        await run_ingest_source(source_path=source, workspace_path=vault, model_override=candidate)

    ingestor_calls = [c for c in captured_converse_calls if c.get("model_id") == candidate]
    assert len(ingestor_calls) >= 1, (
        f"Expected ChatBedrockConverse called with model_id={candidate!r}; "
        f"got: {captured_converse_calls}"
    )
    ingestor_make_llm_calls = [c for c in mock_make_llm.call_args_list if c == call("ingestor")]
    assert len(ingestor_make_llm_calls) == 0, (
        f"make_llm('ingestor') should not be called when model_override is set; "
        f"actual calls: {mock_make_llm.call_args_list}"
    )
