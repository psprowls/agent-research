from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import yaml
from graph_io.handle import GraphReader
from graph_wiki_core.commands.guidance_signals import (
    GuidancePage,
    PathContext,
    _derive_path_languages,
    compute_candidates,
    load_guidance_pages,
    resolve_path_contexts,
)
from guidance_io.index_store import GuidanceIndex, IndexEntry


def _write_page(ws: Path, topic: str, slug: str, fm: dict, body: str = "## Guidance\nDo X.\n") -> None:
    d = ws / "wiki" / "guidance" / topic
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body, encoding="utf-8")


def test_load_pages_extracts_fields(tmp_path: Path) -> None:
    fm = {
        "title": "Retry remote calls",
        "category": "guidance",
        "summary": "Add retry/backoff.",
        "topic": "python",
        "applies_when": "calling a flaky remote service",
        "impact": "high",
        "updated": "2026-06-22",
        "tokens": 0,
        "tags": ["retry"],
        "triggers": {
            "globs": ["**/pool.py"],
            "keywords": ["ainvoke", "backoff"],
            "entities": ["[[entities/pkg_subagent_runtime]]"],
        },
    }
    _write_page(tmp_path, "python", "retry-patterns", fm)
    pages = load_guidance_pages(tmp_path)
    assert len(pages) == 1
    p = pages[0]
    assert p.slug == "python/retry-patterns"
    assert p.topic == "python"
    assert p.tags == ["retry"]
    assert p.keywords == ["ainvoke", "backoff"]
    assert p.entities == ["pkg_subagent_runtime"]
    assert p.globs == ["**/pool.py"]
    assert "Do X." in p.guidance_body


def _page(**kw) -> GuidancePage:
    base = dict(
        slug="python/p",
        topic="python",
        tags=[],
        keywords=[],
        entities=[],
        globs=[],
        summary="",
        applies_when="",
        impact="medium",
        guidance_body="",
        language=None,
    )
    base.update(kw)
    return GuidancePage(**base)


def _ctx(rel_path: str, language: str | None) -> PathContext:
    return PathContext(
        rel_path=rel_path,
        content="",
        package_stem=None,
        index_topics=[],
        index_tags=[],
        languages={language} if language else set(),
    )


def test_glob_signal_fires() -> None:
    page = _page(globs=["**/pool.py"])
    ctx = PathContext(
        rel_path="packages/x/src/x/pool.py",
        content="",
        package_stem=None,
        index_topics=[],
        index_tags=[],
    )
    cands = compute_candidates([page], message="", path_contexts=[ctx], k=5)
    fired = next(c for c in cands if c.page.slug == "python/p")
    assert "globs" in fired.signals_fired


def test_keyword_and_entity_and_index_signals() -> None:
    page = _page(
        keywords=["ainvoke"],
        entities=["pkg_x"],
        tags=["retry"],
    )
    ctx = PathContext(
        rel_path="packages/x/src/x/pool.py",
        content="result = await llm.ainvoke(msgs)",
        package_stem="pkg_x",
        index_topics=["python"],
        index_tags=["retry"],
    )
    cands = compute_candidates([page], message="", path_contexts=[ctx], k=5)
    fired = next(c for c in cands if c.page.slug == "python/p")
    assert {"keywords", "entity", "index"} <= set(fired.signals_fired)


def test_message_signal_without_paths() -> None:
    page = _page(tags=["retry"], keywords=["backoff"])
    cands = compute_candidates([page], message="add a retry with backoff", path_contexts=[], k=5)
    fired = next(c for c in cands if c.page.slug == "python/p")
    assert "message" in fired.signals_fired
    assert fired.base_score > 0


def test_topup_reaches_k() -> None:
    pages = [_page(slug=f"python/p{i}", summary=f"page {i}") for i in range(8)]
    # message matches none strongly; top-up should still return k candidates
    cands = compute_candidates(pages, message="zzz", path_contexts=[], k=5)
    assert len(cands) == 5


