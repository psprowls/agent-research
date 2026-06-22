"""`gw guidance suggest` — hybrid recall→rank over the guidance corpus.

Stage 1: deterministic recall (guidance_signals), no LLM. Stage 2: one
structured ranking call (guidance_orchestrator). Optional --assemble emits the
concatenated top-N ## Guidance bodies within a token budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from graph_io.store import GraphNotInitializedError, read_only_connect
from graph_io.tokens import count_tokens
from guidance_io.index_store import GuidanceIndex, load_index
from guidance_io.paths import guidance_index_path
from wiki_io._workspace import resolve_wiki_and_repo
from workspace_io.paths import graph_dir

from graph_wiki_core.commands.guidance_signals import (
    compute_candidates,
    load_guidance_pages,
    resolve_path_contexts,
)
from graph_wiki_core.prompts.guidance_orchestrator import (
    build_guidance_orchestrator_prompt,
    parse_orchestrator_response,
)

try:  # Bedrock stack — guarded
    from langchain_core.messages import HumanMessage, SystemMessage
    from model_adapter.loader import make_llm
except ImportError:  # pragma: no cover
    make_llm = None  # type: ignore[assignment]
    HumanMessage = SystemMessage = None  # type: ignore[assignment]


@dataclass
class RankedGuidance:
    slug: str
    relevance: str
    signals_fired: list[str]
    reason: str


@dataclass
class GuidanceSuggestResult:
    ranked: list[RankedGuidance] = field(default_factory=list)
    assembled: str | None = None
    index_present: bool = False
    warnings: list[str] = field(default_factory=list)


def _assemble(bodies: list[tuple[str, str]], budget: int | None) -> str:
    """Concatenate (slug, body) blocks, truncating tokens to stay within budget."""
    out: list[str] = []
    used = 0
    for slug, body in bodies:
        block = f"<!-- {slug} -->\n{body}".strip()
        if budget is None:
            out.append(block)
            continue
        toks = count_tokens(block)
        if used + toks <= budget:
            out.append(block)
            used += toks
        else:
            # take a token-bounded prefix of this block, then stop
            words = block.split()
            prefix: list[str] = []
            for w in words:
                if used + count_tokens(" ".join(prefix + [w])) > budget:
                    break
                prefix.append(w)
            if prefix:
                out.append(" ".join(prefix))
            break
    return "\n\n".join(out)


async def run_guidance_suggest(
    message: str,
    workspace_path: Path | None = None,
    repo_path: Path | None = None,
    *,
    paths: list[str] | None = None,
    top: int = 5,
    candidates: int = 12,
    assemble: bool = False,
    budget: int | None = None,
    model_override: str | None = None,
    make_llm_fn: Any = None,
) -> GuidanceSuggestResult:
    """Rank guidance for a coding task. See module docstring."""
    wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent
    repo = repo_path.resolve() if repo_path else resolved_repo

    result = GuidanceSuggestResult()
    pages = load_guidance_pages(workspace)
    if not pages:
        return result

    index_present = guidance_index_path(workspace).is_file()
    result.index_present = index_present
    index = load_index(workspace) if index_present else GuidanceIndex()
    if not index_present:
        result.warnings.append("no guidance index yet — run `gw guidance scan` to improve recall")

    conn = None
    if paths:
        try:
            conn = read_only_connect(graph_dir(workspace) / "code.db")
        except GraphNotInitializedError:
            conn = None
    try:
        path_contexts = resolve_path_contexts(paths or [], conn, repo, index)
        slate = compute_candidates(pages, message, path_contexts, k=candidates)
    finally:
        if conn is not None:
            conn.close()

    if not slate:
        return result

    by_slug = {c.page.slug: c for c in slate}
    path_summaries = [
        f"{ctx.rel_path} — {ctx.package_stem or '?'} [{', '.join(ctx.index_topics) or '-'}]" for ctx in path_contexts
    ]
    cand_payload = [
        {
            "slug": c.page.slug,
            "topic": c.page.topic,
            "summary": c.page.summary,
            "applies_when": c.page.applies_when,
            "signals_fired": c.signals_fired,
        }
        for c in slate
    ]

    make_llm_fn = make_llm_fn or make_llm
    if make_llm_fn is None:
        result.warnings.append("Bedrock stack unavailable; returning recall order without ranking")
        for c in slate[:top]:
            result.ranked.append(RankedGuidance(c.page.slug, "low", c.signals_fired, "recall-only (no LLM)"))
    else:
        system, human = build_guidance_orchestrator_prompt(message, path_summaries, cand_payload)
        llm = make_llm_fn("guidance_orchestrator", model_override=model_override)
        resp = await llm.ainvoke([SystemMessage(system), HumanMessage(human)])
        content = resp.content if isinstance(resp.content, str) else str(resp.content)
        for item in parse_orchestrator_response(content, set(by_slug)):
            cand = by_slug[item["slug"]]
            result.ranked.append(
                RankedGuidance(
                    slug=item["slug"],
                    relevance=item["relevance"],
                    signals_fired=cand.signals_fired,
                    reason=item["reason"],
                )
            )
        result.ranked = result.ranked[:top]

    if assemble and result.ranked:
        bodies = [(r.slug, by_slug[r.slug].page.guidance_body) for r in result.ranked]
        result.assembled = _assemble(bodies, budget)

    return result
