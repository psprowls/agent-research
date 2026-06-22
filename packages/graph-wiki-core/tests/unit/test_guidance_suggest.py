from __future__ import annotations

from pathlib import Path

import yaml
from graph_wiki_core.commands.guidance_suggest import run_guidance_suggest


def _write_page(ws: Path, topic: str, slug: str, fm: dict, body: str) -> None:
    d = ws / "wiki" / "guidance" / topic
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body, encoding="utf-8")


def _fm(topic: str, tags: list[str], kws: list[str]) -> dict:
    return {
        "title": "T",
        "category": "guidance",
        "summary": "s",
        "topic": topic,
        "applies_when": "w",
        "impact": "high",
        "updated": "2026-06-22",
        "tokens": 0,
        "tags": tags,
        "triggers": {"globs": [], "keywords": kws, "entities": []},
    }


class _FakeResp:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage_metadata = None


class _FakeLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def ainvoke(self, messages):  # noqa: ANN001
        return _FakeResp(self._reply)


async def test_no_pages_returns_empty(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "wiki" / "guidance").mkdir(parents=True)
    result = await run_guidance_suggest("add retry", workspace_path=ws, make_llm_fn=lambda *a, **k: _FakeLLM("[]"))
    assert result.ranked == []


async def test_ranks_and_joins_signals(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    _write_page(ws, "python", "retry", _fm("python", ["retry"], ["backoff"]), "## Guidance\nRetry it.\n")
    reply = "- slug: python/retry\n  relevance: high\n  reason: matches\n"
    result = await run_guidance_suggest(
        "add a retry with backoff",
        workspace_path=ws,
        make_llm_fn=lambda *a, **k: _FakeLLM(reply),
    )
    assert len(result.ranked) == 1
    r = result.ranked[0]
    assert r.slug == "python/retry"
    assert r.relevance == "high"
    assert "message" in r.signals_fired
    assert result.index_present is False
    assert any("scan" in w for w in result.warnings)


async def test_assemble_respects_budget(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    long_body = "## Guidance\n" + ("word " * 500) + "\n"
    _write_page(ws, "python", "retry", _fm("python", ["retry"], ["backoff"]), long_body)
    reply = "- slug: python/retry\n  relevance: high\n  reason: matches\n"
    result = await run_guidance_suggest(
        "add a retry with backoff",
        workspace_path=ws,
        assemble=True,
        budget=50,
        make_llm_fn=lambda *a, **k: _FakeLLM(reply),
    )
    from graph_io.tokens import count_tokens

    assert result.assembled is not None
    assert count_tokens(result.assembled) <= 50