def test_loader_populates_workflow_field(tmp_path: Path) -> None:
    d = tmp_path / "wiki" / "guidance" / "python"
    d.mkdir(parents=True)
    fm = {
        "title": "T",
        "category": "guidance",
        "summary": "s",
        "topic": "python",
        "applies_when": "w",
        "impact": "high",
        "updated": "2026-06-23",
        "tokens": 0,
        "workflow": ["design", "plan"],
    }
    (d / "with-wf.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n## Guidance\nDo X.\n",
        encoding="utf-8",
    )
    fm_no = {**fm}
    del fm_no["workflow"]
    (d / "no-wf.md").write_text(
        "---\n" + yaml.safe_dump(fm_no, sort_keys=False) + "---\n\n## Guidance\nDo Y.\n",
        encoding="utf-8",
    )

    pages = {p.slug: p for p in load_guidance_pages(tmp_path)}
    assert pages["python/with-wf"].workflow == ["design", "plan"]
    assert pages["python/no-wf"].workflow == []


def test_load_pages_reads_role(tmp_path: Path) -> None:
    fm = {
        "title": "Review checklist",
        "category": "guidance",
        "summary": "Look for N+1s.",
        "topic": "python",
        "applies_when": "reviewing a diff",
        "impact": "high",
        "updated": "2026-06-28",
        "tokens": 0,
        "tags": ["review"],
        "role": ["review"],
    }
    _write_page(tmp_path, "python", "review-checklist", fm)
    pages = load_guidance_pages(tmp_path)
    assert len(pages) == 1
    assert pages[0].role == ["review"]


def test_load_pages_role_defaults_empty(tmp_path: Path) -> None:
    fm = {
        "title": "Dual use",
        "category": "guidance",
        "summary": "Applies anywhere.",
        "topic": "python",
        "applies_when": "always",
        "impact": "medium",
        "updated": "2026-06-28",
        "tokens": 0,
        "tags": ["python"],
    }
    _write_page(tmp_path, "python", "dual-use", fm)
    pages = load_guidance_pages(tmp_path)
    assert pages[0].role == []


def test_index_signal_fires_on_alias_tag(tmp_path: Path) -> None:
    # tags.yaml maps alias "retries" -> canonical "retry"; the page is tagged with
    # the alias form, while a working file was indexed under the canonical form.
    (tmp_path / "wiki" / "guidance").mkdir(parents=True)
    (tmp_path / "wiki" / "guidance" / "tags.yaml").write_text(
        yaml.safe_dump({"tags": ["retry"], "aliases": {"retries": "retry"}}), encoding="utf-8"
    )
    fm = {
        "title": "T",
        "category": "guidance",
        "summary": "s",
        "topic": "python",
        "applies_when": "w",
        "impact": "high",
        "updated": "2026-06-22",
        "tokens": 0,
        "tags": ["retries"],  # alias form
    }
    _write_page(tmp_path, "python", "p", fm)
    pages = load_guidance_pages(tmp_path)
    # page tags are canonicalized to the allowlist form
    assert pages[0].tags == ["retry"]
    ctx = PathContext(
        rel_path="packages/x/x.py",
        content="",
        package_stem=None,
        index_topics=[],
        index_tags=["retry"],  # canonical, as the scan writes it
    )
    cands = compute_candidates(pages, message="", path_contexts=[ctx], k=5)
    fired = next(c for c in cands if c.page.slug == "python/p")
    assert "index" in fired.signals_fired


def test_language_filter_python_context() -> None:
    pages = [
        _page(slug="code-review/checks-python", language="python"),
        _page(slug="code-review/checks-typescript", language="typescript"),
        _page(slug="general/pattern", language=None),
    ]
    cands = compute_candidates(pages, message="", path_contexts=[_ctx("a.py", "python")], k=10)
    slugs = {c.page.slug for c in cands}
    assert "code-review/checks-python" in slugs
    assert "general/pattern" in slugs
    assert "code-review/checks-typescript" not in slugs


