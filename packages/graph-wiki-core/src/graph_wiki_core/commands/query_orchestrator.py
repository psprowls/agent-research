"""Structured output parsing and validation for the query orchestrator."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import frontmatter
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from model_adapter.loader import load_role_config, make_llm
from subagent_runtime.pool import FanOutResult, PerItemError, SubagentPool, TaskResult

from graph_wiki_core.agent_loop import run_tool_loop
from graph_wiki_core.agent_tools import (
    body_without_frontmatter,
    build_wiki_catalog,
    filter_graph_tools,
    read_bounded_wiki_page,
)
from graph_wiki_core.agent_tools import (
    search_wiki_catalog as search_catalog_rows,
)
from graph_wiki_core.commands.query import _read_file_bounded
from graph_wiki_core.prompts.code_reader import ORCHESTRATED_CODE_READER_SYSTEM
from graph_wiki_core.prompts.librarian import LIBRARIAN_SYSTEM
from graph_wiki_core.prompts.query_orchestrator import QUERY_ORCHESTRATOR_SYSTEM

ALLOWED_SOURCE_TYPES = {"wiki", "code"}
ALLOWED_FRESHNESS = {"fresh", "stale", "unknown"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_WORKERS = ("librarian", "code_reader")
DEGRADED_STATUS_VALUES = {"degraded", "failed", "error", "blocked", "stale"}
DEGRADED_STATUS_KEYS = ("ingest_status", "proposal_status", "status")
PLACEHOLDER_MARKERS = ("todo", "placeholder", "no narrative available", "needs review")
STALE_DRIFT_VALUES = {"stale", "degraded", "failed", "error", "blocked", "outdated"}
MIN_MEANINGFUL_BODY_CHARS = 40
MAX_ORCHESTRATOR_WIKI_PAGE_CHARS = 40_000
MAX_ORCHESTRATOR_SEARCH_ROWS = 20
MAX_WORKER_WIKI_PAGE_CHARS = 80_000
ORCHESTRATED_CODE_READER_MAX_ITERS = 5
MAX_ORCHESTRATOR_TOOL_ITERS = 5
MAX_ORCHESTRATOR_WORKER_BATCHES = 5
ALLOWED_ORCHESTRATOR_GRAPH_TOOL_NAMES = {"cg_find", "cg_describe"}
REQUIRED_TOP_LEVEL_KEYS = {
    "answer_markdown",
    "citations",
    "evidence",
    "answer_evidence_map",
    "worker_plan",
    "worker_results",
    "gaps",
    "confidence",
}
UNCERTAINTY_WORDS = ("uncertain", "uncertainty", "may", "might", "appears", "suggests", "possibly")
FrozenValue = Mapping[str, Any] | tuple[Any, ...] | str | int | float | bool | None


class OrchestratorValidationError(ValueError):
    """Raised when orchestrator output does not match the structured contract."""


@dataclass(frozen=True)
class InitialCandidate:
    path: str
    score: float
    excerpt: str
    freshness: str = "unknown"
    staleness_reason: str | None = None


@dataclass(frozen=True)
class OrchestratorContext:
    query: str
    wiki_root: Path
    repo_root: Path | None
    initial_candidates: tuple[InitialCandidate, ...]
    graph_tools_available: bool
    graph_tool_names: tuple[str, ...]
    worker_capabilities: Mapping[str, Mapping[str, Any]]
    answer_contract: Mapping[str, Any]


@dataclass(frozen=True)
class OrchestratorEvidence:
    id: str
    source_type: str
    path: str
    freshness: str
    staleness_reason: str | None
    excerpt: str
    line_refs: list[str]


@dataclass(frozen=True)
class AnswerEvidenceMap:
    claim: str
    evidence_ids: list[str]


@dataclass(frozen=True)
class EvidenceGap:
    question: str
    reason: str


@dataclass(frozen=True)
class FreshnessClassification:
    freshness: str
    reason: str | None


@dataclass(frozen=True)
class WorkerTask:
    worker: str
    task_id: str
    query_focus: str
    expected_evidence: str
    page_path: str | None = None
    target_paths_or_hints: tuple[str, ...] = ()


@dataclass(frozen=True)
class OrchestratorOutput:
    answer_markdown: str
    citations: list[str]
    evidence: list[OrchestratorEvidence]
    answer_evidence_map: list[AnswerEvidenceMap]
    worker_plan: tuple[Mapping[str, Any], ...]
    worker_results: tuple[Mapping[str, Any], ...]
    gaps: list[EvidenceGap]
    confidence: str


@dataclass(frozen=True)
class QueryOrchestratorResult:
    output: OrchestratorOutput
    trace_metadata: Mapping[str, Any]


async def run_query_orchestrator(
    *,
    query: str,
    wiki_root: Path,
    repo_root: Path | None,
    initial_candidates: list[InitialCandidate] | tuple[InitialCandidate, ...],
    graph_tools: list[BaseTool],
    trace_dir: Path,
    role_model_overrides: Mapping[str, str] | None = None,
) -> QueryOrchestratorResult:
    """Run the bounded query-orchestration loop with safe degradation."""

    overrides = role_model_overrides or {}
    context = build_orchestrator_context(
        query=query,
        wiki=wiki_root,
        repo_root=repo_root,
        initial_candidates=initial_candidates,
        graph_tools=graph_tools,
    )
    tools = build_orchestrator_tools(wiki=wiki_root, graph_tools=graph_tools)
    llm = make_llm("query_orchestrator", model_override=overrides.get("query_orchestrator"))
    messages: list[Any] = [
        SystemMessage(content=QUERY_ORCHESTRATOR_SYSTEM),
        HumanMessage(content=_orchestrator_context_prompt(context)),
    ]
    trace_metadata: dict[str, Any] = {
        "status": "ok",
        "worker_batches": 0,
        "graph_tools_available": context.graph_tools_available,
        "graph_tool_names": list(context.graph_tool_names),
    }
    accumulated_worker_results: list[Mapping[str, Any]] = []

    for batch_index in range(MAX_ORCHESTRATOR_WORKER_BATCHES + 1):
        try:
            loop_result = await run_tool_loop(
                llm=llm,
                tools=tools,
                messages=messages,
                max_iterations=MAX_ORCHESTRATOR_TOOL_ITERS,
                cap_label="query orchestrator",
            )
        except Exception as exc:
            return _degraded_result(
                query=query,
                status="tool_loop_error",
                error=f"{type(exc).__name__}: {exc}",
                worker_batches=trace_metadata["worker_batches"],
                graph_tools_available=context.graph_tools_available,
                graph_tool_names=context.graph_tool_names,
            )

        if loop_result.status != "ok":
            return _degraded_result(
                query=query,
                status="tool_loop_failed",
                error=loop_result.error or loop_result.status,
                worker_batches=trace_metadata["worker_batches"],
                graph_tools_available=context.graph_tools_available,
                graph_tool_names=context.graph_tool_names,
            )

        try:
            output = parse_orchestrator_output(loop_result.final_text, require_stale_claim_gaps=True)
        except OrchestratorValidationError as exc:
            return _degraded_result(
                query=query,
                status=_degradation_status_for_validation_error(exc),
                error=str(exc),
                worker_batches=trace_metadata["worker_batches"],
                graph_tools_available=context.graph_tools_available,
                graph_tool_names=context.graph_tool_names,
            )

        if not output.worker_plan:
            trace_metadata["status"] = "ok"
            if loop_result.error:
                trace_metadata["tool_loop_error"] = loop_result.error
            return QueryOrchestratorResult(
                output=_output_with_authoritative_worker_results(output, accumulated_worker_results),
                trace_metadata=MappingProxyType(trace_metadata),
            )

        if batch_index >= MAX_ORCHESTRATOR_WORKER_BATCHES:
            trace_metadata["status"] = "capped"
            trace_metadata["error"] = f"worker batch cap reached ({MAX_ORCHESTRATOR_WORKER_BATCHES})"
            return QueryOrchestratorResult(
                output=_capped_output(
                    output,
                    query=query,
                    worker_results=accumulated_worker_results,
                    reason=trace_metadata["error"],
                ),
                trace_metadata=MappingProxyType(trace_metadata),
            )

        try:
            worker_tasks = parse_worker_tasks(output.worker_plan)
        except OrchestratorValidationError as exc:
            return _degraded_result(
                query=query,
                status="validation_error",
                error=str(exc),
                worker_batches=trace_metadata["worker_batches"],
                graph_tools_available=context.graph_tools_available,
                graph_tool_names=context.graph_tool_names,
            )

        try:
            worker_results = await run_worker_batch(
                worker_tasks,
                query=query,
                wiki_root=wiki_root,
                repo_root=repo_root,
                trace_dir=trace_dir,
                role_model_overrides=role_model_overrides,
            )
        except Exception as exc:
            return _degraded_result(
                query=query,
                status="worker_batch_error",
                error=f"{type(exc).__name__}: {exc}",
                worker_batches=trace_metadata["worker_batches"],
                graph_tools_available=context.graph_tools_available,
                graph_tool_names=context.graph_tool_names,
                worker_results=accumulated_worker_results,
            )
        trace_metadata["worker_batches"] += 1
        accumulated_worker_results.extend(worker_results)
        messages.append(AIMessage(content=loop_result.final_text))
        messages.append(
            HumanMessage(
                content=(
                    f"Worker batch {trace_metadata['worker_batches']} results:\n"
                    f"{json.dumps(_jsonable(worker_results), indent=2, sort_keys=True)}\n\n"
                    "Use these results to continue. Return final JSON with an empty worker_plan when sufficient."
                )
            )
        )

    return _degraded_result(
        query=query,
        status="capped",
        error=f"worker batch cap reached ({MAX_ORCHESTRATOR_WORKER_BATCHES})",
        worker_batches=trace_metadata["worker_batches"],
        graph_tools_available=context.graph_tools_available,
        graph_tool_names=context.graph_tool_names,
        worker_results=accumulated_worker_results,
    )


def degraded_output(query: str, *, reason: str) -> OrchestratorOutput:
    """Build a valid low-confidence output for orchestrator failure paths."""

    return OrchestratorOutput(
        answer_markdown=f"Insufficient evidence to answer safely. {reason}",
        citations=[],
        evidence=[],
        answer_evidence_map=[],
        worker_plan=(),
        worker_results=(),
        gaps=[
            EvidenceGap(
                question=query,
                reason=reason,
            )
        ],
        confidence="low",
    )


def _degraded_result(
    *,
    query: str,
    status: str,
    error: str,
    worker_batches: int,
    graph_tools_available: bool,
    graph_tool_names: tuple[str, ...],
    worker_results: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] = (),
) -> QueryOrchestratorResult:
    return QueryOrchestratorResult(
        output=_output_with_authoritative_worker_results(degraded_output(query, reason=error), worker_results),
        trace_metadata=MappingProxyType(
            {
                "status": status,
                "error": error,
                "worker_batches": worker_batches,
                "graph_tools_available": graph_tools_available,
                "graph_tool_names": list(graph_tool_names),
            }
        ),
    )


def _degradation_status_for_validation_error(exc: OrchestratorValidationError) -> str:
    if str(exc).startswith("Invalid JSON"):
        return "invalid_json"
    return "validation_error"


def _output_with_authoritative_worker_results(
    output: OrchestratorOutput,
    worker_results: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> OrchestratorOutput:
    if not worker_results:
        return output
    return OrchestratorOutput(
        answer_markdown=output.answer_markdown,
        citations=list(output.citations),
        evidence=list(output.evidence),
        answer_evidence_map=list(output.answer_evidence_map),
        worker_plan=output.worker_plan,
        worker_results=_freeze_worker_result_rows(worker_results),
        gaps=list(output.gaps),
        confidence=output.confidence,
    )


def _capped_output(
    output: OrchestratorOutput,
    *,
    query: str,
    worker_results: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    reason: str,
) -> OrchestratorOutput:
    return OrchestratorOutput(
        answer_markdown=output.answer_markdown,
        citations=list(output.citations),
        evidence=list(output.evidence),
        answer_evidence_map=list(output.answer_evidence_map),
        worker_plan=(),
        worker_results=_freeze_worker_result_rows(worker_results),
        gaps=[
            *output.gaps,
            EvidenceGap(
                question=query,
                reason=reason,
            ),
        ],
        confidence="low",
    )


def _freeze_worker_result_rows(
    rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> tuple[Mapping[str, Any], ...]:
    return tuple(_freeze_mapping(dict(_jsonable(row))) for row in rows)


def _orchestrator_context_prompt(context: OrchestratorContext) -> str:
    payload = {
        "query": context.query,
        "wiki_root": context.wiki_root.as_posix(),
        "repo_root": context.repo_root.as_posix() if context.repo_root is not None else None,
        "initial_candidates": [
            {
                "path": candidate.path,
                "score": candidate.score,
                "excerpt": candidate.excerpt,
                "freshness": candidate.freshness,
                "staleness_reason": candidate.staleness_reason,
            }
            for candidate in context.initial_candidates
        ],
        "graph_tools_available": context.graph_tools_available,
        "graph_tool_names": list(context.graph_tool_names),
        "worker_capabilities": _jsonable(context.worker_capabilities),
        "answer_contract": _jsonable(context.answer_contract),
        "worker_batch_cap": MAX_ORCHESTRATOR_WORKER_BATCHES,
    }
    return (
        "Answer the user query using the supplied context and tools. "
        "Return exactly one JSON object matching the contract.\n\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value


def build_orchestrator_context(
    *,
    query: str,
    wiki: Path,
    repo_root: Path | None,
    initial_candidates: list[InitialCandidate] | tuple[InitialCandidate, ...],
    graph_tools: list[BaseTool],
) -> OrchestratorContext:
    """Build the bounded context packet supplied to the query orchestrator."""

    allowed_graph_tools = filter_graph_tools(graph_tools, ALLOWED_ORCHESTRATOR_GRAPH_TOOL_NAMES)
    return OrchestratorContext(
        query=query,
        wiki_root=wiki.resolve(),
        repo_root=repo_root.resolve() if repo_root is not None else None,
        initial_candidates=tuple(initial_candidates),
        graph_tools_available=bool(allowed_graph_tools),
        graph_tool_names=tuple(graph_tool.name for graph_tool in allowed_graph_tools),
        worker_capabilities=_worker_capabilities(),
        answer_contract=_answer_contract(),
    )


def build_orchestrator_tools(*, wiki: Path, graph_tools: list[BaseTool]) -> list[BaseTool]:
    """Build direct planning tools for the query orchestrator.

    These tools are intentionally limited to bounded wiki reads, wiki catalog
    search, worker capability discovery, and read-only graph planning tools.
    Source-code reads stay behind code_reader worker tasks.
    """

    catalog = build_wiki_catalog(wiki)

    @tool
    def read_wiki_page(path: str) -> str:
        """Read one markdown page under the wiki root, bounded to a safe size."""
        return read_bounded_wiki_page(wiki, path, max_chars=MAX_ORCHESTRATOR_WIKI_PAGE_CHARS)

    @tool
    def search_wiki(query: str, kind: str | None = None, top_k: int = MAX_ORCHESTRATOR_SEARCH_ROWS) -> str:
        """Search the wiki catalog by title, summary, or slug and return JSON rows."""
        bounded_top_k = max(1, min(top_k, MAX_ORCHESTRATOR_SEARCH_ROWS))
        rows = search_catalog_rows(catalog, query, kind=kind, limit=bounded_top_k)
        return json.dumps(rows, indent=2, sort_keys=True)

    @tool
    def list_worker_capabilities() -> str:
        """Return the valid worker task shapes and limits as JSON."""
        return json.dumps(_worker_capabilities(), indent=2, sort_keys=True)

    allowed_graph_tools = filter_graph_tools(graph_tools, ALLOWED_ORCHESTRATOR_GRAPH_TOOL_NAMES)
    return [read_wiki_page, search_wiki, list_worker_capabilities, *allowed_graph_tools]


def parse_worker_tasks(rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]) -> tuple[WorkerTask, ...]:
    """Parse and validate orchestrator worker-plan rows."""

    if not isinstance(rows, list | tuple):
        raise OrchestratorValidationError("worker_plan must be a list of objects")

    tasks = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise OrchestratorValidationError("worker_plan rows must be objects")

        worker = _required_non_empty_mapping_str(row, "worker")
        if worker not in ALLOWED_WORKERS:
            raise OrchestratorValidationError(f"worker must be one of {list(ALLOWED_WORKERS)}; got {worker!r}")

        task = WorkerTask(
            worker=worker,
            task_id=_required_non_empty_mapping_str(row, "task_id"),
            query_focus=_required_non_empty_mapping_str(row, "query_focus"),
            expected_evidence=_required_non_empty_mapping_str(row, "expected_evidence"),
            page_path=_parse_worker_page_path(row, worker),
            target_paths_or_hints=_parse_worker_target_hints(row, worker),
        )
        tasks.append(task)
    return tuple(tasks)


async def run_worker_batch(
    worker_tasks: list[WorkerTask] | tuple[WorkerTask, ...],
    *,
    query: str,
    wiki_root: Path,
    repo_root: Path | None,
    trace_dir: Path,
    role_model_overrides: Mapping[str, str] | None = None,
) -> tuple[Mapping[str, Any], ...]:
    """Dispatch orchestrated librarian/code-reader tasks and record partial failures."""

    if not worker_tasks:
        return ()

    pool = SubagentPool(trace_dir)
    results: list[Mapping[str, Any]] = []
    overrides = role_model_overrides or {}

    for role in ALLOWED_WORKERS:
        role_tasks = [task for task in worker_tasks if task.worker == role]
        if not role_tasks:
            continue

        cfg = load_role_config(role)
        llm = make_llm(role, model_override=overrides.get(role))
        if role == "librarian":
            task_runner = _build_librarian_task_runner(llm, query=query, wiki_root=wiki_root)
        else:
            if repo_root is None:
                results.extend(
                    _worker_error_row(task, "repo_root is required for code_reader workers") for task in role_tasks
                )
                continue
            task_runner = _build_code_reader_task_runner(llm, query=query, repo_root=repo_root)

        fan_result: FanOutResult = await pool.run_all(
            items=role_tasks,
            task=task_runner,
            role=role,
            model_id=str(cfg["model_id"]),
            max_concurrency=int(cfg["max_concurrency"]),
        )
        results.extend(_worker_success_row(item, result) for item, result in fan_result.successes)
        results.extend(_worker_failure_from_error(error) for error in fan_result.errors)

    return tuple(results)


def _worker_capabilities() -> Mapping[str, Mapping[str, Any]]:
    return {
        "librarian": {
            "description": "Extract relevant evidence from one wiki page.",
            "required_fields": ("page_path", "query_focus", "expected_evidence"),
            "limits": {"page_path": "relative markdown path under wiki root"},
        },
        "code_reader": {
            "description": "Verify source-backed claims through bounded source-reading worker tasks.",
            "required_fields": ("target_paths_or_hints", "query_focus", "expected_evidence"),
            "limits": {
                "target_paths_or_hints": "repo-relative paths or search hints; no direct repo files are read by "
                "orchestrator planning tools"
            },
        },
    }


def _required_non_empty_mapping_str(row: Mapping[str, Any], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise OrchestratorValidationError(f"{field} must be a non-empty string")
    return value


def _parse_worker_page_path(row: Mapping[str, Any], worker: str) -> str | None:
    if worker != "librarian":
        return None
    return _required_non_empty_mapping_str(row, "page_path")


def _parse_worker_target_hints(row: Mapping[str, Any], worker: str) -> tuple[str, ...]:
    if worker != "code_reader":
        return ()
    value = row.get("target_paths_or_hints")
    if not isinstance(value, list | tuple) or not value:
        raise OrchestratorValidationError("target_paths_or_hints must be a non-empty list of strings")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise OrchestratorValidationError("target_paths_or_hints must be a non-empty list of strings")
    return tuple(value)


def _build_librarian_task_runner(llm: Any, *, query: str, wiki_root: Path):
    async def librarian_worker(task: WorkerTask) -> TaskResult:
        page_path = task.page_path or ""
        page_text = read_bounded_wiki_page(wiki_root, page_path, max_chars=MAX_WORKER_WIKI_PAGE_CHARS)
        response = await llm.ainvoke(
            [
                SystemMessage(content=LIBRARIAN_SYSTEM),
                HumanMessage(
                    content=(
                        f"Query: {query}\n\n"
                        f"Worker task: {task.task_id}\n"
                        f"Query focus: {task.query_focus}\n"
                        f"Expected evidence: {task.expected_evidence}\n\n"
                        f"Page ({page_path}):\n{page_text}"
                    )
                ),
            ]
        )
        return TaskResult(value=getattr(response, "content", "") or "", response=response)

    return librarian_worker


def _build_code_reader_task_runner(llm_raw: Any, *, query: str, repo_root: Path):
    async def code_reader_worker(task: WorkerTask) -> TaskResult:
        @tool
        def read_file(path: str) -> str:
            """Read one source file allowed by this worker task's target hints."""
            return _read_worker_scoped_file(repo_root, path, task.target_paths_or_hints)

        llm = llm_raw.bind_tools([read_file])
        hints = "\n".join(f"- {hint}" for hint in task.target_paths_or_hints)
        messages: list[Any] = [
            SystemMessage(content=ORCHESTRATED_CODE_READER_SYSTEM),
            HumanMessage(
                content=(
                    f"Query: {query}\n\n"
                    f"Worker task: {task.task_id}\n"
                    f"Query focus: {task.query_focus}\n"
                    f"Expected evidence: {task.expected_evidence}\n\n"
                    "Target paths or hints:\n"
                    f"{hints}\n\n"
                    "Read only plausible repo-relative source paths through the read_file tool."
                )
            ),
        ]
        for _ in range(ORCHESTRATED_CODE_READER_MAX_ITERS):
            response = await llm.ainvoke(messages)
            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                return TaskResult(value=getattr(response, "content", "") or "", response=response)
            messages.append(response)
            for call in tool_calls:
                call_args = call.get("args", {}) if isinstance(call, dict) else {}
                call_id = call.get("id", "") if isinstance(call, dict) else ""
                requested = call_args.get("path", "")
                tool_output = _read_worker_scoped_file(repo_root, requested, task.target_paths_or_hints)
                messages.append(ToolMessage(content=tool_output, tool_call_id=call_id))
        return TaskResult(value="NO_RELEVANT_CONTENT", response=None)

    return code_reader_worker


