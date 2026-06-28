from __future__ import annotations

from pathlib import Path

import yaml
from graph_wiki_core.commands.guidance_signals import GuidancePage
from graph_wiki_core.commands.next_guidance import (
    derive_recall_inputs,
    filter_by_phase,
    guidance_eligible,
    run_next_guidance,
)
from graph_wiki_core.commands.work import WorkNextResult


def _page(slug: str, workflow: list[str]) -> GuidancePage:
    return GuidancePage(
        slug=slug,
        topic="python",
        tags=["python"],
        keywords=["backoff"],
        entities=[],
        globs=[],
        summary="s",
        applies_when="w",
        impact="high",
        guidance_body="## body",
        workflow=workflow,
    )


def test_derive_recall_inputs():
    fm = {"summary": "do a thing", "affects": ["graph-wiki-core", "src/x.py"], "phase": "plan"}
    message, paths, phase = derive_recall_inputs(fm)
    assert message == "do a thing"
    assert paths == ["graph-wiki-core", "src/x.py"]
    assert phase == "plan"


def test_filter_keeps_agnostic_and_matching_drops_nonmatching():
    pages = [
        _page("g/agnostic", []),
        _page("g/match", ["design", "plan"]),
        _page("g/other", ["execute"]),
    ]
    kept, warnings = filter_by_phase(pages, "plan")
    slugs = {p.slug for p in kept}
    assert slugs == {"g/agnostic", "g/match"}
    assert warnings == []


def test_filter_drops_and_warns_on_invalid_phase_value():
    pages = [_page("g/bad", ["plan", "banana"])]
    kept, warnings = filter_by_phase(pages, "plan")
    assert kept == []
    assert any("banana" in w for w in warnings)


def test_guidance_eligible_rules():
    assert guidance_eligible(WorkNextResult(slug="s", status="open", phase="plan")) is True
    assert guidance_eligible(WorkNextResult(slug="s", blockers=["x"])) is False
    assert guidance_eligible(WorkNextResult(slug="s", status="open", phase="finish")) is False
    assert guidance_eligible(WorkNextResult(slug="s", status="open", phase="done")) is False
    assert guidance_eligible(WorkNextResult(slug="s", status="resolved", phase="execute")) is False
    assert guidance_eligible(WorkNextResult(slug="s", status="mitigated", phase="execute")) is False


def _write_workitem(ws: Path, slug: str, fm: dict) -> None:
    d = ws / "wiki" / "work"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n## Summary\nbody\n", encoding="utf-8"
    )


def _write_guidance(ws: Path, topic: str, slug: str, fm: dict, body: str) -> None:
    d = ws / "wiki" / "guidance" / topic
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body, encoding="utf-8")


def _guidance_fm(topic: str, kws: list[str], workflow: list[str] | None = None) -> dict:
    fm = {
        "title": "T",
        "category": "guidance",
        "summary": "s",
        "topic": topic,
        "applies_when": "w",
        "impact": "high",
        "updated": "2026-06-23",
        "tokens": 0,
        "tags": [topic],
        "triggers": {"globs": [], "keywords": kws, "entities": []},
    }
    if workflow is not None:
        fm["workflow"] = workflow
    return fm


async def test_run_next_guidance_recall_only(tmp_path: Path):
    ws = tmp_path / "ws"
    _write_workitem(
        ws,
        "wi",
        {"title": "WI", "summary": "add retry backoff", "affects": ["python"], "phase": "plan", "status": "open"},
    )
    _write_guidance(ws, "python", "retry", _guidance_fm("python", ["backoff"], ["plan"]), "## Guidance\nRetry.\n")
    _write_guidance(ws, "python", "other", _guidance_fm("python", ["xyz"], ["execute"]), "## Guidance\nNo.\n")

    result = await run_next_guidance("wi", workspace_path=ws, no_rank=True)
    slugs = {r.slug for r in result.ranked}
    assert "python/retry" in slugs  # plan-phase page kept and recalled
    assert "python/other" not in slugs  # execute-only page filtered out
    assert any("deterministic" in w for w in result.warnings)


class _FakeResp:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage_metadata = None


class _FakeLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def ainvoke(self, messages):
        return _FakeResp(self._reply)


async def test_run_next_guidance_all_low_drops_to_empty(tmp_path: Path):
    """drop_low=True is wired through gw next: an all-low LLM ranking collapses to
    empty, so no bundle is assembled and no guidance file would be written."""
    ws = tmp_path / "ws"
    _write_workitem(
        ws,
        "wi",
        {"title": "WI", "summary": "add retry backoff", "affects": ["python"], "phase": "plan", "status": "open"},
    )
    _write_guidance(ws, "python", "retry", _guidance_fm("python", ["backoff"], ["plan"]), "## Guidance\nRetry.\n")

    reply = "- slug: python/retry\n  relevance: low\n  reason: irrelevant\n"
    result = await run_next_guidance(
        "wi",
        workspace_path=ws,
        assemble=True,
        make_llm_fn=lambda *a, **k: _FakeLLM(reply),
    )
    assert result.ranked == []
    assert result.assembled is None


async def test_run_next_guidance_no_guidance_dir(tmp_path: Path):
    ws = tmp_path / "ws"
    _write_workitem(ws, "wi", {"title": "WI", "summary": "x", "affects": [], "phase": "plan", "status": "open"})
    (ws / "wiki" / "guidance").mkdir(parents=True)
    result = await run_next_guidance("wi", workspace_path=ws, no_rank=True)
    assert result.ranked == []


async def test_run_next_guidance_uses_resolved_phase_override(tmp_path: Path):
    """Regression: freshly-filed items have no frontmatter phase; the resolved phase
    from run_work_next must be passed as an override so filter_by_phase uses it."""
    ws = tmp_path / "ws"
    # Work item with NO phase field — as it is when first filed.
    _write_workitem(ws, "wi", {"title": "WI", "summary": "add retry backoff", "affects": ["python"], "status": "open"})
    _write_guidance(
        ws, "python", "design-guide", _guidance_fm("python", ["backoff"], ["design"]), "## Guidance\nDesign.\n"
    )
    _write_guidance(
        ws, "python", "execute-guide", _guidance_fm("python", ["backoff"], ["execute"]), "## Guidance\nExecute.\n"
    )

    # Without override: phase=None → filter_by_phase drops BOTH phase-specific pages.
    result_no_override = await run_next_guidance("wi", workspace_path=ws, no_rank=True)
    slugs_no_override = {r.slug for r in result_no_override.ranked}
    # documents old/current behavior — phase-specific pages are dropped when no phase in frontmatter
    assert "python/design-guide" not in slugs_no_override
    assert "python/execute-guide" not in slugs_no_override

    # With phase="design" override: filter_by_phase keeps only design-tagged page.
    result_with_override = await run_next_guidance("wi", workspace_path=ws, no_rank=True, phase="design")
    slugs_with_override = {r.slug for r in result_with_override.ranked}
    assert "python/design-guide" in slugs_with_override, "with phase override, design page must be kept"
    assert "python/execute-guide" not in slugs_with_override, "with phase override, execute page must still be dropped"