def test_language_filter_multilang_union() -> None:
    pages = [
        _page(slug="code-review/checks-python", language="python"),
        _page(slug="code-review/checks-typescript", language="typescript"),
        _page(slug="code-review/checks-go", language="go"),
        _page(slug="general/pattern", language=None),
    ]
    cands = compute_candidates(
        pages, message="", path_contexts=[_ctx("a.py", "python"), _ctx("b.ts", "typescript")], k=10
    )
    slugs = {c.page.slug for c in cands}
    assert "code-review/checks-python" in slugs
    assert "code-review/checks-typescript" in slugs
    assert "general/pattern" in slugs
    assert "code-review/checks-go" not in slugs


def test_language_filter_message_only_is_noop() -> None:
    pages = [
        _page(slug="code-review/checks-python", language="python"),
        _page(slug="general/pattern", language=None),
    ]
    cands = compute_candidates(pages, message="hello", path_contexts=[], k=10)
    slugs = {c.page.slug for c in cands}
    assert "code-review/checks-python" in slugs
    assert "general/pattern" in slugs


def test_derive_path_languages_extension_fallback() -> None:
    # conn=None → pure extension-map lookup, wrapped in a set.
    assert _derive_path_languages(None, "pkg/mod.py") == {"python"}
    # unknown extension and extension-less paths → empty set.
    assert _derive_path_languages(None, "pkg/data.xyz") == set()
    assert _derive_path_languages(None, "Makefile") == set()


def test_derive_path_languages_db_hit_normalized() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE nodes (kind TEXT, path TEXT, attrs_json TEXT)")
    conn.execute(
        "INSERT INTO nodes (kind, path, attrs_json) VALUES (?, ?, ?)",
        ("file", "pkg/widget.tsx", json.dumps({"language": "TypeScript"})),
    )
    conn.commit()
    reader = GraphReader(conn)
    # DB language wins and is normalized to lowercase, regardless of the extension.
    assert _derive_path_languages(reader, "pkg/widget.tsx") == {"typescript"}
    # A path with no matching file node falls back to the extension map.
    assert _derive_path_languages(reader, "pkg/other.py") == {"python"}
    reader.close()


def _guidance_page_text(title: str, summary: str = "s") -> str:
    fm = {
        "title": title,
        "category": "guidance",
        "summary": summary,
        "topic": "code-review",
        "applies_when": "reviewing code",
        "impact": "high",
        "updated": "2026-06-26",
        "tokens": 0,
    }
    return "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n## Guidance\nDo X.\n"


def test_language_roundtrip_write_load_filter(tmp_path: Path) -> None:
    """Full value path: write language-scoped pages with the REAL writer,
    load them back, and confirm the suggestion filter keys off language."""
    from guidance_io.writer import write_page

    stamp = "2026-06-26"
    r_py = write_page(
        tmp_path,
        topic_raw="code-review",
        slug_raw="checks",
        page_text=_guidance_page_text("Python checks"),
        stamp=stamp,
        language="python",
    )
    r_ts = write_page(
        tmp_path,
        topic_raw="code-review",
        slug_raw="checks",
        page_text=_guidance_page_text("TypeScript checks"),
        stamp=stamp,
        language="typescript",
    )
    r_agnostic = write_page(
        tmp_path,
        topic_raw="code-review",
        slug_raw="general-pattern",
        page_text=_guidance_page_text("General pattern"),
        stamp=stamp,
        language=None,
    )
    # All three wrote successfully and the language suffix shaped the slugs.
    assert r_py.skip_reason is None and r_py.written_rel == "wiki/guidance/code-review/checks-python.md"
    assert r_ts.skip_reason is None and r_ts.written_rel == "wiki/guidance/code-review/checks-typescript.md"
    assert r_agnostic.skip_reason is None and r_agnostic.written_rel == "wiki/guidance/code-review/general-pattern.md"

    # Read them back with the REAL loader (no graph conn → extension/None path).
    pages = {p.slug: p for p in load_guidance_pages(tmp_path)}
    assert pages["code-review/checks-python"].language == "python"
    assert pages["code-review/checks-typescript"].language == "typescript"
    assert pages["code-review/general-pattern"].language is None

    page_list = list(pages.values())

    # A python context keeps the python + agnostic pages, drops typescript.
    py_cands = compute_candidates(page_list, message="", path_contexts=[_ctx("a.py", "python")], k=10)
    py_slugs = {c.page.slug for c in py_cands}
    assert "code-review/checks-python" in py_slugs
    assert "code-review/general-pattern" in py_slugs
    assert "code-review/checks-typescript" not in py_slugs

    # Symmetric: a typescript context keeps typescript + agnostic, drops python.
    ts_cands = compute_candidates(page_list, message="", path_contexts=[_ctx("b.ts", "typescript")], k=10)
    ts_slugs = {c.page.slug for c in ts_cands}
    assert "code-review/checks-typescript" in ts_slugs
    assert "code-review/general-pattern" in ts_slugs
    assert "code-review/checks-python" not in ts_slugs


