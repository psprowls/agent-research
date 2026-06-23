"""Shared recall→rank→assemble pipeline for guidance suggest.

Extracted from guidance_suggest so the same recall/rank core can be reused
across CLI, MCP, and workflow surfaces without duplicating LLM call logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from graph_io.tokens import count_tokens
from langchain_core.messages import HumanMessage, SystemMessage

from graph_wiki_core.commands.guidance_signals import (
    GuidancePage,
    PathContext,
    compute_candidates,
)
from graph_wiki_core.prompts.guidance_orchestrator import (
    build_guidance_orchestrator_prompt,
    parse_orchestrator_response,
)

try:  # Bedrock stack — guarded
    from model_adapter.loader import make_llm
except ImportError:  # pragma: no cover
    make_llm = None  # type: ignore[assignment]

_RECALL_ONLY_DEFAULT = "Bedrock stack unavailable; returning recall order without ranking"


@dataclass
class RankedGuidance:
    slug: str
    relevance: str
    signals_fired: list[str]
    reason: str


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


async def recall_and_rank(
    pages: list[GuidancePage],
    message: str,
    path_contexts: list[PathContext],
    *,
    top: int = 5,
    candidates: int = 12,
    assemble: bool = False,
    budget: int | None = None,
    model_override: str | None = None,
    make_llm_fn: Any = None,
    force_recall_only: bool = False,
    recall_only_reason: str = _RECALL_ONLY_DEFAULT,
) -> tuple[list[RankedGuidance], str | None, list[str]]:
    """Run recall→rank→assemble and return (ranked, assembled, warnings).

    When *force_recall_only* is True the LLM ranking step is skipped and a
    warning containing *recall_only_reason* is emitted.  The same path is taken
    when no LLM factory is available.
    """
    warnings: list[str] = []
    ranked: list[RankedGuidance] = []
    assembled: str | None = None

    if not pages:
        return ranked, assembled, warnings

    slate = compute_candidates(pages, message, path_contexts, k=candidates)

    if not slate:
        return ranked, assembled, warnings

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

    effective_make_llm = make_llm_fn or make_llm

    if force_recall_only or effective_make_llm is None:
        warnings.append(recall_only_reason)
        for c in slate[:top]:
            ranked.append(RankedGuidance(c.page.slug, "low", c.signals_fired, "recall-only (no LLM)"))
    else:
        system, human = build_guidance_orchestrator_prompt(message, path_summaries, cand_payload)
        llm = effective_make_llm("guidance_orchestrator", model_override=model_override)
        resp = await llm.ainvoke([SystemMessage(system), HumanMessage(human)])
        content = resp.content if isinstance(resp.content, str) else str(resp.content)
        for item in parse_orchestrator_response(content, set(by_slug)):
            cand = by_slug[item["slug"]]
            ranked.append(
                RankedGuidance(
                    slug=item["slug"],
                    relevance=item["relevance"],
                    signals_fired=cand.signals_fired,
                    reason=item["reason"],
                )
            )
        ranked = ranked[:top]

    if assemble and ranked:
        bodies = [(r.slug, by_slug[r.slug].page.guidance_body) for r in ranked]
        assembled = _assemble(bodies, budget)

    return ranked, assembled, warnings
