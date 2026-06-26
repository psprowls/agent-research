from unittest.mock import MagicMock

import graph_wiki_core.commands.query as query_mod
import pytest
from graph_io import store
from graph_wiki_core.commands.query import PreparedQueryRetrieval
from graph_wiki_core.commands.query_orchestrator import (
    OrchestratorOutput,
    QueryOrchestratorResult,
)
from subagent_cli.adapters import ADAPTERS, LOOP_ADAPTERS
from subagent_cli.adapters.base import LoopAdapter, RunContext
from subagent_cli.adapters.guidance_orchestrator import GuidanceOrchestratorAdapter
from subagent_cli.adapters.librarian import LibrarianAdapter
from subagent_cli.adapters.query_orchestrator import QueryOrchestratorLoopAdapter
from subagent_cli.adapters.synthesizer import SynthesizerAdapter


def _ctx(tmp_path):
    db = tmp_path / "code.db"
    conn = store.connect(db, create=True)
    conn.close()
    (tmp_path / "wiki").mkdir()
    return RunContext(workspace=tmp_path, repo_root=tmp_path, wiki=tmp_path / "wiki", db_path=db)


@pytest.mark.parametrize(
    "adapter",
    [GuidanceOrchestratorAdapter(), LibrarianAdapter(), SynthesizerAdapter()],
)
def test_query_adapters_have_no_worklist(adapter, tmp_path):
    ctx = _ctx(tmp_path)
    with pytest.raises(ValueError, match="single-query"):
        adapter.items(ctx)
    ctx.close()


async def test_guidance_orchestrator_empty_corpus_raises(tmp_path):
    ctx = _ctx(tmp_path)  # no wiki/guidance/*/*.md → no pages
    adapter = GuidanceOrchestratorAdapter()
    with pytest.raises(RuntimeError, match="guidance"):
        await adapter.prepare(ctx, "how do I add a retry?")
    ctx.close()


async def test_synthesizer_excerpts_mode_skips_retrieval(tmp_path):
    ctx = _ctx(tmp_path)
    excerpts = tmp_path / "ex.txt"
    excerpts.write_text("[entities/pkg_foo]\nFoo does X. `foo.py:10`")
    adapter = SynthesizerAdapter(excerpts_path=excerpts)
    prepared = await adapter.prepare(ctx, "what does foo do?")
    assert prepared.parse is None
    assert "Librarian excerpts:" in prepared.human
    assert "Foo does X." in prepared.human
    assert "what does foo do?" in prepared.human
    assert prepared.note and "skipped" in prepared.note
    ctx.close()


def _canned_output():
    return OrchestratorOutput(
        answer_markdown="## Answer\nFoo does X.",
        citations=["entities/pkg_foo.md"],
        evidence=[],
        answer_evidence_map=[],
        worker_plan=(),
        worker_results=(),
        gaps=[],
        confidence="high",
    )


def test_registry_split():
    assert "query_orchestrator" in LOOP_ADAPTERS
    assert "query_orchestrator" not in ADAPTERS
    assert isinstance(QueryOrchestratorLoopAdapter(), LoopAdapter)


def test_top_k_out_of_range_raises(tmp_path):
    ctx = _ctx(tmp_path)
    adapter = QueryOrchestratorLoopAdapter(top_k=2)
    import pytest

    with pytest.raises(RuntimeError, match="top_k"):
        import asyncio

        asyncio.run(adapter.run(ctx, "q"))
    ctx.close()


async def test_input_assembly_and_mapping(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path)
    wiki = ctx.wiki

    monkeypatch.setattr(
        query_mod,
        "_prepare_query_retrieval",
        lambda query, ws, top_k: PreparedQueryRetrieval(
            wiki=wiki,
            repo_root=ctx.repo_root,
            top_pages=["entities/pkg_foo.md", "entities/pkg_bar.md"],
            search_scores={
                "entities/pkg_foo.md": {"bm25": 1.0, "embed": 0.5, "rrf": 0.9},
                "entities/pkg_bar.md": {"bm25": 0.2, "embed": 0.1, "rrf": 0.3},
            },
        ),
    )
    monkeypatch.setattr(query_mod, "_load_query_graph_tools", lambda ws: (None, []))
    monkeypatch.setattr(query_mod, "_read_candidate_excerpt", lambda w, p, **k: f"excerpt::{p}")

    captured = {}

    async def fake_orch(**kwargs):
        captured.update(kwargs)
        return QueryOrchestratorResult(
            output=_canned_output(),
            trace_metadata={"status": "ok", "worker_batches": 2, "graph_tools_available": False},
        )

    monkeypatch.setattr(query_mod, "run_query_orchestrator", fake_orch)

    outcome = await QueryOrchestratorLoopAdapter(top_k=5).run(ctx, "what does foo do?")

    cands = captured["initial_candidates"]
    assert [c.path for c in cands] == ["entities/pkg_foo.md", "entities/pkg_bar.md"]
    assert cands[0].score == 0.9 and cands[1].score == 0.3
    assert cands[0].excerpt == "excerpt::entities/pkg_foo.md"
    assert captured["role_model_overrides"] is None
    assert captured["trace_dir"].name == "traces"
    assert outcome.answer == "## Answer\nFoo does X."
    assert outcome.trace_metadata["status"] == "ok"
    assert outcome.structured["confidence"] == "high"
    assert outcome.role == "query_orchestrator"
    ctx.close()


async def test_graph_conn_closed_on_orchestrator_failure(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path)
    wiki = ctx.wiki
    conn = MagicMock()

    monkeypatch.setattr(
        query_mod,
        "_prepare_query_retrieval",
        lambda query, ws, top_k: PreparedQueryRetrieval(
            wiki=wiki,
            repo_root=ctx.repo_root,
            top_pages=["entities/pkg_foo.md", "entities/pkg_bar.md"],
            search_scores={
                "entities/pkg_foo.md": {"bm25": 1.0, "embed": 0.5, "rrf": 0.9},
                "entities/pkg_bar.md": {"bm25": 0.2, "embed": 0.1, "rrf": 0.3},
            },
        ),
    )
    monkeypatch.setattr(query_mod, "_load_query_graph_tools", lambda ws: (conn, []))
    monkeypatch.setattr(query_mod, "_read_candidate_excerpt", lambda w, p, **k: f"excerpt::{p}")

    async def fake_orch(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(query_mod, "run_query_orchestrator", fake_orch)

    with pytest.raises(RuntimeError, match="boom"):
        await QueryOrchestratorLoopAdapter(top_k=5).run(ctx, "q")

    conn.close.assert_called_once()
    ctx.close()