def _seed_pkg_graph(nodes, edges):
    """In-memory graph: nodes = (id, kind, name, path, attrs_json, uri),
    edges = (src, dst, kind). Returns an open GraphReader over the in-memory db.
    Deliberately does NOT set row_factory — matches production read_only_connect
    (plain tuple rows), so the package branch is tested under real conditions."""
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
    return GraphReader(conn)


def test_package_branch_fires_entity_and_language(tmp_path) -> None:
    # A .py package: entity stem pkg_p, language {python}.
    reader = _seed_pkg_graph(
        nodes=[
            (1, "package", "p", "packages/p", None, "pkg:o/r/p"),
            (2, "file", "a.py", "packages/p/a.py", json.dumps({"language": "python"}), None),
            (3, "function", "do_thing", None, None, None),
        ],
        edges=[(1, 2, "contains"), (2, 3, "contains")],
    )
    try:
        ctxs = resolve_path_contexts(["packages/p"], reader, tmp_path, GuidanceIndex(files={}))
    finally:
        reader.close()
    assert len(ctxs) == 1
    ctx = ctxs[0]
    assert ctx.package_stem == "pkg_p"  # fires `entity`
    assert ctx.languages == {"python"}  # fires `language`
    assert "do_thing" in ctx.content  # symbol name in keyword haystack
    assert "a.py" in ctx.content  # file name in keyword haystack


def test_package_branch_typescript_not_mislabeled(tmp_path) -> None:
    # Package node attrs would say javascript; file nodes say typescript → set must be {typescript}.
    reader = _seed_pkg_graph(
        nodes=[
            (1, "package", "ts-pkg", "packages/ts-pkg", json.dumps({"language": "javascript"}), "pkg:o/r/ts-pkg"),
            (2, "file", "x.ts", "packages/ts-pkg/x.ts", json.dumps({"language": "typescript"}), None),
        ],
        edges=[(1, 2, "contains")],
    )
    try:
        ctxs = resolve_path_contexts(["packages/ts-pkg"], reader, tmp_path, GuidanceIndex(files={}))
    finally:
        reader.close()
    assert ctxs[0].languages == {"typescript"}


def test_package_branch_mixed_language_union(tmp_path) -> None:
    reader = _seed_pkg_graph(
        nodes=[
            (1, "package", "m", "packages/m", None, "pkg:o/r/m"),
            (2, "file", "a.py", "packages/m/a.py", json.dumps({"language": "python"}), None),
            (3, "file", "b.ts", "packages/m/b.ts", json.dumps({"language": "typescript"}), None),
        ],
        edges=[(1, 2, "contains"), (1, 3, "contains")],
    )
    try:
        ctxs = resolve_path_contexts(["packages/m"], reader, tmp_path, GuidanceIndex(files={}))
    finally:
        reader.close()
    assert ctxs[0].languages == {"python", "typescript"}


