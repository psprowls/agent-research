from __future__ import annotations

"""Real-Bedrock integration tests for SubagentPool.

These tests dispatch actual LLM calls to AWS Bedrock and verify that the
SubagentPool's correctness guarantees (partial-failure isolation, throttle
cap, recursion_limit plumbing) hold against the live Converse API.

Gating: all tests are decorated with @INTEGRATION_GATE which skips them
unless the environment variable CODE_WIKI_RUN_INTEGRATION=1 is set.
This ensures the suite is CI-safe and never incurs unexpected AWS costs.

To run:
    CODE_WIKI_RUN_INTEGRATION=1 uv run --package subagent-runtime pytest \\
        cores/subagent-runtime/tests/integration/test_pool_bedrock.py -v

Estimated cost per full run: <<$0.05 against Haiku (short prompts only).
Estimated runtime: well under 120 seconds.
"""

import json
import os
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)


@pytest.mark.integration
@INTEGRATION_GATE
async def test_partial_failure_real_bedrock(tmp_path: Path) -> None:
    """4 items dispatched, 1 intentionally raises; assert 3 successes + 1 error.

    Verifies SUB-02 / SUB-07 partial-failure isolation against live Bedrock.
    Also asserts the trace JSONL file has exactly 4 records.
    """
    from model_adapter.loader import load_role_config, make_llm
    from subagent_runtime.pool import SubagentPool

    role = "scanner"
    cfg = load_role_config(role)
    llm = make_llm(role)

    async def task(item):
        if item == "bad":
            raise ValueError("intentional")
        return await llm.ainvoke([HumanMessage(content=f"Say: ok-{item}")])

    trace_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=trace_dir)
    result = await pool.run_all(
        items=["a", "b", "bad", "c"],
        task=task,
        role=role,
        model_id=cfg["model_id"],
        max_concurrency=cfg["max_concurrency"],
    )

    assert len(result.successes) == 3, f"Expected 3 successes; got {len(result.successes)}"
    assert len(result.errors) == 1, f"Expected 1 error; got {len(result.errors)}"
    assert result.errors[0].item == "bad", f"Expected error item 'bad'; got {result.errors[0].item}"

    # Verify the trace file has 4 records (1 per item)
    trace_files = list(trace_dir.glob("*.jsonl"))
    assert len(trace_files) == 1, f"Expected 1 trace file; found {len(trace_files)}"
    lines = [l for l in trace_files[0].read_text().splitlines() if l.strip()]
    assert len(lines) == 4, f"Expected 4 JSONL records; got {len(lines)}"

    # Confirm status values
    statuses = [json.loads(l)["status"] for l in lines]
    success_count = statuses.count("success")
    error_count = statuses.count("error")
    assert success_count == 3, f"Expected 3 success records; got {success_count}"
    assert error_count == 1, f"Expected 1 error record; got {error_count}"


@pytest.mark.integration
@INTEGRATION_GATE
async def test_no_throttling_at_max_concurrency_real_bedrock(tmp_path: Path) -> None:
    """Dispatch exactly max_concurrency=10 items simultaneously; confirm no ThrottlingException.

    Uses role 'linter' (max_concurrency=10, the highest configured cap).
    Verifies SUB-05 throttle guarantee at the full configured limit.
    ROADMAP success criterion #3 uses 5 parallel subagents as the floor;
    testing at 10 (the cap) is strictly stronger and still satisfies the criterion.
    """
    from model_adapter.loader import load_role_config, make_llm
    from subagent_runtime.pool import SubagentPool

    role = "linter"
    cfg = load_role_config(role)
    llm = make_llm(role)

    async def task(item):
        return await llm.ainvoke([HumanMessage(content=f"Reply with exactly: ok-{item}")])

    items = [f"item-{i}" for i in range(cfg["max_concurrency"])]  # 10 items

    trace_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=trace_dir)
    result = await pool.run_all(
        items=items,
        task=task,
        role=role,
        model_id=cfg["model_id"],
        max_concurrency=cfg["max_concurrency"],
    )

    assert len(result.errors) == 0, f"errors found: {result.errors}"
    assert len(result.successes) == cfg["max_concurrency"], (
        f"Expected {cfg['max_concurrency']} successes; got {len(result.successes)}"
    )


@pytest.mark.integration
@INTEGRATION_GATE
async def test_recursion_limit_propagated_real_bedrock(tmp_path: Path) -> None:
    """Single item that performs 30 sequential ainvoke calls; confirm no infrastructure failure.

    Verifies SUB-04 recursion_limit propagation: the pool accepts and plumbs the
    parameter, and 30 sequential Bedrock calls inside one task complete without
    GraphRecursionError or other infrastructure failure.

    Note per 02-RESEARCH Pattern 2: the pool wraps raw ainvoke (not a compiled
    LangGraph graph), so GraphRecursionError cannot actually trigger here. The
    test's value is proving forward-compatibility for Phase 3+ when tasks may
    wrap compiled graphs.

    Cost: ~30 minimal Haiku calls (<$0.01 at 5-10 tokens per prompt).
    """
    from model_adapter.loader import load_role_config, make_llm
    from subagent_runtime.pool import SubagentPool

    role = "scanner"
    cfg = load_role_config(role)
    llm = make_llm(role)

    async def chain_task(item):
        resp = None
        for i in range(30):
            resp = await llm.ainvoke([HumanMessage(content=f"Step {i}: respond with 'ok'")])
        return resp  # last response carries usage_metadata

    trace_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=trace_dir)
    result = await pool.run_all(
        items=["chain"],
        task=chain_task,
        role=role,
        model_id=cfg["model_id"],
        max_concurrency=1,
        recursion_limit=100,
    )

    assert len(result.successes) == 1, f"Expected 1 success; got {len(result.successes)}"
    assert len(result.errors) == 0, f"Expected 0 errors; got {result.errors}"

    # Verify the trace file has 1 record with status=success
    trace_files = list(trace_dir.glob("*.jsonl"))
    assert len(trace_files) == 1, f"Expected 1 trace file; found {len(trace_files)}"
    lines = [l for l in trace_files[0].read_text().splitlines() if l.strip()]
    assert len(lines) == 1, f"Expected 1 JSONL record; got {len(lines)}"
    record = json.loads(lines[0])
    assert record["status"] == "success", f"Expected status=success; got {record['status']}"
