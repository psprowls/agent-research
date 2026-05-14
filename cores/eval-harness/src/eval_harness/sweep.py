"""Model sweep runner: iterate N model IDs over eval cases, collect SweepResult records.

run_sweep() is the primary entry point. It:
1. Loads cases from a JSON file (validates schema per T-4-01).
2. For each (model_id, case) pair, opens an EvalWorktree and calls run_query().
3. Collects SweepResult per run, with partial-failure isolation via asyncio.gather.
4. Appends structural checks, token counts, and cost estimates to each SweepResult.

Token counts are extracted from the trace JSONL written by SubagentPool._write_trace
into wt.path / ".code-wiki" / "traces". The most-recently-modified JSONL file is
parsed; tokens_in/tokens_out are summed across all records for the run.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

from code_wiki_agent.commands.query import QueryResult, run_query

from eval_harness.isolation import EvalWorktree
from eval_harness.pricing import UnknownModelError, cost_for_usage
from eval_harness.structural import check_structural

logger = logging.getLogger(__name__)


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
    vault_path: Path,
    model_ids: list[str],
) -> list[SweepResult]:
    """Run a model sweep: for each model_id, run all eval cases under isolation.

    For each (model_id, case) pair:
    - Opens an EvalWorktree (isolated vault copy in tmpdir).
    - Calls run_query() with librarian_model_override=model_id.
    - Collects tokens from trace JSONL and computes cost via pricing.
    - Runs check_structural() on the QueryResult.
    - Produces a SweepResult with status="ok" or status="error".

    Partial-failure isolation: asyncio.gather(return_exceptions=True) ensures
    one failing model does not abort the sweep — other models continue.

    Args:
        cases_path: Path to query_cases.json; cases missing schema keys are skipped.
        vault_path: Path to source vault (copied per run via EvalWorktree).
        model_ids:  List of Bedrock model IDs to sweep over.

    Returns:
        List of SweepResult (one per (model_id, case) pair that was attempted).
    """
    cases = _load_and_validate_cases(cases_path)

    async def _run_one(model_id: str, case: dict) -> SweepResult:
        safe_model_id = _sanitize_model_id(model_id)
        query = case["query"]

        async with EvalWorktree(vault_path) as wt:
            t0 = time.monotonic()
            try:
                result: QueryResult = await run_query(
                    query,
                    vault_path=wt.path,
                    top_k=5,
                    librarian_model_override=model_id,
                )
                wall_seconds = time.monotonic() - t0

                # Extract token counts from trace JSONL
                trace_dir = wt.path / ".code-wiki" / "traces"
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
