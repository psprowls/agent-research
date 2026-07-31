"""Bedrock-only halves of the scan pipeline (narrate=True).

Everything here needs the [bedrock] extra: `langchain_core` messages, the
prose_refresh tool-loop agent, `graph_tools`, and the SubagentPool/roles stack.
`commands/scan.py` stays base-closure-safe and imports `bedrock_provider`
lazily inside `run_scan`'s `if narrate:` branch — the one remaining crossing.
That is what makes the plugin's Claude branch (narrate=False) run on an install
without the extra (epic regression property (e)).

Import direction: this module imports `commands.scan` at module scope; `scan`
never imports this one at module scope. No cycle in either load order. `scan`
is imported AS A MODULE (`_scan`) so test monkeypatching of `scan` attributes
still reaches the code here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from graph_io import GraphNotInitializedError, open_reader
from langchain_core.messages import HumanMessage, SystemMessage
from wiki_io.drift import iter_human_sections, section_hash
from wiki_io.entity_writer import update_frontmatter
from workspace_io.paths import graph_dir

from graph_wiki_core.commands import scan as _scan
from graph_wiki_core.commands.prose_refresh import run_prose_refresh
from graph_wiki_core.commands.scan_contract import (
    DriftResultItem,
    DriftVerdict,
    PropagateFinding,
    PropagateResultItem,
    ProseRefreshTask,
    ScanResults,
    ScanWorklist,
)
from graph_wiki_core.graph_tools import build_graph_tools
from graph_wiki_core.prompts.drift_judge import (
    build_drift_judge_prompt,
    parse_drift_verdict,
)
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


async def _drift_flag_pass(wiki: Path, model_override: str | None) -> None:
    """Judge each human-owned section of every drift candidate against its page's
    regenerated narrative; write `drift_review` + advance `drift_checked_commit`.

    Judge-once: only candidate pages (narrative newer than last check) are judged,
    and each is stamped to its anchor afterward, so a (page, narrative-change) pair
    costs LLM tokens exactly once (spec §3.1/D3).
    """
    stack = _bedrock_stack()
    if stack is None:
        return
    load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
    candidates = _scan._drift_candidates(wiki)
    if not candidates:
        return

    # item = (page_path, anchor, heading, chunk, narrative, file_map)
    items: list[tuple[Path, str, str, str, str, str | None]] = []
    page_anchor: dict[Path, str] = {}
    for page_path, anchor, narrative, file_map in candidates:
        page_anchor[page_path] = anchor
        body = page_path.read_text(encoding="utf-8")
        for heading, chunk in iter_human_sections(body):
            items.append((page_path, anchor, heading, chunk, narrative, file_map))

    verdicts: list[tuple] = []
    if items:
        drift_cfg = load_role_config_fn("drift_judge")
        drift_llm = make_llm_fn("drift_judge", model_override=model_override)
        drift_pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

        async def judge(item: tuple) -> TaskResultType:
            _pp, _anchor, heading, chunk, narrative, file_map = item
            system_msg, human_msg = build_drift_judge_prompt(heading, chunk, narrative, file_map)
            resp = await drift_llm.ainvoke([SystemMessage(content=system_msg), HumanMessage(content=human_msg)])
            return task_result_type(value=parse_drift_verdict(resp.content), response=resp)

        fan = await drift_pool.run_all(
            items=items,
            task=judge,
            role="drift_judge",
            model_id=drift_cfg["model_id"],
            max_concurrency=drift_cfg["max_concurrency"],
        )
        verdicts = list(fan.successes)

    flags_by_page: dict[Path, list[dict]] = {}
    for item, verdict in verdicts:
        page_path, anchor, heading, chunk, _narr, _fmp = item
        if isinstance(verdict, dict) and verdict.get("stale"):
            flags_by_page.setdefault(page_path, []).append(
                {
                    "section": heading.removeprefix("## ").strip(),
                    "detected_commit": anchor,
                    "hash": section_hash(chunk),
                    "reason": str(verdict.get("reason", "")),
                }
            )

    for page_path, anchor in page_anchor.items():
        entries = flags_by_page.get(page_path)
        try:
            if entries:
                update_frontmatter(
                    page_path,
                    {"drift_checked_commit": anchor, "drift_review": entries},
                )
            else:
                update_frontmatter(
                    page_path,
                    {"drift_checked_commit": anchor},
                    delete=["drift_review"],
                )
        except Exception as exc:  # noqa: BLE001 — non-fatal flag write
            logger.warning("drift flag write failed for %s: %s", page_path, exc)


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
    uri; the drift_judge / drift_propagator fan-outs are unchanged. Nothing is
    injected here — the apply half routes results into the pages. Per-item
    failures are surfaced via `results.provider_errors`, which run_scan merges
    into the ScanResult so partial-success reporting is unchanged.
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

        # --- drift_judge fan-out (role="drift_judge") — emit-time ground truth ---
        if stack is not None and worklist.drift_tasks:
            load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
            # item = (page_path, anchor, heading, chunk, narrative, file_map) —
            # identical to _drift_flag_pass so the spies' verdict_fn(it) works.
            drift_items: list[tuple[Path, str, str, str, str, str | None]] = []
            for dtask in worklist.drift_tasks:
                page_path = Path(dtask.page_path)
                for section in dtask.sections:
                    drift_items.append(
                        (page_path, dtask.anchor, section.heading, section.chunk, dtask.narrative, dtask.file_map)
                    )

            if drift_items:
                drift_cfg = load_role_config_fn("drift_judge")
                drift_llm = make_llm_fn("drift_judge", model_override=model_override)
                drift_pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

                async def judge(item: tuple) -> TaskResultType:
                    _pp, _anchor, heading, chunk, narrative, file_map = item
                    system_msg, human_msg = build_drift_judge_prompt(heading, chunk, narrative, file_map)
                    resp = await drift_llm.ainvoke([SystemMessage(content=system_msg), HumanMessage(content=human_msg)])
                    return task_result_type(value=parse_drift_verdict(resp.content), response=resp)

                fan = await drift_pool.run_all(
                    items=drift_items,
                    task=judge,
                    role="drift_judge",
                    model_id=drift_cfg["model_id"],
                    max_concurrency=drift_cfg["max_concurrency"],
                )
                drift_by_uri: dict[str, DriftResultItem] = {}
                task_uri_by_page = {Path(d.page_path): d.uri for d in worklist.drift_tasks}
                for item, verdict in fan.successes:
                    page_path, _anchor, heading, _chunk, _narr, _fmp = item
                    uri = task_uri_by_page.get(page_path)
                    if uri is None:
                        continue
                    if not isinstance(verdict, dict):
                        continue
                    item_out = drift_by_uri.setdefault(uri, DriftResultItem(uri=uri))
                    item_out.verdicts.append(
                        DriftVerdict(
                            section=heading.removeprefix("## ").strip(),
                            stale=bool(verdict.get("stale")),
                            reason=str(verdict.get("reason", "")),
                        )
                    )
                results.drift = list(drift_by_uri.values())

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
