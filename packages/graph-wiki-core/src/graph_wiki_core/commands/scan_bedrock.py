"""Bedrock-only halves of the scan pipeline (narrate=True).

Everything here needs the [bedrock] extra: `langchain_core` messages, the
prose_refresh tool-loop agent, `graph_tools`, and the SubagentPool/roles stack.
`commands/scan.py` stays base-closure-safe and imports `bedrock_provider`
lazily inside `run_scan`'s `if narrate:` branch — the one remaining crossing.
That is what makes the plugin's Claude branch (narrate=False) run on an install
without the extra (epic regression property (e)).

Import direction: `scan.py` imports this module lazily (inside `run_scan`);
this module does not import `scan.py` at module scope (its only prior call
into `scan` — the M2e drift-candidate lookup — was deleted along with the
rest of the M2e drift-judge stage). No cycle in either load order.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from graph_io import GraphNotInitializedError, open_reader
from langchain_core.messages import HumanMessage, SystemMessage
from workspace_io.paths import graph_dir

from graph_wiki_core.commands.prose_refresh import run_prose_refresh
from graph_wiki_core.commands.scan_contract import (
    PropagateFinding,
    PropagateResultItem,
    ProseRefreshTask,
    ScanResults,
    ScanWorklist,
)
from graph_wiki_core.graph_tools import build_graph_tools
from graph_wiki_core.prompts.drift_propagator import (
    build_drift_propagator_prompt,
    parse_drift_propagator_verdict,
)

try:
    from subagent_runtime.pool import FanOutResult, SubagentPool, TaskResult

    from graph_wiki_core.roles import load_role_config, make_llm
except ImportError:  # pragma: no cover — this module is gated; the guard is belt-and-braces
    load_role_config = make_llm = None  # type: ignore[assignment]
    SubagentPool = TaskResult = FanOutResult = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from subagent_runtime.pool import SubagentPool as SubagentPoolType
    from subagent_runtime.pool import TaskResult as TaskResultType

logger = logging.getLogger(__name__)


def _bedrock_stack() -> tuple[Any, Any, type["SubagentPoolType"], type["TaskResultType"]] | None:
    if load_role_config is None or make_llm is None or SubagentPool is None or TaskResult is None:
        return None
    return (
        cast(Any, load_role_config),
        cast(Any, make_llm),
        cast(type["SubagentPoolType"], SubagentPool),
        cast(type["TaskResultType"], TaskResult),
    )


# ---------------------------------------------------------------------------
# Living Wiki M1.5 (split scan pipeline): in-process Bedrock provider
# ---------------------------------------------------------------------------


async def bedrock_provider(
    worklist: ScanWorklist,
    wiki: Path,
    repo: Path,
    *,
    model_override: str | None = None,
    propagate: bool = False,
) -> ScanResults:
    """Turn a ScanWorklist into ScanResults via the in-process Bedrock fan-outs.

    ONE unified prose fan-out (role="prose_refresher") runs a bounded tool-loop
    agent per stale entity and collects each parsed ProseRefreshResult keyed by
    uri; the drift_propagator fan-out is unchanged. Nothing is injected here —
    the apply half routes results into the pages. Per-item failures are
    surfaced via `results.provider_errors`, which run_scan merges into the
    ScanResult so partial-success reporting is unchanged.
    """
    results = ScanResults()
    provider_errors: list[str] = []

    stack = _bedrock_stack()

    # Open a read-only reader for the prose_refresher's graph tools. Closed in
    # finally. The open mirrors run_scan's
    # `if reader is not None` gating: on a NOT_INITIALIZED fallback the graph DB
    # was never written, so open_reader raises GraphNotInitializedError and we
    # proceed reader-less.
    reader = None
    try:
        try:
            reader = open_reader(wiki.parent)
        except GraphNotInitializedError:
            reader = None

        # --- Unified prose-refresh fan-out (role="prose_refresher") ---
        if stack is not None and worklist.prose_tasks:
            load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
            graph_tools = build_graph_tools(reader) if reader is not None else []
            cfg = load_role_config_fn("prose_refresher")
            llm = make_llm_fn("prose_refresher", model_override=model_override)
            pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

            async def refresh(task: ProseRefreshTask) -> TaskResultType:
                result = await run_prose_refresh(llm=llm, task=task, repo=repo, wiki=wiki, graph_tools=graph_tools)
                return task_result_type(value=result, response=result)

            fan = await pool.run_all(
                items=list(worklist.prose_tasks),
                task=refresh,
                role="prose_refresher",
                model_id=cfg["model_id"],
                max_concurrency=cfg["max_concurrency"],
            )
            for task_item, result in fan.successes:
                if result.error:
                    provider_errors.append(f"{task_item.uri}: {result.error}")
                results.prose.append(result)
            for err in fan.errors:
                provider_errors.append(f"{err.item.uri}: {err.exception!r}")

        # --- drift_propagator fan-out (role="drift_propagator") — M4, opt-in ---
        if propagate and stack is not None and worklist.propagate_tasks:
            load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
            # item = (kind, target_slug, title, body, entity_tuples) — mirrors
            # run_propagate_drift's judge half (entity_tuples = (stem, narrative, files)).
            prop_items: list[tuple[str, str, str, str, list[tuple[str, str, list[str]]]]] = []
            for ptask in worklist.propagate_tasks:
                body = Path(ptask.page_path).read_text(encoding="utf-8")
                entity_tuples = [(e.stem, e.narrative, e.changed_files) for e in ptask.entities]
                prop_items.append((ptask.kind, ptask.target_slug, ptask.title, body, entity_tuples))

            if prop_items:
                prop_cfg = load_role_config_fn("drift_propagator")
                prop_llm = make_llm_fn("drift_propagator", model_override=model_override)
                prop_pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

                async def judge_propagate(item: tuple) -> TaskResultType:
                    kind_inner, _slug, title, body, entity_tuples = item
                    system_msg, human_msg = build_drift_propagator_prompt(kind_inner, title, body, entity_tuples)
                    resp = await prop_llm.ainvoke([SystemMessage(content=system_msg), HumanMessage(content=human_msg)])
                    return task_result_type(value=parse_drift_propagator_verdict(resp.content), response=resp)

                fan = await prop_pool.run_all(
                    items=prop_items,
                    task=judge_propagate,
                    role="drift_propagator",
                    model_id=prop_cfg["model_id"],
                    max_concurrency=prop_cfg["max_concurrency"],
                )
                propagate_results: list[PropagateResultItem] = []
                for item, verdict in fan.successes:
                    kind_inner, slug, _title, _body, _entity_tuples = item
                    if not (isinstance(verdict, dict) and verdict.get("stale")):
                        continue
                    findings = [
                        PropagateFinding(
                            entity_stem=str(f.get("entity_stem", "")),
                            claim=str(f.get("stale_claim", "")),
                            reason=str(f.get("rationale", "")),
                        )
                        for f in (verdict.get("findings") or [])
                        if str(f.get("entity_stem", "")).strip()
                    ]
                    if findings:
                        propagate_results.append(
                            PropagateResultItem(kind=kind_inner, target_slug=slug, stale=True, findings=findings)
                        )
                results.propagate = propagate_results
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:  # noqa: BLE001
                pass

    results.provider_errors = provider_errors
    return results
