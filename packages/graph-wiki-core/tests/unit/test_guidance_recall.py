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


async def test_drop_low_all_low_collapses_to_empty_and_no_bundle():
    pages = [_page("python/retry", "python", ["backoff"])]
    reply = "- slug: python/retry\n  relevance: low\n  reason: irrelevant\n"
    ranked, assembled, _warnings = await recall_and_rank(
        pages,
        "add a retry with backoff",
        [],
        drop_low=True,
        assemble=True,
        make_llm_fn=lambda *a, **k: _FakeLLM(reply),
    )
    assert ranked == []
    assert assembled is None


async def test_drop_low_keeps_only_non_low_entries():
    pages = [
        _page("python/retry", "python", ["backoff"], body="## retry body"),
        _page("python/cache", "python", ["cache"], body="## cache body"),
    ]
    reply = (
        "- slug: python/retry\n  relevance: high\n  reason: matches\n"
        "- slug: python/cache\n  relevance: low\n  reason: nope\n"
    )
    ranked, assembled, _warnings = await recall_and_rank(
        pages,
        "add a retry with backoff",
        [],
        drop_low=True,
        assemble=True,
        make_llm_fn=lambda *a, **k: _FakeLLM(reply),
    )
    assert [r.slug for r in ranked] == ["python/retry"]
    assert assembled is not None
    assert "retry body" in assembled
    assert "cache body" not in assembled


async def test_drop_low_with_force_recall_only_preserves_lows():
    pages = [_page("python/retry", "python", ["backoff"])]
    ranked, _assembled, _warnings = await recall_and_rank(
        pages,
        "add a retry with backoff",
        [],
        drop_low=True,
        force_recall_only=True,
        make_llm_fn=lambda *a, **k: _FakeLLM("ignored"),
    )
    # recall-only stamps every entry "low" deterministically; drop_low must not
    # erase them (guards `--no-rank`).
    assert [r.slug for r in ranked] == ["python/retry"]
    assert ranked[0].relevance == "low"


async def test_default_drop_low_false_preserves_lows():
    pages = [_page("python/retry", "python", ["backoff"])]
    reply = "- slug: python/retry\n  relevance: low\n  reason: weak\n"
    ranked, _assembled, _warnings = await recall_and_rank(
        pages,
        "add a retry with backoff",
        [],
        make_llm_fn=lambda *a, **k: _FakeLLM(reply),
    )
    # default drop_low=False protects guidance_suggest's behavior.
    assert [r.slug for r in ranked] == ["python/retry"]
    assert ranked[0].relevance == "low"