def _read_worker_scoped_file(repo_root: Path, requested_path: str, hints: tuple[str, ...]) -> str:
    if not _path_allowed_by_worker_hints(repo_root, requested_path, hints):
        return f"ERROR: refusing to read {requested_path!r}: outside this worker task's target_paths_or_hints"
    try:
        return _read_file_bounded(repo_root, requested_path)
    except PermissionError as exc:
        return f"ERROR: {exc}"
    except OSError as exc:
        return f"ERROR: {exc}"


def _path_allowed_by_worker_hints(repo_root: Path, requested_path: str, hints: tuple[str, ...]) -> bool:
    requested = _repo_relative_posix(repo_root, requested_path)
    if requested is None:
        return False
    for hint in hints:
        normalized_hint = _repo_relative_posix(repo_root, hint)
        if normalized_hint is None:
            continue
        if requested == normalized_hint:
            return True
        hint_is_directoryish = hint.endswith("/") or not Path(normalized_hint).suffix
        if hint_is_directoryish and requested.startswith(normalized_hint.rstrip("/") + "/"):
            return True
    return False


def _repo_relative_posix(repo_root: Path, path: str) -> str | None:
    if not isinstance(path, str) or not path.strip():
        return None
    root = repo_root.resolve(strict=False)
    candidate = (repo_root / path).resolve(strict=False)
    if not candidate.is_relative_to(root):
        return None
    return candidate.relative_to(root).as_posix()


