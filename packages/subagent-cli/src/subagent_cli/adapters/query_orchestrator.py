"""QueryOrchestratorLoopAdapter: run the real query-orchestration loop end-to-end.

Unlike the single-shot adapters this executes graph_wiki_core's production
``run_query_orchestrator`` — it plans over bounded wiki/graph tools and fans out
librarian + code_reader worker batches. The production seams are referenced via
the ``query`` module object (not ``from … import``) so tests can patch them.
"""

from __future__ import annotations

from dataclasses import asdict

from graph_wiki_core.commands import query as query_mod
from graph_wiki_core.commands.query_orchestrator import InitialCandidate
from workspace_io.paths import graph_dir

from .base import LoopOutcome, RunContext

_LOOP_NOTE = "loop adapter: no token/cost aggregation (multi-call orchestration); see trace file"


class QueryOrchestratorLoopAdapter:
    name = "query_orchestrator"
    role = "query_orchestrator"
    selector = "query"

    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    async def run(self, ctx: RunContext, item: str) -> LoopOutcome:
        if not (3 <= self.top_k <= 10):
            raise RuntimeError(f"top_k must be between 3 and 10 (got {self.top_k})")

        prepared = query_mod._prepare_query_retrieval(item, ctx.workspace, self.top_k)
        repo_root = prepared.repo_root or ctx.repo_root
        graph_reader, graph_tools = query_mod._load_query_graph_tools(prepared.wiki.parent)
        try:
            result = await query_mod.run_query_orchestrator(
                query=item,
                wiki_root=prepared.wiki,
                repo_root=repo_root,
                initial_candidates=[
                    InitialCandidate(
                        path=page,
                        score=prepared.search_scores[page]["rrf"],
                        excerpt=query_mod._read_candidate_excerpt(prepared.wiki, page),
                    )
                    for page in prepared.top_pages
                ],
                graph_tools=graph_tools,
                trace_dir=graph_dir(ctx.workspace) / "traces",
                role_model_overrides=None,
            )
        finally:
            if graph_reader is not None:
                graph_reader.close()

        output = result.output
        return LoopOutcome(
            item_id=item[:80],
            role=self.role,
            model_id="",  # filled in by runner.run_loop
            region="",  # filled in by runner.run_loop
            answer=output.answer_markdown,
            structured=asdict(output),
            trace_metadata=dict(result.trace_metadata),
            latency_s=0.0,  # filled in by runner.run_loop
            trace_path=None,  # filled in by runner.run_loop
            note=_LOOP_NOTE,
        )
