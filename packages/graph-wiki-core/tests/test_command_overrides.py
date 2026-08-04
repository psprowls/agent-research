"""Unit tests for per-role model_override surfaces on command functions.

Proves D-06 single-role-swap protocol: when exactly one role is overridden,
all other roles still use their models.toml defaults (make_llm path).

Fix D contract (quick-260529-sot): the override role's LLM is now built via
`make_llm(role, model_override=<candidate>)` — a `_GuardedChatBedrockConverse`
that applies the content normalizer + AccessDenied guard — NOT a raw
`ChatBedrockConverse`. Other roles still go through `make_llm(role)` with no
model_override.

All tests use unittest.mock.patch and AsyncMock — no real Bedrock calls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_query_result(answer: str = "test answer [[wiki-page]]"):
    from graph_wiki_core.commands.query import QueryResult

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


def _make_llm_factory(default_resp):
    """Return (fake_make_llm, calls) where calls records (role, model_override)
    for every make_llm invocation, and each call yields an AsyncMock LLM.

    backend_override is accepted (query.py now always passes it) but not
    recorded -- existing (role, model_override) call-tuple assertions stay
    valid unchanged. Tests that need to assert on backend_override define
    their own local fake (see test_run_query_*_backend_override below).
    """
    calls: list[tuple[str, str | None]] = []

    def _fake_make_llm(role: str, *, model_override: str | None = None, backend_override: str | None = None):
        calls.append((role, model_override))
        inst = AsyncMock()
        inst.ainvoke = AsyncMock(return_value=default_resp)
        # code_reader path calls .bind_tools(...) then ainvoke on the result.
        inst.bind_tools = MagicMock(return_value=inst)
        return inst

    return _fake_make_llm, calls


# ---------------------------------------------------------------------------
# Task 1: run_query overrides (synthesizer, code_reader, librarian back-compat)
# ---------------------------------------------------------------------------


async def test_run_query_synthesizer_override(tmp_path: Path) -> None:
    """role_model_overrides={"synthesizer": "..."} routes the synthesizer LLM
    through make_llm("synthesizer", model_override=candidate)."""
    candidate = "us.amazon.nova-pro-v1:0"
    vault = _make_vault(tmp_path)

    mock_resp = MagicMock()
    mock_resp.content = "The answer [[page]]"

    mock_fan = MagicMock()
    mock_fan.successes = [("page.md", "relevant excerpt")]
    mock_fan.errors = []

    fake_make_llm, make_llm_calls = _make_llm_factory(mock_resp)

    with (
        patch(
            "graph_wiki_core.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch("graph_wiki_core.commands.query.build_index"),
        patch(
            "graph_wiki_core.commands.query.bm25_query",
            return_value=(["page.md"], [1.0]),
        ),
        patch(
            "graph_wiki_core.commands.query.BedrockEmbeddings",
        ) as mock_embed_cls,
        patch(
            "graph_wiki_core.commands.query._cosine_search_sqlite",
            return_value=[("page.md", 0.9)],
        ),
        patch(
            "graph_wiki_core.commands.query.SubagentPool",
        ) as mock_pool_cls,
        patch(
            "graph_wiki_core.commands.query.make_llm",
            side_effect=fake_make_llm,
        ),
        patch("graph_wiki_core.commands.query.apply_guardrails", side_effect=lambda r, *a, **kw: r),
    ):
        mock_embed_cls.return_value.embed_query.return_value = [0.1] * 10
        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = AsyncMock(return_value=mock_fan)
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_core.commands.query import run_query

        await run_query(
            "test query",
            workspace_path=vault,
            top_k=3,
            role_model_overrides={"synthesizer": candidate},
            use_legacy=True,
        )

    # synthesizer went through make_llm with the candidate override.
    assert ("synthesizer", candidate) in make_llm_calls, (
        f"Expected make_llm('synthesizer', model_override={candidate!r}); got calls: {make_llm_calls}"
    )
    # librarian was NOT overridden (no model_override).
    assert ("librarian", None) in make_llm_calls, (
        f"Expected librarian to use make_llm('librarian') with no override; got calls: {make_llm_calls}"
    )


async def test_run_query_code_reader_override(tmp_path: Path) -> None:
    """role_model_overrides={"code_reader": "..."} routes the code_reader LLM
    through make_llm("code_reader", model_override=candidate) when the
    vault-thin code fallback fires."""
    candidate = "us.amazon.nova-micro-v1:0"
    vault = _make_vault(tmp_path)

    # Simulate empty librarian fan-out -> triggers code fallback
    mock_fan_empty = MagicMock()
    mock_fan_empty.successes = []
    mock_fan_empty.errors = []

    mock_code_fan = MagicMock()
    mock_code_fan.successes = []
    mock_code_fan.errors = []

    mock_resp = MagicMock()
    mock_resp.content = "code answer"

    fake_make_llm, make_llm_calls = _make_llm_factory(mock_resp)

    with (
        patch(
            "graph_wiki_core.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch("graph_wiki_core.commands.query.build_index"),
        patch(
            "graph_wiki_core.commands.query.bm25_query",
            return_value=(["page.md"], [1.0]),
        ),
        patch(
            "graph_wiki_core.commands.query.BedrockEmbeddings",
        ) as mock_embed_cls,
        patch(
            "graph_wiki_core.commands.query._cosine_search_sqlite",
            return_value=[("page.md", 0.9)],
        ),
        patch(
            "graph_wiki_core.commands.query.SubagentPool",
        ) as mock_pool_cls,
        patch(
            "graph_wiki_core.commands.query.make_llm",
            side_effect=fake_make_llm,
        ),
        patch("graph_wiki_core.commands.query.apply_guardrails", side_effect=lambda r, *a, **kw: r),
        patch("graph_wiki_core.commands.query._resolve_repo_root", return_value=tmp_path),
    ):
        mock_embed_cls.return_value.embed_query.return_value = [0.1] * 10
        mock_pool_instance = MagicMock()
        # First call: librarian fan-out (empty), second call: code fan-out (empty -> disclaimer)
        mock_pool_instance.run_all = AsyncMock(side_effect=[mock_fan_empty, mock_code_fan])
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_core.commands.query import run_query

        await run_query(
            "How is _StdoutGuard implemented?",
            workspace_path=vault,
            top_k=3,
            role_model_overrides={"code_reader": candidate},
            use_legacy=True,
        )

    assert ("code_reader", candidate) in make_llm_calls, (
        f"Expected make_llm('code_reader', model_override={candidate!r}); got calls: {make_llm_calls}"
    )


async def test_run_query_librarian_back_compat(tmp_path: Path) -> None:
    """Legacy librarian_model_override=... still works when role_model_overrides
    is absent — routed through make_llm('librarian', model_override=candidate)."""
    candidate = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    vault = _make_vault(tmp_path)

    mock_resp = MagicMock()
    mock_resp.content = "The answer [[page]]"

    mock_fan = MagicMock()
    mock_fan.successes = [("page.md", "relevant")]
    mock_fan.errors = []

    fake_make_llm, make_llm_calls = _make_llm_factory(mock_resp)

    with (
        patch(
            "graph_wiki_core.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch("graph_wiki_core.commands.query.build_index"),
        patch(
            "graph_wiki_core.commands.query.bm25_query",
            return_value=(["page.md"], [1.0]),
        ),
        patch(
            "graph_wiki_core.commands.query.BedrockEmbeddings",
        ) as mock_embed_cls,
        patch(
            "graph_wiki_core.commands.query._cosine_search_sqlite",
            return_value=[("page.md", 0.9)],
        ),
        patch(
            "graph_wiki_core.commands.query.SubagentPool",
        ) as mock_pool_cls,
        patch(
            "graph_wiki_core.commands.query.make_llm",
            side_effect=fake_make_llm,
        ),
        patch("graph_wiki_core.commands.query.apply_guardrails", side_effect=lambda r, *a, **kw: r),
    ):
        mock_embed_cls.return_value.embed_query.return_value = [0.1] * 10
        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = AsyncMock(return_value=mock_fan)
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_core.commands.query import run_query

        await run_query(
            "test query",
            workspace_path=vault,
            top_k=3,
            librarian_model_override=candidate,
            use_legacy=True,
        )

    assert ("librarian", candidate) in make_llm_calls, (
        f"Expected make_llm('librarian', model_override={candidate!r}); got calls: {make_llm_calls}"
    )


async def test_run_query_other_roles_unaffected(tmp_path: Path) -> None:
    """Single-role-swap: role_model_overrides={"librarian": X} must NOT override synthesizer.

    Confirms D-06 protocol: only the named role gets model_override=candidate;
    all others go through make_llm(role) with model_override=None.
    """
    librarian_candidate = "us.amazon.nova-pro-v1:0"
    vault = _make_vault(tmp_path)

    mock_resp = MagicMock()
    mock_resp.content = "The answer [[page]]"

    mock_fan = MagicMock()
    mock_fan.successes = [("page.md", "relevant excerpt")]
    mock_fan.errors = []

    fake_make_llm, make_llm_calls = _make_llm_factory(mock_resp)

    with (
        patch(
            "graph_wiki_core.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch("graph_wiki_core.commands.query.build_index"),
        patch(
            "graph_wiki_core.commands.query.bm25_query",
            return_value=(["page.md"], [1.0]),
        ),
        patch(
            "graph_wiki_core.commands.query.BedrockEmbeddings",
        ) as mock_embed_cls,
        patch(
            "graph_wiki_core.commands.query._cosine_search_sqlite",
            return_value=[("page.md", 0.9)],
        ),
        patch(
            "graph_wiki_core.commands.query.SubagentPool",
        ) as mock_pool_cls,
        patch(
            "graph_wiki_core.commands.query.make_llm",
            side_effect=fake_make_llm,
        ),
        patch("graph_wiki_core.commands.query.apply_guardrails", side_effect=lambda r, *a, **kw: r),
    ):
        mock_embed_cls.return_value.embed_query.return_value = [0.1] * 10
        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = AsyncMock(return_value=mock_fan)
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_core.commands.query import run_query

        await run_query(
            "test query",
            workspace_path=vault,
            top_k=3,
            role_model_overrides={"librarian": librarian_candidate},
            use_legacy=True,
        )

    # librarian got the candidate.
    assert ("librarian", librarian_candidate) in make_llm_calls, (
        f"Expected make_llm('librarian', model_override={librarian_candidate!r}); got calls: {make_llm_calls}"
    )
    # synthesizer went through make_llm WITHOUT the candidate (no override bleed).
    assert ("synthesizer", None) in make_llm_calls, (
        f"Expected synthesizer to use make_llm('synthesizer') with no override; got calls: {make_llm_calls}"
    )
    # The candidate appears exactly once — only for librarian.
    candidate_overrides = [c for c in make_llm_calls if c[1] == librarian_candidate]
    assert candidate_overrides == [("librarian", librarian_candidate)], (
        f"Librarian candidate bled into another role (D-06 violation); all make_llm calls: {make_llm_calls}"
    )


async def test_run_query_passes_query_orchestrator_role_override(tmp_path: Path) -> None:
    """Default run_query path forwards query_orchestrator overrides to the orchestrator."""
    from contextlib import ExitStack

    from graph_wiki_core.commands.query import run_query
    from graph_wiki_core.commands.query_orchestrator import OrchestratorOutput, QueryOrchestratorResult

    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "alpha.md").write_text("# Alpha")
    (wiki.parent / ".graph-wiki" / "bm25").mkdir(parents=True)
    (wiki.parent / ".graph-wiki" / "search.db").touch()
    captured = {}

    async def _fake_orchestrator(**kwargs):
        captured.update(kwargs["role_model_overrides"])
        return QueryOrchestratorResult(
            output=OrchestratorOutput(
                answer_markdown="No evidence.",
                citations=[],
                evidence=[],
                answer_evidence_map=[],
                worker_plan=(),
                worker_results=(),
                gaps=[],
                confidence="low",
            ),
            trace_metadata={"status": "ok"},
        )

    patches = [
        patch("graph_wiki_core.commands.query.resolve_wiki_and_repo", return_value=(wiki, tmp_path / "repo")),
        patch("graph_wiki_core.commands.query.bm25_query", return_value=(["alpha.md"], [1.0])),
        patch("graph_wiki_core.commands.query._cosine_search_sqlite", return_value=[("alpha.md", 0.5)]),
        patch("graph_wiki_core.commands.query.BedrockEmbeddings"),
        patch("graph_wiki_core.commands.query.graph_io.open_reader", side_effect=Exception("missing graph")),
        patch("graph_wiki_core.commands.query.run_query_orchestrator", new=AsyncMock(side_effect=_fake_orchestrator)),
    ]
    with ExitStack() as stack:
        for item in patches:
            stack.enter_context(item)
        await run_query(
            "q",
            workspace_path=wiki.parent,
            top_k=3,
            role_model_overrides={"query_orchestrator": "override-model"},
        )

    assert captured["query_orchestrator"] == "override-model"


async def test_run_query_default_path_preserves_librarian_override_precedence(tmp_path: Path) -> None:
    """role_model_overrides['librarian'] wins over deprecated librarian_model_override."""
    from contextlib import ExitStack

    from graph_wiki_core.commands.query import run_query
    from graph_wiki_core.commands.query_orchestrator import OrchestratorOutput, QueryOrchestratorResult

    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "alpha.md").write_text("# Alpha")
    (wiki.parent / ".graph-wiki" / "bm25").mkdir(parents=True)
    (wiki.parent / ".graph-wiki" / "search.db").touch()
    captured = {}

    async def _fake_orchestrator(**kwargs):
        captured.update(kwargs["role_model_overrides"])
        return QueryOrchestratorResult(
            output=OrchestratorOutput(
                answer_markdown="No evidence.",
                citations=[],
                evidence=[],
                answer_evidence_map=[],
                worker_plan=(),
                worker_results=(),
                gaps=[],
                confidence="low",
            ),
            trace_metadata={"status": "ok", "worker_batches": 0},
        )

    patches = [
        patch("graph_wiki_core.commands.query.resolve_wiki_and_repo", return_value=(wiki, tmp_path / "repo")),
        patch("graph_wiki_core.commands.query.bm25_query", return_value=(["alpha.md"], [1.0])),
        patch("graph_wiki_core.commands.query._cosine_search_sqlite", return_value=[("alpha.md", 0.5)]),
        patch("graph_wiki_core.commands.query.BedrockEmbeddings"),
        patch("graph_wiki_core.commands.query.graph_io.open_reader", side_effect=Exception("missing graph")),
        patch("graph_wiki_core.commands.query.run_query_orchestrator", new=AsyncMock(side_effect=_fake_orchestrator)),
    ]
    with ExitStack() as stack:
        for item in patches:
            stack.enter_context(item)
        await run_query(
            "q",
            workspace_path=wiki.parent,
            top_k=3,
            librarian_model_override="deprecated-model",
            role_model_overrides={"librarian": "explicit-model"},
        )

    assert captured["librarian"] == "explicit-model"


# ---------------------------------------------------------------------------
# Task 2: scan, lint, ingest model_override
# ---------------------------------------------------------------------------


async def test_run_scan_model_override(tmp_path: Path) -> None:
    """`run_scan(model_override=...)` builds the PROSE_REFRESHER LLM via
    make_llm("prose_refresher", model_override=candidate) — NOT
    make_llm("prose_refresher") with no override.
    """
    from types import SimpleNamespace

    from wiki_io.entity_writer import EntityWriteResult

    candidate = "us.amazon.nova-lite-v1:0"
    vault = _make_vault(tmp_path)
    # The contract opens its own DB-existence-guarded read-only conn; resolve is
    # patched to wiki=vault, so the graph DB resolves under vault.parent/.graph-wiki.
    from workspace_io.paths import graph_dir as _graph_dir

    _graph_dir(vault.parent).mkdir(parents=True, exist_ok=True)
    (_graph_dir(vault.parent) / "code.db").write_bytes(b"")

    prose_refresher_resp = MagicMock()
    prose_refresher_resp.content = "prose body"
    prose_refresher_resp.usage_metadata = None

    prose_refresher_instance = AsyncMock()
    prose_refresher_instance.ainvoke = AsyncMock(return_value=prose_refresher_resp)

    make_llm_calls: list[tuple[str, str | None]] = []

    def _fake_make_llm(role: str, *, model_override: str | None = None):
        make_llm_calls.append((role, model_override))
        return prose_refresher_instance

    # write_entities returns one URI needing a first fill so the prose_refresher
    # fan-out fires.
    needy_uri = "pkg:agent-research/foo"
    fake_write_result = EntityWriteResult(
        created=[needy_uri],
        updated=[],
        deleted=[],
        unchanged=[],
        needs_narrative={needy_uri},
        errors=[],
    )

    fake_node = SimpleNamespace(name="foo", path="packages/foo", kind="package", attrs={"uri": needy_uri})
    fake_list_fns = {"package": lambda conn: [fake_node]}

    # The split contract builds its worklist (prose_tasks) from on-disk entity
    # pages, so the mocked write_entities must leave a placeholder page behind.
    from wiki_io.entity_writer import short_filename as _short_filename

    def _write_entities_with_page(conn, wiki, admitted_kinds):
        page = wiki / "entities" / f"{_short_filename(needy_uri, frozenset())}.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            f"---\nuri: {needy_uri}\nkind: package\n---\n\n# foo\n\n"
            "## Narrative\n_(scanner will populate on next scan)_\n",
            encoding="utf-8",
        )
        return fake_write_result

    async def fake_run_all(items, task, **kwargs):
        result = MagicMock()
        successes = []
        for item in items:
            tr = await task(item)
            successes.append((item, tr.value))
        result.successes = successes
        result.errors = []
        return result

    from contextlib import ExitStack

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "graph_wiki_core.commands.scan.resolve_wiki_and_repo",
                return_value=(vault, None),
            )
        )
        stack.enter_context(
            patch(
                "graph_wiki_core.commands.scan.compute_state_gate",
                return_value={"allowed": True, "reason": "ok", "head_commit": "abc123"},
            )
        )
        # cg update + read_only_connect simulate a healthy graph so Step 9a runs.
        stack.enter_context(
            patch(
                "graph_wiki_core.commands.scan._cg_run_build",
                return_value=(0, "", ""),
            )
        )
        _reader_mock = MagicMock()
        _reader_mock.list_test_suites.return_value = []
        stack.enter_context(
            patch(
                "graph_wiki_core.commands.scan.open_reader",
                return_value=_reader_mock,
            )
        )
        # bedrock_provider (scan_bedrock.py) opens its own read-only reader —
        # patch it too so it doesn't trip over the placeholder code.db written above.
        stack.enter_context(
            patch(
                "graph_wiki_core.commands.scan_bedrock.open_reader",
                return_value=_reader_mock,
            )
        )
        # write_entities + prose pool + the (patched) refresh agent.
        stack.enter_context(
            patch(
                "graph_wiki_core.commands.scan.write_entities",
                side_effect=_write_entities_with_page,
            )
        )
        from graph_wiki_core.commands.scan_contract import ProseRefreshResult

        async def _fake_run_prose_refresh(*, llm, task, repo, wiki, graph_tools):
            return ProseRefreshResult(uri=task.uri, sections={"## Narrative": "prose body"})

        stack.enter_context(
            patch(
                "graph_wiki_core.commands.scan_bedrock.run_prose_refresh",
                side_effect=_fake_run_prose_refresh,
            )
        )
        stack.enter_context(patch("graph_wiki_core.commands.scan_bedrock.build_graph_tools", return_value=[]))
        stack.enter_context(
            patch(
                "graph_wiki_core.commands.scan._kind_list_fns",
                return_value=fake_list_fns,
            )
        )
        stack.enter_context(
            patch(
                "graph_wiki_core.commands.scan._compute_collision_set",
                return_value=frozenset(),
            )
        )
        stack.enter_context(
            patch(
                "graph_wiki_core.commands.scan.scanner_frontmatter_for_node",
                return_value={"uri": needy_uri, "kind": "package"},
            )
        )
        stack.enter_context(patch("graph_wiki_core.commands.scan.replace_prose_sections", return_value=[]))
        stack.enter_context(
            patch(
                "graph_wiki_core.commands.scan.generate_index",
                return_value=MagicMock(changed=False, bytes_written=0),
            )
        )
        mock_pool_cls = stack.enter_context(patch("graph_wiki_core.commands.scan_bedrock.SubagentPool"))
        stack.enter_context(
            patch(
                "graph_wiki_core.commands.scan_bedrock.make_llm",
                side_effect=_fake_make_llm,
            )
        )
        stack.enter_context(patch("graph_wiki_core.commands.scan.append_log"))
        stack.enter_context(patch("graph_wiki_core.commands.scan.update_index"))

        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = AsyncMock(side_effect=fake_run_all)
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_core.commands.scan import run_scan

        await run_scan(workspace_path=vault, model_override=candidate, no_file_map=True)

    # prose_refresher built via make_llm with the candidate override.
    assert ("prose_refresher", candidate) in make_llm_calls, (
        f"Expected make_llm('prose_refresher', model_override={candidate!r}); got: {make_llm_calls}"
    )
    # make_llm('prose_refresher') with NO override must NOT have happened.
    assert ("prose_refresher", None) not in make_llm_calls, (
        f"make_llm('prose_refresher') with no override should not be called when "
        f"model_override is set; got: {make_llm_calls}"
    )


async def test_run_lint_model_override(tmp_path: Path) -> None:
    """run_lint(model_override=...) builds the linter LLM via
    make_llm("linter", model_override=candidate) inside run_linter_group, NOT
    make_llm("linter") with no override.

    The pool.run_all mock invokes the provided task function so that
    run_linter_group actually executes and the make_llm call can be captured.
    """
    candidate = "us.amazon.nova-lite-v1:0"
    vault = _make_vault(tmp_path)

    linter_resp = MagicMock()
    linter_resp.content = ""

    linter_instance = AsyncMock()
    linter_instance.ainvoke = AsyncMock(return_value=linter_resp)

    make_llm_calls: list[tuple[str, str | None]] = []

    def _fake_make_llm(role: str, *, model_override: str | None = None):
        make_llm_calls.append((role, model_override))
        return linter_instance

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
            "graph_wiki_core.commands.lint.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch(
            "graph_wiki_core.commands.lint_mechanical.scan",
            return_value={
                "wiki": str(vault),
                "total_pages": 1,
                "orphans": [],
                "broken_links": [],
                "stale": [],
                "missing_frontmatter": [],
                "missing_tokens": [],
                "source_path_drift": [],
                "duplicate_titles": [],
                "unparseable_frontmatter": [],
                "log_gap": False,
                "code_drift": {},
                "file_map_drift": [],
                "package_sync_drift": [],
                "workflow_hints": [],
                "concept_kind": [],
                "dependency_layer": [],
                "obsidian_render_findings": [],
                "guidance_lint_findings": [],
                "work_lifecycle": {},
                "scanner_heading_drift": [],
                "pages": non_empty_pages,
                "index_pages": {},
            },
        ),
        patch(
            "graph_wiki_core.commands.lint.SubagentPool",
        ) as mock_pool_cls,
        patch(
            "graph_wiki_core.commands.lint.make_llm",
            side_effect=_fake_make_llm,
        ),
    ):
        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = _mock_run_all
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_core.commands.lint import run_lint

        await run_lint(workspace_path=vault, model_override=candidate)

    assert ("linter", candidate) in make_llm_calls, (
        f"Expected make_llm('linter', model_override={candidate!r}); got: {make_llm_calls}"
    )
    assert ("linter", None) not in make_llm_calls, (
        f"make_llm('linter') with no override should not be called when model_override is set; got: {make_llm_calls}"
    )


async def test_run_ingest_source_model_override(tmp_path: Path) -> None:
    """run_ingest_source(source_path, model_override=...) builds the ingestor LLM
    via make_llm("ingestor", model_override=candidate), NOT make_llm("ingestor")
    with no override."""
    candidate = "us.amazon.nova-lite-v1:0"
    vault = _make_vault(tmp_path)
    source = tmp_path / "test_source.py"
    source.write_text("def hello(): pass\n")

    ingestor_resp = MagicMock()
    ingestor_resp.content = "---\npage_type: concept\ntarget_slug: hello-func\n---\n# Hello\n"

    ingestor_instance = AsyncMock()
    ingestor_instance.ainvoke = AsyncMock(return_value=ingestor_resp)

    make_llm_calls: list[tuple[str, str | None]] = []

    def _fake_make_llm(role: str, *, model_override: str | None = None):
        make_llm_calls.append((role, model_override))
        return ingestor_instance

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
            "graph_wiki_core.commands.ingest.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch(
            "graph_wiki_core.commands.ingest.make_llm",
            side_effect=_fake_make_llm,
        ),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        from graph_wiki_core.commands.ingest import run_ingest_source

        await run_ingest_source(source_path=source, workspace_path=vault, model_override=candidate)

    assert ("ingestor", candidate) in make_llm_calls, (
        f"Expected make_llm('ingestor', model_override={candidate!r}); got: {make_llm_calls}"
    )
    assert ("ingestor", None) not in make_llm_calls, (
        f"make_llm('ingestor') with no override should not be called when model_override is set; got: {make_llm_calls}"
    )


# ---------------------------------------------------------------------------
# Task 3: role_backend_overrides (2026-06-24: gateway-aware model sweep)
# ---------------------------------------------------------------------------


async def test_run_query_synthesizer_backend_override(tmp_path: Path) -> None:
    """role_backend_overrides={"synthesizer": "vercel"} routes the synthesizer LLM
    through make_llm("synthesizer", ..., backend_override="vercel")."""
    candidate = "openai/gpt-4o"
    vault = _make_vault(tmp_path)

    mock_resp = MagicMock()
    mock_resp.content = "The answer [[page]]"

    mock_fan = MagicMock()
    mock_fan.successes = [("page.md", "relevant excerpt")]
    mock_fan.errors = []

    calls: list[tuple[str, str | None, str | None]] = []

    def _fake_make_llm(role: str, *, model_override: str | None = None, backend_override: str | None = None):
        calls.append((role, model_override, backend_override))
        inst = AsyncMock()
        inst.ainvoke = AsyncMock(return_value=mock_resp)
        inst.bind_tools = MagicMock(return_value=inst)
        return inst

    with (
        patch("graph_wiki_core.commands.query.resolve_wiki_and_repo", return_value=(vault, None)),
        patch("graph_wiki_core.commands.query.build_index"),
        patch("graph_wiki_core.commands.query.bm25_query", return_value=(["page.md"], [1.0])),
        patch("graph_wiki_core.commands.query.BedrockEmbeddings") as mock_embed_cls,
        patch("graph_wiki_core.commands.query._cosine_search_sqlite", return_value=[("page.md", 0.9)]),
        patch("graph_wiki_core.commands.query.SubagentPool") as mock_pool_cls,
        patch("graph_wiki_core.commands.query.make_llm", side_effect=_fake_make_llm),
        patch("graph_wiki_core.commands.query.apply_guardrails", side_effect=lambda r, *a, **kw: r),
    ):
        mock_embed_cls.return_value.embed_query.return_value = [0.1] * 10
        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = AsyncMock(return_value=mock_fan)
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_core.commands.query import run_query

        await run_query(
            "test query",
            workspace_path=vault,
            top_k=3,
            role_model_overrides={"synthesizer": candidate},
            role_backend_overrides={"synthesizer": "vercel"},
            use_legacy=True,
        )

    assert ("synthesizer", candidate, "vercel") in calls, (
        f"Expected make_llm('synthesizer', model_override={candidate!r}, backend_override='vercel'); got: {calls}"
    )
    assert ("librarian", None, None) in calls, (
        f"Expected librarian to use make_llm('librarian') with no overrides; got: {calls}"
    )


async def test_run_query_code_reader_backend_override(tmp_path: Path) -> None:
    """role_backend_overrides={"code_reader": "vercel"} routes the code_reader LLM
    through make_llm("code_reader", ..., backend_override="vercel") when the
    vault-thin code fallback fires."""
    candidate = "openai/gpt-4o-mini"
    vault = _make_vault(tmp_path)

    mock_fan_empty = MagicMock()
    mock_fan_empty.successes = []
    mock_fan_empty.errors = []

    mock_code_fan = MagicMock()
    mock_code_fan.successes = []
    mock_code_fan.errors = []

    mock_resp = MagicMock()
    mock_resp.content = "code answer"

    calls: list[tuple[str, str | None, str | None]] = []

    def _fake_make_llm(role: str, *, model_override: str | None = None, backend_override: str | None = None):
        calls.append((role, model_override, backend_override))
        inst = AsyncMock()
        inst.ainvoke = AsyncMock(return_value=mock_resp)
        inst.bind_tools = MagicMock(return_value=inst)
        return inst

    with (
        patch("graph_wiki_core.commands.query.resolve_wiki_and_repo", return_value=(vault, None)),
        patch("graph_wiki_core.commands.query.build_index"),
        patch("graph_wiki_core.commands.query.bm25_query", return_value=(["page.md"], [1.0])),
        patch("graph_wiki_core.commands.query.BedrockEmbeddings") as mock_embed_cls,
        patch("graph_wiki_core.commands.query._cosine_search_sqlite", return_value=[("page.md", 0.9)]),
        patch("graph_wiki_core.commands.query.SubagentPool") as mock_pool_cls,
        patch("graph_wiki_core.commands.query.make_llm", side_effect=_fake_make_llm),
        patch("graph_wiki_core.commands.query.apply_guardrails", side_effect=lambda r, *a, **kw: r),
        patch("graph_wiki_core.commands.query._resolve_repo_root", return_value=tmp_path),
    ):
        mock_embed_cls.return_value.embed_query.return_value = [0.1] * 10
        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = AsyncMock(side_effect=[mock_fan_empty, mock_code_fan])
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_core.commands.query import run_query

        await run_query(
            "How is _StdoutGuard implemented?",
            workspace_path=vault,
            top_k=3,
            role_model_overrides={"code_reader": candidate},
            role_backend_overrides={"code_reader": "vercel"},
            use_legacy=True,
        )

    assert ("code_reader", candidate, "vercel") in calls, (
        f"Expected make_llm('code_reader', model_override={candidate!r}, backend_override='vercel'); got: {calls}"
    )


async def test_run_query_librarian_backend_override(tmp_path: Path) -> None:
    """role_backend_overrides={"librarian": "vercel"} routes the librarian LLM
    through make_llm("librarian", ..., backend_override="vercel")."""
    candidate = "openai/gpt-4o-mini"
    vault = _make_vault(tmp_path)

    mock_resp = MagicMock()
    mock_resp.content = "The answer [[page]]"

    mock_fan = MagicMock()
    mock_fan.successes = [("page.md", "relevant excerpt")]
    mock_fan.errors = []

    calls: list[tuple[str, str | None, str | None]] = []

    def _fake_make_llm(role: str, *, model_override: str | None = None, backend_override: str | None = None):
        calls.append((role, model_override, backend_override))
        inst = AsyncMock()
        inst.ainvoke = AsyncMock(return_value=mock_resp)
        inst.bind_tools = MagicMock(return_value=inst)
        return inst

    with (
        patch("graph_wiki_core.commands.query.resolve_wiki_and_repo", return_value=(vault, None)),
        patch("graph_wiki_core.commands.query.build_index"),
        patch("graph_wiki_core.commands.query.bm25_query", return_value=(["page.md"], [1.0])),
        patch("graph_wiki_core.commands.query.BedrockEmbeddings") as mock_embed_cls,
        patch("graph_wiki_core.commands.query._cosine_search_sqlite", return_value=[("page.md", 0.9)]),
        patch("graph_wiki_core.commands.query.SubagentPool") as mock_pool_cls,
        patch("graph_wiki_core.commands.query.make_llm", side_effect=_fake_make_llm),
        patch("graph_wiki_core.commands.query.apply_guardrails", side_effect=lambda r, *a, **kw: r),
    ):
        mock_embed_cls.return_value.embed_query.return_value = [0.1] * 10
        mock_pool_instance = MagicMock()
        mock_pool_instance.run_all = AsyncMock(return_value=mock_fan)
        mock_pool_cls.return_value = mock_pool_instance

        from graph_wiki_core.commands.query import run_query

        await run_query(
            "test query",
            workspace_path=vault,
            top_k=3,
            role_model_overrides={"librarian": candidate},
            role_backend_overrides={"librarian": "vercel"},
            use_legacy=True,
        )

    assert ("librarian", candidate, "vercel") in calls, (
        f"Expected make_llm('librarian', model_override={candidate!r}, backend_override='vercel'); got: {calls}"
    )
    assert ("synthesizer", None, None) in calls, (
        f"Expected synthesizer to use make_llm('synthesizer') with no overrides; got: {calls}"
    )