def _worker_success_row(task: WorkerTask, result: Any) -> Mapping[str, Any]:
    return _freeze_mapping(
        {
            "task_id": task.task_id,
            "worker": task.worker,
            "status": "complete",
            "result": str(result or ""),
        }
    )


def _worker_failure_from_error(error: PerItemError) -> Mapping[str, Any]:
    task = error.item
    if isinstance(task, WorkerTask):
        return _worker_error_row(task, str(error.exception))
    return _freeze_mapping(
        {
            "task_id": "",
            "worker": "",
            "status": "error",
            "error": str(error.exception),
        }
    )


def _worker_error_row(task: WorkerTask, error: str) -> Mapping[str, Any]:
    return _freeze_mapping(
        {
            "task_id": task.task_id,
            "worker": task.worker,
            "status": "error",
            "error": error,
        }
    )


def _answer_contract() -> Mapping[str, Any]:
    return MappingProxyType(
        {
            "answer_markdown": "Markdown final answer.",
            "citations": "List of cited wiki/code paths.",
            "evidence": (
                "Rows with id, source_type, path, freshness, staleness_reason, excerpt, and line_refs. "
                "source_type must be wiki or code."
            ),
            "answer_evidence_map": "Claim-to-evidence id mapping.",
            "worker_plan": "Worker tasks requested by the orchestrator.",
            "worker_results": "Worker result summaries considered by the orchestrator.",
            "gaps": "Explicit unanswered questions or stale-only evidence gaps.",
            "confidence": "One of high, medium, or low.",
        }
    )


