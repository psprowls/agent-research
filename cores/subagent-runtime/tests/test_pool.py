from __future__ import annotations

"""Unit tests for subagent_runtime.pool.SubagentPool.

Covers partial failure isolation, semaphore concurrency cap, JSONL trace
completeness (success and error paths), token metadata None guard, trace
writer OSError isolation, multi-run lineage, and RunnableConfig recursion
limit propagation.

No real Bedrock calls — all LLM paths are mocked via conftest fixtures.
"""

import asyncio
import json
import logging
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Test 1: FanOutResult dataclass returned on empty input
# ---------------------------------------------------------------------------


async def test_fanout_returns_fanout_result_dataclass(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool, FanOutResult, PerItemError

    pool = SubagentPool(trace_dir=tmp_path / "traces")
    task = make_task()
    result = await pool.run_all(
        items=[],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )
    assert isinstance(result, FanOutResult)
    assert result.successes == []
    assert result.errors == []


# ---------------------------------------------------------------------------
# Test 2: Partial failure isolation — 1 of 4 fails
# ---------------------------------------------------------------------------


async def test_partial_failure_isolation(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool, FanOutResult, PerItemError

    task = make_task(raise_for={"bad"})
    pool = SubagentPool(trace_dir=tmp_path / "traces")
    result = await pool.run_all(
        items=["a", "b", "bad", "c"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )
    assert len(result.successes) == 3
    assert len(result.errors) == 1
    assert result.errors[0].item == "bad"
    assert isinstance(result.errors[0].exception, ValueError)


# ---------------------------------------------------------------------------
# Test 3: First task failure does not cancel siblings
# ---------------------------------------------------------------------------


async def test_first_task_failure_does_not_cancel_siblings(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool, FanOutResult, PerItemError

    task = make_task(raise_for={"bad"})
    pool = SubagentPool(trace_dir=tmp_path / "traces")
    result = await pool.run_all(
        items=["bad", "a", "b", "c"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )
    assert len(result.successes) == 3
    assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# Test 4: All tasks fail
# ---------------------------------------------------------------------------


async def test_all_tasks_fail(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool, FanOutResult, PerItemError

    task = make_task(raise_for={"a", "b", "c", "d"})
    pool = SubagentPool(trace_dir=tmp_path / "traces")
    result = await pool.run_all(
        items=["a", "b", "c", "d"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )
    assert len(result.successes) == 0
    assert len(result.errors) == 4


# ---------------------------------------------------------------------------
# Test 5: Semaphore caps concurrency
# ---------------------------------------------------------------------------


async def test_semaphore_caps_concurrency(tmp_path):
    from subagent_runtime.pool import SubagentPool

    peak = 0
    current = 0

    async def counting_task(item):
        nonlocal peak, current
        current += 1
        if current > peak:
            peak = current
        await asyncio.sleep(0.01)
        current -= 1
        return item

    pool = SubagentPool(trace_dir=tmp_path / "traces")
    result = await pool.run_all(
        items=list(range(6)),
        task=counting_task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=2,
    )
    assert peak <= 2
    assert len(result.successes) == 6


# ---------------------------------------------------------------------------
# Test 6: max_concurrency=1 serializes tasks
# ---------------------------------------------------------------------------


async def test_max_concurrency_one_serializes_tasks(tmp_path):
    from subagent_runtime.pool import SubagentPool

    peak = 0
    current = 0

    async def counting_task(item):
        nonlocal peak, current
        current += 1
        if current > peak:
            peak = current
        await asyncio.sleep(0.01)
        current -= 1
        return item

    pool = SubagentPool(trace_dir=tmp_path / "traces")
    result = await pool.run_all(
        items=list(range(3)),
        task=counting_task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=1,
    )
    assert peak == 1
    assert len(result.successes) == 3


# ---------------------------------------------------------------------------
# Test 7: Trace record completeness on success path
# ---------------------------------------------------------------------------


async def test_trace_record_completeness_success_path(tmp_path, fake_llm_response):
    from subagent_runtime.pool import SubagentPool

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)

    async def task(item):
        return fake_llm_response

    result = await pool.run_all(
        items=["item-1"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )

    assert len(result.successes) == 1

    trace_files = list(traces_dir.glob("*.jsonl"))
    assert len(trace_files) == 1

    lines = trace_files[0].read_text().strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    required_keys = {
        "role", "model_id", "prompt_hash", "item_id",
        "status", "latency_ms", "tokens_in", "tokens_out",
        "cost_usd", "timestamp",
    }
    assert required_keys.issubset(record.keys())
    assert record["status"] == "success"
    assert record["tokens_in"] == 10
    assert record["tokens_out"] == 5
    assert record["cost_usd"] is None


# ---------------------------------------------------------------------------
# Test 8: Trace record on error path
# ---------------------------------------------------------------------------


async def test_trace_record_error_path(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)
    task = make_task(raise_for={"bad"})

    result = await pool.run_all(
        items=["bad"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )

    assert len(result.errors) == 1

    trace_files = list(traces_dir.glob("*.jsonl"))
    assert len(trace_files) == 1

    lines = trace_files[0].read_text().strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["status"] == "error"
    assert "error" in record
    assert record["error"]  # non-empty string
    assert record["tokens_in"] is None
    assert record["tokens_out"] is None


# ---------------------------------------------------------------------------
# Test 9: usage_metadata=None guard — no AttributeError
# ---------------------------------------------------------------------------


async def test_token_metadata_none_guard(tmp_path, fake_llm_response_error):
    from subagent_runtime.pool import SubagentPool

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)

    async def task(item):
        return fake_llm_response_error  # usage_metadata is None

    # Must not raise; tokens_in and tokens_out must be null, not 0, not missing
    result = await pool.run_all(
        items=["x"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )

    assert len(result.successes) == 1

    trace_files = list(traces_dir.glob("*.jsonl"))
    lines = trace_files[0].read_text().strip().splitlines()
    record = json.loads(lines[0])

    assert record["tokens_in"] is None
    assert record["tokens_out"] is None


# ---------------------------------------------------------------------------
# Test 10: _write_trace OSError is logged as WARNING, does not mask success
# ---------------------------------------------------------------------------


async def test_write_trace_oserror_logged_not_raised(tmp_path, fake_llm_response, caplog, monkeypatch):
    from subagent_runtime.pool import SubagentPool

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)  # mkdir happens here — dir exists

    # Monkeypatch Path.open to raise OSError on any open call
    original_open = Path.open

    def raising_open(self, *args, **kwargs):
        if str(self).endswith(".jsonl"):
            raise OSError("simulated write failure")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", raising_open)

    async def task(item):
        return fake_llm_response

    with caplog.at_level(logging.WARNING):
        result = await pool.run_all(
            items=["a"],
            task=task,
            role="scanner",
            model_id="test-model-id",
            max_concurrency=4,
        )

    # Success must NOT be converted to PerItemError due to trace failure
    assert len(result.successes) == 1
    assert len(result.errors) == 0

    # A WARNING must have been logged about the trace failure
    warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("simulated write failure" in msg or "Trace write failed" in msg for msg in warning_messages)


# ---------------------------------------------------------------------------
# Test 11: Two sequential run_all() calls produce two separate trace files
# ---------------------------------------------------------------------------


async def test_separate_trace_files_per_run_all(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool
    import time

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)
    task = make_task()

    await pool.run_all(
        items=["a"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )

    # Sleep slightly more than 1 second to guarantee distinct unix timestamps
    await asyncio.sleep(1.1)

    await pool.run_all(
        items=["b"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )

    trace_files = list(traces_dir.glob("*.jsonl"))
    assert len(trace_files) == 2
    # Both must be distinct paths
    assert trace_files[0] != trace_files[1]


# ---------------------------------------------------------------------------
# Test 12: RunnableConfig recursion_limit is propagated to every task call
# ---------------------------------------------------------------------------


async def test_recursion_limit_propagated_to_runnableconfig(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, call
    import subagent_runtime.pool as pool_module

    traces_dir = tmp_path / "traces"

    # --- Part A: explicit recursion_limit=42 ---
    mock_rc_a = MagicMock(side_effect=lambda **kwargs: kwargs)
    monkeypatch.setattr(pool_module, "RunnableConfig", mock_rc_a)

    pool_a = pool_module.SubagentPool(trace_dir=traces_dir)

    async def simple_task(item):
        return MagicMock(usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})

    await pool_a.run_all(
        items=["a", "b"],
        task=simple_task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
        recursion_limit=42,
    )

    # RunnableConfig must have been called twice (once per item)
    assert mock_rc_a.call_count == 2
    for c in mock_rc_a.call_args_list:
        assert c.kwargs.get("recursion_limit") == 42

    # --- Part B: default_recursion_limit from __init__ ---
    mock_rc_b = MagicMock(side_effect=lambda **kwargs: kwargs)
    monkeypatch.setattr(pool_module, "RunnableConfig", mock_rc_b)

    pool_b = pool_module.SubagentPool(trace_dir=traces_dir, default_recursion_limit=99)

    await pool_b.run_all(
        items=["x"],
        task=simple_task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
        # recursion_limit NOT passed — should use default_recursion_limit=99
    )

    assert mock_rc_b.call_count == 1
    assert mock_rc_b.call_args.kwargs.get("recursion_limit") == 99
