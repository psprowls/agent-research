from __future__ import annotations

from pathlib import Path

import yaml
from graph_wiki_core.commands.guidance_suggest import run_guidance_suggest


def _write_guidance(ws: Path, topic: str, slug: str, fm: dict, body: str) -> None:
    d = ws / "wiki" / "guidance" / topic
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body, encoding="utf-8")


def _fm(topic: str, kws: list[str], role: list[str] | None = None) -> dict:
    fm = {
        "title": "T",
        "category": "guidance",
        "summary": "s",
        "topic": topic,
        "applies_when": "w",
        "impact": "high",
        "updated": "2026-06-28",
        "tokens": 0,
        "tags": [topic],
        "triggers": {"globs": [], "keywords": kws, "entities": []},
    }
    if role is not None:
        fm["role"] = role
    return fm


class _FakeResp:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage_metadata = None


class _FakeLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def ainvoke(self, messages):  # noqa: ANN001
        return _FakeResp(self._reply)


# Rank every slug high; the role filter decides which actually reach the ranker
# (parse drops any slug not in the candidate slate, so impl-only never appears).
_REPLY = (
    "- slug: python/review-only\n  relevance: high\n  reason: matches\n"
    "- slug: python/dual\n  relevance: high\n  reason: matches\n"
    "- slug: python/impl-only\n  relevance: high\n  reason: matches\n"
)


async def test_suggest_role_wires_role_filter_through_run_guidance_suggest(tmp_path: Path):
    """Wiring smoke test: `role=` passed to run_guidance_suggest reaches the
    filter_by_role step and actually drops non-matching candidates. The
    filter_by_role case matrix itself (none/agnostic/matching/invalid) is
    covered directly against the pure function in test_next_guidance.py."""
    ws = tmp_path / "ws"
    _write_guidance(ws, "python", "review-only", _fm("python", ["backoff"], ["review"]), "## Guidance\nR.\n")
    _write_guidance(ws, "python", "impl-only", _fm("python", ["backoff"], ["implement"]), "## Guidance\nI.\n")
    _write_guidance(ws, "python", "dual", _fm("python", ["backoff"]), "## Guidance\nD.\n")

    result = await run_guidance_suggest(
        "add retry backoff",
        workspace_path=ws,
        role="review",
        make_llm_fn=lambda *a, **k: _FakeLLM(_REPLY),
    )
    slugs = {r.slug for r in result.ranked}
    assert "python/review-only" in slugs
    assert "python/dual" in slugs
    assert "python/impl-only" not in slugs