def classify_wiki_freshness(page_path: Path, *, repo_head: str | None) -> FreshnessClassification:
    """Classify whether wiki evidence is fresh enough to use as current evidence."""

    try:
        text = page_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return FreshnessClassification(freshness="unknown", reason="wiki page not found")

    metadata = frontmatter.loads(text).metadata
    body = body_without_frontmatter(text)

    if _drift_review_is_stale(metadata.get("drift_review")):
        return FreshnessClassification(freshness="stale", reason="drift_review")

    last_updated_commit = metadata.get("last_updated_commit")
    if repo_head and last_updated_commit and str(last_updated_commit) != repo_head:
        return FreshnessClassification(freshness="stale", reason="last_updated_commit mismatch")

    if _has_placeholder_content(body):
        return FreshnessClassification(freshness="stale", reason="placeholder content")

    if _has_degraded_status(metadata):
        return FreshnessClassification(freshness="stale", reason="degraded status")

    if repo_head and last_updated_commit and str(last_updated_commit) == repo_head:
        return FreshnessClassification(freshness="fresh", reason=None)

    return FreshnessClassification(freshness="unknown", reason=None)


def parse_orchestrator_output(
    raw: str | dict[str, Any],
    *,
    require_stale_claim_gaps: bool = False,
) -> OrchestratorOutput:
    """Parse raw orchestrator output and validate its structured contract.

    Parsing always performs structural and cross-reference validation. Pass
    require_stale_claim_gaps=True to also require stale-only claim support to
    include an explicit gap or uncertainty wording.
    """

    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OrchestratorValidationError(f"Invalid JSON orchestrator output: {exc}") from exc
    else:
        payload = raw

    if not isinstance(payload, dict):
        raise OrchestratorValidationError("Orchestrator output must be a JSON object")
    _validate_top_level_keys(payload)

    output = OrchestratorOutput(
        answer_markdown=_required_non_empty_str(payload, "answer_markdown"),
        citations=_str_list(payload["citations"], "citations"),
        evidence=_parse_evidence_rows(payload["evidence"]),
        answer_evidence_map=_parse_answer_evidence_map(payload["answer_evidence_map"]),
        worker_plan=_object_tuple(payload["worker_plan"], "worker_plan"),
        worker_results=_object_tuple(payload["worker_results"], "worker_results"),
        gaps=_parse_gaps(payload["gaps"]),
        confidence=_required_non_empty_str(payload, "confidence"),
    )
    validate_orchestrator_output(output, require_stale_claim_gaps=require_stale_claim_gaps)
    return output


