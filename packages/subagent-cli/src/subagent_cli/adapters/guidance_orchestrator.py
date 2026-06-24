"""GuidanceOrchestratorAdapter: stage-2 guidance ranking for a single task message."""

from __future__ import annotations

from graph_wiki_core.commands.guidance_signals import (
    Candidate,
    compute_candidates,
    load_guidance_pages,
    resolve_path_contexts,
)
from graph_wiki_core.prompts.guidance_orchestrator import (
    build_guidance_orchestrator_prompt,
    parse_orchestrator_response,
)
from guidance_io.index_store import load_index

from .base import Prepared, RunContext

_TOP_N = 8  # number of recall candidates to pass to the ranking prompt


class GuidanceOrchestratorAdapter:
    name = "guidance_orchestrator"
    role = "orchestrator"
    selector = "query"
    supports_all = False

    async def prepare(self, ctx: RunContext, item: str) -> Prepared:
        """Build a guidance ranking prompt for *item* (the task message).

        Raises RuntimeError mentioning "guidance" when no pages are found.
        """
        # Load and score pages — both of these are pure/Bedrock-free.
        try:
            pages = load_guidance_pages(ctx.workspace)
        except (FileNotFoundError, OSError):
            pages = []

        if not pages:
            raise RuntimeError("No guidance pages found in workspace; run `gw guidance ingest` to populate guidance.")

        index = load_index(ctx.workspace)
        # No working-file paths supplied in the single-query adapter — pass empty list.
        path_contexts = resolve_path_contexts([], None, ctx.repo_root, index)
        candidates: list[Candidate] = compute_candidates(pages, item, path_contexts, _TOP_N)

        candidate_slugs = {c.page.slug for c in candidates}
        cand_payload = [
            {
                "slug": c.page.slug,
                "topic": c.page.topic,
                "summary": c.page.summary,
                "applies_when": c.page.applies_when,
                "signals_fired": c.signals_fired,
            }
            for c in candidates
        ]

        system, human = build_guidance_orchestrator_prompt(
            message=item,
            path_summaries=[],
            candidates=cand_payload,
        )

        return Prepared(
            item_id=item[:80],
            system=system,
            human=human,
            parse=lambda text: parse_orchestrator_response(text, candidate_slugs),
        )

    def items(self, ctx: RunContext) -> list[str]:
        raise ValueError("GuidanceOrchestratorAdapter is a single-query adapter; use prepare() directly")
