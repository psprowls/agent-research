from __future__ import annotations

from pathlib import Path

import yaml
from graph_wiki_core.commands.guidance_signals import (
    GuidancePage,
    PathContext,
    compute_candidates,
    load_guidance_pages,
)


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
    )
    base.update(kw)
    return GuidancePage(**base)


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