def _drift_review_is_stale(value: Any) -> bool:
    if not value:
        return False
    if isinstance(value, dict):
        return any(
            _stale_drift_value(value.get(key)) for key in ("status", "reason", "verdict", "state") if key in value
        )
    if isinstance(value, list | tuple | set):
        return any(_drift_review_is_stale(item) for item in value)
    return _stale_drift_value(value)


def _stale_drift_value(value: Any) -> bool:
    if isinstance(value, dict):
        return _drift_review_is_stale(value)
    if isinstance(value, list | tuple | set):
        return any(_stale_drift_value(item) for item in value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"", "false", "none", "null", "[]", "{}"}:
            return False
        return normalized in STALE_DRIFT_VALUES
    if value is None:
        return False
    return str(value).strip().lower() in STALE_DRIFT_VALUES


def _has_placeholder_content(body: str) -> bool:
    normalized = " ".join(body.split()).lower()
    if len(normalized) < MIN_MEANINGFUL_BODY_CHARS:
        return True
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def _has_degraded_status(metadata: Mapping[str, Any]) -> bool:
    return any(_status_value_is_stale(metadata.get(key)) for key in DEGRADED_STATUS_KEYS)


def _status_value_is_stale(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_status_value_is_stale(item) for item in value.values())
    if isinstance(value, list | tuple | set):
        return any(_status_value_is_stale(item) for item in value)
    if value is None:
        return False
    return str(value).strip().lower() in DEGRADED_STATUS_VALUES


