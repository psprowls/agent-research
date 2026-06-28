from __future__ import annotations

import json
import sqlite3

from graph_wiki_core.commands.guidance_recall import recall_and_rank
from graph_wiki_core.commands.guidance_signals import (
    GuidancePage,
    compute_candidates,
    resolve_path_contexts,
)
from guidance_io.index_store import GuidanceIndex


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


def _seed_pkg_graph(nodes, edges):
    """In-memory graph: nodes = (id, kind, name, path, attrs_json, uri),
    edges = (src, dst, kind). Returns an open sqlite3 connection.
    Deliberately does NOT set row_factory — matches production read_only_connect
    (plain tuple rows), so the package branch is exercised under real conditions."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE nodes (id INTEGER PRIMARY KEY, kind TEXT, name TEXT, path TEXT, "
        "line INTEGER, attrs_json TEXT, uri TEXT)"
    )
    conn.execute("CREATE TABLE edges (src INTEGER, dst INTEGER, kind TEXT, attrs_json TEXT)")
    for nid, kind, name, path, attrs_json, uri in nodes:
        conn.execute(
            "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) VALUES (?, ?, ?, ?, NULL, ?, ?)",
            (nid, kind, name, path, attrs_json, uri),
        )
    for src, dst, kind in edges:
        conn.execute(
            "INSERT INTO edges (src, dst, kind, attrs_json) VALUES (?, ?, ?, NULL)",
            (src, dst, kind),
        )
    conn.commit()
    return conn


def test_dir_affects_recalls_via_entity_and_language(tmp_path) -> None:
    # End-to-end recall parity: a *directory* affects ("packages/p") resolves to its
    # enclosing package (stem "pkg_p", language python) and must fire the `entity`
    # signal through compute_candidates — not message-only. Pre-Task-3 the directory
    # affects produced no package stem, so `entity` never fired and this would FAIL.
    conn = _seed_pkg_graph(
        nodes=[
            (1, "package", "p", "packages/p", None, "pkg:o/r/p"),
            (2, "file", "a.py", "packages/p/a.py", json.dumps({"language": "python"}), None),
        ],
        edges=[(1, 2, "contains")],
    )
    py_page = GuidancePage(
        slug="python/async",
        topic="python",
        tags=[],
        keywords=[],
        entities=["pkg_p"],  # the package stem the dir resolves to
        globs=[],
        summary="",
        applies_when="",
        impact="medium",
        guidance_body="",
        language="python",
    )
    # Same entity stem, but a non-matching language: the language pre-filter must
    # suppress this page entirely (context langs are {python}), so its `entity`
    # signal can never fire even though it lists pkg_p.
    swift_page = GuidancePage(
        slug="swift/ui",
        topic="swift",
        tags=[],
        keywords=[],
        entities=["pkg_p"],
        globs=[],
        summary="",
        applies_when="",
        impact="medium",
        guidance_body="",
        language="swift",
    )
    try:
        ctxs = resolve_path_contexts(["packages/p"], conn, tmp_path, GuidanceIndex(files={}))
        cands = compute_candidates([py_page, swift_page], "", ctxs, 5)
    finally:
        conn.close()

    py = next((c for c in cands if c.page.slug == "python/async"), None)
    sw = next((c for c in cands if c.page.slug == "swift/ui"), None)
    assert py is not None and "entity" in py.signals_fired  # python page fires `entity`
    # swift page is language-filtered: even though it lists pkg_p, entity must NOT fire for it
    assert sw is None or "entity" not in sw.signals_fired
