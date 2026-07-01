from __future__ import annotations

from pathlib import Path

import yaml
from graph_wiki_core.commands.guidance_signals import GuidancePage
from graph_wiki_core.commands.next_guidance import (
    derive_recall_inputs,
    filter_by_phase,
    filter_by_role,
    guidance_eligible,
    run_next_guidance,
)
from graph_wiki_core.commands.work import WorkNextResult
from work_io import paths as _paths


def _page(slug: str, workflow: list[str], role: list[str] | None = None) -> GuidancePage:
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
        role=role or [],
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


def test_filter_by_role_none_keeps_all():
    pages = [_page("g/a", [], ["review"]), _page("g/b", [], [])]
    kept, warnings = filter_by_role(pages, None)
    assert {p.slug for p in kept} == {"g/a", "g/b"}
    assert warnings == []


def test_filter_by_role_keeps_agnostic_and_matching():
    pages = [
        _page("g/agnostic", [], []),
        _page("g/impl", [], ["implement"]),
        _page("g/review", [], ["review"]),
    ]
    kept, warnings = filter_by_role(pages, "implement")
    assert {p.slug for p in kept} == {"g/agnostic", "g/impl"}
    assert warnings == []


def test_filter_by_role_drops_and_warns_invalid():
    pages = [_page("g/bad", [], ["bogus"])]
    kept, warnings = filter_by_role(pages, "implement")
    assert kept == []
    assert any("bogus" in w for w in warnings)


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


def _guidance_fm(topic: str, kws: list[str], workflow: list[str] | None = None, role: list[str] | None = None) -> dict:
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
    if role is not None:
        fm["role"] = role
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


async def test_run_next_guidance_role_filters_review_at_execute(tmp_path: Path):
    """At execute, active_role='implement' drops a role:[review] page from the
    implementer bundle but keeps a dual-use (no-role) page."""
    ws = tmp_path / "ws"
    _write_workitem(
        ws,
        "wi",
        {"title": "WI", "summary": "add retry backoff", "affects": ["python"], "phase": "execute", "status": "open"},
    )
    _write_guidance(
        ws,
        "python",
        "review-only",
        _guidance_fm("python", ["backoff"], ["execute"], ["review"]),
        "## Guidance\nReview.\n",
    )
    _write_guidance(
        ws,
        "python",
        "dual-use",
        _guidance_fm("python", ["backoff"], ["execute"]),
        "## Guidance\nBoth.\n",
    )

    result = await run_next_guidance("wi", workspace_path=ws, no_rank=True, phase="execute")
    slugs = {r.slug for r in result.ranked}
    assert "python/review-only" not in slugs
    assert "python/dual-use" in slugs


async def test_run_next_guidance_role_off_at_design(tmp_path: Path):
    """At design, active_role=None, so a role:[review] page is unaffected by role
    filtering (kept because its phase matches)."""
    ws = tmp_path / "ws"
    _write_workitem(
        ws,
        "wi",
        {"title": "WI", "summary": "add retry backoff", "affects": ["python"], "phase": "design", "status": "open"},
    )
    _write_guidance(
        ws,
        "python",
        "review-design",
        _guidance_fm("python", ["backoff"], ["design"], ["review"]),
        "## Guidance\nReview.\n",
    )

    result = await run_next_guidance("wi", workspace_path=ws, no_rank=True, phase="design")
    slugs = {r.slug for r in result.ranked}
    assert "python/review-design" in slugs


def test_resolve_guidance_target_empty_string_skips(tmp_path: Path):
    from graph_wiki_core.commands.next_guidance import resolve_guidance_target

    assert resolve_guidance_target("", tmp_path, "wi", "design") is None


def test_resolve_guidance_target_auto_uses_artifact_path(tmp_path: Path):
    from graph_wiki_core.commands.next_guidance import resolve_guidance_target

    result = resolve_guidance_target("auto", tmp_path, "wi", "design")
    assert result == _paths.artifact_path(tmp_path, "wi", "design", "guidance", ext="md")


def test_resolve_guidance_target_auto_falls_back_to_open_phase(tmp_path: Path):
    from graph_wiki_core.commands.next_guidance import resolve_guidance_target

    result = resolve_guidance_target("auto", tmp_path, "wi", None)
    assert result == _paths.artifact_path(tmp_path, "wi", "open", "guidance", ext="md")


def test_resolve_guidance_target_explicit_path_passthrough(tmp_path: Path):
    from graph_wiki_core.commands.next_guidance import resolve_guidance_target

    result = resolve_guidance_target("/tmp/x.md", tmp_path, "wi", "design")
    assert result == Path("/tmp/x.md")


async def test_run_next_guidance_populates_target_path_auto(tmp_path: Path):
    ws = tmp_path / "ws"
    _write_workitem(
        ws,
        "wi",
        {"title": "WI", "summary": "add retry backoff", "affects": ["python"], "phase": "plan", "status": "open"},
    )
    _write_guidance(ws, "python", "retry", _guidance_fm("python", ["backoff"], ["plan"]), "## Guidance\nRetry.\n")

    result = await run_next_guidance("wi", workspace_path=ws, no_rank=True, file="auto", phase="plan")
    assert result.target_path == _paths.artifact_path(ws, "wi", "plan", "guidance", ext="md")


async def test_run_next_guidance_populates_target_path_on_early_return(tmp_path: Path):
    """target_path must be set even when the work item has no guidance pages to rank —
    the CLI needs to know the resolved target regardless of whether anything was ranked."""
    ws = tmp_path / "ws"
    _write_workitem(ws, "wi", {"title": "WI", "summary": "x", "affects": [], "phase": "plan", "status": "open"})
    (ws / "wiki" / "guidance").mkdir(parents=True)

    result = await run_next_guidance("wi", workspace_path=ws, no_rank=True, file="auto", phase="plan")
    assert result.ranked == []
    assert result.target_path == _paths.artifact_path(ws, "wi", "plan", "guidance", ext="md")