def _validate_top_level_keys(payload: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - payload.keys())
    if missing:
        raise OrchestratorValidationError(f"Missing required top-level orchestrator output keys: {missing}")
    extra = sorted(payload.keys() - REQUIRED_TOP_LEVEL_KEYS)
    if extra:
        raise OrchestratorValidationError(f"Unexpected top-level orchestrator output keys: {extra}")


def validate_orchestrator_output(
    output: OrchestratorOutput,
    require_stale_claim_gaps: bool = True,
) -> None:
    """Validate cross-field invariants in parsed orchestrator output."""

    if not output.answer_markdown.strip():
        raise OrchestratorValidationError("answer_markdown must be non-empty")
    if output.confidence not in ALLOWED_CONFIDENCE:
        raise OrchestratorValidationError(
            f"confidence must be one of {sorted(ALLOWED_CONFIDENCE)}; got {output.confidence!r}"
        )

    evidence_ids: set[str] = set()
    evidence_by_id: dict[str, OrchestratorEvidence] = {}
    for row in output.evidence:
        if not row.id.strip():
            raise OrchestratorValidationError("evidence id must be non-empty")
        if row.id in evidence_ids:
            raise OrchestratorValidationError(f"evidence ids must be unique; duplicate {row.id!r}")
        evidence_ids.add(row.id)
        evidence_by_id[row.id] = row

        if row.source_type not in ALLOWED_SOURCE_TYPES:
            raise OrchestratorValidationError(
                f"source_type must be one of {sorted(ALLOWED_SOURCE_TYPES)}; got {row.source_type!r}"
            )
        if row.freshness not in ALLOWED_FRESHNESS:
            raise OrchestratorValidationError(
                f"freshness must be one of {sorted(ALLOWED_FRESHNESS)}; got {row.freshness!r}"
            )
        if not row.path.strip():
            raise OrchestratorValidationError("evidence path must be non-empty")
        if row.staleness_reason is not None and not row.staleness_reason.strip():
            raise OrchestratorValidationError("evidence staleness_reason must be non-empty when present")
        if not row.excerpt.strip():
            raise OrchestratorValidationError("evidence excerpt must be non-empty")

    for row in output.answer_evidence_map:
        if not row.claim.strip():
            raise OrchestratorValidationError("answer_evidence_map claim must be non-empty")
        missing_ids = [evidence_id for evidence_id in row.evidence_ids if evidence_id not in evidence_by_id]
        if missing_ids:
            raise OrchestratorValidationError(f"answer_evidence_map references missing evidence ids: {missing_ids}")

        if require_stale_claim_gaps and _is_stale_only_claim(row, evidence_by_id):
            if not output.gaps and not _contains_uncertainty_note(output.answer_markdown):
                raise OrchestratorValidationError(
                    "stale-only claim support requires a gap entry or uncertainty wording in answer_markdown"
                )


