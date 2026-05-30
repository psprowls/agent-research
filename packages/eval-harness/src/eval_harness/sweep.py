"""Model sweep runner: iterate N model IDs over eval cases, collect SweepResult records.

run_sweep() is the primary entry point. It:
1. Loads cases from a JSON file (validates schema per T-4-01).
2. For each (model_id, case) pair, opens an EvalWorktree and calls run_query().
3. Collects SweepResult per run, with partial-failure isolation via asyncio.gather.
4. Appends structural checks, token counts, and cost estimates to each SweepResult.

run_role_sweep() is the Phase 7 addition for the cost-frontier sweep (SWEEP-01).
It runs a single (role, candidate) cell using the single-role-swap protocol (D-06):
the role-under-test uses candidate_model_id while all other roles stay at their
models.toml defaults.  ROLE_COMMAND_MAP routes each role to the appropriate command
function (_sweep_query_role, _sweep_scan_role, _sweep_lint_role, _sweep_ingest_role).

Token counts are extracted from the trace JSONL written by SubagentPool._write_trace
into wt.path / "wiki" / ".graph-wiki" / "traces" (wt.path is the workspace root after
the Phase 22 rename; wiki content lives under wt.path/wiki). The most-recently-modified
JSONL file is parsed; tokens_in/tokens_out are summed across all records for the run.

Every public function in this module accepts ``workspace_path: Path`` and derives the
wiki dir internally via ``workspace_io.paths.wiki_dir(workspace_path)`` (Phase 24 §D-01,
§D-09). EvalWorktree call sites operate on the derived wiki path.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

from langchain_aws import ChatBedrockConverse

from graph_wiki_agent.commands.ingest import run_ingest_source
from graph_wiki_agent.commands.lint import run_lint
from graph_wiki_agent.commands.query import QueryResult, run_query
from graph_wiki_agent.commands.scan import run_scan

from workspace_io.paths import wiki_dir

from eval_harness.divergence import ROLE_CHECKS, ROLE_RUBRICS
from eval_harness.divergence.metric import DivergenceMetric
from eval_harness.isolation import EvalWorktree
from eval_harness.preflight import HARD_CAP_USD, estimate_sweep_cost, preflight_bed01, preflight_check  # noqa: F401
from eval_harness.pricing import UnknownModelError, cost_for_usage
from eval_harness.structural import check_structural
from eval_harness.two_gate import ROLES_WITH_DIVERGENCE, TwoGateOutcome, score_two_gate  # noqa: F401

# Package baselines dir: packages/eval-harness/baselines (recorded divergence floors).
# sweep.py is at packages/eval-harness/src/eval_harness/sweep.py -> parents[2] = packages/eval-harness.
_BASELINES_DIR = Path(__file__).resolve().parents[2] / "baselines"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Usage capture: bypass the trace pipeline (which loses usage_metadata when
# closures return resp.content strings) by wrapping ChatBedrockConverse.ainvoke
# once at import time.  Each cell sets a per-task contextvar bucket; concurrent
# cells stay isolated via asyncio task-local context propagation.
# ---------------------------------------------------------------------------
_USAGE_CAPTURE: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    "_eval_harness_usage_capture", default=None
)

_ORIG_AINVOKE = ChatBedrockConverse.ainvoke


async def _capturing_ainvoke(self, *args, **kwargs):
    result = await _ORIG_AINVOKE(self, *args, **kwargs)
    bucket = _USAGE_CAPTURE.get()
    if bucket is not None:
        meta = getattr(result, "usage_metadata", None)
        if meta:
            bucket.append({
                "model_id": getattr(self, "model_id", None),
                "tokens_in": meta.get("input_tokens"),
                "tokens_out": meta.get("output_tokens"),
            })
    return result


ChatBedrockConverse.ainvoke = _capturing_ainvoke  # type: ignore[assignment]


def _aggregate_usage(bucket: list) -> tuple[int | None, int | None, float | None]:
    """Sum tokens_in / tokens_out across all captured calls and compute total cost.

    cost_usd is computed PER call (not aggregated by candidate) because the
    sweep mixes candidate + default model calls in a single cell; the candidate
    line items dominate cost only for the role under test.  We return the
    total cost across ALL calls in the cell for raw accounting; the per-role
    Pareto frontier uses model_id-grouped accounting downstream.
    """
    if not bucket:
        return None, None, None
    total_in = sum(b["tokens_in"] for b in bucket if b["tokens_in"] is not None) or None
    total_out = sum(b["tokens_out"] for b in bucket if b["tokens_out"] is not None) or None
    cost = 0.0
    have_any_cost = False
    for b in bucket:
        m = b.get("model_id")
        ti = b.get("tokens_in")
        to = b.get("tokens_out")
        if not (m and ti is not None and to is not None):
            continue
        try:
            cost += cost_for_usage(m, {"input": ti, "output": to})
            have_any_cost = True
        except (UnknownModelError, KeyError):
            continue
    return total_in, total_out, (cost if have_any_cost else None)


@dataclass
class SweepResult:
    """Result of a single (model_id, case) sweep run.

    Fields:
        model_id:      Raw Bedrock model ID (used for API calls).
        safe_model_id: model_id with non-filename-safe chars replaced by "_"
                       (T-4-02: re.sub applied before any filename construction).
        query:         The query string from the eval case.
        answer:        Synthesized answer from run_query().
        citations:     List of wikilink targets in the answer.
        pages_drilled: Number of librarian pages successfully drilled.
        tokens_in:     Total input tokens across all trace records (None if unavailable).
        tokens_out:    Total output tokens across all trace records (None if unavailable).
        cost_usd:      Estimated USD cost (None if model unknown or tokens unavailable).
        wall_seconds:  Wall-clock seconds for the run_query() call.
        structural:    EVAL-06 structural check dict from check_structural().
        status:        "ok" if run_query() succeeded, "error" if it raised.
        judge_scores:  Reserved for Plan 03 judge scoring; None until populated.
        seed:          None — librarian role is non-deterministic (temperature != 0).
                       Judges use temperature=0 (deterministic), but seed is not
                       exposed by Bedrock Converse API. Reserved for future use.
    """

    model_id: str
    safe_model_id: str
    query: str
    answer: str
    citations: list[str]
    pages_drilled: int
    tokens_in: int | None
    tokens_out: int | None
    cost_usd: float | None
    wall_seconds: float
    structural: dict
    status: str = "ok"
    judge_scores: dict | None = None
    seed: int | None = None


def _sanitize_model_id(model_id: str) -> str:
    """Replace non-filename-safe characters with underscores.

    Security (T-4-02): model_id may contain colons (e.g. 'us.amazon.nova-pro-v1:0').
    The sanitized form is used ONLY for filename components; the original model_id
    is used for all API calls.

    Example: 'us.amazon.nova-pro-v1:0' -> 'us.amazon.nova-pro-v1_0'
    """
    return re.sub(r"[^a-zA-Z0-9._-]", "_", model_id)


def _extract_tokens_from_traces(trace_dir: Path) -> tuple[int | None, int | None]:
    """Sum tokens_in and tokens_out from the most recently modified JSONL trace file.

    Returns (tokens_in, tokens_out) — both None if no trace file found or
    if the trace contains no token records.
    """
    if not trace_dir.exists():
        return None, None

    jsonl_files = sorted(trace_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not jsonl_files:
        return None, None

    # Use the most recently modified file (the one written for this run)
    latest = jsonl_files[-1]
    total_in = 0
    total_out = 0
    found_any = False

    try:
        for line in latest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            ti = record.get("tokens_in")
            to = record.get("tokens_out")
            if ti is not None:
                total_in += int(ti)
                found_any = True
            if to is not None:
                total_out += int(to)
                found_any = True
    except OSError:
        return None, None

    if not found_any:
        return None, None
    return total_in, total_out


def _load_and_validate_cases(cases_path: Path) -> list[dict]:
    """Load eval cases from JSON, skipping entries that fail schema validation.

    Security (T-4-01): Each case must have "query" (str) and "expected_answer" (str).
    Invalid entries are skipped with a logged warning — they never reach run_query().
    """
    with cases_path.open(encoding="utf-8") as f:
        raw_cases: list[dict] = json.load(f)

    valid: list[dict] = []
    for i, case in enumerate(raw_cases):
        if not isinstance(case.get("query"), str):
            logger.warning(
                "cases[%d] missing required 'query' string key — skipped (T-4-01)", i
            )
            continue
        if not isinstance(case.get("expected_answer"), str):
            logger.warning(
                "cases[%d] missing required 'expected_answer' string key — skipped (T-4-01)", i
            )
            continue
        valid.append(case)

    return valid


async def run_sweep(
    cases_path: Path,
    workspace_path: Path,
    model_ids: list[str],
) -> list[SweepResult]:
    """Run a model sweep: for each model_id, run all eval cases under isolation.

    For each (model_id, case) pair:
    - Opens an EvalWorktree (isolated wiki copy in tmpdir).
    - Calls run_query() with librarian_model_override=model_id.
    - Collects tokens from trace JSONL and computes cost via pricing.
    - Runs check_structural() on the QueryResult.
    - Produces a SweepResult with status="ok" or status="error".

    Partial-failure isolation: asyncio.gather(return_exceptions=True) ensures
    one failing model does not abort the sweep — other models continue.

    Args:
        cases_path:     Path to query_cases.json; cases missing schema keys are skipped.
        workspace_path: Path to the source workspace root; the wiki is derived
                        internally via wiki_dir(workspace_path) (D-01/D-09).
        model_ids:      List of Bedrock model IDs to sweep over.

    Returns:
        List of SweepResult (one per (model_id, case) pair that was attempted).
    """
    cases = _load_and_validate_cases(cases_path)
    wiki = wiki_dir(workspace_path)

    async def _run_one(model_id: str, case: dict) -> SweepResult:
        safe_model_id = _sanitize_model_id(model_id)
        query = case["query"]

        async with EvalWorktree(wiki) as wt:
            t0 = time.monotonic()
            try:
                result: QueryResult = await run_query(
                    query,
                    workspace_path=wt.path,
                    top_k=5,
                    librarian_model_override=model_id,
                )
                wall_seconds = time.monotonic() - t0

                # Extract token counts from trace JSONL
                trace_dir = wt.path / "wiki" / ".graph-wiki" / "traces"
                tokens_in, tokens_out = _extract_tokens_from_traces(trace_dir)

                # Compute cost (None if model unknown or tokens unavailable)
                cost_usd: float | None = None
                if tokens_in is not None and tokens_out is not None:
                    try:
                        cost_usd = cost_for_usage(
                            model_id, {"input": tokens_in, "output": tokens_out}
                        )
                    except (UnknownModelError, KeyError):
                        cost_usd = None

                structural = check_structural(result, wt.path)

                return SweepResult(
                    model_id=model_id,
                    safe_model_id=safe_model_id,
                    query=query,
                    answer=result.answer,
                    citations=result.citations,
                    pages_drilled=result.pages_drilled,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost_usd,
                    wall_seconds=wall_seconds,
                    structural=structural,
                    status="ok",
                    seed=None,
                )

            except Exception as exc:
                wall_seconds = time.monotonic() - t0
                logger.warning(
                    "Sweep run failed: model=%s query=%r error=%s",
                    model_id,
                    query,
                    exc,
                )
                return SweepResult(
                    model_id=model_id,
                    safe_model_id=safe_model_id,
                    query=query,
                    answer="",
                    citations=[],
                    pages_drilled=0,
                    tokens_in=None,
                    tokens_out=None,
                    cost_usd=None,
                    wall_seconds=wall_seconds,
                    structural={},
                    status="error",
                    seed=None,
                )

    # Build coroutine list: all (model_id, case) pairs
    coros = [_run_one(model_id, case) for model_id in model_ids for case in cases]

    # return_exceptions=True: one failure does NOT abort siblings
    raw = await asyncio.gather(*coros, return_exceptions=True)

    results: list[SweepResult] = []
    for item in raw:
        if isinstance(item, SweepResult):
            results.append(item)
        elif isinstance(item, BaseException):
            # asyncio.gather itself raised — should not happen with return_exceptions=True
            logger.error("Unexpected gather exception: %s", item)

    return results


# ---------------------------------------------------------------------------
# Phase 7 additions: role-rotation sweep (SWEEP-01, D-06)
# ---------------------------------------------------------------------------

# Maps role name → which command function to call for a sweep cell.
# librarian/synthesizer/code_reader go through run_query with role_model_overrides.
# scanner/linter/ingestor each have their own run_* entry point with model_override.
ROLE_COMMAND_MAP: dict[str, str] = {
    "librarian":   "_sweep_query_role",
    "synthesizer": "_sweep_query_role",
    "code_reader": "_sweep_query_role",
    "scanner":     "_sweep_scan_role",
    "linter":      "_sweep_lint_role",
    "ingestor":    "_sweep_ingest_role",
}


async def _sweep_query_role(
    role: str,
    candidate_model_id: str,
    case: dict,
    workspace_path: Path,
) -> tuple[QueryResult, str]:
    """Run a query sweep cell for librarian/synthesizer/code_reader.

    Passes role_model_overrides={role: candidate_model_id} to run_query so only
    the role under test uses the candidate; all others keep their defaults (D-06).

    Returns:
        (QueryResult, answer_text) tuple.
    """
    result: QueryResult = await run_query(
        case["query"],
        workspace_path=workspace_path,
        role_model_overrides={role: candidate_model_id},
    )
    return result, result.answer


async def _sweep_scan_role(
    role: str,
    candidate_model_id: str,
    case: dict,
    workspace_path: Path,
) -> tuple[object, str]:
    """Run a scan sweep cell for the scanner role.

    Args:
        role:               Must be "scanner".
        candidate_model_id: Bedrock model ID to pass as model_override.
        case:               Eval case dict (query key used for the answer stub).
        workspace_path:     Workspace root for the isolated worktree.

    Returns:
        (ScanResult, summary_string) tuple.
    """
    from graph_wiki_agent.commands.scan import ScanResult  # noqa: PLC0415

    result = await run_scan(
        workspace_path=workspace_path,
        model_override=candidate_model_id,
    )
    # Produce a short summary string for structural checks
    summary = (
        f"scan: added={result.added} updated={result.updated} errors={result.errors}"
    )
    return result, summary


async def _sweep_lint_role(
    role: str,
    candidate_model_id: str,
    case: dict,
    workspace_path: Path,
) -> tuple[object, str]:
    """Run a lint sweep cell for the linter role.

    Args:
        role:               Must be "linter".
        candidate_model_id: Bedrock model ID to pass as model_override.
        case:               Eval case dict (unused for lint).
        workspace_path:     Workspace root for the isolated worktree.

    Returns:
        (LintResult, summary_string) tuple.
    """
    result = await run_lint(
        workspace_path=workspace_path,
        model_override=candidate_model_id,
    )
    summary = f"lint: orphans={result.orphans} errors={result.errors}"
    return result, summary


async def _sweep_ingest_role(
    role: str,
    candidate_model_id: str,
    case: dict,
    workspace_path: Path,
) -> tuple[object, str]:
    """Run an ingest sweep cell for the ingestor role.

    The case dict may provide a ``source_path`` key pointing to a source file to
    ingest.  When absent, the workspace's wiki dir is used as a synthetic target
    so token counts are still captured.  See module docstring for the fixture
    convention.

    Args:
        role:               Must be "ingestor".
        candidate_model_id: Bedrock model ID to pass as model_override.
        case:               Eval case dict — ``source_path`` key is optional.
        workspace_path:     Workspace root for the isolated worktree.

    Returns:
        (IngestResult, summary_string) tuple.
    """
    if "source_path" in case:
        source_path = Path(case["source_path"])
    else:
        # Fallback: use the wiki dir as source (the ingestor accepts any Path).
        source_path = wiki_dir(workspace_path)

    result = await run_ingest_source(
        source_path=source_path,
        workspace_path=workspace_path,
        model_override=candidate_model_id,
    )
    summary = f"ingest: page_path={result.page_path} status={result.status}"
    return result, summary


async def run_role_sweep(
    role: str,
    candidate_model_id: str,
    cases_path: Path,
    workspace_path: Path,
    repeats: int = 3,
    semaphore: asyncio.Semaphore | None = None,
) -> list[SweepResult]:
    """Single-role-swap sweep: run one (role, candidate) cell across all eval cases.

    For each (case, repeat_idx) pair:
    - Acquires the shared semaphore (default: Semaphore(8)) to throttle Bedrock
      rate limits (Pitfall 4).
    - Opens an EvalWorktree for wiki isolation.
    - Dispatches to the appropriate command function via ROLE_COMMAND_MAP.
    - Extracts tokens from the trace JSONL and computes cost.
    - Produces a SweepResult per run.

    Partial-failure isolation: asyncio.gather(return_exceptions=True) ensures one
    failing cell does not abort the entire sweep matrix (mirrors run_sweep pattern).

    Note: Two-gate scoring (score_two_gate) is NOT called here — it is the
    responsibility of the outer multi-cell driver in Plan 07-07.  This function
    produces raw SweepResult records only.

    Args:
        role:               Role name (must be a key in ROLE_COMMAND_MAP).
        candidate_model_id: Bedrock model ID for the role under test.
        cases_path:         Path to query_cases.json (schema validated per T-4-01).
        workspace_path:     Path to the source workspace root; the wiki is
                            derived via wiki_dir(workspace_path) (D-01/D-09)
                            and copied per cell via EvalWorktree.
        repeats:            Number of repeat runs per case (default 3).
        semaphore:          Optional caller-provided semaphore.  When None, a fresh
                            Semaphore(8) is created per call (Pitfall 4).

    Returns:
        List of SweepResult — one per (case, repeat_idx) that was attempted.
    """
    if role not in ROLE_COMMAND_MAP:
        raise ValueError(
            f"Unknown role {role!r} — must be one of {sorted(ROLE_COMMAND_MAP)}"
        )

    sem = semaphore or asyncio.Semaphore(8)
    cases = _load_and_validate_cases(cases_path)
    safe_model_id = _sanitize_model_id(candidate_model_id)
    dispatch_name = ROLE_COMMAND_MAP[role]
    wiki = wiki_dir(workspace_path)

    # Map dispatch name string to actual function (module-level callables)
    _dispatch: dict[str, object] = {
        "_sweep_query_role":  _sweep_query_role,
        "_sweep_scan_role":   _sweep_scan_role,
        "_sweep_lint_role":   _sweep_lint_role,
        "_sweep_ingest_role": _sweep_ingest_role,
    }
    cmd_fn = _dispatch[dispatch_name]

    async def _run_role_one(case: dict, repeat_idx: int) -> SweepResult:
        query = case["query"]
        async with sem:
            async with EvalWorktree(wiki) as wt:
                t0 = time.monotonic()
                bucket: list = []
                token = _USAGE_CAPTURE.set(bucket)
                try:
                    _result, _answer = await cmd_fn(
                        role, candidate_model_id, case, wt.path
                    )
                    wall_seconds = time.monotonic() - t0

                    # Aggregate usage from THIS task's contextvar bucket
                    # (per-asyncio-task isolation; concurrent cells stay separate).
                    tokens_in, tokens_out, cell_total_cost = _aggregate_usage(bucket)

                    # cost_usd at the SweepResult level represents the candidate
                    # model's cost only — used for the per-role Pareto frontier.
                    # When tokens are mixed-model in the cell, attribute usage
                    # for the candidate model_id specifically.
                    cand_in = sum(
                        b["tokens_in"] for b in bucket
                        if b.get("model_id") == candidate_model_id
                        and b.get("tokens_in") is not None
                    ) or None
                    cand_out = sum(
                        b["tokens_out"] for b in bucket
                        if b.get("model_id") == candidate_model_id
                        and b.get("tokens_out") is not None
                    ) or None
                    cost_usd: float | None = None
                    if cand_in is not None and cand_out is not None:
                        try:
                            cost_usd = cost_for_usage(
                                candidate_model_id,
                                {"input": cand_in, "output": cand_out},
                            )
                        except (UnknownModelError, KeyError):
                            cost_usd = None
                    if cand_in is not None:
                        tokens_in = cand_in
                    if cand_out is not None:
                        tokens_out = cand_out

                    # Structural check: only meaningful for QueryResult
                    if hasattr(_result, "answer"):
                        structural = check_structural(_result, wt.path)
                        citations = getattr(_result, "citations", [])
                        pages_drilled = getattr(_result, "pages_drilled", 0)
                        answer = _answer
                    else:
                        structural = {}
                        citations = []
                        pages_drilled = 0
                        answer = _answer

                    return SweepResult(
                        model_id=candidate_model_id,
                        safe_model_id=safe_model_id,
                        query=query,
                        answer=answer,
                        citations=citations,
                        pages_drilled=pages_drilled,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        cost_usd=cost_usd,
                        wall_seconds=wall_seconds,
                        structural=structural,
                        status="ok",
                        seed=None,
                    )

                except Exception as exc:
                    wall_seconds = time.monotonic() - t0
                    logger.warning(
                        "Role sweep cell failed: role=%s model=%s repeat=%d query=%r error=%s",
                        role,
                        candidate_model_id,
                        repeat_idx,
                        query,
                        exc,
                    )
                    return SweepResult(
                        model_id=candidate_model_id,
                        safe_model_id=safe_model_id,
                        query=query,
                        answer="",
                        citations=[],
                        pages_drilled=0,
                        tokens_in=None,
                        tokens_out=None,
                        cost_usd=None,
                        wall_seconds=wall_seconds,
                        structural={},
                        status="error",
                        seed=None,
                    )
                finally:
                    _USAGE_CAPTURE.reset(token)

    coros = [
        _run_role_one(case, repeat_idx)
        for case in cases
        for repeat_idx in range(repeats)
    ]

    raw = await asyncio.gather(*coros, return_exceptions=True)

    results: list[SweepResult] = []
    for item in raw:
        if isinstance(item, SweepResult):
            results.append(item)
        elif isinstance(item, BaseException):
            logger.error("Unexpected gather exception in run_role_sweep: %s", item)

    return results


_QUALITY_ROLES: frozenset[str] = frozenset({"librarian", "synthesizer"})

_TIER_LABEL: dict[str, str] = {
    "librarian":   "quality",
    "synthesizer": "quality",
    "linter":      "mid",
    "ingestor":    "mid",
    "scanner":     "cheap-fast",
    "code_reader": "cheap-fast",
}


def _panel_mean_for_candidate(
    role: str,
    candidate_results: list[SweepResult],
    cases_path: Path,
) -> float | None:
    """Compute the mean panel score for a candidate's runs.

    Returns None when GRAPH_WIKI_RUN_JUDGES is unset, when no case has
    expected_answer, or when every run produced a failing/empty answer.
    """
    import os

    if not os.environ.get("GRAPH_WIKI_RUN_JUDGES"):
        return None

    cases_by_query: dict[str, dict] = {}
    try:
        for case in _load_and_validate_cases(cases_path):
            cases_by_query[case["query"]] = case
    except (OSError, json.JSONDecodeError):
        return None

    from eval_harness.judge import panel_score  # noqa: PLC0415

    scores: list[float] = []
    for r in candidate_results:
        if r.status != "ok" or not r.answer:
            continue
        case = cases_by_query.get(r.query)
        if not case:
            continue
        expected = case.get("expected_answer", "")
        if not expected:
            continue
        try:
            panel = panel_score(r.query, r.answer, expected)
            scores.append(float(panel["mean"]))
        except Exception as exc:
            logger.warning("panel_score failed for %s/%s: %s", role, r.model_id, exc)
    if not scores:
        return None
    return sum(scores) / len(scores)


async def run_full_matrix(
    role_candidates: dict[str, list[str]],
    workspace_path: Path,
    query_cases_path: Path,
    code_reader_cases_path: Path,
    ingestor_source_path: Path,
    repeats: int = 3,
    output_dir: Path = Path(".planning/sweep"),
    *,
    dry_run: bool = False,
    threshold_quality: float = 0.95,
    threshold_other: float = 0.90,
    skip_bed01: bool = False,
    auto_confirm: bool = False,
) -> dict[str, list[SweepResult]]:
    """Drive the full sweep matrix end-to-end (SWEEP-01, SWEEP-03).

    Composes the existing primitives: preflight_check, run_role_sweep,
    score_two_gate, render_role_doc, render_index_md.  Writes per-role markdown
    docs and INDEX.md into ``output_dir`` and prints recommendation blocks to
    stdout for human paste into models.toml.

    Routing:
      - librarian / synthesizer / scanner / linter -> query_cases_path
      - code_reader                                -> code_reader_cases_path
      - ingestor                                   -> synthesized cases file
        containing one entry with ``source_path=ingestor_source_path``

    Args:
        role_candidates:          mapping role -> [candidate model_ids]
        workspace_path:           source workspace root (wiki copied per cell by
                                  EvalWorktree via wiki_dir(workspace_path))
        query_cases_path:         JSON cases for query-style roles
        code_reader_cases_path:   JSON cases for the code_reader role (D-09)
        ingestor_source_path:     single source file the ingestor should ingest
        repeats:                  repeats per (role, candidate, case) cell
        output_dir:               directory to receive per-role docs + INDEX.md
        dry_run:                  when True, skip BED-01 ping and live cells
        threshold_quality:        Gate-2 threshold for quality-tier roles
        threshold_other:          Gate-2 threshold for non-quality roles
        skip_bed01:               propagate to preflight_check
        auto_confirm:             propagate to preflight_check (skips input prompt)

    Returns:
        dict[role, list[SweepResult]] — raw cell records per role.
    """
    import datetime
    import subprocess
    import tempfile

    from eval_harness.report import render_index_md, render_recommendation_block, render_role_doc
    from model_adapter.loader import load_role_config

    n_query = len(_load_and_validate_cases(query_cases_path))
    n_code_reader = len(_load_and_validate_cases(code_reader_cases_path))
    n_cases_for_estimate = max(n_query, n_code_reader, 1)

    preflight_check(
        role_candidates,
        n_cases_for_estimate,
        repeats,
        skip_bed01=skip_bed01 or dry_run,
        auto_confirm=auto_confirm,
    )

    cases_path_for_role: dict[str, Path] = {
        "librarian":   query_cases_path,
        "synthesizer": query_cases_path,
        "code_reader": code_reader_cases_path,
        "scanner":     query_cases_path,
        "linter":      query_cases_path,
    }

    ingestor_cases_tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tf:
            json.dump(
                [
                    {
                        "query": f"ingest {ingestor_source_path.name}",
                        "expected_answer": "ingestor produces a wiki page",
                        "source_path": str(ingestor_source_path),
                        "case_id": "ingestor-01",
                    }
                ],
                tf,
            )
            ingestor_cases_tmp = Path(tf.name)
        cases_path_for_role["ingestor"] = ingestor_cases_tmp

        all_results: dict[str, list[SweepResult]] = {}

        for role, candidates in role_candidates.items():
            cases_path = cases_path_for_role.get(role, query_cases_path)
            role_results: list[SweepResult] = []
            for candidate in candidates:
                if dry_run:
                    continue
                cell_results = await run_role_sweep(
                    role, candidate, cases_path, workspace_path, repeats=repeats
                )
                role_results.extend(cell_results)
            all_results[role] = role_results

        run_date = datetime.date.today().isoformat()
        try:
            commit_sha = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], text=True
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            commit_sha = "unknown"

        output_dir.mkdir(parents=True, exist_ok=True)

        role_doc_paths: list[Path] = []
        total_cost_run = 0.0

        for role, candidates in role_candidates.items():
            role_results = all_results.get(role, [])
            cases_path = cases_path_for_role.get(role, query_cases_path)

            default_model_id: str | None = None
            try:
                default_model_id = load_role_config(role).get("model_id")
            except KeyError:
                default_model_id = None

            results_by_candidate: dict[str, list[SweepResult]] = {}
            for r in role_results:
                results_by_candidate.setdefault(r.model_id, []).append(r)

            panel_means: dict[str, float | None] = {}
            for candidate in candidates:
                panel_means[candidate] = _panel_mean_for_candidate(
                    role, results_by_candidate.get(candidate, []), cases_path
                )

            default_panel_mean = (
                panel_means.get(default_model_id) if default_model_id else None
            )

            threshold = (
                threshold_quality if role in _QUALITY_ROLES else threshold_other
            )

            # Wire Gate 1 per role: a divergence-eligible role gets a real
            # DivergenceMetric + the package baselines dir; any role NOT in
            # ROLES_WITH_DIVERGENCE keeps both None (preserves the D-08 contract).
            # Note: synthesizer + code_reader have no recorded baseline JSON yet, so
            # metric.load_baseline() returns {} (0-failure floor) — no crash. Recording
            # those baselines via --accept-divergence-baseline is an explicit non-goal here.
            if role in ROLES_WITH_DIVERGENCE:
                divergence_metric: DivergenceMetric | None = DivergenceMetric(
                    role=role,
                    checks=ROLE_CHECKS[role],
                    rubric_path=ROLE_RUBRICS[role],
                    wiki=wiki_dir(workspace_path),
                )
                baselines_dir_for_role: Path | None = _BASELINES_DIR
            else:
                divergence_metric = None
                baselines_dir_for_role = None

            two_gate_outcomes: dict[str, TwoGateOutcome] = {}
            for candidate in candidates:
                outputs_by_case: list[tuple[str, object]] = [
                    (r.query, type("AgentOutputProxy", (), {"answer": r.answer})())
                    for r in results_by_candidate.get(candidate, [])
                    if r.status == "ok"
                ]
                outcome = score_two_gate(
                    role=role,
                    divergence_metric_or_none=divergence_metric,
                    agent_outputs_by_case=outputs_by_case,
                    baselines_dir=baselines_dir_for_role,
                    panel_mean=panel_means.get(candidate),
                    default_panel_mean=default_panel_mean,
                    threshold=threshold,
                )
                two_gate_outcomes[candidate] = outcome

            role_total_cost = sum(
                r.cost_usd for r in role_results
                if r.cost_usd is not None
            )
            total_cost_run += role_total_cost

            doc_text = render_role_doc(
                role=role,
                tier=_TIER_LABEL.get(role, "mid"),
                candidates=candidates,
                sweep_results=role_results,
                divergence_results=None,
                run_date=run_date,
                commit_sha=commit_sha,
                total_cost_usd=role_total_cost,
                two_gate_outcomes=two_gate_outcomes,
            )

            doc_path = output_dir / f"{role}.md"
            doc_path.write_text(doc_text, encoding="utf-8")
            role_doc_paths.append(doc_path)

            from eval_harness.report import cost_frontier_table, pareto_frontier  # noqa: PLC0415
            table = cost_frontier_table(role_results)
            frontier = pareto_frontier(table)
            rec_block = render_recommendation_block(
                role=role,
                run_date=run_date,
                frontier=frontier,
                current_default=default_model_id or (candidates[0] if candidates else "unknown"),
            )
            print(f"### Recommendation block for [roles.{role}] ###")
            print(rec_block)
            print()

        story_path = output_dir / "STORY.md"
        index_text = render_index_md(
            role_doc_paths=[p.name for p in role_doc_paths],
            run_date=run_date,
            total_cost_usd=total_cost_run,
            story_path="STORY.md" if story_path.exists() else None,
        )
        (output_dir / "INDEX.md").write_text(index_text, encoding="utf-8")

        return all_results
    finally:
        if ingestor_cases_tmp is not None:
            ingestor_cases_tmp.unlink(missing_ok=True)
