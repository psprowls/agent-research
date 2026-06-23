from __future__ import annotations

from graph_wiki_core.commands.guidance_recall import recall_and_rank
from graph_wiki_core.commands.guidance_signals import GuidancePage


class _FakeResp:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage_metadata = None


class _FakeLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def ainvoke(self, messages):
        return _FakeResp(self._reply)


def _page(slug: str, topic: str, kws: list[str], body: str = "## body") -> GuidancePage:
    return GuidancePage(
        slug=slug,
        topic=topic,
        tags=[topic],
        keywords=kws,
        entities=[],
        globs=[],
        summary="s",
        applies_when="w",
        impact="high",
        guidance_body=body,
    )


async def test_force_recall_only_skips_llm_and_warns():
    pages = [_page("python/retry", "python", ["backoff"])]
    ranked, assembled, warnings = await recall_and_rank(
        pages,
        "add a retry with backoff",
        [],
        force_recall_only=True,
        recall_only_reason="ranking is deterministic (--no-rank)",
        make_llm_fn=lambda *a, **k: _FakeLLM("- slug: python/retry\n  relevance: high\n  reason: r\n"),
    )
    assert [r.slug for r in ranked] == ["python/retry"]
    assert ranked[0].relevance == "low"  # recall-only always returns "low"
    assert any("deterministic" in w for w in warnings)
    assert assembled is None


async def test_llm_rank_path_returns_ranked():
    pages = [_page("python/retry", "python", ["backoff"])]
    reply = "- slug: python/retry\n  relevance: high\n  reason: matches\n"
    ranked, _assembled, warnings = await recall_and_rank(
        pages,
        "add a retry with backoff",
        [],
        make_llm_fn=lambda *a, **k: _FakeLLM(reply),
    )
    assert ranked[0].slug == "python/retry"
    assert ranked[0].relevance == "high"
    assert warnings == []


async def test_empty_slate_returns_empty():
    ranked, assembled, warnings = await recall_and_rank(
        [], "nothing here", [], make_llm_fn=lambda *a, **k: _FakeLLM("[]")
    )
    assert ranked == []
    assert assembled is None