def _required_non_empty_str(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise OrchestratorValidationError(f"{field} must be a non-empty string")
    return value


def _str_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError(f"{field} must be a list of strings")
    if not all(isinstance(item, str) for item in value):
        raise OrchestratorValidationError(f"{field} must be a list of strings")
    return list(value)


def _object_tuple(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError(f"{field} must be a list of objects")
    if not all(isinstance(item, dict) for item in value):
        raise OrchestratorValidationError(f"{field} must be a list of objects")
    return tuple(_freeze_mapping(item) for item in value)


def _freeze_mapping(value: dict[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})


def _freeze_value(value: Any) -> FrozenValue:
    if isinstance(value, dict):
        return _freeze_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def _parse_evidence_rows(value: Any) -> list[OrchestratorEvidence]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError("evidence must be a list")
    rows = []
    for item in value:
        if not isinstance(item, dict):
            raise OrchestratorValidationError("evidence rows must be objects")
        rows.append(
            OrchestratorEvidence(
                id=_required_non_empty_str(item, "id"),
                source_type=_required_non_empty_str(item, "source_type"),
                path=_required_non_empty_str(item, "path"),
                freshness=_required_non_empty_str(item, "freshness"),
                staleness_reason=_optional_non_empty_str(item, "staleness_reason"),
                excerpt=_required_non_empty_str(item, "excerpt"),
                line_refs=_str_list(item.get("line_refs"), "line_refs"),
            )
        )
    return rows


def _optional_non_empty_str(payload: dict[str, Any], field: str) -> str | None:
    if field not in payload:
        raise OrchestratorValidationError(f"{field} must be present")
    value = payload[field]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise OrchestratorValidationError(f"{field} must be a string or null")
    return value


def _parse_answer_evidence_map(value: Any) -> list[AnswerEvidenceMap]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError("answer_evidence_map must be a list")
    rows = []
    for item in value:
        if not isinstance(item, dict):
            raise OrchestratorValidationError("answer_evidence_map rows must be objects")
        if "evidence_ids" not in item:
            raise OrchestratorValidationError("answer_evidence_map rows must include evidence_ids")
        evidence_ids = _str_list(item["evidence_ids"], "evidence_ids")
        if not evidence_ids:
            raise OrchestratorValidationError("answer_evidence_map evidence_ids must be non-empty")
        rows.append(
            AnswerEvidenceMap(
                claim=_required_non_empty_str(item, "claim"),
                evidence_ids=evidence_ids,
            )
        )
    return rows


def _parse_gaps(value: Any) -> list[EvidenceGap]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError("gaps must be a list")
    gaps = []
    for item in value:
        if not isinstance(item, dict):
            raise OrchestratorValidationError("gaps rows must be objects")
        gaps.append(
            EvidenceGap(
                question=_required_non_empty_str(item, "question"),
                reason=_required_non_empty_str(item, "reason"),
            )
        )
    return gaps


def _is_stale_only_claim(row: AnswerEvidenceMap, evidence_by_id: dict[str, OrchestratorEvidence]) -> bool:
    if not row.evidence_ids:
        return False
    mapped_evidence = [evidence_by_id[evidence_id] for evidence_id in row.evidence_ids]
    return all(evidence.freshness == "stale" for evidence in mapped_evidence)


def _contains_uncertainty_note(answer_markdown: str) -> bool:
    answer_lower = answer_markdown.lower()
    return any(_contains_uncertainty_word(answer_lower, word) for word in UNCERTAINTY_WORDS)


def _contains_uncertainty_word(answer_lower: str, word: str) -> bool:
    if word == "may":
        return re.search(r"\bmay\b(?!\s+\d{4}\b)", answer_lower) is not None
    return re.search(rf"\b{re.escape(word)}\b", answer_lower) is not None
