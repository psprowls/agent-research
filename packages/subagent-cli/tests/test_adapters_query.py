import pytest
from graph_io import store
from subagent_cli.adapters.base import RunContext
from subagent_cli.adapters.guidance_orchestrator import GuidanceOrchestratorAdapter
from subagent_cli.adapters.librarian import LibrarianAdapter
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