def test_package_branch_aggregates_index(tmp_path) -> None:
    reader = _seed_pkg_graph(
        nodes=[
            (1, "package", "p", "packages/p", None, "pkg:o/r/p"),
            (2, "file", "a.py", "packages/p/a.py", json.dumps({"language": "python"}), None),
        ],
        edges=[(1, 2, "contains")],
    )
    index = GuidanceIndex(
        files={"packages/p/a.py": IndexEntry(topics=["async"], tags=["retry"], content_hash="", scanned_at="")}
    )
    try:
        ctxs = resolve_path_contexts(["packages/p"], reader, tmp_path, index)
    finally:
        reader.close()
    assert "async" in ctxs[0].index_topics
    assert "retry" in ctxs[0].index_tags


def test_package_branch_no_match_stays_dark(tmp_path) -> None:
    # A non-package path with no package ancestor: all signal inputs empty, no crash.
    reader = _seed_pkg_graph(
        nodes=[(1, "package", "p", "packages/p", None, "pkg:o/r/p")],
        edges=[],
    )
    try:
        ctxs = resolve_path_contexts(["docs/notes"], reader, tmp_path, GuidanceIndex(files={}))
    finally:
        reader.close()
    ctx = ctxs[0]
    assert ctx.package_stem is None
    assert ctx.languages == set()
    assert ctx.index_topics == [] and ctx.index_tags == []


def test_package_branch_nested_subdir_resolves(tmp_path) -> None:
    reader = _seed_pkg_graph(
        nodes=[
            (1, "package", "p", "packages/p", None, "pkg:o/r/p"),
            (2, "file", "a.py", "packages/p/src/a.py", json.dumps({"language": "python"}), None),
        ],
        edges=[(1, 2, "contains")],
    )
    try:
        ctxs = resolve_path_contexts(["packages/p/src"], reader, tmp_path, GuidanceIndex(files={}))
    finally:
        reader.close()
    assert ctxs[0].package_stem == "pkg_p"
    assert ctxs[0].languages == {"python"}


def test_unresolved_real_file_with_graph_still_reads_disk(tmp_path) -> None:
    # A real on-disk file that is neither an admitted entity nor under a package
    # node: content must still come from disk so the keyword signal can match.
    (tmp_path / "README.md").write_text("alpha beta gamma", encoding="utf-8")
    reader = _seed_pkg_graph(nodes=[(1, "package", "p", "packages/p", None, "pkg:o/r/p")], edges=[])
    try:
        ctxs = resolve_path_contexts(["README.md"], reader, tmp_path, GuidanceIndex(files={}))
    finally:
        reader.close()
    assert "alpha beta gamma" in ctxs[0].content
    assert ctxs[0].package_stem is None


def test_no_graph_path_still_fires_index_and_language(tmp_path) -> None:
    # conn=None (graph absent) but an on-disk guidance index exists: a file affects
    # must still fire index + (extension) language. Regression guard for the rebuild-graph window.
    index = GuidanceIndex(
        files={"pkg/a.py": IndexEntry(topics=["async"], tags=["retry"], content_hash="", scanned_at="")}
    )
    ctxs = resolve_path_contexts(["pkg/a.py"], None, tmp_path, index)
    assert ctxs[0].index_topics == ["async"]
    assert ctxs[0].index_tags == ["retry"]
    assert ctxs[0].languages == {"python"}


def test_unresolved_file_with_graph_keeps_index_and_language(tmp_path) -> None:
    # Graph present, path is a real file that is NOT an admitted entity and NOT under any
    # package node: it must keep its rel-level index entry and extension language.
    (tmp_path / "conftest.py").write_text("x = 1", encoding="utf-8")
    reader = _seed_pkg_graph(nodes=[(1, "package", "p", "packages/p", None, "pkg:o/r/p")], edges=[])
    index = GuidanceIndex(
        files={"conftest.py": IndexEntry(topics=["fixtures"], tags=[], content_hash="", scanned_at="")}
    )
    try:
        ctxs = resolve_path_contexts(["conftest.py"], reader, tmp_path, index)
    finally:
        reader.close()
    assert ctxs[0].index_topics == ["fixtures"]
    assert ctxs[0].languages == {"python"}
    assert ctxs[0].package_stem is None
